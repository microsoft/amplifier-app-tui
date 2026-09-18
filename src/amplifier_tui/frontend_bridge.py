"""Experimental local JSONL boundary; scene mode imports no Amplifier runtime.

One request/reply identity, one terminal owner. This is not a remote protocol or
durable conversation store. Overload fails closed instead of dropping evidence.
"""

from __future__ import annotations

import argparse
import asyncio
import codecs
import json
import os
import queue
import re
import select
import sys
import threading
import time
import unicodedata
from collections import deque
from decimal import Decimal
from pathlib import Path

VERSION = 1
MAX_REQUESTS = 4096
MAX_LINE = 2 * 1024 * 1024
MAX_OUTPUT_BYTES = 64 * 1024 * 1024


class ChildChannel:
    """Private inherited-socket RPC; no terminal input, network or object loading.

    The reader stays independent of handlers so a permission wait cannot block a
    cancellation. Frames and concurrent requests are bounded; overflow fails closed.
    """

    MAX_FRAME = 16 * 1024 * 1024
    MAX_PENDING = 128

    def __init__(self, reader, writer, handler):
        self.reader, self.writer, self.handler = reader, writer, handler
        self.pending, self.incoming = {}, {}
        self.sequence = 0
        self.lock = asyncio.Lock()
        self.closed = False
        self.reader_task = asyncio.create_task(self.read())

    @classmethod
    async def connect(cls, sock, handler):
        sock.setblocking(False)
        reader, writer = await asyncio.open_connection(sock=sock)
        return cls(reader, writer, handler)

    async def send(self, packet):
        def encode(value):
            if isinstance(value, Decimal):
                if not value.is_finite():
                    raise ValueError("Non-finite child wire decimal")
                return str(value)  # Preserve provider cost precision.
            if hasattr(value, "model_dump"):
                return value.model_dump(mode="json")
            if hasattr(value, "to_dict"):
                return value.to_dict()
            raise TypeError(f"Unsupported child wire value: {type(value).__name__}")

        data = json.dumps(packet, default=encode, allow_nan=False).encode()
        if len(data) > self.MAX_FRAME:
            raise ValueError("Child frame exceeds 16 MiB")
        async with self.lock:
            if self.closed:
                raise RuntimeError("Child connection closed")
            self.writer.write(len(data).to_bytes(4, "big") + data)
            await self.writer.drain()

    async def call(self, operation, **payload):
        if len(self.pending) >= self.MAX_PENDING:
            raise RuntimeError("Child request capacity exceeded")
        self.sequence += 1
        identity = self.sequence
        future = asyncio.get_running_loop().create_future()
        self.pending[identity] = future
        try:
            await self.send({"id": identity, "op": operation, "payload": payload})
            return await future
        except asyncio.CancelledError:
            if not self.closed:
                await self.send({"cancel": identity})
            raise
        finally:
            self.pending.pop(identity, None)

    async def dispatch(self, packet):
        identity = packet["id"]
        try:
            value = await self.handler(packet["op"], packet["payload"])
            reply = {"reply": identity, "value": value}
        except asyncio.CancelledError:
            reply = {"reply": identity, "error": "Child operation cancelled"}
        except Exception as exc:
            reply = {"reply": identity, "error": f"{type(exc).__name__}: {exc}"[:4096]}
        try:
            await self.send(reply)
        except (ConnectionError, RuntimeError, ValueError, TypeError):
            # An unencodable/oversized response must terminate the wait, not hang.
            self.writer.close()
        finally:
            self.incoming.pop(identity, None)

    async def read(self):
        try:
            while True:
                size = int.from_bytes(await self.reader.readexactly(4), "big")
                if not 0 < size <= self.MAX_FRAME:
                    raise ValueError("Invalid child frame size")
                packet = json.loads(await self.reader.readexactly(size))
                if not isinstance(packet, dict):
                    raise ValueError("Invalid child packet")
                if "reply" in packet:
                    future = self.pending.get(packet["reply"])
                    if future and not future.done():
                        if "error" in packet:
                            future.set_exception(RuntimeError(packet["error"]))
                        else:
                            future.set_result(packet.get("value"))
                elif "cancel" in packet:
                    task = self.incoming.get(packet["cancel"])
                    if task:
                        task.cancel()
                elif (
                    isinstance(packet.get("id"), int)
                    and isinstance(packet.get("op"), str)
                    and isinstance(packet.get("payload"), dict)
                    and packet["id"] not in self.incoming
                    and len(self.incoming) < self.MAX_PENDING
                ):
                    self.incoming[packet["id"]] = asyncio.create_task(self.dispatch(packet))
                else:
                    raise ValueError("Invalid or excessive child request")
        except (asyncio.IncompleteReadError, ConnectionError, ValueError, TypeError):
            pass
        finally:
            self.closed = True
            for future in self.pending.values():
                if not future.done():
                    future.set_exception(RuntimeError("Child connection lost; work uncertain"))
            for task in list(self.incoming.values()):
                task.cancel()
            self.writer.close()

    async def close(self):
        self.writer.close()
        self.reader_task.cancel()
        await asyncio.gather(self.reader_task, *self.incoming.values(), return_exceptions=True)
        try:
            await self.writer.wait_closed()
        except ConnectionError:
            pass  # A killed/crashed worker still has to be reaped by its owner.


class RuntimeOutput:
    """Process-owned compatibility sink, never a journal or a tool-result source.

    Capture descriptors, not just Python streams: Rich, native writes and inherited
    subprocess stderr all share the same untrusted, unattributed diagnostic scope.
    Draining runs independently of the asyncio loop; readers request bounded copies.
    """

    MAX_ROWS = 128
    MAX_BYTES = 256 * 1024
    MAX_LINE = 4096
    sensitive = re.compile(
        r"(?i)(api[_ -]?key|access[_ -]?token|refresh[_ -]?token|id[_ -]?token|"
        r"secret|password|passwd|authorization|credential|cookie|connection[_ -]?string|"
        r"\btoken[\"']?\s*[:=])"
    )
    shapes = re.compile(
        r"(?i)\b(?:bearer\s+\S+|sk-[\w-]{8,}|gh[pousr]_[\w]{8,}|"
        r"github_pat_[\w]{8,}|eyJ[\w-]+\.[\w-]+\.[\w-]+)"
    )
    secret_name = re.compile(r"(?i)(key|token|secret|password|passwd|credential|auth|cookie)")
    scope = (
        "Private stdout/stderr from this app process, including startup and switched conversations. "
        "Review before copying: redaction is limited; no session/agent/tool attribution or outcome proof. "
        "Memory only, not conversation journals/exports; module-owned logs are independent. "
        "Latest 128 lines / 256 KiB, 4096 characters per line; oversized lines omitted, "
        "unterminated lines wait for newline. "
        "Terminal controls and recognizable credentials removed, not arbitrary private text. "
        "Refresh for new output."
    )

    def __init__(self):
        self.rows = deque()
        self.bytes = self.total = self.omitted = 0
        self.lock = threading.Lock()
        self.stopping = threading.Event()
        self.decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self.line = ""
        self.oversize = False
        self.escape = ""
        self.failed = False
        self.private_key = False

    def redact(self, text):
        if "-----BEGIN " in text and "PRIVATE KEY-----" in text:
            self.private_key = True
        if self.private_key:
            if "-----END " in text and "PRIVATE KEY-----" in text:
                self.private_key = False
            return "[sensitive diagnostic line omitted]"
        if (
            self.sensitive.search(text)
            or self.shapes.search(text)
            or any(
                value and value in text
                for key, value in os.environ.copy().items()
                if self.secret_name.search(key)
            )
            or "PRIVATE KEY" in text
        ):
            return "[sensitive diagnostic line omitted]"
        # URLs can carry unlabelled credentials in userinfo, paths or query strings.
        return re.sub(r"\b[a-zA-Z][\w+.-]*://\S+", "[endpoint omitted]", text)

    def summary(self):
        with self.lock:
            return {"lines": self.total, "omitted": self.omitted, "failed": self.failed}

    def feed(self, data):
        for char in self.decoder.decode(data):
            if self.escape in ("string", "string-escape"):
                if (
                    char == "\x07"
                    or char == "\x9c"
                    or (self.escape == "string-escape" and char == "\\")
                ):
                    self.escape = ""
                else:
                    self.escape = "string-escape" if char == "\x1b" else "string"
                continue
            if self.escape == "csi":
                if "@" <= char <= "~":
                    self.escape = ""
                continue
            if self.escape == "escape":
                self.escape = "csi" if char == "[" else "string" if char in "]PX^_" else ""
                continue
            if char in ("\x1b", "\x9b", "\x9d", "\x90"):
                self.escape = "escape" if char == "\x1b" else "csi" if char == "\x9b" else "string"
            elif char in "\n\r":
                self.finish_line()
            elif char == "\t" or not unicodedata.category(char).startswith("C"):
                if not self.oversize:
                    self.line += "    " if char == "\t" else char
                    if len(self.line) > self.MAX_LINE:
                        self.line, self.oversize = "", True

    def finish_line(self):
        text = self.line.strip()
        self.line = ""
        if self.oversize:
            self.oversize = False
            with self.lock:
                self.omitted += 1
            return
        if not text:
            return
        text = self.redact(text)
        size = len(text.encode())
        with self.lock:
            self.total += 1
            self.rows.append((self.total, time.strftime("%H:%M:%S"), text, size))
            self.bytes += size
            while len(self.rows) > self.MAX_ROWS or self.bytes > self.MAX_BYTES:
                self.bytes -= self.rows.popleft()[3]
                self.omitted += 1

    def catalog(self):
        with self.lock:
            rows, omitted, failed = list(self.rows), self.omitted, self.failed
        return {
            "rows": [
                {
                    "id": f"runtime-output:{number}",
                    "kind": "runtime_output",
                    "label": text[:120],
                    "status": stamp,
                    "detail": "Private process output; review before copying.\n\n" + text,
                }
                for number, stamp, text, _ in reversed(rows)
            ],
            "partial": bool(omitted or failed),
            "scope": self.scope,
            "context_note": f"{omitted} lines omitted. "
            + ("Capture failed; later output unavailable." if failed else ""),
        }

    def __enter__(self):
        sys.stdout.flush()
        sys.stderr.flush()
        self.protocol = os.fdopen(os.dup(1), "wb", buffering=0)
        self.saved = (os.dup(1), os.dup(2))
        self.read_fd, write_fd = os.pipe()
        try:
            os.dup2(write_fd, 1)
            os.dup2(write_fd, 2)
            self.thread = threading.Thread(target=self.read, name="tui-runtime-output")
            self.thread.start()
        except BaseException:
            for fd, original in zip((1, 2), self.saved, strict=True):
                os.dup2(original, fd)
                os.close(original)
            os.close(self.read_fd)
            self.protocol.close()
            raise
        finally:
            os.close(write_fd)
        return self

    def read(self):
        try:
            while not self.stopping.is_set():
                ready, _, _ = select.select([self.read_fd], [], [], 0.05)
                if not ready:
                    continue
                data = os.read(self.read_fd, 65536)
                if not data:
                    break
                if not self.failed:
                    try:
                        self.feed(data)
                    except Exception:
                        # A decoder failure must not break module writes or
                        # block their pipe. Keep draining, disclose lost capture.
                        with self.lock:
                            self.failed = True
        except (OSError, ValueError):
            with self.lock:
                self.failed = True
        finally:
            os.close(self.read_fd)

    def __exit__(self, *_):
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        finally:
            for fd, original in zip((1, 2), self.saved, strict=True):
                os.dup2(original, fd)
                os.close(original)
            self.stopping.set()
            self.thread.join()
            self.protocol.close()


class PipeWriter:
    """One owned writer; runtime loop stalls are not evidence of a dead reader.

    Only immutable encoded records cross threads. Nonblocking writes and a short
    poll make shutdown joinable even when the reader never consumes another byte.
    The two-second deadline measures lack of pipe progress, not runtime scheduling.
    """

    def __init__(self, output):
        self.loop = asyncio.get_running_loop()
        self.failed = asyncio.Event()
        self.error = None
        self.pending = queue.Queue(maxsize=1024)
        self.stopping = threading.Event()
        self.lock = threading.Lock()
        self.pending_bytes = 0
        self.fd = os.dup(output.fileno())
        self.blocking = os.get_blocking(self.fd)
        try:
            os.set_blocking(self.fd, False)
            self.thread = threading.Thread(target=self.write, name="tui-pipe-writer")
            self.thread.start()
        except BaseException:
            os.set_blocking(self.fd, self.blocking)
            os.close(self.fd)
            raise

    def fail(self, error):
        with self.lock:
            if self.error is not None:
                return
            self.error = error
        self.loop.call_soon_threadsafe(self.failed.set)

    def emit(self, value):
        if self.error is not None or self.stopping.is_set():
            return
        try:
            record = (json.dumps(value, ensure_ascii=False) + "\n").encode()
            with self.lock:
                if self.pending_bytes + len(record) > MAX_OUTPUT_BYTES:
                    raise BufferError("Output byte budget exceeded")
                self.pending.put_nowait(record)
                self.pending_bytes += len(record)
        except (ValueError, TypeError, BufferError, queue.Full) as exc:
            self.fail(exc)

    def write(self):
        try:
            while not self.stopping.is_set():
                try:
                    record = self.pending.get(timeout=0.05)
                except queue.Empty:
                    continue
                try:
                    remaining = memoryview(record)
                    deadline = time.monotonic() + 2
                    while remaining and not self.stopping.is_set():
                        try:
                            written = os.write(self.fd, remaining[:65536])
                        except BlockingIOError:
                            if time.monotonic() >= deadline:
                                raise TimeoutError("Output reader made no progress for two seconds")
                            select.select([], [self.fd], [], 0.05)
                        else:
                            if written == 0:
                                raise BrokenPipeError("Output pipe closed")
                            remaining = remaining[written:]
                            deadline = time.monotonic() + 2
                finally:
                    with self.lock:
                        self.pending_bytes -= len(record)
                    self.pending.task_done()
        except Exception as exc:
            self.fail(exc)
        finally:
            os.set_blocking(self.fd, self.blocking)
            os.close(self.fd)

    async def flush(self):
        while self.pending.unfinished_tasks and self.error is None:
            await asyncio.sleep(0.01)

    async def close(self):
        self.stopping.set()
        while self.thread.is_alive():
            await asyncio.sleep(0.01)
        self.thread.join()


class Scene:
    def __init__(self, data, emit):
        self.data, self.emit = data, emit
        self.pending = data.get("approval")
        self.task = None
        self.turn = 0
        self.ready = True

    async def open(self):
        self.emit({"type": "snapshot", **self.data, "mode": "SIMULATED", "ready": True})
        self.state("Waiting for your decision" if self.pending else "Ready")

    def state(self, status):
        self.emit({"type": "state", "status": status, "approval": self.pending, "ready": True})

    def item(self, identity, kind, text, status="", detail=""):
        self.emit(
            {
                "type": "item",
                "id": identity,
                "kind": kind,
                "text": text,
                "status": status,
                "detail": detail,
            }
        )

    def command(self, request):
        op = request.get("op")
        if op == "submit":
            text = request.get("text")
            if not isinstance(text, str) or not text.strip():
                return False, "Write a message first"
            if self.pending or (self.task and not self.task.done()):
                return False, "Busy · draft retained; queue and steer unavailable"
            self.turn += 1
            self.item(f"user-{self.turn + 1}", "user", text)
            self.task = asyncio.create_task(self.stream())
            return True, f"scene-turn-{self.turn}"
        if op == "decision":
            if not self.pending or request.get("approval_id") != self.pending["id"]:
                return False, "Stale decision rejected"
            option = request.get("option")
            if option not in self.pending["options"]:
                return False, "Unsupported decision"
            self.pending = None
            if option == "allow":
                self.item(
                    "test-1",
                    "tool",
                    "Focused regression tests",
                    "failed",
                    self.data["failure_detail"],
                )
                self.state("Ready · simulated test failed; inspect evidence")
            else:
                self.item(
                    "test-1",
                    "tool",
                    "Focused regression tests",
                    "denied",
                    "Denied · no command was executed.",
                )
                self.state("Ready · command denied")
            return True, option
        if op == "stop":
            active = bool(self.pending or (self.task and not self.task.done()))
            self.pending = None
            if self.task and not self.task.done():
                self.task.cancel()
            self.state("Interrupted · nothing was undone" if active else "Ready · no active turn")
            return active, "Stopped; nothing was undone" if active else "No active turn"
        return False, "Unsupported operation"

    async def stream(self):
        self.state("Working · draft stays editable")
        identity = f"response-{self.turn}"
        self.item(identity, "assistant", "")
        try:
            for word in self.data["response"].split(" "):
                await asyncio.sleep(self.data["stream_interval_ms"] / 1000)
                self.emit({"type": "delta", "id": identity, "text": word + " "})
            self.item(identity, "assistant", self.data["response"])
            self.state("Completed · tool results remain independent")
        except asyncio.CancelledError:
            self.state("Interrupted · partial text retained; nothing was undone")

    async def close(self):
        if self.task and not self.task.done():
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)


class Admission:
    """Never evict accepted identities and then silently execute a duplicate."""

    def __init__(self):
        self.replies = {}

    def apply(self, request, dispatch):
        identity = request.get("request_id")
        reply = {"type": "reply", "request_id": identity, "accepted": False}
        if request.get("version") != VERSION:
            return {**reply, "reason": "Protocol version mismatch"}
        if not isinstance(identity, str) or not identity or len(identity) > 128:
            return {**reply, "reason": "Invalid request identity"}
        if request.get("op") in {
            "draft",
            "editor_draft",
            "inspect",
            "file_snapshot",
            "conversations",
            "complete_path",
            "workspace_changes",
            "workspace_diff",
        }:
            # Ordered, idempotent state replacement on this one connection.
            # Autosaves must not consume the bounded execution-admission ledger.
            accepted, reason = dispatch(request)
            return {**reply, "accepted": accepted, "reason": reason}
        if identity in self.replies:
            previous, result = self.replies[identity]
            return result if previous == request else {**reply, "reason": "Identity reused"}
        if len(self.replies) >= MAX_REQUESTS:
            return {**reply, "reason": "Request limit reached; restart explicitly"}
        accepted, reason = dispatch(request)
        result = {**reply, "accepted": accepted, "reason": reason}
        self.replies[identity] = (request.copy(), result)
        return result


async def serve(factory, output=None, trace=None, runtime_output=None):
    """Read controls independently of pipe writes; bound pending outbound records.

    A stalled stdout fails the experimental connection. No automatic reconnect or
    retry is provided. Complete slow-reader durability remains a later host gate.
    """
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader(limit=MAX_LINE)
    transport, _ = await loop.connect_read_pipe(
        lambda: asyncio.StreamReaderProtocol(reader), sys.stdin
    )
    try:
        writer = PipeWriter(output or sys.stdout)
    except BaseException:
        transport.close()
        raise
    failed = writer.failed

    def emit(value):
        if trace is not None and value.get("type") == "delta":
            trace.write(
                json.dumps({"emitted_ns": time.monotonic_ns(), "text": value["text"]}) + "\n"
            )
            trace.flush()
        writer.emit({"version": VERSION, **value})

    try:
        backend = factory(emit)
        backend.runtime_output = runtime_output
    except BaseException:
        await writer.close()
        transport.close()
        raise
    admission = Admission()
    opening = asyncio.create_task(backend.open())
    overload = asyncio.create_task(failed.wait())
    source_failure = getattr(backend, "failure", None)
    source_overload = (
        asyncio.create_task(source_failure.wait()) if source_failure is not None else None
    )
    failures = [overload] + ([source_overload] if source_overload is not None else [])

    async def requests():
        while line := await reader.readline():
            try:
                request = json.loads(line)
                if not isinstance(request, dict):
                    raise ValueError("Request must be an object")
                if request.get("op") == "shutdown" and request.get("version") == VERSION:
                    break
                emit(admission.apply(request, backend.command))
            except (ValueError, TypeError) as exc:
                emit({"type": "error", "message": str(exc)})

    controls = asyncio.create_task(requests())

    async def diagnostics():
        previous = None
        while True:
            current = runtime_output.summary()
            if current != previous:
                emit({"type": "runtime_output_status", **current})
                previous = current
            await asyncio.sleep(0.5)

    diagnostic_status = asyncio.create_task(diagnostics()) if runtime_output else None
    try:
        done, _ = await asyncio.wait(
            [controls, opening, *failures], return_when=asyncio.FIRST_COMPLETED
        )
        if opening in done:
            try:
                opening.result()
            except Exception as exc:
                emit(
                    {
                        "type": "state",
                        "status": f"Startup failed: {type(exc).__name__}: {exc}",
                        "ready": False,
                        "approval": None,
                    }
                )
            await asyncio.wait([controls, *failures], return_when=asyncio.FIRST_COMPLETED)
    finally:
        opening.cancel()
        controls.cancel()
        if diagnostic_status:
            diagnostic_status.cancel()
            await asyncio.gather(diagnostic_status, return_exceptions=True)
        overload.cancel()
        if source_overload is not None:
            source_overload.cancel()
        await asyncio.gather(opening, controls, *failures, return_exceptions=True)
        try:
            await asyncio.wait_for(backend.close(), timeout=2)
            if not failed.is_set():
                await asyncio.wait_for(writer.flush(), timeout=0.5)
        except (TimeoutError, BrokenPipeError):
            pass
        finally:
            await writer.close()
            transport.close()
    if writer.error is not None:
        raise RuntimeError(
            f"Terminal output failed: {type(writer.error).__name__}"
        ) from writer.error
    if source_failure is not None and source_failure.is_set():
        raise RuntimeError("Runtime event delivery failed; no work retried")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", type=Path, required=True)
    parser.add_argument("--history", type=int, default=0)
    parser.add_argument("--rate", type=int)
    parser.add_argument(
        "--trace", type=Path, help="Synthetic delta timestamps for local measurement"
    )
    args = parser.parse_args()
    data = json.loads(args.scene.read_text())
    if not 0 <= args.history <= 100_000:
        parser.error("History must be between 0 and 100000")
    history = [
        {
            "id": f"history-{i}",
            "kind": "assistant",
            "text": f"Historical observation {i} · synthetic; no operation executed.",
            "status": "",
            "detail": "",
        }
        for i in range(args.history)
    ]
    data["items"] = history + data["items"]
    if args.rate:
        data["stream_interval_ms"] = 1000 / max(1, args.rate)
        data["response"] = " ".join(f"delta-{i}" for i in range(2000))
    if args.trace:
        with args.trace.open("w") as trace:
            asyncio.run(serve(lambda emit: Scene(data, emit), trace=trace))
    else:
        asyncio.run(serve(lambda emit: Scene(data, emit)))


if __name__ == "__main__":
    main()

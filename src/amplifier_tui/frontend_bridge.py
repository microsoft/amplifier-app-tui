"""Experimental local JSONL boundary; scene mode imports no Amplifier runtime.

One request/reply identity, one terminal owner. This is not a remote protocol or
durable conversation store. Overload fails closed instead of dropping evidence.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

VERSION = 1
MAX_REQUESTS = 4096
MAX_LINE = 2 * 1024 * 1024


class Scene:
    def __init__(self, data, emit):
        self.data, self.emit = data, emit
        self.pending = data.get("approval")
        self.task = None
        self.turn = 0
        self.ready = True

    async def open(self):
        self.emit({"type": "snapshot", **self.data, "mode": "SIMULATED"})
        self.state("Waiting for your decision" if self.pending else "Ready")

    def state(self, status):
        self.emit({"type": "state", "status": status, "approval": self.pending})

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


async def serve(factory, output=None, trace=None):
    """Read controls independently of pipe writes; bound pending outbound records.

    A stalled stdout fails the experimental connection. No automatic reconnect or
    retry is provided. Complete slow-reader durability remains a later host gate.
    """
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader(limit=MAX_LINE)
    transport, _ = await loop.connect_read_pipe(
        lambda: asyncio.StreamReaderProtocol(reader), sys.stdin
    )
    queue = asyncio.Queue(maxsize=1024)
    failed = asyncio.Event()

    def emit(value):
        if trace is not None and value.get("type") == "delta":
            trace.write(
                json.dumps({"emitted_ns": time.monotonic_ns(), "text": value["text"]}) + "\n"
            )
            trace.flush()
        try:
            queue.put_nowait({"version": VERSION, **value})
        except asyncio.QueueFull:
            failed.set()

    async def write():
        # Dedicated blocking writer in a daemon thread is avoided: pipe writes
        # use asyncio flow control so shutdown can cancel a disconnected client.
        protocol = asyncio.streams.FlowControlMixin(loop=loop)
        pipe, _ = await loop.connect_write_pipe(lambda: protocol, output or sys.stdout)
        writer = asyncio.StreamWriter(pipe, protocol, None, loop)
        try:
            while True:
                value = await queue.get()
                writer.write((json.dumps(value, ensure_ascii=False) + "\n").encode())
                await asyncio.wait_for(writer.drain(), timeout=2)
                queue.task_done()
        finally:
            writer.close()

    backend = factory(emit)
    admission = Admission()
    writer = asyncio.create_task(write())
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
    try:
        done, _ = await asyncio.wait(
            [controls, writer, opening, *failures], return_when=asyncio.FIRST_COMPLETED
        )
        if opening in done:
            try:
                opening.result()
            except Exception as exc:
                emit(
                    {
                        "type": "state",
                        "status": f"Startup failed: {type(exc).__name__}: {exc}",
                        "approval": None,
                    }
                )
            await asyncio.wait([controls, writer, *failures], return_when=asyncio.FIRST_COMPLETED)
    finally:
        opening.cancel()
        controls.cancel()
        overload.cancel()
        if source_overload is not None:
            source_overload.cancel()
        await asyncio.gather(opening, controls, *failures, return_exceptions=True)
        try:
            await asyncio.wait_for(backend.close(), timeout=2)
            if not failed.is_set() and not writer.done():
                await asyncio.wait_for(queue.join(), timeout=0.5)
        except (TimeoutError, BrokenPipeError):
            pass
        writer.cancel()
        await asyncio.gather(writer, return_exceptions=True)
        transport.close()


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

import asyncio
import json
import os
import queue
import sys
import threading
from pathlib import Path

import pytest

from amplifier_tui.frontend_bridge import Admission, PipeWriter, Scene
from amplifier_tui.host import RuntimeBridge

ROOT = Path(__file__).resolve().parents[1]

# Controlled transport: a large replay followed by blocking preparation, not AI.
BLOCKED_STARTUP = r"""
import asyncio,time
from amplifier_tui.frontend_bridge import serve
class Startup:
 def __init__(self,emit): self.emit=emit
 async def open(self):
  self.emit({'type':'snapshot','ready':False,'mode':'TRANSPORT FIXTURE',
   'session_id':'startup-fixture','title':'Startup fixture','items':[
    {'id':str(i),'kind':'tool','text':'Historical fixture tool',
     'status':'succeeded','detail':'x'*3072} for i in range(403)]})
  self.emit({'type':'background','phase':'Preparing controlled bundle'})
  await asyncio.sleep(0)
  await asyncio.sleep(0)
  time.sleep(2.4)
  self.emit({'type':'state','ready':True,'busy':False,'status':'Ready'})
 async def close(self): pass
 def command(self,request): return False,'Diagnostic fixture never executes'
asyncio.run(serve(Startup))
"""


async def test_large_replay_and_blocking_startup_do_not_kill_a_healthy_reader():
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        BLOCKED_STARTUP,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        limit=4 * 1024 * 1024,
    )
    try:
        records = []
        async with asyncio.timeout(12):
            while line := await process.stdout.readline():
                value = json.loads(line)
                records.append(value)
                if value.get("ready"):
                    break
        assert [row["type"] for row in records] == ["snapshot", "background", "state"]
        assert records[-1]["ready"] is True
        assert len(records[0]["items"]) == 403
        assert all(row["detail"] == "x" * 3072 for row in records[0]["items"])
        process.stdin.write(b'{"version":1,"op":"shutdown"}\n')
        await asyncio.wait_for(process.wait(), 4)
        assert process.returncode == 0, (await process.stderr.read()).decode()
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()


@pytest.mark.parametrize("stalled", [False, True])
async def test_pipe_writer_stall_detection_and_joined_shutdown(stalled):
    read_fd, write_fd = os.pipe()
    output = os.fdopen(write_fd, "wb", buffering=0)
    writer = PipeWriter(output)
    try:
        writer.emit({"text": "x" * (2 * 1024 * 1024)})
        if stalled:
            await asyncio.wait_for(writer.failed.wait(), 4)
            assert isinstance(writer.error, TimeoutError)
        await asyncio.wait_for(writer.close(), 0.5)
        assert not writer.thread.is_alive()
        assert os.get_blocking(output.fileno())
    finally:
        await writer.close()
        output.close()
        os.close(read_fd)


@pytest.mark.parametrize("failure", ["serialization", "bytes", "records"])
async def test_pipe_writer_overflow_and_serialization_fail_closed(failure, monkeypatch):
    if failure == "bytes":
        monkeypatch.setattr("amplifier_tui.frontend_bridge.MAX_OUTPUT_BYTES", 16)
    read_fd, write_fd = os.pipe()
    output = os.fdopen(write_fd, "wb", buffering=0)
    writer = PipeWriter(output)
    try:
        if failure == "serialization":
            writer.emit({"unserializable": object()})
            expected = TypeError
        elif failure == "bytes":
            writer.emit({"oversized": "x" * 16})
            expected = BufferError
        else:
            # An unread pipe fills before the bounded queue can drain.
            for _ in range(2048):
                writer.emit({"text": "x" * 1024})
            expected = queue.Full
        await asyncio.wait_for(writer.failed.wait(), 1)
        assert isinstance(writer.error, expected)
        before = writer.pending.qsize()
        writer.emit({"must_not_send": True})
        assert writer.pending.qsize() <= before
    finally:
        await writer.close()
        output.close()
        os.close(read_fd)


async def test_pipe_writer_preserves_records_and_releases_budget():
    read_fd, write_fd = os.pipe()
    output = os.fdopen(write_fd, "wb", buffering=0)
    writer = PipeWriter(output)
    try:
        value = {"nested": {"text": "Original é 😀"}}
        writer.emit(value)
        value["nested"]["text"] = "Mutation must not cross the thread boundary"
        writer.emit({"second": True})
        await asyncio.wait_for(writer.flush(), 1)
        assert writer.pending_bytes == 0
        assert [json.loads(line) for line in os.read(read_fd, 4096).splitlines()] == [
            {"nested": {"text": "Original é 😀"}},
            {"second": True},
        ]
    finally:
        await writer.close()
        output.close()
        os.close(read_fd)


async def test_pipe_writer_start_failure_restores_pipe_and_closes_owned_fd(monkeypatch):
    read_fd, write_fd = os.pipe()
    output = os.fdopen(write_fd, "wb", buffering=0)
    owned = []
    duplicate = os.dup

    def track(fd):
        owned.append(duplicate(fd))
        return owned[-1]

    def refuse(_):
        raise RuntimeError("Controlled thread-start refusal")

    monkeypatch.setattr(os, "dup", track)
    monkeypatch.setattr(threading.Thread, "start", refuse)
    try:
        with pytest.raises(RuntimeError, match="thread-start refusal"):
            PipeWriter(output)
        assert os.get_blocking(write_fd)
        with pytest.raises(OSError):
            os.fstat(owned[0])
    finally:
        output.close()
        os.close(read_fd)


@pytest.mark.parametrize("failure", ["writer", "factory"])
async def test_serve_output_and_factory_failure_exit_nonzero_without_hanging(failure):
    program = """
import asyncio,sys
from amplifier_tui.frontend_bridge import serve
class Startup:
 def __init__(self,emit): self.emit=emit
 async def open(self): self.emit({'bad':object()})
 async def close(self): pass
def factory(emit):
 if sys.argv[1]=='factory': raise RuntimeError('Controlled factory refusal')
 return Startup(emit)
asyncio.run(serve(factory))
"""
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        program,
        failure,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        async with asyncio.timeout(4):
            error = await process.stderr.read()
            assert await process.wait() != 0
        expected = (
            b"Terminal output failed: TypeError" if failure == "writer" else b"factory refusal"
        )
        assert expected in error
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()


def test_protocol_rejects_mismatch_reuse_and_duplicate_effects():
    admission = Admission()
    calls = []

    def dispatch(request):
        calls.append(request)
        return True, "accepted"

    request = {"version": 1, "request_id": "one", "op": "submit", "text": "hello"}
    first = admission.apply(request, dispatch)
    assert admission.apply(request, dispatch) == first
    assert len(calls) == 1
    assert not admission.apply({**request, "text": "changed"}, dispatch)["accepted"]
    assert not admission.apply({**request, "version": 2}, dispatch)["accepted"]
    assert not admission.apply({**request, "request_id": []}, dispatch)["accepted"]
    assert len(calls) == 1


async def test_scene_busy_approval_failure_and_no_stale_authority():
    events = []
    scene = Scene(json.loads((ROOT / "scenes/retry.json").read_text()), events.append)
    await scene.open()
    assert not scene.command({"op": "submit", "text": "retained"})[0]
    assert not scene.command({"op": "decision", "approval_id": "stale", "option": "allow"})[0]
    assert scene.command({"op": "decision", "approval_id": "c18", "option": "allow"})[0]
    assert not scene.command({"op": "decision", "approval_id": "c18", "option": "allow"})[0]
    assert any(e.get("status") == "failed" for e in events)
    assert scene.command({"op": "submit", "text": "first"})[0]
    assert not scene.command({"op": "submit", "text": "second"})[0]
    scene.command({"op": "stop"})
    await scene.close()
    assert "nothing was undone" in events[-1]["status"]


async def test_runtime_adapter_uses_actual_host_and_generic_tool(prepared, tmp_path):
    from amplifier_tui.host import SessionHost

    host = SessionHost()
    events = []

    async def opener(target):
        await target.open(*prepared, tmp_path)

    bridge = RuntimeBridge(host, opener, events.append, True, tmp_path)
    try:
        await bridge.open()
        assert bridge.command({"op": "submit", "text": "Compute a digest"})[0]
        await host.task
        await asyncio.sleep(0)
        assert any(e.get("type") == "system" for e in events)
        tools = [e for e in events if e.get("kind") == "tool"]
        assert tools[-1]["status"] == "succeeded"
        assert "sha256" in tools[-1]["detail"]
        assert any(e.get("type") == "delta" for e in events)
        assert any(e.get("status") == "completed" for e in events)
        assert all(e.get("sequence") for e in events if e.get("type") in {"item", "delta"})
    finally:
        await bridge.close()


async def test_runtime_approvals_queue_actual_options_and_reject_stale_answer(prepared, tmp_path):
    from amplifier_tui.host import SessionHost

    host = SessionHost()
    events = []

    async def opener(target):
        await target.open(*prepared, tmp_path)

    bridge = RuntimeBridge(host, opener, events.append, True, tmp_path)
    tasks = []
    try:
        await bridge.open()
        tasks = [
            asyncio.create_task(host.request_approval(prompt, options, 10, "deny"))
            for prompt, options in [
                ("First command", ["once", "deny"]),
                ("Second command", ["approve-session", "deny"]),
            ]
        ]
        for _ in range(4):
            await asyncio.sleep(0)
        first = bridge.pending.copy()
        assert first["command"] == "First command"
        assert first["options"] == ["once", "deny"]
        assert not bridge.command(
            {"op": "decision", "approval_id": first["id"], "option": "allow"}
        )[0]
        assert bridge.command({"op": "decision", "approval_id": first["id"], "option": "once"})[0]
        assert await tasks[0] == "once"
        for _ in range(3):
            await asyncio.sleep(0)
        second = bridge.pending.copy()
        assert second["command"] == "Second command"
        assert not bridge.command({"op": "decision", "approval_id": first["id"], "option": "once"})[
            0
        ]
        assert not tasks[1].done()
        assert bridge.command({"op": "decision", "approval_id": second["id"], "option": "deny"})[0]
        assert await tasks[1] == "deny"
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await bridge.close()


@pytest.mark.parametrize("real", [False, True])
async def test_bidirectional_subprocess_and_shutdown(tmp_path, real):
    if real:
        command = [
            sys.executable,
            "-m",
            "amplifier_tui",
            "--fixture",
            "--no-install",
            "--bridge",
            "--sources",
            str(ROOT.parent / "tui-sources.json"),
            "--state-dir",
            str(tmp_path / "state"),
        ]
    else:
        command = [
            sys.executable,
            "-m",
            "amplifier_tui.frontend_bridge",
            "--scene",
            str(ROOT / "scenes/retry.json"),
        ]
    process = await asyncio.create_subprocess_exec(
        *command,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )

    async def until(predicate):
        async with asyncio.timeout(15):
            while line := await process.stdout.readline():
                event = json.loads(line)
                assert event["version"] == 1
                if predicate(event):
                    return event
        raise AssertionError("Protocol ended before expected event")

    def send(op, identity, **data):
        process.stdin.write(
            (json.dumps({"version": 1, "request_id": identity, "op": op, **data}) + "\n").encode()
        )

    try:
        if not real:
            await until(lambda e: e.get("approval") is not None)
            send("decision", "allow-1", approval_id="c18", option="deny")
            await until(lambda e: e.get("request_id") == "allow-1")
        else:
            await until(lambda e: e.get("status", "").startswith("Ready"))
        send("submit", "send-1", text="Compute a digest")
        ack = await until(lambda e: e.get("request_id") == "send-1")
        assert ack["accepted"]
        await until(lambda e: e.get("status", "").startswith("Completed"))
        send("shutdown", "close-1")
        await asyncio.wait_for(process.wait(), 4)
        assert process.returncode == 0, (await process.stderr.read()).decode()
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()

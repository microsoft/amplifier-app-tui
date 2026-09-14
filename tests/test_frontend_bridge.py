import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

from amplifier_tui.frontend_bridge import Admission, Scene
from amplifier_tui.host import RuntimeBridge

ROOT = Path(__file__).resolve().parents[1]


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

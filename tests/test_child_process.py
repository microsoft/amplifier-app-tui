"""Actual fresh-process sessions; deterministic providers, no external effects."""

import asyncio
import os
import time
from pathlib import Path

import pytest
from test_child_admission import until
from test_navigation import bridge_for
from test_questions import ANSWERS, QUESTIONS, question_prepared  # noqa: F401


def process_agent(operation="inspect", **arguments):
    return {
        "probe": {
            "tools": [
                {
                    "module": "tool-process-probe",
                    "source": str(Path(__file__).parent / "fixtures/process_probe"),
                }
            ],
            "providers": [
                {
                    "module": "provider-fixture",
                    "config": {
                        "tool": "process_probe",
                        "arguments": {"operation": operation, **arguments},
                        "delay": 0,
                    },
                }
            ],
        }
    }


def messages(host):
    return [
        message for row in host.children.records.values() for message in row.get("messages", [])
    ]


@pytest.mark.parametrize("configured", [False, True])
async def test_process_child_executes_and_continues_under_same_identity(host, configured):
    result = await asyncio.wait_for(
        host.children.spawn(
            "probe",
            "Compute an isolated fixture digest",
            host.session,
            {"probe": {"spawn_mode": "subprocess"} if configured else {}},
            use_subprocess=not configured,
        ),
        20,
    )
    identity = result["session_id"]
    row = host.children.records[identity]
    assert row["use_subprocess"] and row["status"] == "completed"
    assert not row["execution_uncertain"]
    assert "Fixture round trip" in result["output"]
    assert "fixture_probe" in row["tools"]
    before = list(row["messages"])
    again = await asyncio.wait_for(
        host.children.resume(identity, "Explicit second isolated turn"), 20
    )
    assert again["session_id"] == identity
    assert row["messages"][: len(before)] == before
    assert len(row["messages"]) > len(before)
    assert not host.children.active


async def test_distinct_process_identity_scope_observations_and_environment(
    host, tmp_path, monkeypatch
):
    monkeypatch.setenv("FIXTURE_UNRELATED_SECRET", "invented-local-only-value")
    result = await host.children.spawn(
        "probe",
        "Inspect isolated scope",
        host.session,
        process_agent(),
        use_subprocess=True,
        self_delegation_depth=2,
    )
    row = host.children.records[result["session_id"]]
    assert row["status"] == "completed"
    assert row["usage"]["totals"]["input_tokens"] == 12
    assert row["usage"]["totals"]["output_tokens"] == 3
    assert row["usage"]["totals"]["cost_usd"] == "0.01"
    content = str(messages(host))
    assert f'"cwd": "{tmp_path}"' in content
    assert '"self_depth": 2' in content and '"unrelated_env": null' in content
    assert f'"pid": {os.getpid()}' not in content
    assert any(value == "succeeded" for value in host.observed_tools["children"].values())
    assert not host.children.tasks


@pytest.mark.parametrize("nested_process", [False, True])
async def test_nested_delegation_from_process_has_exact_owner_and_independent_capacity(
    host, nested_process
):
    host.children.capacity = 1
    result = await asyncio.wait_for(
        host.children.spawn(
            "probe",
            "Run a nested fixture",
            host.session,
            process_agent("nested", subprocess=nested_process),
            use_subprocess=True,
        ),
        20,
    )
    row = host.children.records[result["session_id"]]
    assert row["status"] == "completed"
    descendants = [r for r in host.children.records.values() if r["parent"] == result["session_id"]]
    assert len(descendants) == 1
    child = descendants[0]
    assert child["status"] == "completed" and child["self_depth"] == 2
    assert child["use_subprocess"] == nested_process
    assert child["parent_item_id"].startswith(
        f"activity:{result['session_id']}:{row['activity_run']}:"
    )
    assert not host.children.tasks


@pytest.mark.parametrize("answer", ["allow", "deny"])
async def test_process_approval_is_a_real_parent_wait(host, answer):
    host.children.prepared.bundle.tools[0]["config"] = {"approval": True}
    task = asyncio.create_task(
        host.children.spawn("self", "Ask first", host.session, {}, use_subprocess=True)
    )
    await until(lambda: host._pending)
    identity = next(iter(host.children.records))
    worker = host.children.active[identity]
    assert worker.process.pid != os.getpid() and not task.done()
    assert host.children.records[identity]["activity_status"] == "waiting_permission"
    approval = next(iter(host._pending))
    assert host.answer(approval, answer)
    await asyncio.wait_for(task, 10)
    assert ("Denied" in str(messages(host))) == (answer == "deny")
    assert worker.process.returncode == 0 and worker.finished


@pytest.mark.parametrize("force", [False, True])
async def test_two_stage_stop_drains_or_kills_and_reaps(host, force):
    operation = "uncooperative" if force else "cooperative"
    task = asyncio.create_task(
        host.children.spawn(
            "probe",
            "Stop this controlled operation",
            host.session,
            process_agent(operation, delay=0.6),
            use_subprocess=True,
        )
    )
    await until(
        lambda: any(
            r.get("usage", {}).get("totals", {}).get("input_tokens")
            for r in host.children.records.values()
        )
    )
    identity = next(iter(host.children.records))
    worker = host.children.active[identity]
    started = time.monotonic()
    host.children.stop(immediate=False)
    await asyncio.sleep(0.15)
    assert not task.done() and worker.process.returncode is None
    if force:
        host.children.stop(immediate=True)
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 5)
    else:
        result = await asyncio.wait_for(task, 5)
        assert result["metadata"]["status"] == "cancelled"
        assert time.monotonic() - started >= 0.3
    row = host.children.records[identity]
    assert row["status"] == "interrupted"
    assert row["resumable"] is (not force)
    assert worker.process.returncode is not None
    assert not host.children.tasks


async def test_lost_worker_cannot_claim_completed_or_resumable(host):
    with pytest.raises(RuntimeError, match="connection|uncertain"):
        await asyncio.wait_for(
            host.children.spawn(
                "probe",
                "Crash the fixture worker",
                host.session,
                process_agent("crash"),
                use_subprocess=True,
            ),
            10,
        )
    identity = next(iter(host.children.records))
    row = host.children.records[identity]
    assert row["execution_uncertain"] and not row["resumable"]
    with pytest.raises(ValueError, match="incomplete"):
        await host.children.resume(identity, "Do not replay effects")
    assert not host.children.tasks


async def test_cold_process_continuation_keeps_execution_mode(prepared, tmp_path):
    bridge, _ = await bridge_for(prepared, tmp_path, tmp_path)
    try:
        host = bridge.host
        first = await host.children.spawn(
            "self", "Initial process turn", host.session, {}, use_subprocess=True
        )
        row = host.children.records[first["session_id"]]
        prior = list(row["messages"])
        row["archived"] = True
        row.pop("prepared")
        row.pop("messages")
        result = await host.children.resume(
            first["session_id"], "Explicit cold process continuation"
        )
        restored = host.children.records[result["session_id"]]
        assert restored["use_subprocess"] and restored["messages"][: len(prior)] == prior
    finally:
        await bridge.close()


async def test_process_question_uses_existing_answer_surface(question_prepared, tmp_path):  # noqa: F811
    from amplifier_core import ToolResult

    bridge, _ = await bridge_for(question_prepared, tmp_path, tmp_path)
    host = bridge.host
    host.children.prepared.bundle.providers[0]["config"] = {"questions": QUESTIONS}
    host.session.coordinator.get("providers")["fixture"].config.pop("questions", None)

    async def ask_child(_input):
        result = await host.children.spawn(
            "self", "Ask a fixture question", host.session, {}, use_subprocess=True
        )
        return ToolResult(success=True, output=result)

    host.session.coordinator.get("tools")["fixture_probe"].execute = ask_child
    host.children.register(host.session)
    assert host.submit("Ask through the isolated child")[0]
    task = host.task
    try:
        await until(lambda: host.questions.pending)
        assert not host._pending and not task.done()
        accepted, reason = bridge.command(
            {
                "op": "question_answer",
                "question_id": next(iter(host.questions.pending)),
                "session_id": host.session_id,
                "turn_id": host.turn_id,
                "answers": ANSWERS,
            }
        )
        assert accepted, reason
        await asyncio.wait_for(task, 10)
        assert "Preserve" in str(messages(host)) and "my changes" in str(messages(host))
        assert not host.questions.pending
    finally:
        await bridge.close()


async def test_force_stop_during_permission_wait_releases_it_and_reaps(host):
    host.children.prepared.bundle.tools[0]["config"] = {"approval": True}
    task = asyncio.create_task(
        host.children.spawn("self", "Wait for permission", host.session, {}, use_subprocess=True)
    )
    await until(lambda: host._pending)
    worker = next(iter(host.children.active.values()))
    host.children.stop(immediate=True)
    task.cancel()  # Repeated cancellation must not abandon process ownership.
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 5)
    assert not host._pending and not host.children.tasks
    assert worker.process.returncode is not None


async def test_private_channel_keeps_control_responsive_and_fails_closed():
    import socket
    from decimal import Decimal

    from amplifier_tui.frontend_bridge import ChildChannel

    blocked, release = asyncio.Event(), asyncio.Event()

    async def handle(operation, payload):
        if operation == "wait":
            blocked.set()
            await release.wait()
        if operation == "oversized":
            return "x" * 4096
        if operation == "decimal":
            return {"cost_usd": Decimal("0.123456789")}
        return operation

    left, right = socket.socketpair()
    parent = await ChildChannel.connect(left, handle)
    child = await ChildChannel.connect(right, handle)
    try:
        wait = asyncio.create_task(parent.call("wait"))
        await blocked.wait()
        assert await asyncio.wait_for(parent.call("control"), 1) == "control"
        assert await parent.call("decimal") == {"cost_usd": "0.123456789"}
        wait.cancel()
        with pytest.raises(asyncio.CancelledError):
            await wait
        await until(lambda: not child.incoming)
        child.MAX_FRAME = 1024
        with pytest.raises(RuntimeError, match="connection lost"):
            await asyncio.wait_for(parent.call("oversized"), 1)
        assert parent.closed
    finally:
        await parent.close()
        await child.close()


async def test_process_module_startup_failure_is_reaped(host, monkeypatch):
    from amplifier_tui.composition import ProcessSession

    workers = []
    cleanup = ProcessSession.cleanup

    async def observe(self):
        try:
            return await cleanup(self)
        finally:
            workers.append(self)

    monkeypatch.setattr(ProcessSession, "cleanup", observe)
    host.children.prepared.bundle.tools[0]["config"] = {"skip_mount": True}
    # Missing required runtime component fails inside the fresh worker, not before launch.
    host.children.prepared.bundle.providers = []
    with pytest.raises(RuntimeError, match="provider|Provider"):
        await asyncio.wait_for(
            host.children.spawn("self", "Must not execute", host.session, {}, use_subprocess=True),
            10,
        )
    assert workers and all(worker.process.returncode is not None for worker in workers)
    assert not host.children.tasks


@pytest.mark.skipif(not Path("/proc").is_dir(), reason="Linux process observation")
async def test_blocked_worker_terminates_when_owning_host_disappears(prepared, tmp_path):
    import signal
    import sys

    root = Path(__file__).resolve().parents[1]
    program = r"""
import asyncio,os,sys
from pathlib import Path
root=Path(sys.argv[1]); work=Path(sys.argv[2])
sys.path.insert(0,str(root/'tests'))
from test_child_process import process_agent
from amplifier_tui.composition import prepare,SourceMap
from amplifier_tui.host import SessionHost
async def run():
 paths={f'https://github.com/microsoft/{n}':str(root.parent/n) for n in
        ('amplifier-module-loop-streaming','amplifier-module-context-simple')}
 prepared=await prepare(str(root/'src/amplifier_tui/fixtures/bundle.yaml'),[],work,SourceMap(paths),install_deps=False)
 host=SessionHost(); await host.open(*prepared,work)
 task=asyncio.create_task(host.children.spawn('probe','Controlled host loss',host.session,
                         process_agent('uncooperative'),use_subprocess=True))
 while not any(r.get('usage',{}).get('totals',{}).get('input_tokens') for r in host.children.records.values()):
  if task.done(): task.result()
  await asyncio.sleep(.01)
 print(next(iter(host.children.active.values())).process.pid,flush=True)
 await asyncio.to_thread(sys.stdin.readline)
 os._exit(0)
asyncio.run(run())
"""
    parent = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        program,
        str(root),
        str(tmp_path),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    worker_pid = None

    def running():
        try:
            return Path(f"/proc/{worker_pid}/stat").read_text().split(") ", 1)[1][0] != "Z"
        except (FileNotFoundError, ProcessLookupError):
            return False

    try:
        worker_pid = int(await asyncio.wait_for(parent.stdout.readline(), 15))
        assert worker_pid != parent.pid and running()
        await asyncio.sleep(0.1)
        parent.stdin.write(b"exit\n")
        await parent.stdin.drain()
        await asyncio.wait_for(parent.wait(), 3)
        async with asyncio.timeout(3):
            while running():
                await asyncio.sleep(0.025)
    finally:
        if parent.returncode is None:
            parent.kill()
            await parent.wait()
        if worker_pid and running():
            os.kill(worker_pid, signal.SIGKILL)

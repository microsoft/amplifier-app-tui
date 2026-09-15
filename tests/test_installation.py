"""Installed launch configuration must not depend on the development workspace."""

import asyncio
import json
import sys
from pathlib import Path

import pytest
from test_host import ending

from amplifier_tui.conversations import ConversationStore
from amplifier_tui.delivery import EventDelivery
from amplifier_tui.events import Event
from amplifier_tui.host import SessionHost
from amplifier_tui.launcher import PACKAGE, arguments, state_directory


def test_default_remote_launch_and_packaged_overlays(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fixture-value-not-a-credential")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    _, command = arguments([])
    assert command[command.index("--bundle") + 1].startswith("git+https://")
    assert "#subdirectory=bundles/anchors" in command[command.index("--bundle") + 1]
    assert "--sources" not in command
    assert str(PACKAGE / "assets/user-questions.yaml") in command
    assert str(PACKAGE / "assets/anthropic.yaml") in command
    assert state_directory() == tmp_path / "data/amplifier-tui"
    assert not (tmp_path / "data").exists()


def test_doctor_does_not_write_state_or_reveal_credentials(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "private-fixture-marker")
    with pytest.raises(SystemExit):
        arguments(["--doctor", "--state-dir", str(tmp_path / "missing")])
    text = capsys.readouterr().out
    assert json.loads(text)["frontend"] == "ratatui"
    assert "private-fixture-marker" not in text
    assert not (tmp_path / "missing").exists()


def test_packaged_question_source_exists():
    import yaml

    file = PACKAGE / "assets/user-questions.yaml"
    value = yaml.safe_load(file.read_text())
    assert (file.parent / value["tools"][0]["source"] / "pyproject.toml").is_file()
    assert Path(value["tools"][0]["source"]).is_absolute() is False


def test_explicit_transcript_import_is_a_new_launch_not_resume(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _, command = arguments(["--fixture", "--import-transcript", "old.md"])
    assert command[command.index("--import-transcript") + 1] == str(tmp_path / "old.md")
    assert "--resume" not in command
    with pytest.raises(SystemExit):
        arguments(["--resume", "a" * 32, "--import-transcript", "old.md"])


async def test_tool_failure_summary_does_not_override_turn_completion(host):
    host.session.coordinator.get("tools")["fixture_probe"].config["fail"] = True
    host.submit("Compute")
    event = (await ending(host))[-1]
    assert event.payload["status"] == "completed"
    assert event.payload["tools"]["root"]["failed"] == 1
    assert "1 failed" in event.payload["message"]
    assert "See Activity evidence" in event.payload["message"]
    host.session.coordinator.get("tools")["fixture_probe"].config["fail"] = False
    host.submit("Again")
    event = (await ending(host))[-1]
    assert event.payload["tools"]["root"]["failed"] == 0
    assert event.payload["message"] == "Turn complete."


async def test_child_observation_summary_counts_calls_not_events(host):
    host.emit(
        "child.observed", "activity:child:1:call:tool:pre", event="tool:pre", status="running"
    )
    host.emit(
        "child.observed", "activity:child:1:call:tool:post", event="tool:post", status="failed"
    )
    assert host.observed_tools["children"] == {"activity:child:1:call": "failed"}


async def test_source_delivery_overload_is_bounded_durable_and_stops_admission(prepared, tmp_path):
    store = ConversationStore(tmp_path, {})
    host = SessionHost(store)
    try:
        await host.open(*prepared, tmp_path)
        assert host.submit("No automatic retry")[0]
        for index in range(4100):
            host.emit("display.message", f"burst-{index}", text="Observed before failure")
        await host.task
        assert host.events.qsize() == 4096
        assert host.delivery_failed.is_set()
        assert not host.ready and not host.submit("Must not run")[0]
        assert not host.session.coordinator.get("providers")["fixture"].calls
        with pytest.raises(RuntimeError, match="backlog exceeded"):
            await host.next_event()
        rows = [json.loads(line) for line in (store.path / "events.jsonl").read_text().splitlines()]
        assert sum(r["kind"] == "display.message" for r in rows) == 4100
        assert rows[-1]["kind"] == "turn.ended"
        assert rows[-1]["payload"]["status"] == "interrupted"
        assert json.loads((store.path / "checkpoint.json").read_text())["status"] == "uncertain"
    finally:
        await host.close()


async def test_delivery_byte_bound_and_budget_release():
    queue = EventDelivery(maxsize=2, max_bytes=400)
    event = Event("session", 1, "turn", "text.delta", "item", {"text": "small"})
    queue.put_nowait(event)
    assert 0 < queue.pending_bytes < 400
    assert await queue.get() == event
    assert queue.pending_bytes == 0
    with pytest.raises(asyncio.QueueFull):
        queue.put_nowait(Event("session", 2, "turn", "text.final", "large", {"text": "x" * 500}))
    assert queue.empty() and queue.pending_bytes == 0


async def test_bridge_exits_on_source_failure_with_input_still_open():
    # Fault producer only, not a replacement runtime conformance claim. Keeping
    # stdin open proves shutdown follows source failure rather than input EOF.
    code = """
import asyncio
from pathlib import Path
from amplifier_tui.frontend_bridge import serve
from amplifier_tui.host import RuntimeBridge, SessionHost
async def open_host(host):
    for i in range(4100):
        host.emit('display.message', str(i), text='overload fault')
asyncio.run(serve(lambda emit: RuntimeBridge(SessionHost(), open_host, emit, True, Path.cwd())))
"""
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        code,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        async with asyncio.timeout(5):
            output, error = await asyncio.gather(process.stdout.read(), process.stderr.read())
            assert await process.wait() == 0
        assert b"Source event delivery exceeded" in error
        assert b"snapshot" in output
    finally:
        if process.returncode is None:
            process.kill()
        await process.wait()

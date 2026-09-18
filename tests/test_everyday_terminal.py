"""Natural navigation: actual runtime history; selection/native view use labelled scenes."""

import os
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from interaction_probe import action, capture, click  # noqa: E402
from terminal_probe import Probe  # noqa: E402
from test_navigation_terminal import start  # noqa: E402
from test_reading_terminal import draft_is, scene  # noqa: E402
from test_structured_reading_terminal import copied  # noqa: E402

pytestmark = pytest.mark.skipif(
    os.environ.get("TUI_TEST_CANDIDATES") != "1", reason="Build Ratatui first"
)


async def test_large_saved_conversation_resumes_through_blocking_preparation(prepared, tmp_path):
    import json

    from amplifier_tui.conversations import ConversationStore
    from amplifier_tui.events import Event
    from amplifier_tui.host import SessionHost

    state = tmp_path / "state"
    store = ConversationStore(state, {"fixture": True, "cwd": str(tmp_path)})
    host = SessionHost(store)
    try:
        await host.open(*prepared, tmp_path)
        assert host.submit("Original fixture turn")[0]
        await host.task
        assert host.outcome == "success"
        # Synthetic retained tool detail drives a >1 MiB replay; these records do
        # not claim additional actual tool executions. The first turn is real core.
        for i in range(403):
            host.sequence += 1
            store.record(
                Event(
                    host.session_id,
                    host.sequence,
                    "synthetic-history",
                    "tool.ended",
                    f"synthetic-{i}",
                    {
                        "name": "historical_fixture",
                        "status": "succeeded",
                        "result": {"text": "Synthetic retained observation", "padding": "x" * 3072},
                    },
                )
            )
        store.checkpoint(
            await host.session.coordinator.get("context").get_messages(),
            host.sequence,
            host.fingerprint,
            True,
        )
        store.save_draft("Retained startup draft")
        identity = host.session_id
        initial_sequence = host.sequence
    finally:
        await host.close()
    restored = ConversationStore(state, store.metadata["launch"], identity)
    try:
        assert len(json.dumps(restored.projection()).encode()) > 1024 * 1024
    finally:
        restored.close()
    # Actual host, store, Foundation and core. Delay just preparation scheduling,
    # matching synchronous startup work without involving a provider or user data.
    program = r"""
import asyncio,json,sys,time
from pathlib import Path
from amplifier_tui.composition import SourceMap,prepare
from amplifier_tui.conversations import ConversationStore
from amplifier_tui.host import SessionHost
from amplifier_tui.navigation import WorkspaceBridge
from amplifier_tui.frontend_bridge import serve
state,cwd,identity,fixture,sources=map(str,sys.argv[1:])
host=SessionHost()
async def opener(target):
 target.background('Preparing controlled bundle')
 await asyncio.sleep(0)
 await asyncio.sleep(0)
 time.sleep(2.4)
 prepared,report=await prepare(fixture,[],Path(state),SourceMap.read(Path(sources)),install_deps=False)
 report['fixture']=True
 await target.open(prepared,report,Path(cwd))
asyncio.run(serve(lambda emit:WorkspaceBridge(host,opener,emit,True,Path(cwd),
 lambda:ConversationStore(Path(state),{'fixture':True,'cwd':cwd},identity),
 state_dir=Path(state),open_launch=None)))
"""
    p = Probe(
        [
            str(ROOT / "frontends/ratatui/target/release/amplifier-ratatui"),
            "--host-json",
            json.dumps(
                [
                    sys.executable,
                    "-c",
                    program,
                    str(state),
                    str(tmp_path),
                    identity,
                    str(ROOT / "src/amplifier_tui/fixtures/bundle.yaml"),
                    str(ROOT.parent / "tui-sources.json"),
                ]
            ),
        ],
        cols=175,
        rows=50,
        env={"AMPLIFIER_HOME": str(tmp_path / "foundation")},
    )
    try:
        p.wait("Preparing controlled bundle")
        p.send(b"\x1b[F plus new text")
        p.wait("Ready", timeout=20)
        draft_is(p, "Retained startup draft plus new text")
        rows = [json.loads(line) for line in (store.path / "events.jsonl").read_text().splitlines()]
        assert not any(
            row["kind"] == "turn.accepted" or row["kind"].startswith("tool.")
            for row in rows[initial_sequence:]
        )
        capture(p, "startup-large-resume-ready")
        p.send(b"\r")
        p.wait_idle()
        rows = [json.loads(line) for line in (store.path / "events.jsonl").read_text().splitlines()]
        assert sum(row["kind"] == "turn.accepted" for row in rows) == 2
        calls = [
            row
            for row in rows[initial_sequence:]
            if row["kind"] == "tool.updated" and row["payload"].get("status") == "running"
        ]
        assert len(calls) == 1
        assert calls[0]["payload"]["name"] == "fixture_probe"
    finally:
        p.close()


def test_directory_history_and_visible_resume(tmp_path):
    probe = start(tmp_path)
    try:
        probe.wait("Ready")
        probe.send(b"Earlier same-directory input\r")
        probe.wait_idle()
        action(probe, "New conversation", "[ Send ]")
        # Previous output remains terminal history; New changes context, not rows.
        probe.wait("Untitled conversation")
        probe.wait("Ready")  # Navigation does not execute a turn.
        # Wait for the read-only asynchronous history snapshot, without guessing its timing.
        action(probe, "History —", "Directory history")
        probe.wait("Earlier same-directory input")
        probe.send(b"\x1b")
        probe.wait("Directory history", absent=True)
        probe.send(b"Unsent draft\x1b[A")
        draft_is(probe, "Earlier same-directory input")
        probe.send(b"\x1b[B")
        draft_is(probe, "Unsent draft")
        click(probe, "[Resume]")
        probe.wait("Saved conversations")
        capture(probe, "everyday-resume")
        probe.send(b"\x1b")
        probe.wait("Saved conversations", absent=True)
        draft_is(probe, "Unsent draft")
    finally:
        probe.close()


def test_startup_picker_cancel_does_not_mount_or_write(tmp_path):
    probe = start(tmp_path)
    try:
        probe.wait("Ready")
        probe.send(b"Picker source\r")
        probe.wait_idle()
    finally:
        probe.close()
    state = tmp_path / "state"
    before = {str(p): p.read_bytes() for p in state.rglob("*") if p.is_file()}
    probe = Probe(
        [sys.executable, str(ROOT / "scripts/run.py"), "--resume", "--state-dir", str(state)],
        cwd=tmp_path,
    )
    try:
        probe.wait("Resume conversation")
        probe.wait("Picker source")
        capture(probe, "everyday-startup-picker")
        probe.send(b"\x1b")
    finally:
        probe.close()
    assert before == {str(p): p.read_bytes() for p in state.rglob("*") if p.is_file()}


def test_resume_options_stay_in_the_actual_launch_directory(tmp_path):
    import json

    work, child, state = tmp_path / "work", tmp_path / "work/child", tmp_path / "state"
    child.mkdir(parents=True)
    command = [
        sys.executable,
        str(ROOT / "scripts/run.py"),
        "--no-install",
        "--state-dir",
        str(state),
    ]
    for cwd, prompt in ((work, "Directory local marker"), (child, "Foreign child marker")):
        p = Probe([*command, "--fixture"], cwd=cwd, cols=175, rows=50)
        try:
            p.wait("Ready")
            p.send(prompt.encode() + b"\r")
            p.wait_idle()
        finally:
            p.close()
    before = {p: p.read_bytes() for p in state.rglob("*") if p.is_file()}
    p = Probe([*command, "--resume"], cwd=work, cols=175, rows=50)
    try:
        p.wait("Resume conversation · this directory")
        p.wait("Directory local marker")
        assert "Foreign child marker" not in p.text
        capture(p, "directory-resume-startup")
        p.send(b"\x1b")
    finally:
        p.close()
    assert before == {p: p.read_bytes() for p in state.rglob("*") if p.is_file()}
    p = Probe([*command, "--resume", "latest"], cwd=work, cols=175, rows=50)
    try:
        p.wait("Ready")
        p.wait("Directory local marker")
        p.send(b"Retained local draft")
        click(p, "[Resume]")
        p.wait("Saved conversations · this directory")
        p.wait("Directory local marker")
        assert "Foreign child marker" not in p.text
        capture(p, "directory-resume-native")
        p.send(b"\x1b")
        draft_is(p, "Retained local draft")
    finally:
        p.close()
    for file in (state / "conversations").glob("*/events.jsonl"):
        assert (
            sum(
                json.loads(line)["kind"] == "turn.accepted"
                for line in file.read_text().splitlines()
            )
            == 1
        )
    p = Probe([*command, "--resume"], cwd=tmp_path, cols=175, rows=50)
    try:
        p.wait("No saved conversations in this working directory")
        assert "Directory local marker" not in p.text and "Foreign child marker" not in p.text
        capture(p, "directory-resume-empty-parent")
    finally:
        # The launch intentionally refuses; the normal probe expects a clean UI exit.
        with pytest.raises(
            AssertionError, match="No saved conversations in this working directory"
        ):
            p.close()
        assert p.process.returncode == 2


def test_selection_wheel_and_edge_scroll_beyond_initial_page(tmp_path):
    probe = scene(
        tmp_path,
        [
            {
                "id": "a",
                "kind": "assistant",
                "text": "```text\n" + "\n".join(f"row {i:03d}" for i in range(100)) + "\n```",
            }
        ],
        draft="Keep draft",
        stream_interval_ms=100,  # Keep the controlled stream observable through navigation.
    )
    try:
        probe.wait("row 099")
        action(probe, "Transcript —", "[ Latest")
        probe.wait("row 090")
        assert "row 050" not in probe.text
        y = next(i for i, row in enumerate(probe.screen.display) if "row 090" in row)
        x = probe.screen.display[y].index("row 090")
        probe.send(f"\x1b[<0;{x + 1};{y + 1}M".encode())
        # Wheel up while dragging, then reach the top edge and let autoscroll continue.
        probe.send(f"\x1b[<64;{x + 1};{y + 1}M\x1b[<32;{x + 8};7M".encode())
        probe.wait("row 050")
        probe.send(f"\x1b[<0;{x + 8};7m".encode())
        probe.wait("Text selected")
        probe.send(b"\x03")
        text = copied(probe)
        assert "row 051" in text and "row 089" in text
        draft_is(probe, "Keep draft")
        capture(probe, "everyday-scroll-selection")
        probe.send(b"\x1b")
    finally:
        probe.close()


def test_native_scrollback_keeps_draft_and_ingests_updates(tmp_path):
    probe = scene(
        tmp_path,
        [
            {
                "id": "a",
                "kind": "assistant",
                "text": "early marker\n" + "\n".join(f"row {i:03d}" for i in range(100)),
            }
        ],
        draft="Keep draft",
    )
    try:
        probe.wait("row 099")
        probe.send(b"\r")
        probe.wait("Working")
        action(probe, "Native scrollback", "Native terminal history")
        assert b"early marker" in probe.raw
        assert b"\x1b[?1049l" in probe.raw
        # Normal native view remains the editable composer. Paste never submits.
        probe.send(b"\x1b[200~never send\r\x1b[201~")
        until = time.monotonic() + 1
        while time.monotonic() < until:
            probe.read(0.02)
        probe.wait("[ Send ]")
        probe.wait("Streaming new content without disturbing the reading anchor.")
        draft_is(probe, "never send")
        assert "you\nnever send" not in probe.text
        capture(probe, "everyday-native-return")
    finally:
        probe.close()

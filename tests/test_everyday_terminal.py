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


def test_directory_history_and_visible_resume(tmp_path):
    probe = start(tmp_path)
    try:
        probe.wait("Ready")
        probe.send(b"Earlier same-directory input\r")
        probe.wait("Completed")
        action(probe, "New conversation", "[ Send ]")
        # Previous output remains terminal history; New changes context, not rows.
        probe.wait("Ready")
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
        probe.wait("Completed")
    finally:
        probe.close()
    state = tmp_path / "state"
    before = {str(p): p.read_bytes() for p in state.rglob("*") if p.is_file()}
    probe = Probe(
        [sys.executable, str(ROOT / "scripts/run.py"), "--resume", "--state-dir", str(state)]
    )
    try:
        probe.wait("Resume conversation")
        probe.wait("Picker source")
        capture(probe, "everyday-startup-picker")
        probe.send(b"\x1b")
    finally:
        probe.close()
    assert before == {str(p): p.read_bytes() for p in state.rglob("*") if p.is_file()}


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
    )
    try:
        probe.wait("row 099")
        action(probe, "Transcript —", "[ Latest")
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
        probe.wait("Completed")
        draft_is(probe, "never send")
        assert "you\nnever send" not in probe.text
        capture(probe, "everyday-native-return")
    finally:
        probe.close()

"""Opt-in real terminal regressions; compiled candidates must be installed first."""

import base64
import json
import os
import re
import signal
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from terminal_probe import Probe  # noqa: E402

pytestmark = pytest.mark.skipif(
    os.environ.get("TUI_TEST_CANDIDATES") != "1",
    reason="Build candidates; set TUI_TEST_CANDIDATES=1",
)


@pytest.mark.parametrize("frontend", ["ratatui", "opentui"])
@pytest.mark.parametrize("initial_cols", [160, 200])
def test_full_width_launch_and_resize_preserve_draft(frontend, initial_cols):
    probe = Probe([sys.executable, str(ROOT / "scripts/compare.py"), frontend], cols=initial_cols)

    def assert_layout(cols, rows):
        pad = 0 if frontend == "ratatui" else (3 if cols >= 80 else 2)
        compose_y = rows - (7 if rows >= 30 else 5)
        approval_y = compose_y - (7 if rows >= 30 else 5)
        if frontend == "ratatui":
            approval_y -= 1  # visible navigation row above the unchanged composer
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            display = probe.screen.display
            if frontend == "ratatui":
                composers = [r for r in display if r.strip().startswith("Message ·")]
                if (
                    composers
                    and composers[-1].startswith(" " * pad + "Message")
                    and "SIMULATED" in composers[-1]
                    and "Ratatui" not in composers[-1]
                    and any("Review decision" in r for r in display)
                    and probe.screen.buffer[rows - 1][cols - pad - 1].bg
                    == probe.screen.buffer[rows - 1][pad].bg
                ):
                    return
                probe.read()
                continue
            if (
                display[3] == "─" * cols
                and display[compose_y][pad] == "╭"
                and display[compose_y][cols - pad - 1] == "╮"
                and display[approval_y][pad] == "╭"
                and display[approval_y][cols - pad - 1] == "╮"
                and (frontend + " · simulated") in display[2][pad:].lower()
            ):
                return
            probe.read()
        pytest.fail(f"Layout did not fill {cols}x{rows} with {pad}-cell padding\n{probe.text}")

    try:
        probe.wait("Waiting for your decision")
        assert_layout(initial_cols, 40)
        probe.send(b" width-check")
        probe.wait("width-check")
        for cols, rows in [(60, 20), (200, 40), (80, 24), (160, 40)]:
            probe.resize(cols, rows)
            assert_layout(cols, rows)
            # At 60x20 the editor has one row; the cursor's wrapped line may
            # show only the suffix. Verify the full draft on widening below.
            probe.wait("check")
        probe.send(b"\r")
        probe.wait("Busy")
        probe.wait("are not retried. width-check")
    finally:
        probe.close()


@pytest.mark.parametrize("frontend", ["ratatui", "opentui"])
def test_real_terminal_paste_selection_views_and_failure(frontend):
    probe = Probe([sys.executable, str(ROOT / "scripts/compare.py"), frontend])
    try:
        probe.wait("Waiting for your decision")
        # Cursor is at the end of the supplied draft. Select its last character,
        # change views without remounting the editor, then replace the selection.
        probe.send(b"\x1b[1;2D\x1bOR")
        probe.wait("Not available")
        probe.send(b"!")
        probe.wait("are not retried!")
        probe.send(b"\x1bOP\r")
        probe.wait("Busy")
        probe.wait("are not retried!")
        probe.send(b"\x19")
        probe.wait("simulated test failed")
        probe.send(b"\x05")
        probe.wait("assert attempts == 1")
        probe.send(b"\x10")
        probe.wait("Source copied" if frontend == "ratatui" else "Evidence copied")
        copies = re.findall(rb"\x1b\]52;[^;]*;([A-Za-z0-9+/=]+)", probe.raw)
        assert copies, "No actual clipboard escape reached the terminal"
        expected = json.loads((ROOT / "scenes/retry.json").read_text())["failure_detail"]
        assert base64.b64decode(copies[-1]).decode() == expected
        probe.send(b"\x1b")
        probe.wait("Evidence ·", absent=True)
        probe.send(b"\r")
        probe.wait("Working")
        probe.send("\x1b[200~Preserve this draft.\nUnicode: 界 é 🦀\x13\x1b[201~".encode())
        probe.wait("Unicode:")
        probe.wait_idle()
        probe.wait("Preserve this draft.")
        # No implicit second submit from pasted newlines/control characters.
        assert (
            probe.screen.display[-1].strip() == "Ready" or "Completed" in probe.screen.display[-1]
        )
    finally:
        probe.close()


@pytest.mark.parametrize("frontend", ["ratatui", "opentui"])
def test_boundary_loss_keeps_draft_and_never_claims_completion(frontend):
    probe = Probe([sys.executable, str(ROOT / "scripts/compare.py"), frontend])
    try:
        probe.wait("Waiting for your decision")
        children = (
            Path(f"/proc/{probe.process.pid}/task/{probe.process.pid}/children").read_text().split()
        )
        assert len(children) == 1, "Resolve only the owned backend child"
        os.kill(int(children[0]), signal.SIGKILL)
        probe.wait("Disconnected")
        probe.wait("Also check that permanent failures")
        probe.send(b"\r")
        probe.wait("no retry" if frontend == "ratatui" else "no automatic retry")
        probe.wait("Also check that permanent failures")
        assert "Starting" not in probe.text and "Session not ready" not in probe.text
    finally:
        probe.close()


@pytest.mark.parametrize("frontend", ["ratatui", "opentui"])
def test_no_color_and_signal_restore(frontend):
    probe = Probe(
        [sys.executable, str(ROOT / "scripts/compare.py"), frontend], env={"NO_COLOR": "1"}
    )
    try:
        probe.wait("Waiting for your decision")
        probe.wait("Review decision" if frontend == "ratatui" else "Ctrl+Y Allow once")
        probe.send(b"\x19")
        probe.wait("simulated test failed")
        probe.send(b"\x05")
        probe.wait("FAILED test_permanent")
        os.kill(probe.process.pid, signal.SIGTERM)
        probe.process.wait(timeout=4)
    finally:
        probe.close()


@pytest.mark.parametrize("frontend", ["ratatui", "opentui"])
@pytest.mark.parametrize("failure", [False, True])
def test_real_runtime_terminal_round_trip_or_startup_error(frontend, failure, tmp_path):
    command = [
        sys.executable,
        str(ROOT / "scripts/compare.py"),
        frontend,
        "--runtime",
        "--fixture",
        "--sources",
        str(ROOT.parent / "tui-sources.json"),
        "--no-install",
        "--state-dir",
        str(tmp_path / "state"),
    ]
    if failure:
        command += ["--require-tool", "absent-fixture-tool"]
    probe = Probe(command)
    try:
        # The provisional editor is usable before runtime admission; Send is
        # deliberately unavailable until ready in the working native client.
        probe.wait("Message · Mode:" if frontend == "ratatui" else "Enter send")
        probe.send(b"Compute a digest")
        probe.wait("Compute a digest")
        probe.wait("Startup failed" if failure else "Ready")
        if failure:
            probe.send(b"\r")
            probe.wait("not ready")
            probe.wait("Compute a digest")
        else:
            probe.send(b"\r")
            probe.wait_idle()
            probe.wait("fixture_probe")
            probe.send(b"\x05")
            probe.wait("sha256")
    finally:
        probe.close()

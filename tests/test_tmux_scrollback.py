"""Actual isolated tmux copy-mode, never the user's server or configuration."""

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from terminal_probe import Probe  # noqa: E402

pytestmark = pytest.mark.skipif(
    os.environ.get("TUI_TEST_CANDIDATES") != "1" or not shutil.which("tmux"),
    reason="Build native client and install tmux",
)


@pytest.mark.parametrize("case", ["long", "short", "stream"])
def test_primary_screen_reaches_real_tmux_history_and_copy_mode(tmp_path, case):
    short = case == "short"
    scene = tmp_path / "scene.json"
    scene.write_text(
        json.dumps(
            {
                "title": "Tmux proof",
                "context": "simulated transcript",
                "draft": "Unsent tmux draft",
                "items": [
                    {
                        "id": "a",
                        "kind": "assistant",
                        "text": "Short answer: 界 é 🦀 end."
                        if short
                        else "```text\nEARLY-TMUX-MARKER\n"
                        + "\n".join(f"native row {i:03d}" for i in range(150))
                        + "\n```",
                    }
                ],
                "system": [],
            }
        )
    )
    if case == "stream":
        data = json.loads(scene.read_text())
        data["items"] = []
        data["response"] = "EARLY-TMUX-MARKER\n\n" + "\n\n".join(
            f"native row {i:03d}" for i in range(150)
        )
        data["stream_interval_ms"] = 2
        scene.write_text(json.dumps(data))
    command = [
        str(ROOT / "frontends/ratatui/target/release/amplifier-ratatui"),
        "--host-json",
        json.dumps([sys.executable, "-m", "amplifier_tui.frontend_bridge", "--scene", str(scene)]),
    ]
    # Socket path is uniquely owned by this test, and the only external target.
    socket = str(tmp_path / "tmux.sock")
    manifest = ROOT.parent / "WORKSPACE-MANIFEST.json"

    def record(status):
        data = (
            json.loads(manifest.read_text())
            if manifest.exists()
            else {"version": 1, "resources": []}
        )
        entry = next((r for r in data["resources"] if r["id"] == socket), None)
        now = datetime.now(timezone.utc).isoformat()
        if entry is None:
            entry = {
                "kind": "tmux",
                "id": socket,
                "created_at": now,
                "note": "Isolated native scrollback test server; no user configuration",
                "teardown": f"tmux -S {socket} kill-server",
            }
            data["resources"].append(entry)
        entry["status"] = status
        if status == "reaped":
            entry["reaped_at"] = now
        manifest.write_text(json.dumps(data, indent=2) + "\n")

    def tmux(*args, check=True):
        return subprocess.run(
            ["tmux", "-S", socket, "-f", "/dev/null", *args],
            capture_output=True,
            text=True,
            check=check,
        ).stdout

    def wait(needle, *args):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            text = tmux(*args)
            if needle in text:
                return text
            time.sleep(0.02)
        raise AssertionError(f"Missing {needle}: {text}")

    wrapper = (
        "import subprocess; print('SHELL-BEFORE', flush=True); "
        + f"subprocess.run({command!r}); print('SHELL-AFTER', flush=True); input()"
    )
    tmux(
        "new-session",
        "-d",
        "-x",
        "120",
        "-y",
        "40",
        "-s",
        "copy-proof",
        sys.executable,
        "-c",
        wrapper,
    )
    record("active")
    try:
        if case == "stream":
            wait("Ready", "capture-pane", "-p")
            tmux("send-keys", "Enter")
            wait("native row 050", "capture-pane", "-p", "-S", "-")
            # Before finalization, completed blocks already belong to native history.
            assert int(tmux("display-message", "-p", "#{history_size}")) > 0
            wait("Completed", "capture-pane", "-p")
            tmux("send-keys", "-l", "Unsent tmux draft")
            wait("Unsent tmux draft", "capture-pane", "-p")
        marker = "Short answer:" if short else "native row 149"
        wait(marker, "capture-pane", "-p")
        assert tmux("display-message", "-p", "#{alternate_on}").strip() == "0"
        history = tmux("capture-pane", "-p", "-S", "-")
        if short:
            preview = tmux("capture-pane", "-e", "-p", "-S", "-30")
            assert "Short answer: 界 é 🦀 end." in "\n".join(preview.rstrip().splitlines()[-20:])
            tmux("send-keys", "C-q")
            exited = wait("SHELL-AFTER", "capture-pane", "-p", "-S", "-")
            assert exited.count(marker) == 1
            assert "[ Actions ]" not in exited
            return
        assert int(tmux("display-message", "-p", "#{history_size}")) > 100
        assert "EARLY-TMUX-MARKER" in history and "native row 149" in history
        attached = Probe(["tmux", "-S", socket, "attach-session", "-t", "copy-proof"], rows=41)
        try:
            attached.wait("Unsent tmux draft")
            tmux("copy-mode")
            assert tmux("display-message", "-p", "#{pane_in_mode}").strip() == "1"
            tmux("send-keys", "-X", "history-top")
            attached.wait("EARLY-TMUX-MARKER")
            tmux("send-keys", "-X", "begin-selection")
            tmux("send-keys", "-X", "history-bottom")
            tmux("send-keys", "-X", "copy-selection-and-cancel")
            copied = tmux("show-buffer")
            assert "EARLY-TMUX-MARKER" in copied and "native row 100" in copied
        finally:
            tmux("detach-client", "-s", "copy-proof", check=False)
            attached.close()
        # Actual fullscreen inspection must restore primary history without replay.
        tmux("send-keys", "F4")
        wait("Search:", "capture-pane", "-p")
        assert tmux("display-message", "-p", "#{alternate_on}").strip() == "1"
        tmux("send-keys", "Escape")
        wait("0", "display-message", "-p", "#{alternate_on}")
        restored = wait("[ Actions ]", "capture-pane", "-p")
        assert "Unsent tmux draft" in restored
        assert "Working" not in restored
        for width, height in [(60, 25), (160, 40), (80, 24), (120, 40)]:
            tmux("resize-window", "-x", str(width), "-y", str(height))
            wait("─" * (width - 12), "capture-pane", "-p")
            tmux("send-keys", "-l", "x")
            wait("draftx", "capture-pane", "-p")
            tmux("send-keys", "BSpace")
            wait("Unsent tmux draft", "capture-pane", "-p")
            history = tmux("capture-pane", "-p", "-S", "-")
            assert history.count("EARLY-TMUX-MARKER") == history.count("native row 149") == 1, (
                width,
                height,
                history[-2500:],
            )
        tmux("send-keys", "C-q")
        exited = wait("SHELL-AFTER", "capture-pane", "-p", "-S", "-")
        assert "SHELL-BEFORE" in exited
        assert exited.count("EARLY-TMUX-MARKER") == exited.count("native row 149") == 1
        for i in range(150):
            assert exited.count(f"native row {i:03d}") == 1
        assert "[ Actions ]" not in exited
    finally:
        tmux("kill-server", check=False)
        absent = subprocess.run(
            ["tmux", "-S", socket, "has-session"], capture_output=True
        ).returncode
        assert absent != 0
        record("reaped")

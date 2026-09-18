"""Actual isolated tmux copy-mode, never the user's server or configuration."""

import fcntl
import json
import os
import shutil
import struct
import subprocess
import sys
import termios
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


@pytest.mark.parametrize(
    "case,start_row",
    [("long", 1), ("short", 1), ("short", 20), ("short", 39), ("stream", 1), ("short-exit", 1)],
)
def test_primary_screen_reaches_real_tmux_history_and_copy_mode(tmp_path, case, start_row):
    short = case.startswith("short")
    edge_line = "EDGE-" + "x" * 111 + "-END"  # exactly 120 terminal columns
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
                        "text": "Short answer: 界 é 🦀 end.\n\n" + edge_line
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
        data["stream_interval_ms"] = 5
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

    def settled_draft(expected):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            screen = tmux("capture-pane", "-p")
            lines = screen.splitlines()
            headers = [i for i, line in enumerate(lines) if line.strip().startswith("Message ·")]
            if len(headers) == 1:
                start = headers[0] + 1
                end = next(
                    (i for i in range(start, len(lines)) if "[ Actions ]" in lines[i]), start
                )
                if "\n".join(line.strip() for line in lines[start:end]).strip() == expected:
                    # Capture-pane sees intermediate synchronized frames too.
                    time.sleep(0.04)
                    return
            time.sleep(0.02)
        raise AssertionError(f"Draft did not settle: {screen}")

    def sized_frame(width, height):
        # tmux changes its grid before the process receives SIGWINCH. Allow that
        # delivery before injecting the next edit; capture-pane can see mid-frames.
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            fd = os.open(
                tmux("display-message", "-p", "#{pane_tty}").strip(), os.O_RDONLY | os.O_NOCTTY
            )
            try:
                actual = struct.unpack("HHHH", fcntl.ioctl(fd, termios.TIOCGWINSZ, b"\0" * 8))[:2]
            finally:
                os.close(fd)
            lines = tmux("capture-pane", "-N", "-p").splitlines()
            headers = [line for line in lines if line.strip().startswith("Message ·")]
            if (
                actual == (height, width)
                and len(headers) == 1
                and headers[0].startswith("Message")
                and "[ Actions ]" in "\n".join(lines[-4:])
                and ("Enter send" in "\n".join(lines[-4:])) == (width >= 80)
            ):
                return
            time.sleep(0.02)
        raise AssertionError(f"No painted {width}x{height} frame: {lines!r}")

    wrapper = (
        "import subprocess; print('SHELL-BEFORE', flush=True); "
        + f"print('\\n' * {start_row - 1}, end='', flush=True); "
        + f"result = subprocess.run({command!r}); print('APP-EXIT', result.returncode, flush=True); print('SHELL-AFTER', flush=True); input()"
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
            assert "Completed" not in tmux("capture-pane", "-p")
            tmux("copy-mode")
            tmux("send-keys", "-X", "history-top")
            tmux("send-keys", "-X", "begin-selection")
            tmux("send-keys", "-X", "history-bottom")
            tmux("send-keys", "-X", "copy-selection-and-cancel")
            during_stream = tmux("show-buffer")
            assert "EARLY-TMUX-MARKER" in during_stream and "native row 040" in during_stream
            wait("Ready", "capture-pane", "-p")
            tmux("send-keys", "-l", "Unsent tmux draft")
            wait("Unsent tmux draft", "capture-pane", "-p")
        marker = "Short answer:" if short else "native row 149"
        wait(marker, "capture-pane", "-p")
        assert tmux("display-message", "-p", "#{alternate_on}").strip() == "0"
        history = tmux("capture-pane", "-p", "-S", "-")
        if short:
            preview = tmux("capture-pane", "-e", "-p", "-S", "-30")
            assert "Short answer: 界 é 🦀 end." in preview
            screen = tmux("capture-pane", "-p")
            assert edge_line in screen.splitlines()  # no gutter or lost last column
            assert "SHELL-BEFORE" not in screen
            assert screen.splitlines()[0].startswith("amplifier ·")
            assert "[ Actions ]" in screen.splitlines()[-2]
            tmux("send-keys", "C-j")
            tmux("send-keys", "-l", "Second copy line 界")
            tmux("send-keys", "C-j")
            tmux("send-keys", "-l", "Third copy line")
            wait("Third copy line", "capture-pane", "-p")
            # Real terminal-owned selection, not OSC52 or an app copy operation.
            tmux("copy-mode")
            tmux("send-keys", "-X", "history-top")
            tmux("send-keys", "-X", "begin-selection")
            tmux("send-keys", "-X", "history-bottom")
            tmux("send-keys", "-X", "copy-selection-and-cancel")
            copied = [line.rstrip() for line in tmux("show-buffer").splitlines()]
            assert copied.count(edge_line) == 1
            start = copied.index("Unsent tmux draft")
            assert copied[start : start + 3] == [
                "Unsent tmux draft",
                "Second copy line 界",
                "Third copy line",
            ]
            tmux("send-keys", "F4")
            wait("Search:", "capture-pane", "-p")
            tmux("resize-window", "-x", "80", "-y", "24")
            sized_frame(80, 24)
            if case == "short-exit":
                tmux("send-keys", "C-q")
                exited = wait("SHELL-AFTER", "capture-pane", "-p", "-S", "-")
                assert exited.count("SHELL-BEFORE") == exited.count(marker) == 1
                assert exited.count("EDGE-") == exited.count("-END") == 1
                assert "APP-EXIT 0" in exited and "[ Actions ]" not in exited
                return
            tmux("send-keys", "Escape")
            wait("0", "display-message", "-p", "#{alternate_on}")
            settled_draft("Unsent tmux draft\nSecond copy line 界\nThird copy line")
            retained = tmux("capture-pane", "-p", "-S", "-")
            assert retained.count(marker) == 1, retained
            for width, height in [(60, 25), (40, 20), (160, 40), (80, 24), (120, 40)]:
                tmux("resize-window", "-x", str(width), "-y", str(height))
                sized_frame(width, height)
                tmux("send-keys", "-l", "z")
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    current = tmux("capture-pane", "-p")
                    if (
                        "Third copy linez" in current
                        and "[ Actions ]" in "\n".join(current.splitlines()[-4:])
                        and current.count("Message ·") == 1
                    ):
                        break
                    time.sleep(0.02)
                tmux("send-keys", "BSpace")
                settled_draft("Unsent tmux draft\nSecond copy line 界\nThird copy line")
                assert current.count("Message ·") == 1
                assert "[ Actions ]" in "\n".join(current.splitlines()[-4:]), (
                    width,
                    height,
                    current,
                )
                retained = tmux("capture-pane", "-p", "-S", "-")
                assert retained.count("SHELL-BEFORE") == retained.count(marker) == 1
            tmux("send-keys", "C-q")
            exited = wait("SHELL-AFTER", "capture-pane", "-p", "-S", "-")
            assert exited.count("SHELL-BEFORE") == 1
            assert exited.count(marker) == 1
            assert exited.count("EDGE-") == exited.count("-END") == 1
            assert "[ Actions ]" not in exited
            assert "APP-EXIT 0" in exited
            return
        assert int(tmux("display-message", "-p", "#{history_size}")) > 100
        assert "EARLY-TMUX-MARKER" in history and "native row 149" in history
        attached = Probe(["tmux", "-S", socket, "attach-session", "-t", "copy-proof"], rows=41)
        try:
            attached.wait("Unsent tmux draft")
            tmux("copy-mode")
            assert tmux("display-message", "-p", "#{pane_in_mode}").strip() == "1"
            tmux("send-keys", "-X", "history-top")
            attached.wait("SHELL-BEFORE")
            tmux("send-keys", "-X", "begin-selection")
            tmux("send-keys", "-X", "page-down")
            attached.wait("EARLY-TMUX-MARKER")
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
            sized_frame(width, height)
            tmux("send-keys", "-l", "x" * width)
            # Open input has no side borders. Check one bottom-aligned live composer.
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                screen = tmux("capture-pane", "-p")
                composers = [
                    line for line in screen.splitlines() if line.strip().startswith("Message ·")
                ]
                if (
                    composers
                    and composers[-1].startswith("Message")
                    and "[ Actions ]" in screen.splitlines()[-2]
                    and any(
                        len(line) == width and "xxxxxxxx" in line for line in screen.splitlines()
                    )
                    and len(composers) == 1
                ):
                    break
                time.sleep(0.02)
            else:
                raise AssertionError(f"Composer did not fill {width}x{height}: {screen}")
            assert len(composers) == 1, f"Stale live chrome after resize: {screen}"
            tmux("send-keys", "-N", str(width), "BSpace")
            settled_draft("Unsent tmux draft")
            history = tmux("capture-pane", "-p", "-S", "-")
            assert history.count("SHELL-BEFORE") == 1, (width, height, history)
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
        assert "APP-EXIT 0" in exited
    finally:
        tmux("kill-server", check=False)
        absent = subprocess.run(
            ["tmux", "-S", socket, "has-session"], capture_output=True
        ).returncode
        assert absent != 0
        record("reaped")

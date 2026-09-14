"""Linux PTY smoke: real CLI/driver, bracketed paste, turn and terminal restoration."""

import errno
import json
import os
import select
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Linux PTY smoke")


@pytest.mark.parametrize("startup_failure", [False, True])
def test_real_terminal_restores_modes_and_leaves_alternate_screen(tmp_path, startup_failure):
    import fcntl
    import pty
    import struct
    import termios

    workspace = Path(
        os.environ.get("AMPLIFIER_TUI_SOURCE_ROOT", Path(__file__).resolve().parents[2])
    )
    mapping = tmp_path / "sources.json"
    mapping.write_text(
        json.dumps(
            {
                f"https://github.com/microsoft/{name}": str(workspace / name)
                for name in ("amplifier-module-loop-streaming", "amplifier-module-context-simple")
            }
        )
    )
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 36, 100, 0, 0))
    original = termios.tcgetattr(slave)
    command = [
        sys.executable,
        "-m",
        "amplifier_tui",
        "--fixture",
        "--no-install",
        "--sources",
        str(mapping),
        "--state-dir",
        str(tmp_path / "state"),
    ]
    if startup_failure:
        command.extend(["--require-tool", "missing-tool"])
    process = subprocess.Popen(
        command,
        stdin=slave,
        stdout=slave,
        stderr=slave,
        env={**os.environ, "TERM": "xterm-256color", "PYTHONDONTWRITEBYTECODE": "1"},
    )
    output = bytearray()

    def read_until(needle):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if needle in output:
                return
            if select.select([master], [], [], 0.05)[0]:
                try:
                    output.extend(os.read(master, 65536))
                except OSError as exc:
                    if exc.errno != errno.EIO:
                        raise
                    break
        raise AssertionError(f"Terminal did not emit {needle!r}; tail: {bytes(output[-1500:])!r}")

    try:
        read_until(b"Startup failed" if startup_failure else b"Ready.")
        if not startup_failure:
            os.write(master, b"\x1b[200~PTY task\nsecond line\x1b[201~")
            read_until(b"second line")
            os.write(master, b"\x13")  # Ctrl+S, not Enter
            read_until(b"evidence.")
        os.write(master, b"\x11")  # Ctrl+Q
        process.wait(timeout=10)
        read_until(b"\x1b[?1049l")
        assert process.returncode == 0
        assert termios.tcgetattr(slave) == original
        assert b"\x1b[?1049h" in output
        assert b"\x1b[?2004l" in output
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        os.close(master)
        os.close(slave)

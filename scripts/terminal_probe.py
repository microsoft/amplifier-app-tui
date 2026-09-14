"""Low-overhead Linux PTY observer for tests and measured candidate comparisons.

Unlike the screenshot helper this never adds a fixed settling delay. Measures
end at parsed terminal output, not a GPU paint or the app's render callback.
"""

import codecs
import copy
import fcntl
import json
import os
import pty
import re
import select
import signal
import struct
import subprocess
import termios
import time
from datetime import datetime, timezone
from pathlib import Path

import pyte

ROOT = Path(__file__).resolve().parents[1]


def record(pid, status):
    path = ROOT.parent / "WORKSPACE-MANIFEST.json"
    data = json.loads(path.read_text()) if path.exists() else {"version": 1, "resources": []}
    now = datetime.now(timezone.utc).isoformat()
    identity = f"probe-pty-{pid}"
    entry = next((e for e in data["resources"] if e["id"] == identity), None)
    if entry is None:
        entry = {
            "kind": "pty",
            "id": identity,
            "pid": pid,
            "created_at": now,
            "note": "Isolated PTY probe process group",
            "teardown": f"kill -TERM -- -{pid}",
        }
        data["resources"].append(entry)
    entry["status"] = status
    if status == "reaped":
        entry["reaped_at"] = now
    path.write_text(json.dumps(data, indent=2) + "\n")


class Screen(pyte.Screen):
    """Model DEC alternate-screen save/restore; pyte's base Screen ignores 1049.

    This is an observer adapter, not proof of real terminal scrollback. That gate
    uses an independently attached tmux server.
    """

    primary = None

    def set_mode(self, *modes, **kwargs):
        if kwargs.get("private") and 1049 in modes and self.primary is None:
            self.primary = (copy.deepcopy(self.buffer), copy.deepcopy(self.cursor))
            self.erase_in_display(2)
            self.cursor_position()
        super().set_mode(*modes, **kwargs)

    def reset_mode(self, *modes, **kwargs):
        if kwargs.get("private") and 1049 in modes and self.primary is not None:
            self.buffer, self.cursor = self.primary
            self.primary = None
            self.dirty.update(range(self.lines))
        super().reset_mode(*modes, **kwargs)


class Probe:
    def __init__(self, command, cols=120, rows=40, env=None, alternate_screen=True, cwd=None):
        self.alternate_screen = alternate_screen
        self.cols, self.rows = cols, rows
        self.master, self.slave = pty.openpty()
        fcntl.ioctl(self.slave, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
        self.original = termios.tcgetattr(self.slave)
        self.screen = Screen(cols, rows)
        self.stream = pyte.Stream(self.screen)
        self.screen.write_process_input = lambda value: os.write(self.master, value.encode())
        self.decoder = codecs.getincrementaldecoder("utf-8")("replace")
        environment = {
            **os.environ,
            "TERM": "xterm-256color",
            "COLORTERM": "truecolor",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        environment.pop("NO_COLOR", None)
        environment.update(env or {})

        def controlling_terminal():
            os.setsid()
            fcntl.ioctl(self.slave, termios.TIOCSCTTY, 0)

        self.start = time.monotonic_ns()
        self.process = subprocess.Popen(
            command,
            stdin=self.slave,
            stdout=self.slave,
            stderr=self.slave,
            preexec_fn=controlling_terminal,
            env=environment,
            cwd=cwd or ROOT,
        )
        record(self.process.pid, "active")
        self.bytes = 0
        self.raw = bytearray()
        self.visible_deltas = {}
        self.observer_ns = []
        self.peak_rss_kib = 0

    @property
    def text(self):
        return "\n".join(self.screen.display)

    def read(self, timeout=0.01):
        if not select.select([self.master], [], [], timeout)[0]:
            return
        try:
            data = os.read(self.master, 65536)
        except OSError:
            return
        before = time.monotonic_ns()
        self.bytes += len(data)
        self.raw.extend(data)
        self.stream.feed(self.decoder.decode(data))
        now = time.monotonic_ns()
        self.observer_ns.append(now - before)
        for token in re.findall(r"delta-\d+(?=\s)", self.text):
            self.visible_deltas.setdefault(token, now)

    def wait(self, text, timeout=15, absent=False):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if (text in self.text) != absent:
                return time.monotonic_ns()
            self.read()
        raise AssertionError(f"Terminal did not reach {text!r}\n{self.text}")

    def send(self, data):
        start = time.monotonic_ns()
        os.write(self.master, data)
        return start

    def resize(self, cols, rows):
        self.cols, self.rows = cols, rows
        self.screen.resize(lines=rows, columns=cols)
        fcntl.ioctl(self.slave, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))

    def rss(self):
        try:
            status = Path(f"/proc/{self.process.pid}/status").read_text()
            match = re.search(r"^VmRSS:\s+(\d+)", status, re.M)
            if match:
                self.peak_rss_kib = max(self.peak_rss_kib, int(match[1]))
        except FileNotFoundError:
            pass
        return self.peak_rss_kib

    def close(self):
        try:
            if self.process.poll() is None:
                self.send(b"\x11" if self.alternate_screen else b"\x04")
            end = time.monotonic() + 4
            while self.process.poll() is None and time.monotonic() < end:
                self.read()
            if self.process.poll() is None:
                raise AssertionError("Terminal did not quit within 4 seconds")
            for _ in range(5):
                self.read(0)
            assert self.process.returncode == 0, self.text
            assert termios.tcgetattr(self.slave) == self.original, (
                "Terminal modes were not restored"
            )
            if self.alternate_screen and b"\x1b[?1049h" in self.raw:
                assert b"\x1b[?1049l" in self.raw, "Alternate screen was not released"
        finally:
            # Targets only the independently created process group, never user sessions.
            try:
                os.killpg(self.process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait()
            os.close(self.master)
            os.close(self.slave)
            record(self.process.pid, "reaped")

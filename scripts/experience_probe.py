"""Interactive journey driver over the real native terminal; receipts stay private.

This is an observer, not an execution adapter. Tests and exploratory sessions use
the same send/observe/capture steps, without bypassing the UI to mutate host state.
"""

import hashlib
import json
import time
from pathlib import Path

from interaction_probe import capture
from terminal_probe import Probe


class Journey:
    def __init__(self, command, directory, *, cols=175, rows=50, env=None, cwd=None):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.receipt = self.directory / "steps.jsonl"
        if self.receipt.exists():
            raise ValueError("Use a new journey directory; never overwrite failed evidence")
        self.started = time.monotonic()
        self.probe = Probe(command, cols=cols, rows=rows, env=env, cwd=cwd)
        self.record("launch", columns=cols, rows=rows, executable=str(command[0]))

    def record(self, step, **data):
        with self.receipt.open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps({"step": step, "elapsed": time.monotonic() - self.started, **data})
                + "\n"
            )
        self.receipt.chmod(0o600)

    def send(self, data, *, label="input"):
        self.probe.send(data)
        # Do not duplicate prompts or authentication material into step receipts.
        self.record(label, bytes=len(data))

    def observe(self, expected, *, timeout=30, absent=False):
        try:
            self.probe.wait(expected, timeout=timeout, absent=absent)
        except Exception:
            self.record("observation-failed", expected=expected, absent=absent)
            raise
        self.record("observed", expected=expected, absent=absent)

    def screenshot(self, name):
        if not name.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Use a filename label, not a path")
        path = capture(self.probe, name)
        self.record("capture", name=name, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        return path

    def resize(self, cols, rows):
        self.probe.resize(cols, rows)
        self.record("resize", columns=cols, rows=rows)

    def close(self):
        try:
            self.probe.close()
        except Exception:
            self.record("cleanup-failed")
            raise
        self.record("closed", terminal_restored=True)

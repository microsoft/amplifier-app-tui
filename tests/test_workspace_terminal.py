"""Read-only native workspace inspection over a real temporary Git repository."""

import base64
import os
import re
import sys
from pathlib import Path

import pytest
from test_workspace_review import repository  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from interaction_probe import action, capture  # noqa: E402
from terminal_probe import Probe  # noqa: E402
from test_reading_terminal import draft_is  # noqa: E402

pytestmark = pytest.mark.skipif(
    os.environ.get("TUI_TEST_CANDIDATES") != "1", reason="Build Ratatui"
)


def test_native_workspace_diffs_copy_and_no_execution(tmp_path, repository):  # noqa: F811
    before = (repository / ".git/index").read_bytes()
    probe = Probe(
        [
            sys.executable,
            str(ROOT / "scripts/run.py"),
            "--fixture",
            "--no-install",
            "--cwd",
            str(repository),
            "--state-dir",
            str(tmp_path / "state"),
        ],
        cols=160,
    )
    try:
        probe.wait("Ready")
        probe.send(b"Keep unsent scratch")
        action(probe, "Workspace changes", "Workspace changes · observed")
        probe.wait("staged · MM · file.txt")
        probe.wait("unstaged · MM · file.txt")
        capture(probe, "workspace-changes")
        probe.send("staged · MM".encode())
        # Both staged and unstaged match this substring; the staged row is first.
        probe.send(b"\r")
        probe.wait("Workspace diff · read-only")
        probe.wait("HEAD → index")
        probe.wait("+staged")
        capture(probe, "workspace-staged")
        probe.send(b"Copy observed\r")
        probe.wait("Source copied")
        copies = re.findall(rb"\x1b\]52;c;([^\x07]*)\x07", probe.raw)
        copied = base64.b64decode(copies[-1]).decode()
        assert "-base" in copied and "+staged" in copied
        draft_is(probe, "Keep unsent scratch")
        action(probe, "Workspace changes", "Workspace changes · observed")
        probe.send(b"unstaged\r")
        probe.wait("index → working tree")
        probe.wait("+working")
        probe.send(b"\x1b")
        action(probe, "Workspace changes", "Workspace changes · observed")
        probe.send(b"untracked\r")
        probe.wait("contents are not read")
        assert "private untracked content" not in probe.text
        probe.send(b"\x1b")
        draft_is(probe, "Keep unsent scratch")
        path = next((tmp_path / "state/conversations").glob("*/events.jsonl"))
        assert "turn.accepted" not in path.read_text()
        assert (repository / ".git/index").read_bytes() == before
    finally:
        probe.close()

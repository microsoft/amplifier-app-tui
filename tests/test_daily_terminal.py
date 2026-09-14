"""Actual keyboard workflows over the native client and real fixture runtime."""

import json
import os
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from interaction_probe import capture  # noqa: E402
from questions_probe import wait_ready  # noqa: E402
from terminal_probe import Probe  # noqa: E402
from test_navigation_terminal import start  # noqa: E402
from test_questions_terminal import start as questions_start  # noqa: E402
from test_reading_terminal import draft_is  # noqa: E402
from test_structured_reading_terminal import copied  # noqa: E402

pytestmark = pytest.mark.skipif(
    os.environ.get("TUI_TEST_CANDIDATES") != "1", reason="Build native client"
)


def action(probe, query, expected):
    probe.send(b"\x1bOS")  # F4: keyboard path on the mouse-owned native terminal.
    probe.wait("Search:")
    probe.send(query.encode() + b"\r")
    probe.wait(expected)


def dismiss(probe, title):
    probe.send(b"\x1b")
    probe.wait(title, absent=True)


def test_file_preview_insertion_and_observed_activity(tmp_path):
    (tmp_path / "notes.md").write_text("Snapshot violet")
    probe = start(tmp_path)
    try:
        wait_ready(probe)
        probe.send(b"My draft")
        action(probe, "Insert text file", "Workspace-relative")
        probe.send(b"notes.md\r")
        probe.wait("preview before inserting")
        (tmp_path / "notes.md").write_text("Changed after preview")
        capture(probe, "daily-file-preview")
        probe.send(b"\r")
        draft_is(probe, "Snapshot violet")
        assert "Changed after preview" not in probe.text
        probe.send(b"\r")
        probe.wait("Completed")
        action(probe, "Activity evidence", "Activity evidence · identified")
        probe.send(b"fixture_probe\r")
        probe.wait("Observed evidence")
        probe.wait("sha256")
        capture(probe, "daily-activity")
        dismiss(probe, "Observed evidence")
        action(probe, "Context intelligence", "Context intelligence · observed")
        probe.wait("means unavailable, not zero")
        capture(probe, "daily-context")
    finally:
        probe.close()


def test_answer_draft_autosaves_and_recovery_is_copy_only(tmp_path):
    probe = questions_start(tmp_path)
    try:
        wait_ready(probe)
        probe.send(b"Ask me\r")
        probe.wait("Answer questions")
        action(probe, "Questions —", "Questions · clarification")
        probe.send(b"\r")
        probe.wait("Questions · review")
        probe.send(b"keep in mind\r")
        probe.wait("Write my own answer")
        probe.send(b"\r")
        probe.wait("Enter review")
        probe.send("Unsent 界 answer".encode())
        source = next((tmp_path / "state/conversations").iterdir())
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            probe.read(0.05)
            path = source / "editors.json"
            if path.exists() and "Unsent 界 answer" in path.read_text():
                break
        assert "Unsent 界 answer" in path.read_text()
        capture(probe, "daily-unsent-answer")
    finally:
        probe.close()
    original = {p.name: p.read_bytes() for p in source.iterdir() if p.is_file()}
    probe = Probe(
        [
            sys.executable,
            str(ROOT / "scripts/run.py"),
            "--recover",
            source.name,
            "--no-install",
            "--state-dir",
            str(tmp_path / "state"),
        ],
        cols=160,
    )
    try:
        wait_ready(probe)
        action(probe, "Saved local drafts", "Saved local drafts · never")
        probe.send(b"\r")
        probe.wait("historical intent")
        probe.send(b"\r")
        assert copied(probe) == "Unsent 界 answer"
        capture(probe, "daily-recovered-draft")
        assert original == {p.name: p.read_bytes() for p in source.iterdir() if p.is_file()}
        for path in (tmp_path / "state/conversations").glob("*/events.jsonl"):
            assert not any(
                json.loads(line)["kind"] == "question.updated"
                and json.loads(line)["payload"]["status"] == "answered"
                for line in path.read_text().splitlines()
            )
    finally:
        probe.close()


@pytest.mark.parametrize("success", [True, False])
def test_external_editor_preserves_native_transcript_and_never_submits(tmp_path, success):
    script = tmp_path / "editor.py"
    script.write_text(
        "import pathlib,sys\np=pathlib.Path(sys.argv[1])\np.write_text('Edited in external editor')\n"
        + ("" if success else "sys.exit(2)\n")
    )
    probe = Probe(
        [
            sys.executable,
            str(ROOT / "scripts/run.py"),
            "--fixture",
            "--no-install",
            "--state-dir",
            str(tmp_path / "state"),
        ],
        env={"VISUAL": f"{sys.executable} {script}"},
    )
    try:
        wait_ready(probe)
        probe.send(b"Keep original")
        action(
            probe,
            "Edit in external editor",
            "Editor returned" if success else "original draft retained",
        )
        draft_is(probe, "Edited in external editor" if success else "Keep original")
        for path in (tmp_path / "state/conversations").glob("*/events.jsonl"):
            assert not any(
                json.loads(line)["kind"] == "turn.accepted"
                for line in path.read_text().splitlines()
            )
        capture(probe, "daily-editor-success" if success else "daily-editor-failure")
    finally:
        probe.close()

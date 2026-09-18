"""Native questions through a normally composed tool and real Amplifier loop."""

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from interaction_probe import action, capture, click  # noqa: E402
from terminal_probe import Probe  # noqa: E402
from test_reading_terminal import draft_is  # noqa: E402
from test_workflow_terminal import events  # noqa: E402

pytestmark = pytest.mark.skipif(
    os.environ.get("TUI_TEST_CANDIDATES") != "1", reason="Build Ratatui"
)


def start(tmp_path):
    return Probe(
        [
            sys.executable,
            str(ROOT / "scripts/run.py"),
            "--fixture",
            "--no-install",
            "--overlay",
            str(ROOT / "examples/fixture-questions.yaml"),
            "--state-dir",
            str(tmp_path / "state"),
        ],
        cols=160,
    )


def test_native_questions_review_dismiss_free_text_and_resume(tmp_path):
    probe = start(tmp_path)
    try:
        probe.wait("Ready")
        probe.send(b"Ask for my preferences\r")
        probe.wait("[ Queue ]")
        probe.send(b"Keep main draft")
        probe.wait("[ Answer questions 1 ]")
        draft_is(probe, "Keep main draft")
        click(probe, "[ Answer questions 1 ]")
        probe.wait("Questions · clarification")
        probe.send(b"\r")
        probe.wait("Questions · review answers")
        probe.send(b"Which scope\r")
        probe.wait("Question · choose")
        probe.send(b"Small slice\r")
        probe.wait("Answer: Small slice")
        assert [
            e["payload"]["status"] for e in events(tmp_path) if e["kind"] == "question.updated"
        ] == ["waiting"]
        probe.send(b"\x1b")
        draft_is(probe, "Keep main draft")
        action(probe, "Questions —", "Questions · clarification")
        probe.send(b"\r")
        probe.wait("Answer: Small slice")
        probe.send(b"keep in mind\r")
        probe.wait("Write my own answer")
        probe.send(b"\r")
        probe.wait("Enter review")
        probe.send(b"\x1b[200~Preserve my work\nUse a narrow test\x1b[201~")
        probe.wait("Use a narrow test")
        probe.send(b"\x1b")
        draft_is(probe, "Keep main draft")
        action(probe, "Questions —", "Questions · clarification")
        probe.send(b"\r")
        probe.wait("Answer: Preserve my work")
        probe.wait("Submit reviewed answers")
        capture(probe, "questions-review")
        assert not any(
            e["payload"]["status"] == "answered"
            for e in events(tmp_path)
            if e["kind"] == "question.updated"
        )
        probe.send(b"Submit reviewed\r")
        probe.wait_idle()
        draft_is(probe, "Keep main draft")
        rows = [e for e in events(tmp_path) if e["kind"] == "question.updated"]
        assert [e["payload"]["status"] for e in rows] == ["waiting", "answered"]
        assert (
            rows[-1]["payload"]["answers"]["notes"]["text"] == "Preserve my work\nUse a narrow test"
        )
        assert len([e for e in events(tmp_path) if e["kind"] == "turn.accepted"]) == 1
        capture(probe, "questions-completed")
        action(probe, "Questions —", "Questions · clarification")
        probe.send(b"\r")
        probe.wait("Message · retained source preview")
        probe.wait("Answer: Small slice")
        probe.send(b"\x1b")
        identity = next((tmp_path / "state/conversations").iterdir()).name
    finally:
        probe.close()
    restored = Probe(
        [
            sys.executable,
            str(ROOT / "scripts/run.py"),
            "--resume",
            identity,
            "--no-install",
            "--state-dir",
            str(tmp_path / "state"),
        ],
        cols=160,
    )
    try:
        restored.wait("Ready")
        draft_is(restored, "Keep main draft")
        assert "[ Answer questions" not in restored.text
        action(restored, "Questions —", "Questions · clarification")
        restored.send(b"\r")
        restored.wait("Answer: Small slice")
        assert len([e for e in events(tmp_path) if e["kind"] == "turn.accepted"]) == 1
    finally:
        restored.close()


@pytest.mark.parametrize("stop", [False, True])
def test_native_question_cancel_or_stop_does_not_answer(tmp_path, stop):
    probe = start(tmp_path)
    try:
        probe.wait("Ready")
        probe.send(b"Ask\r")
        probe.wait("[ Answer questions 1 ]")
        probe.send(b"Unsent draft")
        if stop:
            click(probe, "[ Stop ]")
            probe.wait("Interrupted")
        else:
            action(probe, "Questions —", "Questions · clarification")
            probe.send(b"\r")
            probe.wait("Cancel this question")
            probe.send(b"Cancel this\r")
            probe.wait_idle()
        draft_is(probe, "Unsent draft")
        rows = [e for e in events(tmp_path) if e["kind"] == "question.updated"]
        assert rows[-1]["payload"]["status"] == ("stopped" if stop else "cancelled")
        assert rows[-1]["payload"]["answers"] is None
        assert "[ Answer questions" not in probe.text
    finally:
        probe.close()

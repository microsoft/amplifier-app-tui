"""Real native input/layout; scene projections are explicitly not live execution."""

import json
import os
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from experience_probe import Journey  # noqa: E402

pytestmark = pytest.mark.skipif(
    os.environ.get("TUI_TEST_CANDIDATES") != "1", reason="Build native client"
)
SIZES = [(175, 50), (120, 35), (80, 24), (60, 24), (40, 20), (175, 25), (240, 65), (32, 12)]


@pytest.mark.parametrize("cols,rows", SIZES)
def test_waiting_question_keeps_draft_and_choice_reachable(tmp_path, cols, rows):
    from interaction_probe import action
    from questions_probe import wait_ready
    from test_questions_terminal import start as questions_start
    from test_workflow_terminal import events

    p = questions_start(tmp_path)
    try:
        wait_ready(p)
        p.send(b"Ask for my preferences\r")
        p.wait("[ Answer questions 1 ]")
        p.send(b"\x1b[200~Keep this draft\x1b[201~")
        p.wait("Keep this draft")
        p.resize(cols, rows)
        settle(p)
        action(p, "Questions —", "Questions · clarification")
        p.send(b"\r")
        p.wait("Questions · review answers")
        p.send(b"Which scope\r")
        p.wait("Question · choose")
        p.send(b"Small slice")
        p.wait("Small slice")
        # Resize while a decision owns focus; the selected answer is not submitted.
        p.resize(32, 12)
        settle(p)
        p.send(b"\r")
        p.wait("Questions · review answers")
        for _ in range(12):
            if "Answer: Small slice" in p.text:
                break
            p.send(b"\x1b[6~")
            settle(p)
        p.wait("Answer: Small slice")
        from interaction_probe import capture

        capture(p, f"experience-question-{cols}x{rows}-shrunk")
        p.send(b"\x1b")
        p.wait("Actions / choices", absent=True)
        p.resize(cols, rows)
        settle(p)
        p.wait("Keep this draft")
        assert sum(e["kind"] == "turn.accepted" for e in events(tmp_path)) == 1
        assert not any(
            e["kind"] == "question.updated" and e["payload"]["status"] == "answered"
            for e in events(tmp_path)
        )
    finally:
        p.close()


def settle(probe):
    deadline = time.monotonic() + 0.12
    while time.monotonic() < deadline:
        probe.read(0.01)


def start(tmp_path, cols, rows, theme="dark"):
    scene = tmp_path / "scene.json"
    scene.write_text(
        json.dumps(
            {
                "title": "Quarterly summary",
                "context": "SIMULATED layout review",
                "draft": "",
                "items": [
                    {
                        "id": "u",
                        "kind": "user",
                        "text": "Compare the two proposals and explain the trade-offs.",
                    },
                    {
                        "id": "a",
                        "kind": "assistant",
                        "text": "## Recommendation\n\nChoose **Option B** for lower ongoing effort.\n\n| Choice | Setup | Support |\n|---|---|---|\n| A | Quick | Manual |\n| B | Moderate | Automated |\n\n```python\ndef summarize(rows):\n    return sum(row.amount for row in rows)\n```\n\nThe failed check below still needs attention.",
                    },
                    {
                        "id": "t",
                        "kind": "tool",
                        "text": "run_checks\nExpected 12, observed 10\nInspect the source before continuing.",
                        "status": "failed",
                        "detail": "EXACT-EVIDENCE-MARKER",
                    },
                ],
                "system": [],
            }
        )
    )
    env = {"AMPLIFIER_TUI_THEME": theme}
    if theme == "plain":
        env["NO_COLOR"] = "1"
    return Journey(
        [
            str(ROOT / "frontends/ratatui/target/release/amplifier-ratatui"),
            "--host-json",
            json.dumps(
                [sys.executable, "-m", "amplifier_tui.frontend_bridge", "--scene", str(scene)]
            ),
        ],
        tmp_path / "journey",
        cols=cols,
        rows=rows,
        env=env,
    )


@pytest.mark.parametrize("cols,rows", SIZES)
def test_task_actions_resize_and_copy_friendly_draft(tmp_path, cols, rows):
    journey = start(tmp_path, cols, rows)
    p = journey.probe
    try:
        journey.observe("Ready")
        journey.send(b"\x1b[200~Copy this draft\x1b[201~")
        journey.observe("Copy this draft")
        settle(p)
        line = next(row for row in p.screen.display if "Copy this draft" in row)
        assert line.startswith("Copy this draft")
        journey.screenshot(f"experience-work-{cols}x{rows}")
        journey.send(b"\x1bOS")
        journey.observe("Search:")
        # Task groups are discoverable without memorized search labels.
        if rows >= 20:
            journey.observe("Current task")
        journey.send(b"\x1b[B\r")  # first group: Write and attach
        journey.observe("Write and attach")
        journey.send(b"\x1b")
        journey.observe("Actions / choices", absent=True)
        journey.observe("Copy this draft")
        journey.resize(32, 12)
        settle(p)
        journey.send(b"\x1bOS")
        journey.observe("Search:")
        journey.send(b"Getting started\r")
        journey.observe("Getting started")
        journey.screenshot(f"experience-short-menu-from-{cols}x{rows}")
        journey.send(b"\x1b")
        journey.observe("Actions / choices", absent=True)
        journey.resize(cols, rows)
        journey.observe("Copy this draft")
        assert b"\x1b[3J" not in p.raw
    finally:
        journey.close()


@pytest.mark.parametrize("theme", ["dark", "light", "terminal", "plain"])
def test_theme_retains_content_and_visible_focus(tmp_path, theme):
    journey = start(tmp_path, 175, 50, theme)
    p = journey.probe
    try:
        journey.observe("Ready")
        journey.observe("failed")
        journey.screenshot(f"experience-theme-{theme}")
        journey.send(b"\x1bOS")
        journey.observe("Getting started")
        settle(p)
        assert any("› Getting started" in row for row in p.screen.display)
        journey.screenshot(f"experience-actions-{theme}")
    finally:
        journey.close()

"""Native session operations at laptop and narrow sizes; scripted provider only."""

import json
import os
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from interaction_probe import action, capture  # noqa: E402
from terminal_probe import Probe  # noqa: E402
from test_reading_terminal import draft_is  # noqa: E402

pytestmark = pytest.mark.skipif(
    os.environ.get("TUI_TEST_CANDIDATES") != "1", reason="Build Ratatui"
)


def paste(probe, text):
    probe.send(b"\x1b[200~" + text.encode() + b"\x1b[201~")
    draft_is(probe, text)
    probe.send(b"\r")


def until(probe, predicate):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        probe.read(0.02)
        if predicate():
            return
    pytest.fail("Session operation did not reach its expected state")


def completed(probe, path, count):
    def finished():
        events = [json.loads(line) for line in (path / "events.jsonl").read_text().splitlines()]
        return (
            sum(e["kind"] == "turn.ended" for e in events) == count
            and probe.text.splitlines()[-1].strip() == "Ready"
        )

    until(probe, finished)


@pytest.mark.parametrize("cols,rows", [(175, 50), (40, 20)])
def test_context_clear_default_no_keeps_draft_history_and_exports(tmp_path, cols, rows):
    state = tmp_path / "state"
    probe = Probe(
        [
            sys.executable,
            str(ROOT / "scripts/run.py"),
            "--fixture",
            "--no-install",
            "--state-dir",
            str(state),
        ],
        cols=cols,
        rows=rows,
    )
    try:
        probe.wait("Ready")
        path = next((state / "conversations").iterdir())
        paste(probe, "Synthetic history before clearing")
        completed(probe, path, 1)
        before = json.loads((path / "checkpoint.json").read_text())["messages"]
        assert before
        probe.send(b"Retained draft while clearing")
        draft_is(probe, "Retained draft while clearing")
        action(probe, "Clear context and goal", "Clear context and goal?")
        capture(probe, f"session-clear-confirm-{cols}")
        probe.send(b"\r")  # Default No.
        probe.wait("Clear context and goal?", absent=True)
        assert json.loads((path / "checkpoint.json").read_text())["messages"] == before
        draft_is(probe, "Retained draft while clearing")
        action(probe, "Clear context and goal", "Clear context and goal?")
        probe.send(b"\x1b[B\r")
        until(probe, lambda: json.loads((path / "checkpoint.json").read_text())["messages"] == [])
        draft_is(probe, "Retained draft while clearing")
        assert list((path / "context-clears").glob("*.json"))
        action(probe, "Export structured", "Private transcript saved")
        output = next((state / "exports").glob("*.json"))
        assert "Synthetic history before clearing" in output.read_text()
        draft_is(probe, "Retained draft while clearing")
        capture(probe, f"session-cleared-export-{cols}")
    finally:
        probe.close()


@pytest.mark.parametrize("cols,rows", [(175, 50), (40, 20)])
def test_turn_branch_requires_confirmation_and_preserves_source(tmp_path, cols, rows):
    state = tmp_path / "state"
    probe = Probe(
        [
            sys.executable,
            str(ROOT / "scripts/run.py"),
            "--fixture",
            "--no-install",
            "--state-dir",
            str(state),
        ],
        cols=cols,
        rows=rows,
    )
    try:
        probe.wait("Ready")
        source = next((state / "conversations").iterdir())
        paste(probe, "Synthetic first branch turn")
        completed(probe, source, 1)
        first = json.loads((source / "checkpoint.json").read_text())["messages"]
        paste(probe, "Synthetic second branch turn")
        until(
            probe,
            lambda: (
                len(json.loads((source / "checkpoint.json").read_text())["messages"]) > len(first)
            ),
        )
        completed(probe, source, 2)
        paste(probe, "/fork 1 Synthetic branch")
        probe.wait("Branch through turn 1?")
        capture(probe, f"session-branch-confirm-{cols}")
        probe.send(b"\r")  # Default No.
        probe.wait("Branch through turn 1?", absent=True)
        assert len(list((state / "conversations").iterdir())) == 1
        paste(probe, "/fork 1 Synthetic branch")
        probe.wait("Branch through turn 1?")
        probe.send(b"\x1b[B\r")
        until(probe, lambda: len(list((state / "conversations").iterdir())) == 2)
        probe.wait("Public-context branch")
        probe.wait("Ready")
        branch = next(p for p in (state / "conversations").iterdir() if p != source)
        messages = json.loads((branch / "checkpoint.json").read_text())["messages"]
        assert "Synthetic first branch turn" in str(messages)
        assert "Synthetic second branch turn" not in str(messages)
        journal = [json.loads(line) for line in (branch / "events.jsonl").read_text().splitlines()]
        assert not any(e["kind"] in ("turn.accepted", "tool.started") for e in journal)
        assert json.loads((branch / "metadata.json").read_text())["title"] == "Synthetic branch"
        capture(probe, f"session-branched-{cols}")
    finally:
        probe.close()


@pytest.mark.parametrize("cols,rows", [(175, 50), (40, 20)])
def test_direct_tool_has_native_approval_and_observed_result(tmp_path, cols, rows):
    state = tmp_path / "state"
    overlay = tmp_path / "approval.yaml"
    overlay.write_text(
        json.dumps(
            {
                "bundle": {"name": "synthetic-direct-approval"},
                "tools": [{"module": "tool-fixture", "config": {"approval": True}}],
            }
        )
    )
    probe = Probe(
        [
            sys.executable,
            str(ROOT / "scripts/run.py"),
            "--fixture",
            "--no-install",
            "--overlay",
            str(overlay),
            "--state-dir",
            str(state),
        ],
        cols=cols,
        rows=rows,
    )
    try:
        probe.wait("Ready")
        path = next((state / "conversations").iterdir())
        command = '/tool invoke fixture_probe {"text":"synthetic native direct"}'
        probe.send(b"\x1b[200~" + command.encode() + b"\x1b[201~")
        until(probe, lambda: json.loads((path / "draft.json").read_text())["text"] == command)
        probe.wait("/tool invoke fixture_probe")
        probe.send(b"\r")
        probe.wait("Compute the fixture digest?")
        capture(probe, f"session-direct-approval-{cols}")
        action(probe, "Decisions", "Options (exact runtime scope)")
        probe.send(b"allow\r")
        completed(probe, path, 1)
        probe.wait("Direct tool")
        journal = [json.loads(line) for line in (path / "events.jsonl").read_text().splitlines()]
        assert any(
            e["kind"] == "tool.updated" and e["payload"].get("status") == "succeeded"
            for e in journal
        )
        assert not any(e["payload"].get("usage_call") for e in journal)
        capture(probe, f"session-direct-complete-{cols}")
    finally:
        probe.close()

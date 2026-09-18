"""Native workflow checks; actual modules, no provider credential required."""

import base64
import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from interaction_probe import action, capture, click  # noqa: E402
from terminal_probe import Probe  # noqa: E402
from test_reading_terminal import draft_is, scene  # noqa: E402

pytestmark = pytest.mark.skipif(
    os.environ.get("TUI_TEST_CANDIDATES") != "1", reason="Build Ratatui"
)


def start(tmp_path, approval=False):
    args = [
        sys.executable,
        str(ROOT / "scripts/run.py"),
        "--fixture",
        "--no-install",
        "--state-dir",
        str(tmp_path / "state"),
    ]
    if approval:
        args += ["--overlay", str(ROOT / "examples/fixture-approval.yaml")]
    return Probe(args)


def events(tmp_path):
    path = next((tmp_path / "state/conversations").glob("*/events.jsonl"))
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_native_queue_remove_advance_and_stop(tmp_path):
    probe = start(tmp_path, approval=True)
    try:
        probe.wait("Ready")
        probe.send(b"First task\r")
        probe.wait("Waiting for your decision")
        probe.wait("[ Queue ]")
        probe.send(b"Second task\r")
        probe.wait("[Pending 1]")
        probe.send(b"Discard this follow-up\r")
        probe.wait("[Pending 2]")
        click(probe, "[Pending 2]")
        probe.wait("Pending follow-ups · enabled")
        capture(probe, "workflow-queue")
        probe.send(b"Discard this\r")
        probe.wait("Follow-up · inspect")
        probe.send(b"Remove waiting\r")
        probe.wait("[Pending 1]")
        action(probe, "Pending follow-ups", "Pending follow-ups · enabled")
        probe.send(b"Second task\r")
        probe.wait("Follow-up · inspect")
        probe.send(b"Edit waiting\r")
        probe.wait("Edit waiting follow-up")
        probe.send(b" corrected\r")
        probe.wait("Edit waiting follow-up", absent=True)
        probe.wait("(paused)")
        action(probe, "Decisions", "Options (exact runtime scope)")
        probe.send(b"allow\r")
        probe.wait_idle()
        assert len([e for e in events(tmp_path) if e["kind"] == "turn.accepted"]) == 1
        action(probe, "Pending follow-ups", "Pending follow-ups · paused")
        probe.send(b"Run pending\r")
        probe.wait("Second task corrected")
        probe.wait("Waiting for your decision")
        action(probe, "Stop active", "Interrupted")
        assert [e["payload"]["text"] for e in events(tmp_path) if e["kind"] == "turn.accepted"] == [
            "First task",
            "Second task corrected",
        ]
    finally:
        probe.close()


def test_native_rename_find_copy_preserve_draft(tmp_path):
    probe = start(tmp_path)
    try:
        probe.wait("Ready")
        probe.send(b"Unique orchard question\r")
        probe.wait_idle()
        probe.send(b"Keep my correction")
        action(probe, "Rename conversation", "New name (up to 100 characters)")
        probe.send(b"cancel this\x1b")
        draft_is(probe, "Keep my correction")
        action(probe, "Rename conversation", "New name (up to 100 characters)")
        probe.send(b"\r")
        probe.wait("Use 1–100 printable characters")
        probe.wait("New name (up to 100 characters)")
        probe.send(b"Orchard work\r")
        probe.wait("Orchard work")
        draft_is(probe, "Keep my correction")
        action(probe, "Find in conversation", "Find message text")
        probe.send(b"Unique orchard\r")
        probe.wait("Conversation matches")
        capture(probe, "workflow-search")
        probe.send(b"\r")
        probe.wait("Message · retained source preview")
        probe.send(b"\r")
        probe.wait("Unique orchard question")
        draft_is(probe, "Keep my correction")
        action(probe, "Assistant replies", "Assistant replies · latest")
        probe.send(b"\r")
        probe.wait("Message · retained source preview")
        probe.send(b"Copy message\r")
        probe.wait("Source copied")
        copied = re.findall(rb"\x1b\]52;c;([^\x07]*)\x07", probe.raw)
        answer = next(e["payload"]["text"] for e in events(tmp_path) if e["kind"] == "text.final")
        assert base64.b64decode(copied[-1]).decode() == answer
        assert len([e for e in events(tmp_path) if e["kind"] == "turn.accepted"]) == 1
        draft_is(probe, "Keep my correction")
    finally:
        probe.close()
    metadata = json.loads(
        next((tmp_path / "state/conversations").glob("*/metadata.json")).read_text()
    )
    assert metadata["title"] == "Orchard work"


def test_partial_search_scope_and_exact_markdown_copy(tmp_path):
    # Explicitly simulated projection fixture; no runtime conformance claim.
    items = [
        {
            "id": f"reply-{i}",
            "kind": "assistant",
            "text": f"**needle {i}**\n\n```python\nprint('hello')\n```",
        }
        for i in range(201)
    ]
    probe = scene(tmp_path, items, draft="Unchanged scratch")
    try:
        probe.wait("Ready")
        action(probe, "Find in conversation", "Find message text")
        probe.send(b"needle\r")
        probe.wait("Partial search")
        probe.send(b"\r")
        probe.wait("Message · retained source preview")
        probe.send(b"Copy message\r")
        probe.wait("Source copied")
        copied = re.findall(rb"\x1b\]52;c;([^\x07]*)\x07", probe.raw)
        assert base64.b64decode(copied[-1]).decode() == items[-1]["text"]
        draft_is(probe, "Unchanged scratch")
    finally:
        probe.close()

"""Native runtime controls; module-backed cases and an explicitly simulated disconnect."""

import base64
import json
import os
import re
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from interaction_probe import action, capture, click  # noqa: E402
from terminal_probe import Probe  # noqa: E402
from test_reading_terminal import draft_is, scene  # noqa: E402
from test_workflow_terminal import events, start  # noqa: E402

pytestmark = pytest.mark.skipif(
    os.environ.get("TUI_TEST_CANDIDATES") != "1", reason="Build Ratatui"
)


def test_unsupported_provider_menu_is_explanatory_not_stuck_loading(tmp_path):
    probe = scene(tmp_path, [], draft="Unchanged scratch")
    try:
        probe.wait("Ready")
        action(probe, "Conversation provider", "selection is unavailable")
        assert "loading" not in probe.text
        draft_is(probe, "Unchanged scratch")
    finally:
        probe.close()


def test_native_correction_insertion_scope_copy_and_draft(tmp_path):
    probe = start(tmp_path, approval=True)
    try:
        probe.wait("Ready")
        probe.send(b"First work\r")
        probe.wait("Waiting for your decision")
        probe.send(b"Keep composer scratch")
        click(probe, "[Steer]")
        probe.wait("Correction for this turn only")
        probe.send(b"\x1b[200~Change direction\nSecond line\x1b[201~")
        probe.wait("Second line")
        assert not any(e["kind"] == "steering.updated" for e in events(tmp_path))
        capture(probe, "controls-correction-editor")
        probe.send(b"\r")
        probe.wait("your correction · pending")
        draft_is(probe, "Keep composer scratch")
        action(probe, "Decisions", "Options (exact runtime scope)")
        probe.send(b"allow\r")
        probe.wait("your correction · applied")
        until = time.monotonic() + 5
        while time.monotonic() < until:
            probe.read(0.02)
            if len([e for e in events(tmp_path) if e["kind"] == "approval.requested"]) == 2:
                break
        else:
            raise AssertionError("Fixture continuation did not request its second tool")
        action(probe, "Decisions", "Options (exact runtime scope)")
        probe.send(b"allow\r")
        probe.wait("Completed")
        assert len([e for e in events(tmp_path) if e["kind"] == "turn.accepted"]) == 1
        action(probe, "Corrections —", "Corrections · latest")
        capture(probe, "controls-corrections")
        probe.send(b"\r")
        probe.wait("Message · retained source preview")
        probe.send(b"Copy message\r")
        probe.wait("Source copied")
        copies = re.findall(rb"\x1b\]52;c;([^\x07]*)\x07", probe.raw)
        assert base64.b64decode(copies[-1]).decode() == "Change direction\nSecond line"
        draft_is(probe, "Keep composer scratch")
    finally:
        probe.close()


def test_native_provider_select_and_resume(tmp_path):
    args = [
        sys.executable,
        str(ROOT / "scripts/run.py"),
        "--fixture",
        "--no-install",
        "--state-dir",
        str(tmp_path / "state"),
        "--overlay",
        str(ROOT / "examples/fixture-models.yaml"),
    ]
    probe = Probe(args, cols=160)
    try:
        probe.wait("Ready")
        probe.send(b"Retain provider draft")
        action(probe, "Conversation provider", "Conversation provider · choose then confirm")
        probe.wait("fixture-alternate")
        assert "fixture · fixture · fixture" in probe.text
        capture(probe, "controls-providers")
        probe.send(b"fixture-alternate\r")
        probe.wait("Apply conversation provider?")
        probe.send(b"\x1b")
        draft_is(probe, "Retain provider draft")
        assert not any(e["kind"] == "turn.accepted" for e in events(tmp_path))
        action(probe, "Conversation provider", "Conversation provider · choose then confirm")
        probe.send(b"fixture-alternate\r")
        probe.wait("Apply conversation provider?")
        probe.send(b"\r")
        probe.wait("Conversation provider saved")
        draft_is(probe, "Retain provider draft")
        probe.send(b"\r")
        probe.wait("Completed")
        selected = [e for e in events(tmp_path) if e["kind"] == "provider.selected"]
        assert selected[-1]["payload"]["provider"] == "fixture-alternate"
    finally:
        probe.close()
    probe = Probe(
        [
            sys.executable,
            str(ROOT / "scripts/run.py"),
            "--resume",
            "latest",
            "--no-install",
            "--state-dir",
            str(tmp_path / "state"),
        ]
    )
    try:
        probe.wait("Ready")
        action(probe, "Conversation provider", "Conversation provider · choose then confirm")
        probe.wait("Current: fixture-alternate")
        probe.send(b"Selection history\r")
        probe.wait("Provider selections · latest")
        probe.wait("automatic → fixture-alternate")
        probe.send(b"\r")
        probe.wait("Source copied")
        assert len([e for e in events(tmp_path) if e["kind"] == "turn.accepted"]) == 1
    finally:
        probe.close()


def test_finished_turn_rejects_open_correction_without_losing_editor(tmp_path):
    overlay = tmp_path / "slow.yaml"
    overlay.write_text(
        json.dumps(
            {
                "bundle": {"name": "slow-fixture", "version": "1"},
                "tools": [{"module": "tool-fixture", "config": {"delay": 0.5}}],
            }
        )
    )
    probe = Probe(
        [
            sys.executable,
            str(ROOT / "scripts/run.py"),
            "--fixture",
            "--no-install",
            "--state-dir",
            str(tmp_path / "state"),
            "--overlay",
            str(overlay),
        ]
    )
    try:
        probe.wait("Ready")
        probe.send(b"Original work\r")
        probe.wait("fixture_probe")
        probe.send(b"Unchanged main draft")
        action(probe, "Correct active turn", "Correction for this turn only")
        probe.send(b"A correction written too late")
        probe.wait("Completed")
        probe.send(b"\r")
        probe.wait("no longer active")
        probe.wait("A correction written too late")
        assert not any(e["kind"] == "steering.updated" for e in events(tmp_path))
        probe.send(b"\x1b")
        draft_is(probe, "Unchanged main draft")
    finally:
        probe.close()


def test_disconnected_modal_text_can_be_copied_and_dismissed_without_retry(tmp_path):
    # Raw, explicitly simulated transport: it exits without acknowledging rename.
    program = """
import json, sys
print(json.dumps(dict(version=1,type="snapshot",session_id="fixture",navigation=True,mode="SIMULATED",draft="Main scratch",items=[],system=[])),flush=True)
print(json.dumps(dict(version=1,type="state",status="Ready")),flush=True)
for line in sys.stdin:
    if json.loads(line).get("op") == "rename": break
"""
    probe = Probe(
        [
            str(ROOT / "frontends/ratatui/target/release/amplifier-ratatui"),
            "--host-json",
            json.dumps([sys.executable, "-c", program]),
        ]
    )
    try:
        probe.wait("Ready")
        action(probe, "Rename conversation", "New name (up to 100 characters)")
        probe.send(b"Unacknowledged title\r")
        probe.wait("Uncertain · F2 copy text")
        probe.send(b"\x1bOQ")  # F2, visible recovery hint.
        probe.wait("Source copied")
        copies = re.findall(rb"\x1b\]52;c;([^\x07]*)\x07", probe.raw)
        assert base64.b64decode(copies[-1]).decode() == "Unacknowledged title"
        probe.send(b"\x1b")
        probe.wait("Uncertain · F2 copy text", absent=True)
        draft_is(probe, "Main scratch")
    finally:
        probe.close()

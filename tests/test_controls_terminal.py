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


@pytest.mark.parametrize("cols,rows", [(175, 50), (40, 20)])
def test_loaded_configuration_is_discoverable_and_never_submits_a_turn(tmp_path, cols, rows):
    probe = Probe(
        [
            sys.executable,
            str(ROOT / "scripts/run.py"),
            "--fixture",
            "--no-install",
            "--state-dir",
            str(tmp_path / "state"),
        ],
        cols=cols,
        rows=rows,
    )
    try:
        probe.wait("Ready")
        action(probe, "Loaded configuration", "/config")
        probe.wait("Actions / choices", absent=True)
        draft_is(probe, "/config")
        assert not any(e["kind"] == "turn.accepted" for e in events(tmp_path))
        probe.send(b"\r")
        probe.wait("Shared settings unchanged")
        capture(probe, f"config-loaded-{cols}")
        journal = events(tmp_path)
        shown = "\n".join(e["payload"].get("text", "") for e in journal)
        assert "Orchestrator: loop-streaming" in shown
        assert "Available agent definitions" in shown
        assert not any(e["kind"] in ("turn.accepted", "tool.started") for e in journal)
        # Paste bypasses the slash-command suggestion menu; explicit Send is
        # separate from accepting an automatically offered command choice.
        query = "/config show providers fixture"
        probe.send(b"\x1b[200~" + query.encode() + b"\x1b[201~")
        draft_is(probe, query)
        prior = sum(e["payload"].get("source") == "config" for e in events(tmp_path))
        probe.send(b"\r")
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if sum(e["payload"].get("source") == "config" for e in events(tmp_path)) > prior:
                break
            probe.read(0.02)
        else:
            pytest.fail("Exact config inspection was not received")
        probe.wait("fixture · enabled")
        probe.send(b"Draft after configuration inspection")
        draft_is(probe, "Draft after configuration inspection")
        capture(probe, f"config-provider-{cols}")
        assert not any(e["kind"] == "turn.accepted" for e in events(tmp_path))
    finally:
        probe.close()


@pytest.mark.parametrize("cols,rows", [(175, 50), (40, 20)])
def test_configuration_toggle_diff_and_definition_aliases(tmp_path, cols, rows):
    probe = Probe(
        [
            sys.executable,
            str(ROOT / "scripts/run.py"),
            "--fixture",
            "--no-install",
            "--state-dir",
            str(tmp_path / "state"),
        ],
        cols=cols,
        rows=rows,
    )
    try:
        probe.wait("Ready")
        for query, expected in (
            ("/config tools disable fixture_probe", "disable applied"),
            ("/config diff", "fixture_probe disabled"),
            ("/tools", "fixture_probe · disabled"),
            ("/config tools enable fixture_probe", "enable applied"),
            ("/agents", "Available agent definitions"),
        ):
            prior = sum(e["payload"].get("source") == "config" for e in events(tmp_path))
            probe.send(b"\x1b[200~" + query.encode() + b"\x1b[201~")
            draft_is(probe, query)
            probe.send(b"\r")
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                shown = [e for e in events(tmp_path) if e["payload"].get("source") == "config"]
                if len(shown) > prior:
                    assert expected in shown[-1]["payload"]["text"]
                    break
                probe.read(0.02)
            else:
                pytest.fail("Configuration control did not finish")
            # The observed result precedes final checkpoint/completion. Do not
            # type the next control while the UI still advertises Enter queue.
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                probe.read(0.02)
                if probe.text.splitlines()[-1].strip() == "Ready":
                    break
            else:
                pytest.fail("Configuration control did not return to idle")
            if query == "/config diff":
                probe.wait("fixture_probe disabled")
                capture(probe, f"config-changes-{cols}")
        probe.send(b"Draft retained after controls")
        draft_is(probe, "Draft retained after controls")
        capture(probe, f"config-aliases-{cols}")
        assert not any(e["kind"] == "turn.accepted" for e in events(tmp_path))
    finally:
        probe.close()


def test_stop_with_replacement_keeps_draft_and_never_submits(tmp_path):
    probe = start(tmp_path, approval=True)
    try:
        probe.wait("Ready")
        probe.send(b"Original task\r")
        probe.wait("Waiting for your decision")
        probe.send(b"Replacement after reviewing effects")
        action(probe, "Stop and keep replacement", "Stop current work and retain this draft?")
        probe.send(b"\x1b")
        assert not any(e["kind"] == "turn.ended" for e in events(tmp_path))
        action(probe, "Stop and keep replacement", "Stop current work and retain this draft?")
        capture(probe, "rc5-stop-replacement")
        probe.send(b"\r")
        probe.wait("Interrupted")
        draft_is(probe, "Replacement after reviewing effects")
        assert len([e for e in events(tmp_path) if e["kind"] == "turn.accepted"]) == 1
        assert not any(e["kind"] == "followup.updated" for e in events(tmp_path))
    finally:
        probe.close()
    draft = next((tmp_path / "state/conversations").glob("*/draft.json"))
    assert json.loads(draft.read_text())["text"] == "Replacement after reviewing effects"


def test_pasted_draft_persists_before_typing_debounce_without_submission(tmp_path):
    probe = start(tmp_path)
    try:
        probe.wait("Ready")
        path = next((tmp_path / "state/conversations").glob("*/draft.json"))
        text = "Pasted first line\nPasted second line"
        started = time.monotonic()
        probe.send(b"\x1b[200~" + text.encode() + b"\x1b[201~")
        deadline = started + 0.20
        while json.loads(path.read_text())["text"] != text and time.monotonic() < deadline:
            probe.read(timeout=0.005)
        assert json.loads(path.read_text())["text"] == text
        assert time.monotonic() - started < 0.20
        assert not any(e["kind"] == "turn.accepted" for e in events(tmp_path))
        # Persistence may precede paint; inspect the rendered paste separately.
        probe.wait("Pasted first line")
        probe.wait("Pasted second line")
        capture(probe, "rc5-pasted-draft")
    finally:
        probe.close()


def test_model_catalog_limits_are_visible_without_a_turn(tmp_path):
    overlay = tmp_path / "model-catalog.yaml"
    overlay.write_text(
        json.dumps(
            {
                "bundle": {"name": "model-catalog-fixture"},
                "providers": [
                    {
                        "module": "provider-fixture",
                        "config": {
                            "models": [
                                {
                                    "id": "catalog-model",
                                    "context_window": 100000,
                                    "max_output_tokens": 8000,
                                    "capabilities": ["tools", "vision"],
                                }
                            ]
                        },
                    }
                ],
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
        ],
        cols=160,
    )
    try:
        probe.wait("Ready")
        probe.send(b"Keep unsent context question")
        action(probe, "Model catalog", "Model catalog · explicit discovery")
        probe.send(b"\r")
        probe.wait("Model catalog · advisory IDs")
        probe.wait("context window: 100000 tokens")
        probe.wait("Maximum output: 8000 tokens")
        capture(probe, "post-rc4-model-limits")
        draft_is(probe, "Keep unsent context question")
        assert not any(e["kind"] == "turn.accepted" for e in events(tmp_path))
    finally:
        probe.close()


def test_uncertain_correction_reuse_is_confirmed_unsent_and_preserves_source(tmp_path):
    probe = start(tmp_path, approval=True)
    text = "Review this uncertain correction"
    try:
        probe.wait("Ready")
        probe.send(b"First work\r")
        probe.wait("Waiting for your decision")
        action(probe, "Correct active turn", "Correction for this turn only")
        probe.send(text.encode() + b"\r")
        probe.wait("Correction pending")
        action(probe, "Stop active", "Interrupted")
        probe.wait("Correction unconfirmed")
        probe.send(b"Existing scratch")
        action(probe, "Corrections —", "Corrections · latest")
        probe.send(b"\r")
        probe.wait("Message · retained source preview")
        probe.send(b"Reuse correction\r")
        probe.wait("Reuse requires an idle empty composer")
        draft_is(probe, "Existing scratch")
        probe.send(b"\x1b")
        probe.wait("Actions / choices", absent=True)
        probe.send(b"\x01\x0b")  # Home then kill-line: explicit removal of scratch.
        draft_is(probe, "")
        for confirm in (False, True):
            action(probe, "Corrections —", "Corrections · latest")
            probe.send(b"\r")
            probe.wait("Message · retained source preview")
            probe.send(b"Reuse correction\r")
            probe.wait("Copy uncertain correction into empty draft?")
            draft_is(probe, "")
            capture(probe, "post-rc4-correction-reuse")
            probe.send(b"\r" if confirm else b"\x1b")
            probe.wait("Actions / choices", absent=True)
            draft_is(probe, text if confirm else "")
        rows = events(tmp_path)
        assert sum(r["kind"] == "turn.accepted" for r in rows) == 1
        updates = [r for r in rows if r["kind"] == "steering.updated"]
        assert [r["payload"]["status"] for r in updates] == ["pending", "unconfirmed"]
        assert not any(r["kind"] == "queue.updated" for r in rows)
    finally:
        probe.close()
    draft = next((tmp_path / "state/conversations").glob("*/draft.json"))
    assert json.loads(draft.read_text())["text"] == text


def test_native_correction_insertion_scope_copy_and_draft(tmp_path):
    probe = start(tmp_path, approval=True)
    try:
        probe.wait("Ready")
        probe.send(b"First work\r")
        probe.wait("Waiting for your decision")
        probe.send(b"Keep composer scratch")
        click(probe, "[Change task]")
        probe.wait("Correction for this turn only")
        probe.send(b"\x1b[200~Change direction\nSecond line\x1b[201~")
        probe.wait("Second line")
        assert not any(e["kind"] == "steering.updated" for e in events(tmp_path))
        capture(probe, "controls-correction-editor")
        probe.send(b"\r")
        probe.wait("Correction pending")
        draft_is(probe, "Keep composer scratch")
        action(probe, "Decisions", "Options (exact runtime scope)")
        probe.send(b"allow\r")
        probe.wait("Correction applied")
        until = time.monotonic() + 5
        while time.monotonic() < until:
            probe.read(0.02)
            if len([e for e in events(tmp_path) if e["kind"] == "approval.requested"]) == 2:
                break
        else:
            raise AssertionError("Fixture continuation did not request its second tool")
        action(probe, "Decisions", "Options (exact runtime scope)")
        probe.send(b"allow\r")
        probe.wait_idle()
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
        probe.wait_idle()
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
        probe.wait_idle()
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

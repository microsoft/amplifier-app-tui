import os
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from interaction_probe import action, capture, click  # noqa: E402
from questions_probe import wait_ready  # noqa: E402
from terminal_probe import Probe  # noqa: E402
from test_reading_terminal import draft_is, scene  # noqa: E402
from test_structured_reading_terminal import copied  # noqa: E402

pytestmark = pytest.mark.skipif(
    os.environ.get("TUI_TEST_CANDIDATES") != "1", reason="Build native client"
)


def test_drag_selection_copy_does_not_quit_or_steal_draft(tmp_path):
    probe = scene(
        tmp_path,
        [{"id": "a", "kind": "assistant", "text": "Select these words and keep typing."}],
        draft="My draft",
    )
    try:
        probe.wait("Select these words")
        action(probe, "Transcript —", "[ Latest")
        y = next(i for i, row in enumerate(probe.screen.display) if "Select these words" in row)
        x = probe.screen.display[y].index("Select these words")
        probe.send(
            f"\x1b[<0;{x + 1};{y + 1}M\x1b[<32;{x + 18};{y + 1}M\x1b[<0;{x + 18};{y + 1}m".encode()
        )
        probe.wait("Copy selection")
        capture(probe, "repair-selection")
        probe.send(b"\x03")
        assert copied(probe) == "Select these word"
        assert probe.process.poll() is None
        draft_is(probe, "My draft")
        probe.send(b"\x1b")
    finally:
        probe.close()


@pytest.mark.parametrize("width", [40, 160])
def test_question_is_directly_answerable_and_exportable(tmp_path, width):
    overlay = tmp_path / "question.yaml"
    overlay.write_text(
        yaml.safe_dump(
            {
                "bundle": {"name": "one-question", "version": "1.0.0"},
                "providers": [
                    {
                        "module": "provider-fixture",
                        "config": {
                            "questions": [
                                {
                                    "id": "proceed",
                                    "question": "Should I proceed?",
                                    "options": [{"label": "Yes, continue"}, {"label": "No, stop"}],
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
            "--overlay",
            str(overlay),
            "--state-dir",
            str(tmp_path / "state"),
        ],
        cols=width,
    )
    try:
        wait_ready(probe)
        probe.send(b"Ask me\r")
        probe.wait("[ Answer question ]")
        probe.send(b"Draft remains")
        capture(probe, f"repair-question-{width}")
        click(probe, "[ Answer question ]")
        probe.wait("Yes, continue")
        probe.send(b"\r")
        probe.wait("Submit reviewed")
        probe.send(b"Submit reviewed\r")
        probe.wait("Completed")
        draft_is(probe, "Draft remains")
        action(probe, "Export conversation", "Private transcript saved")
        probe.wait("Private transcript saved")
        paths = list((tmp_path / "state/exports").glob("*.md"))
        assert len(paths) == 1 and "Yes, continue" in paths[0].read_text()
    finally:
        probe.close()


@pytest.mark.skipif(os.environ.get("TUI_TEST_PRESETS") != "1", reason="Full preset setup")
def test_native_modes_catalog_change_and_restore_without_model_calls(tmp_path):
    import json

    from amplifier_tui.conversations import resolve_resume

    overlay = tmp_path / "provider.yaml"
    overlay.write_text(
        yaml.safe_dump(
            {
                "bundle": {"name": "mode-control-probe", "version": "1.0.0"},
                "providers": [
                    {
                        "module": "provider-fixture",
                        "source": str(ROOT / "src/amplifier_tui/fixtures/provider-fixture"),
                    }
                ],
            }
        )
    )
    state = tmp_path / "state"
    command = [
        sys.executable,
        str(ROOT / "scripts/run.py"),
        "--no-install",
        "--state-dir",
        str(state),
    ]
    probe = Probe([*command, "--preset", "anchors", "--overlay", str(overlay)], cols=100)
    try:
        wait_ready(probe)
        path = state / "conversations" / resolve_resume(state, "latest")["id"]
        probe.send(b"/mode explore\r")
        probe.wait("Apply explore")
        probe.send(b"\r")
        probe.wait("Current: explore")
        probe.wait("Mode: explore")
        assert json.loads((path / "modes.json").read_text())["mode"] == "explore"
    finally:
        probe.close()
    probe = Probe([*command, "--resume", path.name], cols=100)
    try:
        wait_ready(probe)
        probe.wait("Mode: explore")
        action(probe, "Modes —", "Modes · current session policy")
        probe.wait("Current: explore")
        probe.send(b"Default\r")
        probe.wait("Apply default")
        probe.send(b"\r")
        probe.wait("Current: default")
        probe.wait("Mode: default")
        assert not any(
            json.loads(line)["kind"] == "turn.accepted"
            for line in (path / "events.jsonl").read_text().splitlines()
        )
        capture(probe, "repair-native-modes")
    finally:
        probe.close()


def test_native_recovery_is_explicit_and_preserves_original(tmp_path):
    import json

    from amplifier_tui.conversations import resolve_resume

    overlay = tmp_path / "slow.yaml"
    overlay.write_text(
        yaml.safe_dump(
            {
                "bundle": {"name": "slow", "version": "1.0.0"},
                "tools": [{"module": "tool-fixture", "config": {"delay": 10}}],
            }
        )
    )
    state = tmp_path / "state"
    command = [
        sys.executable,
        str(ROOT / "scripts/run.py"),
        "--fixture",
        "--no-install",
        "--state-dir",
        str(state),
    ]
    probe = Probe([*command, "--overlay", str(overlay)], cols=100)
    try:
        wait_ready(probe)
        probe.send(b"Recovery marker\r")
        probe.wait("fixture_probe")
        click(probe, "[ Stop ]")
        probe.wait("Stopped")
        source = state / "conversations" / resolve_resume(state, "latest")["id"]
    finally:
        probe.close()
    before = {p.name: p.read_bytes() for p in source.iterdir() if p.is_file()}
    probe = Probe(command, cols=100)
    try:
        wait_ready(probe)
        action(probe, "Resume", "Saved conversations")
        probe.send(source.name[:8].encode() + b"\r")
        probe.wait("Create recovered conversation")
        capture(probe, "repair-recovery-confirm")
        probe.send(b"\r")
        probe.wait("Recovered historical context")
        wait_ready(probe)
        target = state / "conversations" / resolve_resume(state, "latest")["id"]
        assert target != source
        assert json.loads((target / "metadata.json").read_text())["recovered_from"] == source.name
        assert not any(
            json.loads(line)["kind"] == "turn.accepted"
            for line in (target / "events.jsonl").read_text().splitlines()
        )
        assert before == {p.name: p.read_bytes() for p in source.iterdir() if p.is_file()}
    finally:
        probe.close()

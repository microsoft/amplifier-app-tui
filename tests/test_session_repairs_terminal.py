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


@pytest.mark.parametrize("size", [(175, 50), (40, 20), (32, 12)])
def test_ctrl_c_stops_without_exiting_and_clean_interruption_resumes(tmp_path, size):
    import json

    overlay = tmp_path / "slow-provider.yaml"
    overlay.write_text(
        yaml.safe_dump(
            {
                "bundle": {"name": "cancellation-fixture"},
                "providers": [{"module": "provider-fixture", "config": {"delay": 2}}],
            }
        )
    )
    state = tmp_path / "state"
    base = [
        sys.executable,
        str(ROOT / "scripts/run.py"),
        "--no-install",
        "--state-dir",
        str(state),
    ]
    probe = Probe(
        [*base, "--fixture", "--overlay", str(overlay)],
        cols=size[0],
        rows=size[1],
        cwd=tmp_path,
    )
    try:
        wait_ready(probe)
        probe.send(b"Begin controlled work\r")
        probe.wait("Working")
        probe.send(b"Retain draft")
        draft_is(probe, "Retain draft")
        probe.send(b"\x03")
        probe.wait("Finishing current calls")
        capture(probe, f"graceful-stopping-{size[0]}")
        probe.wait("Stopped")
        probe.wait("[ Send ]")  # A skipped tool can mention Stop before finalization finishes.
        assert probe.process.poll() is None
        draft_is(probe, "Retain draft")
        assert "[ Send ]" in probe.text
        capture(probe, f"cancel-retained-{size[0]}")
    finally:
        probe.close()
    source = next((state / "conversations").iterdir())
    checkpoint = json.loads((source / "checkpoint.json").read_text())
    assert checkpoint["status"] == "ready"
    before = [json.loads(line) for line in (source / "events.jsonl").read_text().splitlines()]
    assert [r["payload"]["status"] for r in before if r["kind"] == "turn.ended"] == ["interrupted"]
    probe = Probe([*base, "--resume", source.name], cols=size[0], rows=size[1], cwd=tmp_path)
    try:
        wait_ready(probe)
        draft_is(probe, "Retain draft")
        after = [json.loads(line) for line in (source / "events.jsonl").read_text().splitlines()]
        assert not any(
            r["kind"] == "turn.accepted" or r["kind"].startswith("tool.")
            for r in after[len(before) :]
        )
        capture(probe, f"cancel-resumed-{size[0]}")
        probe.send(b"\r")
        probe.wait_idle(timeout=20)
        final = [json.loads(line) for line in (source / "events.jsonl").read_text().splitlines()]
        assert sum(r["kind"] == "turn.accepted" for r in final) == 2
        # Native history can already be above the smallest viewport. The durable
        # outcome, not continued visibility of the response, proves completion.
        assert [r["payload"]["status"] for r in final if r["kind"] == "turn.ended"] == [
            "interrupted",
            "completed",
        ]
        assert (
            sum(
                r["kind"] == "tool.updated"
                and r["payload"].get("status") == "running"
                and r["turn_id"] != before[-1]["turn_id"]
                for r in final
            )
            == 1
        )
    finally:
        probe.close()


def test_ctrl_c_press_only_and_caps_lock_stops_but_explicit_quit_exits():
    import json

    # Controlled transport isolates key decoding from module timing; the test
    # above separately proves real cancellation/checkpoint/resume behavior.
    program = r"""
import json, sys
stops = 0
def emit(**value):
 print(json.dumps({'version':1,'session_id':'cancel-key-fixture',**value}),flush=True)
emit(type='snapshot',ready=True,mode='TRANSPORT FIXTURE',title='Cancel keys',items=[])
emit(type='state',ready=True,busy=False,status='Ready')
for line in sys.stdin:
 r=json.loads(line)
 if r['op']=='shutdown': break
 if r['op']=='submit':
  emit(type='reply',request_id=r['request_id'],accepted=True)
  emit(type='state',ready=True,busy=True,status='Working')
 if r['op']=='stop':
  stops += 1
  emit(type='state',ready=True,busy=False,status=f'Stopped {stops}')
"""
    command = [
        str(ROOT / "frontends/ratatui/target/release/amplifier-ratatui"),
        "--host-json",
        json.dumps([sys.executable, "-u", "-c", program]),
    ]
    probe = Probe(command, cols=175, rows=50)
    try:
        probe.wait("Ready")
        probe.send(b"Start\r")
        probe.wait("Working")
        probe.send(b"Keep this draft")
        probe.wait("Keep this draft")
        probe.send(b"\x1b[67;5u")  # Caps Lock Ctrl-C press (CSI-u)
        probe.wait("Stopped 1")
        probe.send(b"\x1b[99;5:2u\x1b[99;5:3u")  # repeat + release, now idle
        probe.read(0.15)
        assert probe.process.poll() is None
        assert "Stopped 1" in probe.text and "Keep this draft" in probe.text
        probe.send(b"\x03")
        probe.wait("Quit Amplifier?")
        assert "› No, stay here" in probe.text
        capture(probe, "graceful-exit-default-no")
        probe.send(b"\r")  # default No, never exit
        probe.read(0.15)
        assert probe.process.poll() is None and "Keep this draft" in probe.text
        probe.send(b"\x03\x03")  # repeated Ctrl-C is not confirmation
        probe.read(0.15)
        assert probe.process.poll() is None
        probe.send(b"\x03")
        probe.wait("Quit Amplifier?")
        probe.send(b"y")  # explicit Yes
        probe.process.wait(timeout=4)
    finally:
        probe.close()
    probe = Probe(command, cols=175, rows=50)
    try:
        probe.wait("Ready")
        probe.send(b"Start\r")
        probe.wait("Working")
        probe.send(b"\x11")  # explicit Quit is distinct from Stop
        probe.process.wait(timeout=4)
    finally:
        probe.close()


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
        probe.wait_idle()
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
        probe.send(b"\x1b")
        probe.wait("Actions / choices", absent=True)
        probe.send(b"\x1b[200~/mode off\x1b[201~\r")
        probe.wait("Mode command finished · default")
        probe.wait("Actions / choices", absent=True)
        probe.send(b"\x1b[200~/mode explore on\x1b[201~\r")
        probe.wait("Mode command finished · explore")
        probe.wait("Actions / choices", absent=True)
        probe.send(b"Draft after mode command")
        draft_is(probe, "Draft after mode command")
        capture(probe, "cli-controls-mode-no-focus-steal")
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
    # Model an older/uncertain checkpoint, not a clean newly drained Stop. New
    # cancelled turns with valid context are now directly resumable.
    from amplifier_tui.conversations import atomic_json

    checkpoint = json.loads((source / "checkpoint.json").read_text())
    checkpoint["status"] = "uncertain"
    atomic_json(source / "checkpoint.json", checkpoint)
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

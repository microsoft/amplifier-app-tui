"""Native geometry and adversarial startup; custom transports are explicitly simulated."""

import json
import os
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from interaction_probe import capture  # noqa: E402
from terminal_probe import Probe  # noqa: E402
from test_reading_terminal import draft_is, scene  # noqa: E402

pytestmark = pytest.mark.skipif(
    os.environ.get("TUI_TEST_CANDIDATES") != "1", reason="Build native client"
)


def composer_rows(probe):
    rows = probe.screen.display
    top = next(i for i, line in enumerate(rows) if line.strip().startswith("Message ·"))
    bottom = next(i for i in range(top + 1, len(rows)) if "[ Actions ]" in rows[i]) - 1
    return top, bottom


def settle(probe, seconds=0.15):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        probe.read(0.01)


def test_content_height_wrap_editing_and_quiet_idle(tmp_path):
    probe = scene(tmp_path, [{"id": "a", "kind": "assistant", "text": "A short reply."}])
    try:
        probe.wait("Enter send")
        top, bottom = composer_rows(probe)
        assert bottom - top == 3
        assert "Ready" in probe.screen.display[top + 5]
        assert "F1 Work" not in probe.text
        assert "[ Stop ]" not in probe.text
        assert "Mode: unavailable" in probe.text
        assert top == probe.rows - 6
        assert "A short reply." in probe.text
        assert not any(c in probe.text for c in "╭╮╰╯│")
        assert "Ratatui" not in probe.text
        capture(probe, "compact-idle")
        probe.send(b"\x1b[200~first\nsecond\nthird\x1b[201~")
        settle(probe)
        top, bottom = composer_rows(probe)
        assert bottom - top == 5
        capture(probe, "compact-multiline")
        # A wrapped single logical line must navigate inside the draft before history.
        probe.send(b"\x1b[200~" + b"x" * 150 + b"\x1b[201~")
        settle(probe)
        assert composer_rows(probe)[1] - composer_rows(probe)[0] >= 5
        probe.resize(40, 24)
        probe.wait("[Modes]")
        assert "Mode: unavailable" in probe.text
        assert composer_rows(probe)[1] - composer_rows(probe)[0] <= 8
        capture(probe, "compact-narrow")
        probe.resize(160, 40)
        probe.wait("Enter send")
        assert b"\x1b[3J" not in probe.raw
    finally:
        probe.close()


@pytest.mark.parametrize("cols", [40, 80, 160, 200])
def test_borderless_composer_uses_full_width_and_quiet_live_labels(tmp_path, cols):
    # Transport-only live label, explicitly NOT a live provider execution test.
    command = """
import json, sys
print(json.dumps({'version':1,'type':'snapshot','ready':True,'mode':'LIVE RUNTIME',
 'session_id':'geometry','title':'Geometry proof','items':[]}), flush=True)
for line in sys.stdin:
 if json.loads(line)['op'] == 'shutdown': break
"""
    probe = Probe(
        [
            str(ROOT / "frontends/ratatui/target/release/amplifier-ratatui"),
            "--host-json",
            json.dumps([sys.executable, "-c", command]),
        ],
        cols=cols,
    )
    try:
        probe.wait("Geometry proof" if cols >= 80 else "Message ·")
        probe.send(b"\x1b[200~" + b"x" * cols + b"NEXT\nthird" + b"\x1b[201~")
        settle(probe)
        top, bottom = composer_rows(probe)
        lines = probe.screen.display[top + 2 : bottom]
        assert not probe.screen.display[top + 1].strip()
        assert probe.screen.display[top].startswith("Message ·")
        assert lines[0] == "x" * cols
        assert lines[1].rstrip() == "NEXT"
        assert lines[2].rstrip() == "third"
        assert "Ratatui" not in probe.text and "LIVE RUNTIME" not in probe.text
        assert not any(c in "\n".join(lines) for c in "│╭╮╰╯")
        capture(probe, f"edge-to-edge-input-{cols}")
        probe.send(b"\x1bOR")  # System inspection retains the full-width composer.
        probe.wait("Message · draft stays editable")
        settle(probe)
        top, bottom = composer_rows(probe)
        assert probe.screen.display[top].startswith("Message ·")
        assert not probe.screen.display[top + 1].strip()
        assert probe.screen.display[top + 2] == "x" * cols
        assert probe.screen.display[top + 3].rstrip() == "NEXT"
    finally:
        probe.close()


def test_delayed_startup_retains_selection_saved_draft_and_never_auto_sends(tmp_path):
    gate = tmp_path / "gate"
    receipt = tmp_path / "requests.jsonl"
    code = f"""
import json, pathlib, sys, threading, time
gate, receipt = pathlib.Path({str(gate)!r}), pathlib.Path({str(receipt)!r})
lock = threading.Lock()
def emit(value):
    with lock:
        print(json.dumps({{'version': 1, **value}}), flush=True)
def read():
    for line in sys.stdin:
        r = json.loads(line)
        with receipt.open('a') as f: f.write(line)
        if r['op'] == 'shutdown': return
        emit({{'type':'reply', 'request_id':r['request_id'], 'accepted':True}})
thread = threading.Thread(target=read, daemon=True)
thread.start()
emit({{'type':'state','status':'Waiting for simulated startup','ready':False}})
while not gate.exists(): time.sleep(.005)
emit({{'type':'snapshot','ready':False,'session_id':'startup-test','mode':'SIMULATED',
       'title':'Startup proof','draft':'Saved previous draft 界','durable':True,'items':[]}})
while gate.read_text() != 'ready': time.sleep(.005)
emit({{'type':'state','ready':True,'status':'Ready - simulated startup'}})
thread.join()
"""
    probe = Probe(
        [
            str(ROOT / "frontends/ratatui/target/release/amplifier-ratatui"),
            "--host-json",
            json.dumps([sys.executable, "-c", code]),
        ]
    )

    def requests():
        return (
            [json.loads(line) for line in receipt.read_text().splitlines()]
            if receipt.exists()
            else []
        )

    try:
        probe.wait("Waiting for simulated startup")
        probe.send("new 界 text".encode() + b"\x1b[1;2D\x1b[1;2D\r\x18")
        probe.wait("Session not ready")
        gate.write_text("snapshot")
        probe.wait("[Saved draft]")
        draft_is(probe, "new 界 text")
        capture(probe, "compact-startup-draft")
        gate.write_text("ready")
        probe.wait("Ready - simulated startup")
        settle(probe, 0.3)
        assert not any(r["op"] in ("submit", "queue", "stop") for r in requests())
        backups = [r["startup_backup"] for r in requests() if "startup_backup" in r]
        assert backups and backups[0]["text"] == "Saved previous draft 界"
        # Replaces exactly the pre-snapshot selection; readiness must not remount it.
        probe.send(b"Z")
        draft_is(probe, "new 界 teZ")
        probe.send(b"\r")
        settle(probe, 0.3)
        sent = [r for r in requests() if r["op"] == "submit"]
        assert len(sent) == 1 and sent[0]["text"] == "new 界 teZ"
        assert sent[0]["startup_backup"]["text"] == "Saved previous draft 界"
    finally:
        # Ensure the deliberately delayed fake host can always shut down.
        gate.write_text("ready")
        probe.close()


@pytest.mark.parametrize("reply", ["silent", "delayed"])
def test_fresh_page_startup_needs_no_cursor_reply_and_preserves_input(tmp_path, reply):
    probe = scene(tmp_path, [])
    original = probe.screen.write_process_input
    replies = []
    probe.screen.write_process_input = replies.append
    try:
        probe.send(b"\x1b[200~early " + "界".encode() + b"\x1b[201~")
        if reply == "delayed":
            settle(probe, 0.2)
            for response in replies:
                original(response)
            probe.screen.write_process_input = original
        probe.wait("Enter send", timeout=5)
        draft_is(probe, "early 界")
        assert not replies and b"\x1b[6n" not in probe.raw
        assert b"\x1b[3J" not in probe.raw
        assert probe.process.poll() is None
        capture(probe, f"compact-probe-{reply}")
    finally:
        probe.close()


def test_silent_resize_probe_is_bounded_and_retains_paste(tmp_path):
    probe = scene(tmp_path, [{"id": "kept", "kind": "assistant", "text": "Retained source"}])
    try:
        probe.wait("Enter send")
        probe.screen.write_process_input = lambda _: None
        start = time.monotonic()
        probe.resize(80, 30)
        probe.send(b"\x1b[200~during resize " + "界".encode() + b"\x1b[201~")
        draft_is(probe, "during resize 界")
        assert time.monotonic() - start < 0.8
        assert b"\x1b[3J" not in probe.raw
        probe.resize(120, 40)
        settle(probe)
        draft_is(probe, "during resize 界")
    finally:
        probe.close()


def test_inspection_without_cursor_replies_preserves_draft_and_primary_history(tmp_path):
    probe = scene(tmp_path, [{"id": "kept", "kind": "assistant", "text": "Retained source"}])
    probe.screen.write_process_input = lambda _: None
    try:
        probe.wait("Enter send")
        probe.send(b"\x1b[200~unsent first\nunsent second\x1b[201~")
        draft_is(probe, "unsent second")
        start = len(probe.raw)
        probe.send(b"\x1bOR")  # F3 is the previously failing inspection transition.
        probe.wait("Message · draft stays editable", timeout=3)
        draft_is(probe, "unsent first")
        assert b"\x1b[6n" not in probe.raw[start:]
        probe.resize(80, 30)
        settle(probe)
        draft_is(probe, "unsent second")
        probe.send(b"\x1bOP")  # F1 returns to primary-screen transcript.
        probe.wait("Retained source")
        probe.send(b"\x1bOS")  # F4 opens Actions, another inspection transition.
        probe.wait("Actions · type to search", timeout=3)
        capture(probe, "inspection-no-cursor-replies")
        probe.send(b"\x1b")
        draft_is(probe, "unsent second")
        assert b"\x1b[3J" not in probe.raw
        assert "could not be read" not in probe.text
    finally:
        probe.close()  # Also verifies clean exit and restored terminal modes.
    assert probe.screen.primary is None
    assert b"Retained source" in probe.raw


def test_skill_menu_inserts_arguments_and_ignores_stale_catalog(tmp_path):
    receipt = tmp_path / "requests.jsonl"
    code = f"""
import json, pathlib, sys
def emit(value): print(json.dumps({{'version':1, **value}}), flush=True)
emit({{'type':'snapshot','ready':True,'session_id':'current','mode':'SIMULATED', 'items':[]}})
emit({{'type':'commands','session_id':'current','commands':['memory']}})
emit({{'type':'commands','session_id':'previous','commands':['stale-skill']}})
for line in sys.stdin:
 r = json.loads(line)
 with pathlib.Path({str(receipt)!r}).open('a') as stream: stream.write(line)
 if r['op'] == 'shutdown': break
 emit({{'type':'reply','request_id':r['request_id'],'accepted':True}})
"""
    probe = Probe(
        [
            str(ROOT / "frontends/ratatui/target/release/amplifier-ratatui"),
            "--host-json",
            json.dumps([sys.executable, "-c", code]),
        ]
    )

    def submissions():
        return (
            [r for r in map(json.loads, receipt.read_text().splitlines()) if r["op"] == "submit"]
            if receipt.exists()
            else []
        )

    try:
        probe.wait("Enter send")
        probe.send(b"/")
        probe.wait("Actions · type to search")
        probe.send(b"memory")
        probe.wait("/memory")
        assert "stale-skill" not in probe.text
        probe.send(b" review literal arguments\r")
        draft_is(probe, "/memory review literal arguments")
        assert not submissions()
        capture(probe, "skill-command-unsent")
        # A second insertion must not replace or append to an occupied draft.
        probe.send(b"\x1bOS")
        probe.wait("Actions · type to search")
        probe.send(b"memory\r")
        probe.wait("Draft retained")
        draft_is(probe, "/memory review literal arguments")
        probe.send(b"\r")
        settle(probe)
        assert [r["text"] for r in submissions()] == ["/memory review literal arguments"]
        probe.send(b"\x1b[200~/mem\x1b[201~\t")
        draft_is(probe, "/memory")
        assert len(submissions()) == 1  # Tab completion does not invoke the skill.
    finally:
        probe.close()


def test_startup_failure_remains_visible_after_send_and_late_draft_refusal(tmp_path):
    receipt = tmp_path / "requests.jsonl"
    code = f"""
import json, pathlib, sys
def emit(value): print(json.dumps({{'version':1, **value}}), flush=True)
emit({{'type':'state','ready':False,'status':'Startup failed: controlled missing module'}})
for line in sys.stdin:
 r=json.loads(line)
 with pathlib.Path({str(receipt)!r}).open('a') as stream: stream.write(line)
 if r['op']=='shutdown': break
 emit({{'type':'reply','request_id':r['request_id'],'accepted':False,'reason':'Session not ready'}})
"""
    probe = Probe(
        [
            str(ROOT / "frontends/ratatui/target/release/amplifier-ratatui"),
            "--host-json",
            json.dumps([sys.executable, "-c", code]),
        ]
    )
    try:
        probe.wait("Startup failed: controlled missing module")
        probe.send(b"retained startup draft\r")
        settle(probe, 0.5)
        probe.wait("Startup failed: controlled missing module")
        draft_is(probe, "retained startup draft")
        assert "correct the startup problem and relaunch" in probe.text
        capture(probe, "startup-failure-retained")
        assert not receipt.exists() or not any(
            json.loads(line)["op"] == "submit" for line in receipt.read_text().splitlines()
        )
    finally:
        probe.close()


def test_real_recipe_file_menu_appends_without_replacing_selection_or_sending(tmp_path):
    from interaction_probe import action

    cwd, state = tmp_path / "workspace", tmp_path / "state"
    recipes = cwd / "recipes"
    recipes.mkdir(parents=True)
    (recipes / "review-me.yaml").write_text("not a validated recipe: [")
    probe = Probe(
        [
            sys.executable,
            str(ROOT / "scripts/run.py"),
            "--no-install",
            "--fixture",
            "--cwd",
            str(cwd),
            "--state-dir",
            str(state),
        ]
    )
    try:
        probe.wait("Ready")
        probe.send(b"/recipes\r")
        probe.wait("Recipe files · local candidates")
        probe.wait("Partial catalog")
        probe.send(b"\x1b")
        probe.wait("Actions / choices", absent=True)
        probe.send(b"keep original text\x1b[1;2D\x1b[1;2D")
        action(probe, "Recipe files", "Recipe files · local candidates")
        probe.send(b"review-me.yaml\r")
        probe.wait("Recipe file review added to draft")
        # Selection is cancelled and request appended, never replacing selected text.
        draft_is(probe, "keep original text")
        draft_is(probe, "Please read and validate")
        capture(probe, "recipe-file-draft-retained")
    finally:
        probe.close()
    rows = [
        json.loads(line)
        for path in (state / "conversations").glob("*/events.jsonl")
        for line in path.read_text().splitlines()
    ]
    assert rows and not any(row["kind"] == "turn.accepted" for row in rows)


def test_real_goal_action_is_unsent_then_local_and_clearable(tmp_path):
    from interaction_probe import action

    state = tmp_path / "state"
    probe = Probe(
        [
            sys.executable,
            str(ROOT / "scripts/run.py"),
            "--no-install",
            "--fixture",
            "--cwd",
            str(tmp_path),
            "--state-dir",
            str(state),
        ]
    )
    try:
        probe.wait("Ready")
        action(probe, "Goal — set", "Command inserted")
        draft_is(probe, "/goal --max-turns 5")
        probe.send(b"Verify the isolated fixture\r")
        probe.wait("Goal set (max 5 turns)")
        capture(probe, "cli-controls-goal-local")
        probe.send(b"\x1b[200~/goal clear\x1b[201~\r")
        probe.wait("Goal cleared")
        probe.send(b"/provider use fixture\r")
        probe.wait("Command inserted")
        draft_is(probe, "/provider use fixture")
        probe.send(b"\r")
        probe.wait("Conversation provider saved")
    finally:
        probe.close()
    rows = [
        json.loads(line)
        for path in (state / "conversations").glob("*/events.jsonl")
        for line in path.read_text().splitlines()
    ]
    assert rows and not any(row["kind"] == "turn.accepted" for row in rows)


def test_transient_auth_prompts_do_not_steal_focus_or_become_history(tmp_path):
    from interaction_probe import action

    code = """
import json, sys
def emit(v): print(json.dumps({'version':1, **v}), flush=True)
emit({'type':'snapshot','ready':True,'session_id':'auth-fixture','mode':'FIXTURE RUNTIME','items':[]})
for line in sys.stdin:
 r=json.loads(line)
 if r['op']=='shutdown': break
 if r['op']=='submit':
  emit({'type':'reply','request_id':r['request_id'],'accepted':True})
  emit({'type':'auth_prompt','session_id':'auth-fixture','active':True,'text':'SYNTHETIC-CODE-ONLY'})
 elif r['op']=='stop':
  emit({'type':'auth_prompt','session_id':'auth-fixture','active':False,'text':'Prompts cleared'})
"""
    probe = Probe(
        [
            str(ROOT / "frontends/ratatui/target/release/amplifier-ratatui"),
            "--host-json",
            json.dumps([sys.executable, "-c", code]),
        ]
    )
    try:
        probe.wait("Enter send")
        probe.send(b"\x1b[200~/provider login fixture\x1b[201~\r")
        probe.wait("Login instructions available")
        assert "SYNTHETIC-CODE-ONLY" not in probe.text
        probe.send(b"retained unsent draft")
        action(probe, "Provider login prompt", "SYNTHETIC-CODE-ONLY")
        capture(probe, "cli-controls-auth-transient")
        probe.send(b"\x1b")
        probe.wait("Actions / choices", absent=True)
        draft_is(probe, "retained unsent draft")
        assert "SYNTHETIC-CODE-ONLY" not in probe.text
        action(probe, "Provider login prompt", "SYNTHETIC-CODE-ONLY")
        probe.send(b"\r")
        probe.wait("Prompts cleared")
        draft_is(probe, "retained unsent draft")
        assert "SYNTHETIC-CODE-ONLY" not in probe.text
        action(probe, "Provider login prompt", "No login prompt active")
        assert "Stop login" not in probe.text
    finally:
        probe.close()

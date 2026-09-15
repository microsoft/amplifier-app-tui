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
        assert bottom - top == 2
        assert "Ready" in probe.screen.display[top + 4]
        assert "F1 Work" not in probe.text
        assert "[ Stop ]" not in probe.text
        assert "Mode: unavailable" in probe.text
        assert top == probe.rows - 5
        assert "A short reply." in probe.text
        assert not any(c in probe.text for c in "╭╮╰╯│")
        assert "Ratatui" not in probe.text
        capture(probe, "compact-idle")
        probe.send(b"\x1b[200~first\nsecond\nthird\x1b[201~")
        settle(probe)
        top, bottom = composer_rows(probe)
        assert bottom - top == 4
        capture(probe, "compact-multiline")
        # A wrapped single logical line must navigate inside the draft before history.
        probe.send(b"\x1b[200~" + b"x" * 150 + b"\x1b[201~")
        settle(probe)
        assert composer_rows(probe)[1] - composer_rows(probe)[0] >= 5
        probe.resize(40, 24)
        probe.wait("[Modes]")
        assert "Mode: unavailable" in probe.text
        assert composer_rows(probe)[1] - composer_rows(probe)[0] <= 7
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
        lines = probe.screen.display[top + 1 : bottom]
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
        assert probe.screen.display[top + 1] == "x" * cols
        assert probe.screen.display[top + 2].rstrip() == "NEXT"
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

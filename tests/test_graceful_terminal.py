"""Actual terminal input and offline runtime; no live model calls."""

import json
import os
import signal
import sys
import time

import pytest
import yaml
from test_brand_terminal import samples
from test_session_repairs_terminal import ROOT, Probe, capture, draft_is, wait_ready

pytestmark = pytest.mark.skipif(
    os.environ.get("TUI_TEST_CANDIDATES") != "1", reason="Build native client"
)


@pytest.mark.parametrize("size", [(175, 50), (40, 20), (32, 12)])
async def test_two_stage_cancel_then_default_no_exit(tmp_path, size):
    overlay = tmp_path / "slow.yaml"
    overlay.write_text(
        yaml.safe_dump(
            {
                "bundle": {"name": "graceful-terminal-fixture"},
                "providers": [{"module": "provider-fixture", "config": {"delay": 20}}],
            }
        )
    )
    state = tmp_path / "state"
    probe = Probe(
        [
            sys.executable,
            str(ROOT / "scripts/run.py"),
            "--no-install",
            "--fixture",
            "--overlay",
            str(overlay),
            "--state-dir",
            str(state),
        ],
        cols=size[0],
        rows=size[1],
        cwd=tmp_path,
    )
    try:
        wait_ready(probe)
        probe.send(b"Start slow controlled request\r")
        probe.wait("Working")
        probe.read(0.2)
        probe.send(b"Retain this draft\x03")
        probe.wait("Finishing current calls")
        probe.read(0.4)
        assert probe.process.poll() is None
        assert "Ctrl-C again" in probe.text
        assert "Stopping" in probe.text and "0 calls" in probe.text
        before = probe.text
        # read(timeout) returns on the next paint, not after timeout seconds.
        # Observe a genuinely quiet drain interval, not just two adjacent frames.
        deadline = time.monotonic() + 2.2
        while time.monotonic() < deadline:
            probe.read(0.05)
        assert probe.text != before and "Stopping" in probe.text
        assert "0 calls" in probe.text
        draft_is(probe, "Retain this draft")
        capture(probe, f"graceful-force-before-{size[0]}")
        # Key repeat must not escalate; second physical press does.
        probe.send(b"\x1b[99;5:2u\x1b[99;5:3u")
        probe.read(0.1)
        assert "Finishing current calls" in probe.text
        probe.send(b"\x03")
        probe.wait("Stopping now")
        probe.wait("Stopped", timeout=5)
        assert probe.process.poll() is None
        draft_is(probe, "Retain this draft")
        source = next((state / "conversations").iterdir())
        checkpoint = json.loads((source / "checkpoint.json").read_text())
        assert checkpoint["status"] == "ready"
        probe.send(b"\x03")
        probe.wait("Quit Amplifier?")
        assert "› No, stay here" in probe.text
        capture(probe, f"graceful-confirm-{size[0]}")
        probe.send(b"\x1b[200~yes\n\x1b[201~")  # Paste cannot confirm or send.
        probe.read(0.1)
        assert "› No, stay here" in probe.text and probe.process.poll() is None
        probe.send(b"\r")
        probe.wait("Quit Amplifier?", absent=True)
        draft_is(probe, "Retain this draft")
        probe.send(b"\x03")
        probe.wait("Quit Amplifier?")
        probe.send(b"\x1b")
        probe.wait("Quit Amplifier?", absent=True)
        probe.send(b"\x03")
        probe.wait("Quit Amplifier?")
        probe.send(b"\x1b[B\r")  # Choose Yes explicitly.
        probe.process.wait(timeout=4)
    finally:
        probe.close()


@pytest.mark.parametrize("size", [(175, 50), (40, 20), (32, 12)])
@pytest.mark.parametrize("treatment", ["animated", "reduced", "plain"])
def test_negative_stop_states_and_quiet_clocks(size, treatment):
    program = r"""
import json,sys,threading,time
stops=0
def emit(**v): print(json.dumps({'version':1,'session_id':'stop-style-fixture',**v}),flush=True)
def delegate(status, seconds):
 emit(type='item',id='delegate',kind='tool',text='delegate',status=status,
      detail=json.dumps({'name':'delegate','child_progress':[{'child_id':'child','agent':'fixture #1',
      'status':status,'activity':'Thinking' if status=='running' else 'interrupted','elapsed_seconds':seconds,'calls':0}]}))
emit(type='snapshot',ready=True,mode='TRANSPORT FIXTURE',title='Stop style fixture',items=[])
emit(type='mode_status',current=None,supported=True)
emit(type='state',ready=True,busy=False,status='Ready')
for line in sys.stdin:
 r=json.loads(line)
 if r['op']=='shutdown':break
 if r['op']=='submit':
  emit(type='reply',request_id=r['request_id'],accepted=True)
  emit(type='state',turn_id='turn',ready=True,busy=True,status='Working')
  emit(type='turn_metrics',turn_id='turn',elapsed_seconds=3605,turn={'calls':0,'cost':'pending'},session={'cost':'$1.23'})
  delegate('running',5)
 if r['op']=='stop':
  stops+=1
  emit(type='state',turn_id='turn',ready=True,busy=True,
       status='Finishing current calls; Ctrl-C again to force stop' if stops==1 else 'Stopping now; partial effects may remain',
       cancellation='graceful' if stops==1 else 'immediate')
  if stops==2:
   def finish():
    time.sleep(2)
    delegate('interrupted',12)
    emit(type='item',id='end',kind='outcome',text='Stopped; partial effects may remain',status='interrupted',detail='')
    emit(type='state',ready=True,busy=False,status='Stopped; partial effects may remain')
   threading.Thread(target=finish,daemon=True).start()
"""
    env = {
        "AMPLIFIER_TUI_THEME": "dark",
        "AMPLIFIER_TUI_REDUCED_MOTION": "1" if treatment == "reduced" else "0",
        **({"NO_COLOR": "1"} if treatment == "plain" else {}),
    }
    probe = Probe(
        [
            str(ROOT / "frontends/ratatui/target/release/amplifier-ratatui"),
            "--host-json",
            json.dumps([sys.executable, "-u", "-c", program]),
        ],
        cols=size[0],
        rows=size[1],
        env=env,
    )
    red = "default" if treatment == "plain" else "f85149"

    def colour(label):
        observed = samples(probe, label, 0.1)
        assert observed and all(set(shades) == {red} for shades in observed), (label, observed)

    try:
        probe.wait("Ready")
        probe.send(b"Controlled wait\r")
        probe.wait("1h 00m 05s")
        probe.send(b"Keep draft\x03")
        probe.wait("Finishing current calls")
        probe.wait("1h 00m 07s", timeout=5)
        colour("Ctrl-C again")
        colour("Finishing current calls")
        colour("[Force")
        # Tiny views replace the bullet with an upward-history cue.
        shades = samples(probe, "Stopping")
        assert shades
        assert (len(shades) > 1) == (treatment == "animated")
        if treatment != "animated":
            assert all(set(shade) == {red} for shade in shades)
        probe.wait("1h 00m 09s", timeout=5)
        assert "Session $1.23" in probe.text and "0 calls" in probe.text
        if size[0] == 175:
            row = next(row for row in probe.screen.display if " · running · " in row)
            assert " · 9s · " in row or " · 10s · " in row, row
            from interaction_probe import action

            action(probe, "Interact", "Interact ·")
            probe.wait("1h 00m 11s", timeout=5)
            row = next(row for row in probe.screen.display if " · running · " in row)
            assert " · 11s · " in row or " · 12s · " in row, row
            capture(probe, f"stop-style-interact-{treatment}-{size[0]}")
            probe.send(b"\x1b")
            probe.wait("Interact ·", absent=True)
        draft_is(probe, "Keep draft")
        capture(probe, f"stop-style-draining-{treatment}-{size[0]}")
        probe.send(b"\x03")
        probe.wait("Stopping now")
        colour("Stopping now")
        assert "1h 00m" in probe.text and "Session $1.23" in probe.text
        capture(probe, f"stop-style-force-{treatment}-{size[0]}")
        probe.wait("Stopped")
        probe.wait("[ Send ]")
        colour("Stopped")
        capture(probe, f"stop-style-stopped-{treatment}-{size[0]}")
        assert "● Stopping" not in probe.text and "1h 00m" not in probe.text
        draft_is(probe, "Keep draft")
        before = probe.bytes
        samples(probe, "Stopped", 1.2)
        assert probe.bytes == before, "Completed work must stop ticking"
    finally:
        probe.close()


def test_sigint_is_not_an_exit_confirmation():
    program = """
import json, sys
print(json.dumps({'version':1,'type':'state','ready':True,'busy':False,'status':'Ready'}),flush=True)
for line in sys.stdin:
 if json.loads(line)['op']=='shutdown': break
"""
    command = [
        str(ROOT / "frontends/ratatui/target/release/amplifier-ratatui"),
        "--host-json",
        json.dumps([sys.executable, "-u", "-c", program]),
    ]
    probe = Probe(command, cols=175, rows=50)
    try:
        probe.wait("Ready")
        probe.process.send_signal(signal.SIGINT)
        probe.wait("Quit Amplifier?")
        probe.process.send_signal(signal.SIGINT)
        probe.wait("Quit Amplifier?", absent=True)
        assert probe.process.poll() is None
        probe.send(b"\x03")
        probe.wait("Quit Amplifier?")
        # Actual clickable choices are available while the confirmation owns the mouse.
        from interaction_probe import click

        click(probe, "No, stay here")
        probe.wait("Quit Amplifier?", absent=True)
        assert probe.process.poll() is None
        probe.send(b"\x03")
        probe.wait("Quit Amplifier?")
        click(probe, "Yes, quit")
        probe.process.wait(timeout=4)
    finally:
        probe.close()

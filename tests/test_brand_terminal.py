"""Observe actual terminal cells and input, with explicitly controlled transport."""

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

pytestmark = pytest.mark.skipif(
    os.environ.get("TUI_TEST_CANDIDATES") != "1", reason="Build native client"
)

PROGRAM = r"""
import json, sys, time, threading
def emit(**v):
 print(json.dumps({'version':1,'session_id':'brand-fixture',**v}),flush=True)
emit(type='snapshot',ready=False,mode='TRANSPORT FIXTURE',title='Brand fixture',items=[])
emit(type='mode_status',current=None,supported=True)
emit(type='background',phase='Loading fixture bundle')
def ready():
 time.sleep(2)
 emit(type='background',phase='')
 emit(type='state',ready=True,busy=False,status='Ready')
threading.Thread(target=ready,daemon=True).start()
for line in sys.stdin:
 r=json.loads(line)
 if r['op']=='shutdown': break
 if r['op']=='submit':
  emit(type='reply',request_id=r['request_id'],accepted=True)
  emit(type='item',id='user',kind='user',text='Review the controlled fixture',status='accepted',detail='')
  emit(type='item',id='reply',kind='assistant',text='Inspecting the fixture.\n\n```python\ndef check():\n    return "sample"\n```',status='completed',detail='')
  emit(type='state',turn_id='one',ready=True,busy=True,status='Working')
  emit(type='turn_metrics',turn_id='one',elapsed_seconds=125,turn={'calls':8,'tokens':1234567,'cost':'$1.23'},session={'cost':'$4.56'})
 if r['op']=='stop':
  emit(type='state',turn_id='one',ready=True,busy=False,status='Ready')
"""


def samples(probe, label, duration=0.7):
    observed = set()
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        probe.read(0.02)
        for y, row in enumerate(probe.screen.display):
            if label in row:
                x = row.index(label)
                observed.add(tuple(probe.screen.buffer[y][n].fg for n in range(x, x + len(label))))
    return observed


def test_lost_runtime_does_not_keep_animating_stale_work():
    # Exit the actual host pipe after submitting, not just a synthetic status label.
    program = PROGRAM.replace(" if r['op']=='stop':", "  break\n if r['op']=='stop':")
    p = Probe(
        [
            str(ROOT / "frontends/ratatui/target/release/amplifier-ratatui"),
            "--host-json",
            json.dumps([sys.executable, "-u", "-c", program]),
        ],
        cols=175,
        rows=50,
        env={"AMPLIFIER_TUI_THEME": "dark", "AMPLIFIER_TUI_REDUCED_MOTION": "0"},
    )
    try:
        p.wait("Ready")
        p.send(b"Start controlled work\r")
        p.wait("Disconnected")
        assert "● Working" not in p.text and "Loading fixture bundle" not in p.text
        samples(p, "Disconnected", 0.4)
        before = p.bytes
        samples(p, "Disconnected", 1.2)
        assert p.bytes == before, "Disconnected observations must not tick or shimmer"
        p.send(b"Keep this unsent")
        p.wait("Keep this unsent")
    finally:
        p.close()


@pytest.mark.parametrize("size", [(175, 50), (40, 20), (32, 12)])
@pytest.mark.parametrize("treatment", ["animated", "reduced", "plain"])
def test_brand_activity_and_static_fallback_keep_input_and_terminal_ownership(size, treatment):
    env = {
        "AMPLIFIER_TUI_THEME": "dark",
        "AMPLIFIER_TUI_REDUCED_MOTION": "1" if treatment == "reduced" else "0",
    }
    if treatment == "plain":
        env["NO_COLOR"] = "1"
    p = Probe(
        [
            str(ROOT / "frontends/ratatui/target/release/amplifier-ratatui"),
            "--host-json",
            json.dumps([sys.executable, "-u", "-c", PROGRAM]),
        ],
        cols=size[0],
        rows=size[1],
        env=env,
    )
    try:
        p.wait("Loading fixture bundle")
        shades = samples(p, "Loading fixture bundle")
        assert (len(shades) > 1) == (treatment == "animated")
        p.wait("Ready")
        p.send(b"Start controlled work\r")
        p.wait("Turn usage:")
        p.wait("Session $4.56")
        p.send(b"\x1b[200~Keep this draft\x1b[201~")
        p.wait("Keep this draft")
        if treatment != "plain":
            y = next(y for y, row in enumerate(p.screen.display) if "Keep this draft" in row)
            x = p.screen.display[y].index("Keep this draft")
            assert p.screen.buffer[y][x].bg == "1a1f2b"
            assert p.screen.buffer[y][x].fg == "f0f6ff"
        before = p.bytes
        shades = samples(p, "Working")
        assert (len(shades) > 1) == (treatment == "animated")
        assert p.bytes - before < 16000, (
            "Quiet animation must stay a small diff, not a full-screen repaint"
        )
        assert "Keep this draft" in p.text
        capture(p, f"brand-{treatment}-{size[0]}x{size[1]}")
        if treatment == "animated":
            action(p, "Interact", "Interact ·")
            assert len(samples(p, "Working")) > 1
            p.send(b"\x1b")
            p.wait("Interact ·", absent=True)
            p.wait("Keep this draft")
        p.send(b"\x18")
        p.wait("Ready")
        samples(p, "Ready", 0.4)  # drain the final paint and draft debounce
        before = p.bytes
        samples(p, "Ready", 1.2)
        assert p.bytes == before, "Idle must not animate or emit timer rows"
        assert "Working" not in p.text
        assert b"\x1b[3J" not in p.raw  # never purge native scrollback
    finally:
        p.close()

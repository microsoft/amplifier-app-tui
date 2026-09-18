"""Painted semantic roles in real native PTYs; invented transport evidence only."""

import time

import pytest
from test_brand_terminal import samples
from test_readable_work_terminal import action, capture, launch, pytestmark, reveal  # noqa: F401

PROGRAM = r"""
import json,sys
def emit(**v):
 print(json.dumps({'version':1,'session_id':'action-fixture',**v}),flush=True)
def tool(identity,name,status,args,**detail):
 emit(type='item',id=identity,kind='tool',text=name,status=status,
      detail=json.dumps({'name':name,'status':status,'arguments':args,**detail}))
emit(type='snapshot',ready=True,mode='TRANSPORT FIXTURE',title='Action styling fixture',items=[])
emit(type='mode_status',current=None,supported=True)
emit(type='state',ready=True,busy=False,status='Ready')
for line in sys.stdin:
 r=json.loads(line)
 if r['op']=='shutdown': break
 if r['op']=='submit':
  emit(type='reply',request_id=r['request_id'],accepted=True)
  emit(type='state',ready=True,busy=True,turn_id='one',status='Working')
  emit(type='turn_metrics',turn_id='one',elapsed_seconds=12,turn={'calls':3,'tokens':1025,'cost':'$0.03'},session={'cost':'$0.05'})
  if r['text']=='Mixed':
   tool('read','read_file','succeeded',{'file_path':'src/example.py'})
   tool('search','grep','succeeded',{'pattern':'cancellation handlers'})
   tool('failure','bash','failed',{'command':'check fixture'},result={'error':{'message':'Fixture check failed'}})
   tool('unknown','custom_inspector','unknown',{'query':'fixture outcome'})
  if r['text'] in ('Mixed','Warnings'):
   tool('parent','delegate','succeeded',{'instruction':'Review parser without modifying it'},
        child_progress=[{'agent':'fixture:reviewer #1','task_title':'Review parser','status':'succeeded',
                         'activity':'Completed','calls':3,'elapsed_seconds':12,
                         'warnings':{'failed':2,'unknown':1},'notices':{'warning':1}}],child_cost_display='$0.03')
  if r['text'] in ('Mixed','Command'):
   tool('command','bash','running',{'command':"printf '%s\\n' 'fixture source'\n  echo done"},
        result={'output':'output row\n'*100})
 if r['op']=='stop':
  tool('command','bash','succeeded',{'command':"printf '%s\\n' 'fixture source'\n  echo done"},result={'output':'output row\n'*100})
  emit(type='state',ready=True,busy=False,status='Ready')
"""


def assert_colour(probe, label, colour, *, row_contains=None):
    observed = set()
    deadline = time.monotonic() + 0.15
    while time.monotonic() < deadline:
        probe.read(0.01)
        for y, row in enumerate(probe.screen.display):
            if label in row and (row_contains is None or row_contains in row):
                x = row.index(label)
                observed.add(tuple(probe.screen.buffer[y][n].fg for n in range(x, x + len(label))))
    assert observed and all(set(shades) == {colour} for shades in observed), (label, observed)


def test_semantic_actions_and_independent_child_badges_in_actual_cells(tmp_path):
    p = launch(tmp_path, (175, 50), program=PROGRAM)
    try:
        p.send(b"Mixed\r")
        p.wait("▸ Run · running")
        for label in ("Read", "Search", "Review parser"):
            assert_colour(p, label, "00d9f5")
        assert_colour(p, "done", "00d9f5", row_contains=" · done · ")
        for label in ("failed", "2 tool errors"):
            assert_colour(p, label, "f85149")
        for label in ("unknown", "1 hook warning"):
            assert_colour(p, label, "f1a640")
        for label in ("src/example.py", "fixture:reviewer #1", "$0.03"):
            assert_colour(p, label, "8e95a3")
        assert len(samples(p, "running", 1.0)) > 1
        assert len(samples(p, "Review parser", 1.0)) == 1
        p.send(b"Keep this draft")
        capture(p, "actions-laptop-native")
        action(p, "Interact", "Interact ·")
        assert_colour(p, "2 tool errors", "f85149")
        p.send(b"\r")
        p.wait("Request · bash command")
        p.wait("[preview excerpt;")
        p.wait("  echo done")
        capture(p, "actions-laptop-command")
        assert p.text.count("output row") == 8
        p.send(b"\x1b")
        p.wait("Interact ·", absent=True)
        p.wait("Keep this draft")
        p.send(b"\x18")
        p.wait("Ready")
        samples(p, "Ready", 0.3)
        before = p.bytes
        samples(p, "Ready", 1.0)
        assert p.bytes == before
        assert b"\x1b[3J" not in p.raw
    finally:
        p.close()


@pytest.mark.parametrize("size", [(40, 20), (32, 12)])
@pytest.mark.parametrize("treatment", ["animated", "reduced", "plain"])
def test_narrow_warning_priority_and_expansion_preserve_draft(tmp_path, size, treatment):
    p = launch(tmp_path, size, treatment, program=PROGRAM)
    try:
        p.send(b"Warnings\r")
        p.wait("2 tool errors")
        p.wait("done")
        assert_colour(p, "2 tool errors", "default" if treatment == "plain" else "f85149")
        assert_colour(p, "done", "default" if treatment == "plain" else "00d9f5")
        p.send(b"Keep draft")
        capture(p, f"actions-warning-{treatment}-{size[0]}")
        action(p, "Interact", "Interact ·")
        p.send(b"\r")
        reveal(p, "instruction: Review parser")
        capture(p, f"actions-detail-{treatment}-{size[0]}")
        p.send(b"\x1b")
        p.wait("Interact ·", absent=True)
        p.wait("Keep draft")
        # Drain the closing frame before checking immutable native history.
        deadline = time.monotonic() + 0.15
        while time.monotonic() < deadline:
            p.read(0.01)
        assert b"\x1b[3J" not in p.raw
    finally:
        p.close()

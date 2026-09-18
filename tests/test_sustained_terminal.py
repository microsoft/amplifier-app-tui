"""Actual native input/layout; explicitly synthetic sustained transport observations."""

import json
import os
import sys
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
import json, sys
from dataclasses import asdict
from amplifier_tui.events import Event, Transcript
from amplifier_tui.inspection import Inspection
from amplifier_tui.children import task_title
TITLES = False
instructions = [
 'Task: Map startup paths\nRead the entry points without changing files.',
 'Task: Review file tools\nCheck the read and write operations without changing files.',
 'Task: Audit persistence\nCheck saved records without changing files.',
 'Task: Check resume handling\nPreserve the original task instructions and saved state.',
]
t, activity, sequence = Transcript(), Inspection(), 0
def emit(**value):
 print(json.dumps({'version':1,'session_id':'sustained-fixture',**value}),flush=True)
def event(kind, key, **payload):
 global sequence
 sequence += 1
 e=Event('sustained-fixture',sequence,'turn',kind,key,payload)
 t.apply(e); activity.observe(e)
 if key in t.items:
  value=asdict(t.items[key]); value['detail']=json.dumps(value['detail'])
  emit(type='item',**value)
emit(type='snapshot',ready=True,mode='TRANSPORT FIXTURE',title='Sustained work fixture',items=[])
emit(type='mode_status',current=None,supported=True)
emit(type='state',ready=True,busy=False,status='Ready')
for line in sys.stdin:
 r=json.loads(line)
 if r['op']=='shutdown': break
 if r['op']=='submit':
  emit(type='reply',request_id=r['request_id'],accepted=True)
  if 'pasted' in r['text']:
   event('text.final','reply',text='Pasted message reached the host')
   continue
  event('turn.accepted','user',text='Review four controlled areas')
  emit(type='state',turn_id='turn',ready=True,busy=True,status='Working')
  for n in range(4):
   event('tool.updated',f'parent-{n}',name='load_skill' if n==0 else 'delegate',status='running',arguments={'instruction':instructions[n] if TITLES else f'Inspect area {n}'})
   event('tool.updated',f'child:{n}',name=f'Agent · explorer #{n+1}',status='running',child_id=str(n),parent_item_id=f'parent-{n}')
   event('activity.observed',f'notice-{n}',child_id=str(n),parent_item_id=f'child:{n}',name='fixture-hook',event='display.message',status='warning' if n==2 else 'observed',block={'type':'text','text':'Controlled child notice'})
  for call in range(20):
   for n in range(4):
    event('display.message',f'usage-{n}-{call}',source='usage',text=f'Call {call} · controlled/model · Input: 100 · Cost: $0.01',usage_call={'cost_usd':'0.01'},child_id=str(n),parent_item_id=f'child:{n}')
    cost = f'${(call + 1) / 100:.2f}'
    event('tool.progress',f'parent-{n}',child_progress=[{'child_id':str(n),'agent':'Skill · fixture-review #1' if n==0 else f'explorer #{n+1}','status':'running','activity':'read_file · running','calls':call+1,'cost_usd':str((call+1)/100),'cost_display':cost,'tools_completed':call*3,'warnings':{'failed':int(n==1)},'notices':{'warning':int(n==2),'error':0},'elapsed_seconds':call*7,**(task_title(instructions[n]) if TITLES else {})}],child_cost_usd=str((call+1)/100),child_cost_display=cost,child_cost_partial=False)
  if TITLES:
   emit(type='turn_metrics',turn_id='turn',elapsed_seconds=133,
        turn={'calls':80,'tokens':8400,'cost':'$0.80'},session={'cost':'$1.20'})
 if r['op']=='stop':
  for n in range(4):
   event('tool.updated',f'parent-{n}',name='delegate',status='succeeded')
   event('tool.updated',f'child:{n}',name='Agent',status='succeeded',child_id=str(n),parent_item_id=f'parent-{n}')
  event('text.final','reply',text='Controlled review complete')
  event('display.message','usage-root',source='usage',text='Root call · Input: 100 · Cost: $0.01',usage_call={'cost_usd':'0.01'})
  event('display.message','total',source='usage',text='Turn: $0.81 · Session: $0.81',usage_summary=True)
  event('turn.ended','end',status='completed')
  emit(type='state',ready=True,busy=False,status='Ready')
 if r['op']=='inspect':
  emit(type='inspection',request_id=r['request_id'],category='activity_tree',**activity.activity_tree(r.get('child')))
"""


@pytest.mark.parametrize("size", [(175, 50), (40, 20), (32, 12)])
def test_sustained_delegates_are_compact_expandable_and_paste_sends(size):
    p = Probe(
        [
            str(ROOT / "frontends/ratatui/target/release/amplifier-ratatui"),
            "--host-json",
            json.dumps([sys.executable, "-u", "-c", PROGRAM]),
        ],
        cols=size[0],
        rows=size[1],
    )
    try:
        p.wait("Ready")
        p.send(b"Start controlled work\r")
        p.wait("#4")
        if size[0] == 175:
            p.wait("20 calls")
            assert p.text.count("20 calls") == 4
            assert p.text.count("$0.20") == 4
            p.wait("Skill · fixture-review #1")
            p.wait("2m 13s")
        if size[1] >= 20:
            p.wait("1 tool error")
            p.wait("1 hook warning")
        else:
            p.wait("earlier rows")
        assert "Call 0" not in p.text and "Input: 100" not in p.text
        assert "Controlled child notice" not in p.text
        capture(p, f"sustained-running-{size[0]}x{size[1]}")
        if size[1] < 20:
            action(p, "Interact", "Interact ·")
            p.send(b"\x1b[A\x1b[A")
            p.wait("1 tool error")
            p.send(b"\x1b")
            p.wait("Interact ·", absent=True)
        action(p, "Interact", "Interact ·")
        # No Up/Down workaround: the initially selected row is expandable.
        p.send(b"\r")
        p.wait("Request")
        if size[1] < 20:
            p.send(b"\x1b[6~")  # Scroll the expanded preview, not whole items.
        p.wait("Inspect area 3")
        capture(p, f"sustained-expanded-{size[0]}x{size[1]}")
        p.send(b"\x1b")
        p.wait("Interact ·", absent=True)
        action(p, "Stop", "Turn: $0.81")
        if size[1] >= 20:
            p.wait("Controlled review complete")
        p.wait("Turn: $0.81")
        assert "Call 0" not in p.text
        action(p, "Interact", "Interact ·")
        p.send(b"\x1b[200~pasted message\x1b[201~")
        p.wait("pasted message")
        assert "Pasted message reached" not in p.text
        p.send(b"\r")
        p.send(b"\x1b")
        p.wait("Pasted message reached the host")
        capture(p, f"sustained-paste-{size[0]}x{size[1]}")
    finally:
        p.close()


@pytest.mark.parametrize("size", [(175, 50), (40, 20)])
def test_bounded_child_progress_keeps_full_counts_and_activity_access(size):
    prefix = PROGRAM[: PROGRAM.index("for line in sys.stdin:")]
    program = (
        prefix
        + r"""
from amplifier_tui.children import Children
for line in sys.stdin:
 r=json.loads(line)
 if r['op']=='shutdown': break
 if r['op']=='submit':
  emit(type='reply',request_id=r['request_id'],accepted=True)
  event('turn.accepted','user',text='Controlled admission display test')
  emit(type='state',ready=True,busy=True,status='Working')
  event('tool.updated','parent',name='delegate',status='running',arguments={'instruction':'Controlled retained child work'})
  summaries=[]
  for n in range(100):
   status='waiting_capacity' if n==0 else 'succeeded'
   event('tool.updated',f'child:{n}',name=f'Agent · probe #{n+1}',status=status,child_id=str(n),parent_item_id='parent',output='Controlled child receipt')
   summaries.append({'child_id':str(n),'agent':f'probe #{n+1}','status':status,
    'activity':'Waiting for agent capacity' if n==0 else 'Completed',
    'calls':2,'tools_completed':0,'cost_usd':'0.01','cost_display':'$0.01','cost_partial':False,
    'warnings':{'failed':1 if n==20 else 0,'unknown':0,'interrupted':0}})
  event('tool.progress','parent',**Children.progress_payload(summaries))
 if r['op']=='inspect':
  emit(type='inspection',request_id=r['request_id'],category='activity_tree',**activity.activity_tree(r.get('child')))
"""
    )
    p = Probe(
        [
            str(ROOT / "frontends/ratatui/target/release/amplifier-ratatui"),
            "--host-json",
            json.dumps([sys.executable, "-u", "-c", program]),
        ],
        cols=size[0],
        rows=size[1],
    )
    try:
        p.wait("Ready")
        p.send(b"Inspect controlled admission\r")
        p.wait("1 tool error")
        if size[0] == 175:
            for marker in (
                "100 agents",
                "200 calls",
                "$1.00",
                "68 earlier in Activity",
                "Waiting for agent capacity",
            ):
                p.wait(marker)
        capture(p, f"admission-progress-{size[0]}x{size[1]}")
        action(p, "Interact", "Interact ·")
        p.send(b"\r")
        p.wait("Request")
        assert "Controlled retained child work" in " ".join(p.text.split())
        capture(p, f"admission-expanded-{size[0]}x{size[1]}")
        p.send(b"\x1b")
        p.wait("Interact ·", absent=True)
        action(p, "Activity", "Activity ·")
        p.send(b"\r")
        p.wait("probe #1")
        capture(p, f"admission-activity-{size[0]}x{size[1]}")
    finally:
        p.close()


@pytest.mark.parametrize("size", [(175, 50), (40, 20), (32, 12)])
def test_task_titles_and_original_instructions_are_readable_in_the_terminal(size):
    p = Probe(
        [
            str(ROOT / "frontends/ratatui/target/release/amplifier-ratatui"),
            "--host-json",
            json.dumps(
                [sys.executable, "-u", "-c", PROGRAM.replace("TITLES = False", "TITLES = True")]
            ),
        ],
        cols=size[0],
        rows=size[1],
    )
    try:
        p.wait("Ready")
        p.send(b"Start controlled titles\r")
        p.wait("Check resume")
        p.wait("Session $1.20")
        if size[0] == 175:
            for title in ("Map startup paths", "Review file tools", "Audit persistence"):
                p.wait(title)
            p.wait("20 calls")
            p.wait("Skill · fixture-review #1")
            p.wait("1 tool error")
            p.wait("1 hook warning")
        capture(p, f"titles-native-{size[0]}x{size[1]}")
        action(p, "Interact", "Interact ·")
        p.wait("Check resume")
        capture(p, f"titles-interact-{size[0]}x{size[1]}")
        p.send(b"\r")
        if size[1] < 20:
            p.send(b"\x1b[6~\x1b[6~")
        p.wait("Request")
        # Expanded source is line-scrolled at tiny sizes, never replaced with a title.
        if size[1] < 20:
            p.send(b"\x1b[6~\x1b[6~\x1b[6~")
        p.wait("Preserve the original")
        capture(p, f"titles-expanded-{size[0]}x{size[1]}")
        p.send(b"\x1b")
        p.wait("Interact ·", absent=True)
        action(p, "Stop", "Turn: $0.81")
    finally:
        p.close()

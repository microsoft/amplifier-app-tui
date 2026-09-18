"""Real native input/cells, explicitly synthetic transport and invented task content."""

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
from test_brand_terminal import samples  # noqa: E402

pytestmark = pytest.mark.skipif(
    os.environ.get("TUI_TEST_CANDIDATES") != "1", reason="Build native client"
)

PROGRAM = r"""
import json, sys
turn=0
def emit(**v):
 print(json.dumps({'version':1,'session_id':'readable-fixture',**v}),flush=True)
def item(identity,kind,detail,status='info',text=''):
 emit(type='item',id=identity,kind=kind,text=text,status=status,detail=json.dumps(detail))
emit(type='snapshot',ready=True,mode='TRANSPORT FIXTURE',title='Readable work fixture',items=[])
emit(type='mode_status',current=None,supported=True)
emit(type='state',ready=True,busy=False,status='Ready')
for line in sys.stdin:
 r=json.loads(line)
 if r['op']=='shutdown': break
 if r['op']=='submit':
  turn+=1
  with open(sys.argv[1],'a') as f: f.write(json.dumps(r['text'])+'\n')
  emit(type='reply',request_id=r['request_id'],accepted=True)
  item('user-'+str(turn),'user',{},text=r['text'])
  emit(type='state',ready=True,busy=True,turn_id=str(turn),status='Working')
  emit(type='turn_metrics',turn_id=str(turn),elapsed_seconds=12,turn={'calls':1,'tokens':1025,'cost':'$0.01'},session={'cost':'$0.01'})
  if turn==1:
   todos=[{'content':'Inspect source files','activeForm':'Inspecting source files','status':'completed'},
          {'content':'Check terminal layout','activeForm':'Checking terminal layout','status':'in_progress'},
          {'content':'Review captured result','activeForm':'Reviewing captured result','status':'pending'}]
   item('todo','tool',{'name':'todo','status':'succeeded','arguments':{'action':'update','todos':todos},'result':{'success':True,'output':{'status':'updated','count':3,'completed':1,'in_progress':1,'pending':1}}},'succeeded','todo')
   usage='Usage · fixture/test-model · pinned · 2.5s · 2026-01-01 12:00:00 UTC\nInput: 1,000 (90% cached) · Output: 25 · Total: 1,025 · Cost: $0.012345'
   item('usage','notice',{'source':'usage','text':usage,'provider':{'model':'test-model','provider':'fixture','basis':'pinned'},'duration_ms':2500,'usage_call':{'input_tokens':1000,'output_tokens':25,'cost_usd':'0.012345'}},text=usage)
   item('tool','tool',{'name':'bash','arguments':{'command':'inspect controlled fixture'},'status':'running'},'running','bash')
   if r['text']=='Wait for user':
    emit(type='state',ready=True,busy=True,turn_id=str(turn),status='Waiting',approval={'id':'fixture-decision','command':'Review fixture action','options':['Allow once','Deny']})
  else:
   emit(type='model_activity',turn_id=str(turn),phase='Thinking')
   emit(type='model_activity',turn_id='obsolete',phase='Stale phase')
   emit(type='model_activity',session_id='other',turn_id=str(turn),phase='Foreign phase')
 if r['op']=='stop':
  item('tool','tool',{'name':'bash','arguments':{'command':'inspect controlled fixture'},'status':'succeeded'},'succeeded','bash')
  item('totals','notice',{'source':'usage','usage_summary':True,'text':'Turn: $0.01 · Session: $0.01'},text='Turn: $0.01 · Session: $0.01')
  emit(type='state',ready=True,busy=False,turn_id=str(turn),status='Ready')
  emit(type='model_activity',turn_id=str(turn),phase='Late phase')
"""


def launch(tmp_path, size, treatment="animated", program=PROGRAM):
    env = {"AMPLIFIER_TUI_THEME": "dark", "AMPLIFIER_TUI_REDUCED_MOTION": "0"}
    if treatment == "reduced":
        env["AMPLIFIER_TUI_REDUCED_MOTION"] = "1"
    elif treatment == "plain":
        env["NO_COLOR"] = "1"
    p = Probe(
        [
            str(ROOT / "frontends/ratatui/target/release/amplifier-ratatui"),
            "--host-json",
            json.dumps([sys.executable, "-u", "-c", program, str(tmp_path / "sent.jsonl")]),
        ],
        cols=size[0],
        rows=size[1],
        env=env,
    )
    p.wait("Ready")
    return p


def reveal(probe, label):
    # A 12-row terminal has one inspection row beside retained input/accounting.
    # Exercise actual line scrolling instead of expecting the whole preview at once.
    for _ in range(24):
        deadline = time.monotonic() + 0.12
        while time.monotonic() < deadline:
            probe.read(0.01)
        if label in probe.text:
            return
        probe.send(b"\x1b[6~")
    probe.wait(label, timeout=1)


def test_usage_spacing_matches_native_and_inspection(tmp_path):
    program = PROGRAM.replace(
        "   item('tool','tool',",
        """   item('thinking','notice',{'source':'thinking','text':'Considering fixture'},text='Considering fixture')
   item('thinking-usage','notice',{'source':'usage','text':usage.replace('0.012345','0.023456'),'usage_call':{}},text='usage')
   item('response','assistant',{},'completed','Fixture response')
   item('response-usage','notice',{'source':'usage','text':usage.replace('0.012345','0.034567'),'usage_call':{}},text='usage')
   item('tool','tool',""",
    )
    p = launch(tmp_path, (175, 50), program=program)
    try:
        p.send(b"Spacing fixture\r")
        p.wait("▸ Run · running")
        for inspection in (False, True):
            if inspection:
                action(p, "Interact", "Interact ·")
            p.wait("0.034567")
            # Header/text can be visible before all cursor-addressed cells land.
            # This is a settled layout assertion, not a latency measurement.
            deadline = time.monotonic() + 0.15
            while time.monotonic() < deadline:
                p.read(0.01)
            rows = p.screen.display
            for cost, above in (("0.012345", "Checking terminal layout"), ("0.023456", "Thinking")):
                assert any(cost in line for line in rows), p.text
                at = next(i for i, line in enumerate(rows) if cost in line)
                assert above in rows[at - 1]
            at = next(i for i, line in enumerate(rows) if "0.034567" in line)
            assert not rows[at - 1].strip() and "Fixture response" in rows[at - 2]
            capture(p, "usage-spacing-inspection" if inspection else "usage-spacing-native")
    finally:
        p.close()


def test_running_tool_is_static_while_waiting_for_a_person(tmp_path):
    p = launch(tmp_path, (175, 50))
    try:
        p.send(b"Wait for user\r")
        p.wait("Review decision")
        p.wait("▸ Run · running")
        assert len(samples(p, "▸ Run · running", 1.0)) == 1
        # The footer also says Waiting in muted text; sample the actual meter,
        # not a union of separately styled status and decision labels.
        p.wait("● Waiting for your answer")
        assert len(samples(p, "● Waiting for your answer", 1.0)) == 1
        p.send(b"Keep a correction")
        p.wait("Keep a correction")
        capture(p, "readable-human-wait")
    finally:
        p.close()


@pytest.mark.parametrize("size", [(175, 50), (40, 20), (32, 12)])
def test_word_wrapped_paste_and_visual_navigation_send_exact_source(tmp_path, size):
    p = launch(tmp_path, size)
    # First word occupies almost a row; the next must move intact, not be split.
    source = "a" * (size[0] - 5) + " words intact\n界面 e\u0301lan 👩‍💻 path/to/long/file.txt"
    try:
        p.send(b"\x1b[200~" + source.encode() + b"\x1b[201~")
        p.wait("words intact")
        assert not (tmp_path / "sent.jsonl").exists(), "Paste must stay unsent"
        # Vertical movement stays inside the displayed draft, not recalled history.
        p.send(b"\x1b[A\x1b[B")
        capture(p, f"readable-composer-{size[0]}x{size[1]}")
        p.resize(175, 50)
        p.wait("words intact")
        p.send(b"\r")
        p.wait("▸ Run · running")
        assert json.loads((tmp_path / "sent.jsonl").read_text().splitlines()[0]) == source
    finally:
        p.close()


@pytest.mark.parametrize("size", [(175, 50), (40, 20), (32, 12)])
@pytest.mark.parametrize("treatment", ["animated", "reduced", "plain"])
def test_todo_usage_inspection_and_scoped_live_motion(tmp_path, size, treatment):
    p = launch(tmp_path, size, treatment)
    try:
        p.send(b"Review controlled work\r")
        p.wait("▸ Run · running")
        p.send(b"Keep my draft")
        before = p.bytes
        shades = samples(p, "▸ Run · running", 1.0)
        assert (len(shades) > 1) == (treatment == "animated")
        assert p.bytes - before < 24000
        capture(p, f"readable-native-{treatment}-{size[0]}x{size[1]}")
        action(p, "Interact", "Interact ·")
        p.wait("▸ Run · running")
        assert (len(samples(p, "▸ Run · running", 1.0)) > 1) == (treatment == "animated")
        # Latest selectable item is the running tool; Up selects the usage row.
        p.send(b"\x1b[A\r")
        reveal(p, "Input: 1,000")
        if size[0] >= 175:
            p.wait("Total: 1,025")
            p.wait("12:00:00 UTC")
        capture(p, f"readable-usage-{treatment}-{size[0]}x{size[1]}")
        p.send(b"\x1b[A\r")
        reveal(p, "[done]")
        if size[1] >= 20:
            p.wait("[active]")
        capture(p, f"readable-todo-{treatment}-{size[0]}x{size[1]}")
        p.send(b"\x1b")
        p.wait("Interact ·", absent=True)
        p.wait("Keep my draft")
        p.send(b"\x18")
        p.wait("Ready")
        assert "● Thinking" not in p.text and "Late phase" not in p.text
        samples(p, "Ready", 0.3)
        before = p.bytes
        samples(p, "Ready", 1.1)
        assert p.bytes == before
        # Submit the retained draft; observed thinking, not a guessed label.
        p.send(b"\r")
        p.wait("● Thinking")
        assert "Stale phase" not in p.text and "Foreign phase" not in p.text
        assert (len(samples(p, "Thinking", 1.0)) > 1) == (treatment == "animated")
        sent = [json.loads(s) for s in (tmp_path / "sent.jsonl").read_text().splitlines()]
        assert sent == ["Review controlled work", "Keep my draft"]
        assert b"\x1b[3J" not in p.raw
    finally:
        p.close()

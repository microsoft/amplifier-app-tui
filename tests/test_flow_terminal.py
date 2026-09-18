"""Actual terminal/input checks; controlled transport versus real fixture labelled."""

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from interaction_probe import action, capture, click  # noqa: E402
from terminal_probe import Probe  # noqa: E402
from test_workflow_terminal import events, start  # noqa: E402

pytestmark = pytest.mark.skipif(
    os.environ.get("TUI_TEST_CANDIDATES") != "1", reason="Build native client"
)


@pytest.mark.parametrize("size", [(175, 50), (40, 20), (32, 12)])
def test_startup_disconnect_stays_visible_after_enter_and_editing(size):
    program = """
import json
print(json.dumps({'version':1,'type':'snapshot','session_id':'disconnected-fixture',
 'mode':'TRANSPORT FIXTURE','title':'Disconnected startup fixture','ready':False,'items':[]}),flush=True)
"""
    p = Probe(
        [
            str(ROOT / "frontends/ratatui/target/release/amplifier-ratatui"),
            "--host-json",
            json.dumps([sys.executable, "-c", program]),
        ],
        cols=size[0],
        rows=size[1],
    )
    try:
        p.wait("Disconnected")
        p.send(b"Unsent recovery question\r")
        p.wait("Unsent recovery question")
        # Wait for the submitted-key frame, not a stale disconnect frame.
        p.read(0.15)
        assert "Starting" not in p.text and "Mode: loading" not in p.text
        assert "Session not ready" not in p.text
        assert "Disconnected" in p.text
        p.send(b" still editable")
        p.wait("editable")
        assert "Unsent recovery question still editable" in " ".join(p.text.split())
        assert p.process.poll() is None
        capture(p, f"startup-disconnected-{size[0]}")
    finally:
        p.close()


@pytest.mark.parametrize("size", [(175, 50), (40, 20), (32, 12)])
def test_working_meter_ticks_without_events_and_survives_inspection(size):
    # Controlled transport isolates the renderer's quiet clock from runtime timing.
    program = r"""
import json, sys, threading, time
turn = 0
def emit(**value):
 print(json.dumps({'version':1,'session_id':'meter-fixture',**value}),flush=True)
emit(type='snapshot',ready=True,mode='TRANSPORT FIXTURE',title='Turn meter fixture',items=[])
emit(type='state',ready=True,busy=False,status='Ready')
for line in sys.stdin:
 r=json.loads(line)
 if r['op']=='shutdown': break
 if r['op']=='submit':
  turn += 1
  emit(type='reply',request_id=r['request_id'],accepted=True)
  emit(type='item',id=f'user-{turn}',kind='user',text='Controlled quiet work',status='',detail='')
  emit(type='state',turn_id=str(turn),ready=True,busy=True,status='Working',
       approval={'id':'controlled-decision','command':'Controlled question','options':['Allow once','Deny']} if turn==3 else None)
  emit(type='turn_metrics',turn_id=str(turn),elapsed_seconds=125 if turn==1 else 0,
       turn=({'calls':8,'tokens':1234567,'cost':'$1.23'} if turn==1 else
             {'calls':2,'tokens':100,'tokens_partial':True,'cost':'$1.23 (partial)'} if turn==3 else
             {'calls':0,'tokens':None,'cost':'pending'}),
       session={'cost':'$4.56'},earlier_usage_unavailable=turn==3)
  # Stale identities must not replace current work, including after reset.
  emit(type='turn_metrics',turn_id='obsolete',elapsed_seconds=999,turn={'tokens':999,'cost':'$999.00'},session={'cost':'$999.00'})
  emit(type='turn_metrics',session_id='different-session',turn_id=str(turn),elapsed_seconds=999,turn={'tokens':999,'cost':'$999.00'},session={'cost':'$999.00'})
 if r['op']=='stop':
  emit(type='state',turn_id=str(turn),ready=True,busy=True,status='Stopping')
  def finish():
   time.sleep(1.5)
   emit(type='state',turn_id=str(turn),ready=True,busy=False,status='Ready')
  threading.Thread(target=finish,daemon=True).start()
"""
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
        p.send(b"Start controlled work\r")
        for text in ("2m 05s", "Turn $1.23", "Session $4.56", "Turn usage:", "8 calls"):
            p.wait(text)
        assert "$999" not in p.text
        p.send(b"\x1b[200~Keep my draft\x1b[201~")
        p.wait("Keep my draft")
        p.wait("2m 07s", timeout=5)  # no new host events or keypresses
        capture(p, f"meter-native-{size[0]}x{size[1]}")
        action(p, "Interact", "Interact ·")
        for text in ("Turn $1.23", "Session $4.56", "tokens", "Keep my draft"):
            p.wait(text)
        capture(p, f"meter-interact-{size[0]}x{size[1]}")
        p.send(b"\x1b")
        p.wait("Interact ·", absent=True)
        p.send(b"\x18")  # actual Stop binding
        p.wait("● Stopping")
        p.wait("Turn $1.23")
        p.wait("Ready")
        assert "● Working" not in p.text and "● Stopping" not in p.text
        p.wait("Keep my draft")
        p.send(b"\r")
        p.wait("tokens pending")
        p.wait("Turn pending")
        p.wait("Session $4.56")
        assert "Turn $1.23" not in p.text and "2m" not in p.text
        capture(p, f"meter-reset-{size[0]}x{size[1]}")
        p.send(b"\x18")
        p.wait("Ready")
        p.send(b"Show partial usage\r")
        for text in (
            "Waiting",
            "0s",
            "100 tokens (partial)",
            "Turn $1.23 (partial)",
            "Session $4.56",
            "[ Review decision ]",
        ):
            p.wait(text)
        capture(p, f"meter-waiting-{size[0]}x{size[1]}")
        from test_brand_terminal import samples

        assert len(samples(p, "Waiting")) == 1, "Human input waits must not shimmer as computation"
    finally:
        p.close()


@pytest.mark.parametrize("size", [(175, 50), (40, 20)])
def test_user_surfaces_dim_thinking_and_contiguous_final_usage(size):
    program = r"""
import json, sys
def emit(**value):
 print(json.dumps({'version':1,'session_id':'feedback-fixture',**value}),flush=True)
emit(type='snapshot',ready=True,mode='TRANSPORT FIXTURE',title='Feedback fixture',items=[])
emit(type='state',ready=True,busy=False,status='Ready')
for line in sys.stdin:
 request=json.loads(line)
 if request['op']=='shutdown': break
 if request['op']!='submit': continue
 emit(type='state',ready=True,busy=True,status='Working')
 for identity,kind,text,status,detail in [
  ('user','user','User authored message','accepted',{}),
  ('correction','correction','User authored correction','applied',{}),
  ('thought','notice','Thinking summary','info',{'source':'thinking','text':'**Inner monologue** and `code`.'}),
  ('reply','assistant','Conversation response','completed',{}),
  ('usage','notice','Input: 10 | Output: 2','info',{'source':'usage','text':'Input: 10 | Output: 2','usage_call':{'input_tokens':10}}),
  ('total','notice','Turn: $0.01 | Session: $0.02','info',{'source':'usage','text':'Turn: $0.01 | Session: $0.02'})]:
  emit(type='item',id=identity,kind=kind,text=text,status=status,detail=json.dumps(detail))
 emit(type='state',ready=True,busy=False,status='Completed')
"""
    p = Probe(
        [
            str(ROOT / "frontends/ratatui/target/release/amplifier-ratatui"),
            "--host-json",
            json.dumps([sys.executable, "-u", "-c", program]),
        ],
        cols=size[0],
        rows=size[1],
        env={"AMPLIFIER_TUI_THEME": "dark"},
    )
    try:
        p.wait("Ready")
        p.send(b"Show controlled feedback\r")
        p.wait("Turn: $0.01")
        lines = p.text.splitlines()
        total = next(n for n, line in enumerate(lines) if "Turn: $0.01" in line)
        assert "▸ Usage" in lines[total - 1]
        capture(p, f"feedback-native-{size[0]}x{size[1]}")
        action(p, "Interact", "Interact ·")
        p.send(b"\x1b[A\r")
        p.wait("[ Activity:")
        # Read actual painted terminal cells, not just source style declarations.
        row = next(
            n
            for n, line in enumerate(p.screen.display)
            if "Inner monologue" in line and "▸" not in line
        )
        col = p.screen.display[row].index("Inner monologue")
        assert p.screen.buffer[row][col].fg == "8e95a3"
        if size[0] == 175:
            for marker in ("User authored message", "User authored correction"):
                row = next(n for n, line in enumerate(p.screen.display) if marker in line)
                assert p.screen.display[row].startswith(marker)
                assert p.screen.buffer[row][0].bg == p.screen.buffer[row][size[0] - 1].bg
                assert p.screen.buffer[row][0].bg != "000000"
        capture(p, f"feedback-expanded-{size[0]}x{size[1]}")
    finally:
        p.close()


@pytest.mark.parametrize("size", [(175, 50), (40, 20), (32, 12)])
def test_inline_expansion_native_return_retains_unsent_draft(tmp_path, size):
    p = start(tmp_path)
    try:
        p.resize(*size)
        p.wait("Ready", timeout=30)
        p.send(b"Calculate a digest\r")
        if size[1] >= 20:
            p.wait("fixture_probe")
        p.wait_idle()
        # Completed primary rows may already be above the tiny native viewport;
        # the real tool result and inspectable source must still exist.
        assert any(
            e["kind"] == "tool.updated"
            and e["payload"].get("name") == "fixture_probe"
            and e["payload"].get("status") == "succeeded"
            for e in events(tmp_path)
        )
        p.send(b"Unsent inspection")
        action(p, "Interact", "Interact ·")
        p.send(b"\x1b[A\r")
        p.wait("Request")
        capture(p, f"flow-inline-{size[0]}x{size[1]}")
        p.send(b"\r")
        p.wait("Request", absent=True)
        click(p, "▸ fixture_probe")
        p.wait("Request")
        if size[0] >= 175:
            click(p, "[ Activity:")
            p.wait("Activity · fixture_probe")
            p.send(b"\x1b")
            p.wait("Actions / choices", absent=True)
        # Typing returns keyboard ownership to the composer without closing details.
        p.send(b" edited")
        p.wait("Unsent inspection edited")
        p.send(b"\x1b")
        p.wait("Interact ·", absent=True)
        p.wait("Unsent inspection edited")
        assert len([e for e in events(tmp_path) if e["kind"] == "turn.accepted"]) == 1
        assert p.raw.rfind(b"\x1b[?1000l") > p.raw.rfind(b"\x1b[?1000h")
    finally:
        p.close()


def test_immediate_welcome_named_startup_and_full_height_live_content():
    program = r"""
import json, sys, threading, time
def emit(**value):
 print(json.dumps({'version':1, 'session_id':'flow-fixture', **value}), flush=True)
def run():
 emit(type='snapshot', ready=False, mode='TRANSPORT FIXTURE', title='Flow fixture', items=[])
 emit(type='background', phase='Loading controlled bundle')
 time.sleep(1.2)
 emit(type='background', phase='')
 emit(type='state', ready=True, busy=False, status='Ready')
threading.Thread(target=run, daemon=True).start()
for line in sys.stdin:
 request=json.loads(line)
 if request['op']=='shutdown': break
 if request['op']=='submit':
  emit(type='state', ready=True, busy=True, status='Working')
  for n in range(4):
   detail={'name':'delegate','arguments':{'agent':'explorer','instruction':f'Inspect area-{n}'},
    'child_progress':[{'agent':'explorer', 'activity':f'read_file area-{n}', 'status':'running'}]}
   emit(type='item', id=f'tool-{n}', kind='tool', text='delegate', status='running', detail=json.dumps(detail))
   emit(type='item', id=f'child-{n}', kind='tool', text='Agent', status='running', detail=json.dumps({'name':'Agent', 'child_id':str(n), 'parent_item_id':f'tool-{n}', 'arguments':{'instruction':f'Hidden child source {n}'}}))
  emit(type='item', id='long', kind='assistant', text='  \n'.join(f'VISIBLE-LINE-{n:02}' for n in range(18)), status='streaming', detail='')
"""
    p = Probe(
        [
            str(ROOT / "frontends/ratatui/target/release/amplifier-ratatui"),
            "--host-json",
            json.dumps([sys.executable, "-u", "-c", program]),
        ],
        cols=175,
        rows=50,
    )
    try:
        p.wait("Loading controlled bundle")
        p.wait("What would you like to accomplish?")
        capture(p, "flow-startup-preparing")
        p.send(b"Draft during startup")
        p.wait("Ready")
        p.wait("Draft during startup")
        p.send(b"\r")
        p.wait("VISIBLE-LINE-17")
        for n in range(4):
            assert f"Inspect area-{n}" in p.text and f"read_file area-{n}" in p.text
        assert "VISIBLE-LINE-00" in p.text
        capture(p, "flow-four-delegates-streaming")
        action(p, "Interact", "Interact ·")
        p.send(b"\r")
        p.wait("Request")
        assert "instruction: Inspect area-3" in p.text
        assert "Hidden child source" not in p.text
        capture(p, "flow-visible-parent-expanded")
    finally:
        p.close()

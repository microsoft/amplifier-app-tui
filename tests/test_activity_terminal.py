"""Read-only Activity through actual native input and actual fixture runtime."""

import base64
import json
import os
import re
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


@pytest.mark.parametrize("size", [(175, 50), (40, 20)])
def test_interact_mouse_selection_crosses_empty_history_without_crashing(tmp_path, size):
    # Transport fixture deliberately retains zero-row source items. This exercises
    # real mouse routing, expansion, selection and resize, not provider behavior.
    program = """
import json, sys
def emit(**value):
 print(json.dumps({'version':1, 'session_id':'fixture', **value}), flush=True)
def item(identity, kind, text='', detail=None):
 return dict(id=identity, kind=kind, text=text, status='succeeded', detail=json.dumps(detail or {}))
items = [item('first', 'assistant'),
 item('tool', 'tool', 'fixture_probe', {'name':'fixture_probe','arguments':{'path':'example.txt'},'result':'Done'}),
 item('blank', 'assistant', '   \\n\\n'),
 item('child', 'tool', 'Hidden child', {'name':'fixture_probe','child_id':'child','parent_item_id':'tool'}),
 item('answer', 'assistant', 'Visible answer marker'),
 item('last', 'assistant', '[reference]: https://example.org')]
emit(type='snapshot', ready=True, mode='TRANSPORT FIXTURE', title='Empty-row selection fixture', items=items)
emit(type='state', ready=True, busy=False, status='Ready')
for line in sys.stdin:
 request = json.loads(line)
 if request['op'] == 'shutdown': break
 if request['op'] in ('submit','queue'): raise RuntimeError('Inspection sent work')
 emit(type='ack', request_id=request.get('request_id'), accepted=True)
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
        p.send(b"Unsent selection draft")
        action(p, "Interact —", "Interact ·")
        click(p, "fixture_probe")
        p.wait("Request · fixture_probe")
        click(p, "fixture_probe")
        p.wait("Request · fixture_probe", absent=True)
        click(p, "Visible answer marker")  # Used to panic while snapshotting zero-row items.
        p.wait("Select with drag")
        p.wait("Unsent selection draft")
        capture(p, f"interact-empty-history-{size[0]}")
        p.resize(80, 30)
        p.wait("Visible answer marker")
        click(p, "Visible answer marker")
        p.wait("Unsent selection draft")
        assert "panicked" not in p.raw.decode(errors="replace")
        p.send(b"\x1b")
        p.wait("Unsent selection draft")
    finally:
        p.close()


@pytest.mark.parametrize("size", [(175, 50), (40, 20), (32, 12)])
def test_activity_click_and_keyboard_details_preserve_draft_without_replay(tmp_path, size):
    p = start(tmp_path)
    try:
        p.resize(*size)
        p.wait("Ready", timeout=30)
        p.send(b"Calculate a digest\r")
        if size[1] >= 20:
            p.wait("fixture_probe", timeout=30)
        p.wait_idle()
        # On 12 rows the completed tool can already be in native history.
        # Assert actual execution, then inspect the stable Activity projection.
        assert any(
            e["kind"] == "tool.updated"
            and e["payload"].get("name") == "fixture_probe"
            and e["payload"].get("status") == "succeeded"
            for e in events(tmp_path)
        )
        p.send(b"Unsent review")
        p.wait("Unsent review")
        before = len([e for e in events(tmp_path) if e["kind"] == "turn.accepted"])
        action(p, "expand tools", "Activity ·")
        p.wait("fixture_probe")
        capture(p, f"activity-root-{size[0]}x{size[1]}")
        click(p, "› ▸ succeeded")  # Owned menu row, not the transcript behind it.
        p.wait("Preview · observed")
        p.send(b"Exact observed\r")
        p.wait("Copy observed")
        capture(p, f"activity-exact-{size[0]}x{size[1]}")
        p.send(b"Back to activity\r")
        p.wait("Preview · observed")
        p.send(b"Preview\r")
        p.wait("Copy observed source")
        # The preview is inspectable, never an execution request.
        p.send(b"\x1b")
        p.wait("Actions / choices", absent=True)
        p.wait("Unsent review")
        assert len([e for e in events(tmp_path) if e["kind"] == "turn.accepted"]) == before == 1
        assert "Turn ended;" not in p.text
    finally:
        p.close()


def test_public_thinking_markdown_and_exact_copy_in_transport_fixture(tmp_path):
    source = "## Public heading\n\n**Compare** the alternatives.\n\n- Check the source\n- Report uncertainty"
    program = """
import json, sys
from amplifier_tui.events import Event
from amplifier_tui.inspection import Inspection
source = sys.argv[1]
index = Inspection()
index.observe(Event('fixture', 1, 'turn', 'display.message', 'thought', {'source':'thinking','text':source}))
def emit(**value):
 print(json.dumps({'version':1, 'session_id':'fixture', **value}), flush=True)
emit(type='snapshot', ready=True, status='Ready', mode='TRANSPORT FIXTURE', title='Public thinking fixture', items=[])
emit(type='state', ready=True, busy=False, status='Ready')
for line in sys.stdin:
 request = json.loads(line)
 if request['op'] == 'shutdown': break
 if request['op'] == 'inspect':
  emit(type='inspection', request_id=request['request_id'], category='activity_tree', **index.activity_tree(request.get('child')))
"""
    p = Probe(
        [
            str(ROOT / "frontends/ratatui/target/release/amplifier-ratatui"),
            "--host-json",
            json.dumps([sys.executable, "-u", "-c", program, source]),
        ],
        cols=175,
        rows=50,
    )
    try:
        p.wait("Ready")
        action(p, "expand tools", "Activity ·")
        p.send(b"Thinking\r")
        p.wait("Preview · observed content")
        p.send(b"\r")
        p.wait("Preview · Thinking")
        p.wait("• Check the source")
        p.wait("• Report uncertainty")
        assert "**Compare**" not in p.text
        assert "## Public heading" not in p.text
        assert any(
            all(p.screen.buffer[y][x + n].bold for n in range(len("Public heading")))
            for y, row in enumerate(p.screen.display)
            for x in [row.find("Public heading")]
            if x >= 0
        )
        capture(p, "activity-thinking-markdown")
        p.send(b"Copy observed source\r")
        p.wait("copied")
        copies = re.findall(rb"\x1b\]52;[^;]*;([A-Za-z0-9+/=]+)", p.raw)
        assert base64.b64decode(copies[-1]).decode() == source
    finally:
        p.close()

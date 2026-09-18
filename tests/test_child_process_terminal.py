"""Native terminal driving actual isolated fixture children, not synthetic events."""

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
import asyncio,sys
from amplifier_core import ToolResult
from amplifier_tui.host import SessionHost
from amplifier_tui.__main__ import main
original=SessionHost.open
async def open_fixture(self,*args,**kwargs):
 await original(self,*args,**kwargs)
 calls=0
 async def delegate(_input):
  nonlocal calls
  calls+=1
  config={'tools':[{'module':'tool-fixture','config':{'approval':True,'delay':3 if calls==2 else 0}}]}
  result=await self.children.spawn('fixture-agent','Compute a digest in a fresh process',self.session,
                                  {'fixture-agent':config},use_subprocess=True)
  return ToolResult(success=True,output=result)
 self.session.coordinator.get('tools')['fixture_probe'].execute=delegate
 self.children.register(self.session)
SessionHost.open=open_fixture
main()
"""


@pytest.mark.parametrize("size", [(175, 50), (40, 20)])
def test_process_approval_progress_and_graceful_stop_are_visible(tmp_path, size):
    command = [
        sys.executable,
        "-u",
        "-c",
        PROGRAM,
        "--bridge",
        "--fixture",
        "--no-install",
        "--state-dir",
        str(tmp_path / "state"),
        "--cwd",
        str(tmp_path),
        "--sources",
        str(ROOT.parent / "tui-sources.json"),
    ]
    probe = Probe(
        [
            str(ROOT / "frontends/ratatui/target/release/amplifier-ratatui"),
            "--host-json",
            json.dumps(command),
        ],
        cols=size[0],
        rows=size[1],
    )
    try:
        probe.wait("Ready", timeout=30)
        probe.send(b"Run the isolated fixture agent\r")
        probe.wait("Compute the fixture digest?", timeout=20)
        capture(probe, f"child-process-{size[0]}-approval")
        action(probe, "Decisions", "Options (exact runtime scope)")
        probe.send(b"allow\r")
        probe.wait("Fixture round trip complete.", timeout=15)
        probe.wait("[ Send ]")
        capture(probe, f"child-process-{size[0]}-complete")
        probe.send(b"Run a slow isolated fixture\r")
        probe.wait("Compute the fixture digest?", timeout=20)
        action(probe, "Decisions", "Options (exact runtime scope)")
        probe.send(b"allow\r")
        probe.wait("Actions / choices", absent=True)
        probe.wait("Waiting for your decision", absent=True)
        probe.send(b"Keep this draft")
        probe.wait("Keep this draft")
        probe.send(b"\x03")
        probe.wait("Finishing current calls")
        capture(probe, f"child-process-{size[0]}-stopping")
        probe.wait("Stopped", timeout=10)
        probe.wait("Keep this draft")
        assert probe.process.poll() is None
        capture(probe, f"child-process-{size[0]}-stopped")
    finally:
        probe.close()
    source = next((tmp_path / "state/conversations").iterdir())
    rows = [json.loads(path.read_text()) for path in (source / "children").glob("*.json")]
    assert len(rows) == 2 and all(row["use_subprocess"] for row in rows)
    assert {row["status"] for row in rows} == {"completed", "interrupted"}
    assert all(row["resumable"] for row in rows)
    assert not any(row["execution_uncertain"] for row in rows)

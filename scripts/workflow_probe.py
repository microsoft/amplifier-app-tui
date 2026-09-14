"""Four billed read-only turns: queued continuation and local organization in both presets."""

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import time
import uuid

from interaction_probe import action, capture
from navigation_probe import read_events
from terminal_probe import ROOT, Probe

from amplifier_tui.conversations import resolve_resume


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", required=True, action="store_true")
    parser.parse_args()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        parser.error("Supply ANTHROPIC_API_KEY; no credential migration")
    state = ROOT / ".state/workflow-live" / uuid.uuid4().hex
    results = []
    for preset in ("anchors", "anchors-amp-dev"):
        probe = Probe(
            [
                sys.executable,
                str(ROOT / "scripts/run.py"),
                "--preset",
                preset,
                "--state-dir",
                str(state / preset),
                "--no-install",
            ],
            cols=160,
        )
        try:
            probe.wait("Ready", timeout=60)
            record = resolve_resume(state / preset, "latest")
            path = state / preset / "conversations" / record["id"]
            marker = "workflow-" + uuid.uuid4().hex[:12]
            probe.send(
                (
                    f"Remember marker {marker}. Use only read_file to read pyproject.toml and report its project name. Do not edit, delegate or use other tools.\r"
                ).encode()
            )
            probe.wait("[ Queue ]")
            probe.send(
                b"Without using any tools, return only the marker I asked you to remember.\r"
            )
            probe.wait("1 waiting")
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                probe.read(0.02)
                events = read_events(path)
                endings = [e for e in events if e["kind"] == "turn.ended"]
                if len(endings) == 2:
                    break
            else:
                raise AssertionError("Queued live continuation did not finish")
            assert all(e["payload"]["status"] == "completed" for e in endings)
            turns = [e for e in events if e["kind"] == "turn.accepted"]
            assert len(turns) == 2 and turns[1]["payload"]["input_id"]
            assert turns[1]["sequence"] > endings[0]["sequence"]
            tools = [e for e in events if e["kind"] == "tool.updated"]
            assert any(
                e["payload"].get("name") == "read_file"
                and e["payload"].get("status") == "succeeded"
                for e in tools
            )
            assert not any(e["turn_id"] == turns[1]["turn_id"] for e in tools)
            answers = [
                e["payload"]["text"]
                for e in events
                if e["kind"] == "text.final" and e["turn_id"] == turns[1]["turn_id"]
            ]
            assert marker in "".join(answers)
            probe.wait("[ Send ]")
            probe.send(b"Unsent review draft")
            action(probe, "Rename conversation", "New name (up to 100 characters)")
            probe.send(b"Workflow verification\r")
            probe.wait("Workflow verification")
            action(probe, "Find in conversation", "Find message text")
            probe.send((marker + "\r").encode())
            probe.wait("Conversation matches")
            capture(probe, f"workflow-live-{preset}")
            probe.send(b"\x1b")
            action(probe, "Assistant replies", "Assistant replies · latest")
            probe.send(b"\r")
            probe.wait("Message · retained source preview")
            probe.send(b"Copy message\r")
            probe.wait("Source copied")
            copies = re.findall(rb"\x1b\]52;c;([^\x07]*)\x07", probe.raw)
            assert base64.b64decode(copies[-1]).decode() == answers[-1]
            assert len([e for e in read_events(path) if e["kind"] == "turn.accepted"]) == 2
            results.append(
                {
                    "preset": preset,
                    "completed_turns": 2,
                    "queued_admission_after_completion": True,
                    "remembered_prior_marker": True,
                    "local_rename_search_copy": True,
                }
            )
            print(json.dumps(results[-1]), flush=True)
        finally:
            probe.close()
        assert json.loads((path / "draft.json").read_text())["text"] == "Unsent review draft"
    files = [
        *sorted((ROOT / "frontends/ratatui/src").glob("*.rs")),
        *sorted((ROOT / "src/amplifier_tui").glob("*.py")),
        ROOT / "frontends/ratatui/Cargo.lock",
        ROOT / "scripts/run.py",
        ROOT / "scripts/workflow_probe.py",
    ]
    receipt = {
        "scope": "Live queued read-only continuation and local organization; not full Codex/CLI parity",
        "results": results,
        "source_fingerprints": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files
        },
    }
    (ROOT / "notes/evidence/workflow-live.json").write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()

"""Four billed read-only turns: visible steering/queue, plan badge, return and native view."""

import argparse
import hashlib
import json
import os
import sys
import uuid

from controls_probe import observed
from interaction_probe import action, capture, click
from navigation_probe import read_events
from terminal_probe import ROOT, Probe

from amplifier_tui.conversations import resolve_resume


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", required=True, action="store_true")
    parser.parse_args()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        parser.error("Supply ANTHROPIC_API_KEY; no credential migration")
    state = ROOT / ".state/everyday-live" / uuid.uuid4().hex
    results = []
    for preset in ("anchors", "anchors-amp-dev"):
        directory = state / preset
        probe = Probe(
            [
                sys.executable,
                str(ROOT / "scripts/run.py"),
                "--no-install",
                "--preset",
                preset,
                "--state-dir",
                str(directory),
            ],
            cols=160,
        )
        marker = "steering-marker-" + uuid.uuid4().hex[:12]
        try:
            probe.wait("Ready", timeout=60)
            probe.wait("Mode: default")
            identity = resolve_resume(directory, "latest")["id"]
            path = directory / "conversations" / identity
            probe.send(b"/mode plan\r")
            probe.wait("Apply plan")
            probe.send(b"\r")
            probe.wait("Current: plan")
            probe.wait("Mode: plan")
            capture(probe, f"everyday-live-{preset}-plan")
            probe.send(b"\x1b")
            probe.wait("Current: plan", absent=True)
            probe.send(
                b"Use only read_file to read pyproject.toml and report its project name. Do not edit files, run commands, delegate, change modes, or use any other tools.\r"
            )
            observed(probe, path, "steering.ready")
            click(probe, "[Steer]")
            probe.wait("Correction for this turn only")
            probe.send(
                f"Remember {marker}. After the read_file, reply with that marker. Do not use other tools or change mode.\r".encode()
            )
            probe.wait("Correction for this turn only", absent=True)
            probe.send(
                b"Recall the steering marker from the prior turn. Use no tools and do not change modes."
            )
            # Explicit Queue works even if the provider completes during human editing.
            action(probe, "Queue current draft", "waiting")
            # Mode changes deliberately hold the queue; release is separate consent.
            click(probe, "[Pending 1]")
            probe.wait("Pending follow-ups")
            probe.send(b"Run pending\r")
            observed(probe, path, "turn.ended", count=2)
            probe.wait("[ Send ]")
            events = read_events(path)
            endings = [e for e in events if e["kind"] == "turn.ended"]
            assert len(endings) == 2 and all(e["payload"]["status"] == "completed" for e in endings)
            accepted = [e for e in events if e["kind"] == "turn.accepted"]
            assert len(accepted) == 2 and accepted[1]["payload"].get("input_id")
            corrections = [e for e in events if e["kind"] == "steering.updated"]
            assert [e["payload"]["status"] for e in corrections] == ["pending", "applied"]
            assert all(e["turn_id"] == accepted[0]["turn_id"] for e in corrections)
            assert any(
                e["kind"] == "tool.updated"
                and e["payload"].get("name") == "read_file"
                and e["payload"].get("status") == "succeeded"
                for e in events
            )
            assert marker in "".join(
                e["payload"]["text"]
                for e in events
                if e["kind"] == "text.final" and e["turn_id"] == accepted[1]["turn_id"]
            )
            probe.send(b"Retain navigation draft")
            action(probe, "New conversation", "[ Send ]")
            probe.wait("Retain navigation draft", absent=True)
            probe.wait("Ready", timeout=60)
            probe.wait("Mode: default")
            action(probe, "History —", "Directory history")
            probe.wait("Recall the steering marker")
            probe.send(b"\x1b")
            probe.wait("Directory history", absent=True)
            click(probe, "[Resume]")
            probe.wait("Saved conversations")
            probe.send(identity[:8].encode() + b"\r")
            probe.wait("Retain navigation draft", timeout=60)
            probe.wait("Ready")
            probe.wait("Mode: plan")
            action(probe, "Native scrollback", "Native terminal history")
            probe.wait("[ Actions ]")
            probe.wait("Retain navigation draft")
            probe.wait("Mode: plan")
            assert len([e for e in read_events(path) if e["kind"] == "turn.accepted"]) == 2
            capture(probe, f"everyday-live-{preset}-returned")
            results.append(
                {
                    "preset": preset,
                    "completed_turns": 2,
                    "identified_steer_applied": True,
                    "queued_followup_recalled_correction": True,
                    "plan_badge_restored": True,
                    "directory_recall_without_context_import": True,
                    "native_view_kept_draft": True,
                }
            )
            print(json.dumps(results[-1]), flush=True)
        finally:
            probe.close()
    files = [
        *sorted((ROOT / "frontends/ratatui/src").glob("*.rs")),
        *sorted((ROOT / "src/amplifier_tui").rglob("*.py")),
        ROOT / "frontends/ratatui/Cargo.lock",
        ROOT / "scripts/run.py",
        ROOT / "scripts/resume_picker.py",
        ROOT / "scripts/everyday_probe.py",
    ]
    receipt = {
        "scope": "Four billed read-only turns across actual presets; not full parity or latency evidence",
        "results": results,
        "source_fingerprints": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files
        },
    }
    (ROOT / "notes/evidence/everyday-live.json").write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()

"""Live daily-work gate: four root + four child turns across both real presets.

Explicit read-only prompts are not a sandbox. State/captures remain private.
"""

import hashlib
import json
import os
import sys
import uuid

from controls_probe import observed
from interaction_probe import capture
from navigation_probe import read_events
from questions_probe import wait_ready
from terminal_probe import ROOT, Probe

from amplifier_tui.conversations import resolve_resume


def action(probe, query, expected):
    probe.wait("Actions / choices", absent=True)
    probe.send(b"\x1bOS")
    probe.wait("Search:")
    probe.send(query.encode() + b"\r")
    probe.wait(expected)


def dismiss(probe, title):
    probe.send(b"\x1b")
    probe.wait(title, absent=True)


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("Supply ANTHROPIC_API_KEY explicitly; no credential migration")
    state = ROOT / ".state/daily-live" / uuid.uuid4().hex
    results = []
    for preset in ("anchors", "anchors-amp-dev"):
        directory = state / preset
        command = [
            sys.executable,
            str(ROOT / "scripts/run.py"),
            "--no-install",
            "--state-dir",
            str(directory),
        ]
        probe = Probe([*command, "--preset", preset], cols=160)
        try:
            wait_ready(probe)
            record = resolve_resume(directory, "latest")
            path = directory / "conversations" / record["id"]
            probe.send(
                b'Use delegate exactly once, agent "self", context_depth "none", instruction "Use only read_file to read pyproject.toml and report its project name. No edits, commands, delegation or other tools." Omit model_role, provider_preferences and orchestrator overrides. Do no other work; summarize the result briefly.\r'
            )
            assert (
                observed(probe, path, "turn.ended", timeout=180)[-1]["payload"]["status"]
                == "completed"
            )
            receipts = list((path / "children").glob("*.json"))
            assert len(receipts) == 1
            child_path = receipts[0]
            first = json.loads(child_path.read_text())
            assert first["status"] == "completed" and first["restart_policy"] is not None
            assert any(
                e["kind"] == "child.observed"
                and e["payload"]["status"] == "succeeded"
                and "read_file" in e["payload"]["name"]
                for e in read_events(path)
            )
            probe.wait("[ Send ]")
            action(probe, "Delegated work", "Delegated work · scoped")
            probe.send(b"Agent\r")
            probe.wait("Observed evidence")
            capture(probe, f"daily-live-{preset}-child")
            probe.send(b"Inspect this child\r")
            probe.wait("Activity evidence · identified")
            probe.send(b"read_file\r")
            probe.wait("Observed evidence")
            capture(probe, f"daily-live-{preset}-child-tool")
            dismiss(probe, "Observed evidence")
            action(probe, "Context intelligence", "Context intelligence · observed")
            capture(probe, f"daily-live-{preset}-context")
        finally:
            probe.close()
        probe = Probe([*command, "--resume", record["id"]], cols=160)
        try:
            wait_ready(probe)
            assert json.loads(child_path.read_text()) == first
            action(probe, "Delegated work", "Delegated work · scoped")
            capture(probe, f"daily-live-{preset}-restored-child")
            dismiss(probe, "Delegated work · scoped")
            probe.send(
                (
                    f'Use delegate exactly once with session_id "{child_path.stem}" and instruction "Without tools, recall the project name you read in the previous child turn." Omit model_role and provider_preferences. Do no other work; briefly report the result.\r'
                ).encode()
            )
            assert (
                observed(probe, path, "turn.ended", count=2, timeout=180)[-1]["payload"]["status"]
                == "completed"
            )
            final = json.loads(child_path.read_text())
            assert final["status"] == "completed"
            assert len(final["messages"]) > len(first["messages"])
            assert "amplifier-app-tui" in str(final["messages"][-1])
            assert len(list((path / "children").glob("*.json"))) == 1
            capture(probe, f"daily-live-{preset}-continued")
        finally:
            probe.close()
        results.append(
            {
                "preset": preset,
                "root_turns": 2,
                "child_turns": 2,
                "read_file_succeeded": True,
                "child_evidence_keyboard": True,
                "context_inspection": True,
                "restart_inspection_no_execution": True,
                "explicit_child_continuation": True,
                "child_context_recalled": True,
            }
        )
        print(json.dumps(results[-1]), flush=True)
    files = [
        *sorted((ROOT / "src/amplifier_tui").rglob("*.py")),
        *sorted((ROOT / "frontends/ratatui/src").glob("*.rs")),
        ROOT / "scripts/daily_probe.py",
        ROOT / "scripts/terminal_probe.py",
        ROOT / "scripts/run.py",
    ]
    receipt = {
        "scope": __doc__,
        "results": results,
        "source_fingerprints": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files
        },
    }
    (ROOT / "notes/evidence/daily-live.json").write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()

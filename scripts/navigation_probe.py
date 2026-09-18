"""Four billed read-only turns across both presets with in-app switching between them."""

import argparse
import hashlib
import json
import os
import sys
import uuid

from interaction_probe import action, capture
from terminal_probe import ROOT, Probe

from amplifier_tui.conversations import resolve_resume


def read_events(path):
    return [json.loads(line) for line in (path / "events.jsonl").read_text().splitlines()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", required=True, action="store_true")
    parser.parse_args()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        parser.error("Supply ANTHROPIC_API_KEY; no CLI credential import")
    state = ROOT / ".state/navigation-live" / uuid.uuid4().hex
    base = [sys.executable, str(ROOT / "scripts/run.py"), "--no-install", "--state-dir", str(state)]
    records = []
    probe = None
    try:
        for preset in ("anchors", "anchors-amp-dev"):
            if probe:
                probe.close()
            probe = Probe([*base, "--preset", preset], cols=160)
            probe.wait("Ready", timeout=60)
            marker = "nav-" + uuid.uuid4().hex[:12]
            probe.send(
                (
                    f"Remember {marker}. Use read_file to read pyproject.toml and report only the project name. "
                    "Do not edit files, run commands, delegate, or use any other tool."
                ).encode()
            )
            probe.send(b"\r")
            probe.wait_idle(timeout=60)
            probe.wait("▸ Read · done")
            probe.send(
                b"What marker did I give you? Reply with only that marker; do not use tools."
            )
            probe.wait("do not use tools.")
            entry = resolve_resume(state, "latest")
            path = state / "conversations" / entry["id"]
            records.append(
                {
                    "preset": preset,
                    "marker": marker,
                    "id": entry["id"],
                    "path": path,
                    "sequence": read_events(path)[-1]["sequence"],
                }
            )
        # From amp-dev, switch to anchors and back; neither picker action submits.
        for record in records:
            action(probe, "Resume", "Saved conversations")
            probe.wait(record["id"][:8])
            capture(probe, "navigation-live-picker")
            probe.send(record["id"][:8].encode())
            probe.send(b"\r")
            probe.wait("Saved conversations", absent=True)
            probe.wait(record["id"][:12])
            probe.wait("Ready", timeout=60)
            probe.wait("What marker did I give you?")
            after_open = [
                e for e in read_events(record["path"]) if e["sequence"] > record["sequence"]
            ]
            assert [e["kind"] for e in after_open] == ["session.ready"]
            probe.send(b"\r")
            probe.wait_idle(timeout=60)
            fresh = [e for e in read_events(record["path"]) if e["sequence"] > record["sequence"]]
            answers = [e["payload"]["text"] for e in fresh if e["kind"] == "text.final"]
            assert answers and record["marker"] in answers[-1]
            assert not any(e["kind"].startswith("tool.") for e in fresh)
            assert (
                fresh[-1]["kind"] == "turn.ended" and fresh[-1]["payload"]["status"] == "completed"
            )
            capture(probe, f"navigation-live-{record['preset']}")
            print(
                json.dumps(
                    {
                        "preset": record["preset"],
                        "restored_draft": True,
                        "new_answer_remembers_prior_marker": True,
                        "replay_execution_events": 0,
                    }
                ),
                flush=True,
            )
    finally:
        if probe:
            probe.close()
    sources = [
        *sorted((ROOT / "frontends/ratatui/src").glob("*.rs")),
        ROOT / "frontends/ratatui/Cargo.lock",
        ROOT / "scripts/run.py",
        *[
            ROOT / "src/amplifier_tui" / name
            for name in (
                "host.py",
                "conversations.py",
                "navigation.py",
                "__main__.py",
                "frontend_bridge.py",
                "events.py",
            )
        ],
    ]
    receipt = {
        "scope": "Both presets: live read_file plus memory turn after in-app switching; no CLI parity or all-module-state claim",
        "presets": [r["preset"] for r in records],
        "completed_live_turns": 4,
        "in_app_switches": 2,
        "draft_restores": 2,
        "recalled_markers": 2,
        "replay_execution_events": 0,
        "source_fingerprints": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources
        },
    }
    (ROOT / "notes/evidence/navigation-live.json").write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()

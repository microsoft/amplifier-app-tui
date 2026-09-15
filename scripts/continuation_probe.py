"""Two explicit billed reference turns; private raw-provider diagnostic opt-in."""

import argparse
import hashlib
import json
import os
import sys
import uuid
from pathlib import Path

import yaml
from controls_probe import observed
from interaction_probe import action, capture
from navigation_probe import read_events
from questions_probe import wait_ready
from terminal_probe import ROOT, Probe

from amplifier_tui.conversations import resolve_resume


def dismiss(probe, title):
    probe.send(b"\x1b")
    probe.wait(title, absent=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", required=True, action="store_true")
    parser.add_argument("--allow-private-provider-raw", required=True, action="store_true")
    parser.add_argument("--output", default="notes/evidence/continuation-live.json")
    args = parser.parse_args()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        parser.error("Supply ANTHROPIC_API_KEY explicitly")
    directory = ROOT / ".state/continuation-live" / uuid.uuid4().hex
    directory.mkdir(parents=True, mode=0o700)
    overlay = yaml.safe_load((ROOT / "examples/anthropic.yaml").read_text())
    overlay["providers"][0]["config"]["raw"] = True
    overlay_path = directory / "explicit-private-raw.yaml"
    overlay_path.write_text(yaml.safe_dump(overlay))
    overlay_path.chmod(0o600)
    results = []
    for preset in ("anchors", "anchors-amp-dev"):
        cwd = directory / preset
        cwd.mkdir(mode=0o700)
        state = cwd / "state"
        source = cwd / "source.txt"
        source.write_text("excluded source\ncobalt-731\nexcluded tail\n")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        command = [
            sys.executable,
            str(ROOT / "scripts/run.py"),
            "--no-install",
            "--state-dir",
            str(state),
        ]
        probe = Probe(
            [*command, "--overlay", str(overlay_path), "--preset", preset, "--cwd", str(cwd)],
            cols=160,
        )
        try:
            wait_ready(probe)
            identity = resolve_resume(state, "latest")["id"]
            path = state / "conversations" / identity
            probe.send(
                b"Reply only with the token in the selected file reference. Do not use tools, read files, delegate or change anything."
            )
            action(probe, "Attach file reference", "Workspace-relative file[:line")
            probe.send(b"source.txt:2\r")
            probe.wait("File reference · confirm attachment")
            probe.wait("cobalt-731")
            capture(probe, f"continuation-{preset}-reference")
            probe.send(b"\r")
            probe.wait("[References attached]")
            source.unlink()
            action(probe, "Queue current draft", "[Pending 1] (paused)")
            assert not any(e["kind"] == "turn.accepted" for e in read_events(path))
        finally:
            probe.close()
        probe = Probe([*command, "--resume", identity], cols=160)
        try:
            wait_ready(probe)
            assert not any(e["kind"] == "turn.accepted" for e in read_events(path))
            action(probe, "Provider request diagnostic", "Provider request · private diagnostic")
            probe.send(b"\r")
            probe.wait("Waiting for the next root provider request")
            dismiss(probe, "Provider request · memory-only projection")
            action(probe, "Pending follow-ups", "Pending follow-ups · paused")
            probe.send(b"Run pending\r")
            assert observed(probe, path, "turn.ended")[-1]["payload"]["status"] == "completed"
            probe.wait("[ Send ]")
            events = read_events(path)
            reply = " ".join(e["payload"]["text"] for e in events if e["kind"] == "text.final")
            assert "cobalt-731" in reply and not any(e["kind"] == "tool.updated" for e in events)
            messages = json.loads((path / "checkpoint.json").read_text())["messages"]
            ref = next(
                json.loads(b["text"].split("\n", 1)[1])
                for m in messages
                if isinstance(m.get("content"), list)
                for b in m["content"]
                if b.get("type") == "text"
                and b.get("text", "").startswith("User-selected file reference")
            )
            assert ref["source_sha256"] == digest and ref["text"] == "cobalt-731\n"
            assert ref["start_line"] == ref["end_line"] == 2
            probe.send(b"Unsent retained draft")
            action(probe, "Provider request diagnostic", "Provider request · private diagnostic")
            probe.send(b"Inspect captured\r")
            probe.wait("Provider request · memory-only projection")
            probe.wait("provider-reported projection")
            capture(probe, f"continuation-{preset}-provider-request")
            probe.send(b"One-shot\r")
            probe.wait("Observed evidence")
            capture(probe, f"continuation-{preset}-provider-request-detail")
            dismiss(probe, "Observed evidence")
            assert "Unsent retained draft" in probe.text
            assert sum(e["kind"] == "turn.accepted" for e in read_events(path)) == 1
            results.append(
                {
                    "preset": preset,
                    "completed_turns": 1,
                    "tool_calls": 0,
                    "queued_reference_survives_reopen": True,
                    "deleted_source_not_reread": True,
                    "canonical_location_and_bytes_match": True,
                    "controlled_token_identified": True,
                    "explicit_provider_reported_projection": True,
                    "diagnostic_added_no_turn": True,
                    "draft_retained": True,
                }
            )
            print(json.dumps(results[-1]), flush=True)
        finally:
            probe.close()
    files = [
        *sorted((ROOT / "frontends/ratatui/src").glob("*.rs")),
        *sorted((ROOT / "src/amplifier_tui").rglob("*.py")),
        ROOT / "frontends/ratatui/Cargo.lock",
        Path(__file__).resolve(),
    ]
    (ROOT / args.output).write_text(
        json.dumps(
            {
                "scope": "Two billed controlled-reference turns with explicit private provider raw logging in isolated test state. Provider-reported projection is not exact wire or delivery proof. No raw captures in this receipt; no universal provider or CLI parity claim.",
                "results": results,
                "source_fingerprints": {
                    str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in files
                },
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()

"""Live resume proof through Ratatui. --live bills four read-only provider turns."""

import argparse
import hashlib
import json
import os
import sys
import time
import uuid

from terminal_probe import ROOT, Probe


def exercise(preset):
    from interaction_probe import capture

    from amplifier_tui.conversations import resolve_resume

    state = ROOT / ".state/reading-probe" / preset
    command = [
        sys.executable,
        str(ROOT / "scripts/run.py"),
        "--state-dir",
        str(state),
        "--no-install",
    ]
    marker = "resume-" + uuid.uuid4().hex[:12]
    probe = Probe([*command, "--preset", preset], cols=160)
    try:
        probe.wait("Ready", timeout=60)
        probe.send(
            (
                f"Remember this exact marker for our next turn: {marker}. "
                "Use read_file to read pyproject.toml. Report the project name using a Markdown heading and one bullet. "
                "Do not edit files, run commands, delegate, or use other tools."
            ).encode()
        )
        probe.send(b"\r")
        probe.wait("Completed", timeout=60)
        probe.wait("✓  read_file")
        probe.send(
            b"What exact marker did I give you previously? Reply with only the marker; do not use tools."
        )
        probe.wait("do not use tools.")
    finally:
        probe.close()
    entry = resolve_resume(state, "latest")
    path = state / "conversations" / entry["id"]
    previous = json.loads((path / "checkpoint.json").read_text())
    assert previous["status"] == "ready"
    probe = Probe([*command, "--resume", entry["id"]], cols=160)
    try:
        probe.wait("Ready", timeout=60)
        probe.wait("What exact marker")
        events = [json.loads(line) for line in (path / "events.jsonl").read_text().splitlines()]
        replay_events = [e for e in events if e["sequence"] > previous["sequence"]]
        assert [e["kind"] for e in replay_events] == ["session.ready"]
        probe.send(b"\r")
        probe.wait("Completed", timeout=60)
        # Do not mistake the first turn's visible marker for a remembered answer.
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            checkpoint = json.loads((path / "checkpoint.json").read_text())
            if checkpoint["sequence"] > previous["sequence"] + 1:
                break
            probe.read(0.02)
        events = [json.loads(line) for line in (path / "events.jsonl").read_text().splitlines()]
        new = [e for e in events if e["sequence"] > previous["sequence"] + 1]
        answers = [e["payload"]["text"] for e in new if e["kind"] == "text.final"]
        assert answers and marker in answers[-1], (
            "New assistant answer did not recall the prior marker"
        )
        assert not any(e["kind"].startswith("tool.") for e in new), (
            "Memory question unexpectedly invoked a tool"
        )
        assert new[-1]["kind"] == "turn.ended" and new[-1]["payload"]["status"] == "completed"
        capture(probe, f"reading-live-{preset}")
    finally:
        probe.close()
    return {
        "preset": preset,
        "completed_turns": 2,
        "first_tool": "read_file",
        "restored_draft": True,
        "same_conversation": True,
        "new_answer_recalls_prior_marker": True,
        "replay_projection_events": [e["kind"] for e in replay_events],
        "second_turn_tools": 0,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    parser.parse_args()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        parser.error("ANTHROPIC_API_KEY is required; no CLI credentials are imported")
    runs = []
    for preset in ("anchors", "anchors-amp-dev"):
        runs.append(exercise(preset))
        print(json.dumps(runs[-1]), flush=True)
    sources = [
        *sorted((ROOT / "frontends/ratatui/src").glob("*.rs")),
        ROOT / "frontends/ratatui/Cargo.lock",
        ROOT / "scripts/run.py",
        *[
            ROOT / "src/amplifier_tui" / name
            for name in (
                "host.py",
                "conversations.py",
                "__main__.py",
                "frontend_bridge.py",
                "events.py",
            )
        ],
    ]
    receipt = {
        "scope": "Live read-only tool followed by explicit process restart and context-memory turn; no CLI parity claim",
        "runs": runs,
        "source_fingerprints": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources
        },
    }
    (ROOT / "notes/evidence/reading-live.json").write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()

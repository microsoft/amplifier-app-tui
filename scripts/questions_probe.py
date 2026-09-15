"""Four billed turns: structured answers, read-only review and remembered answers after resume."""

import argparse
import hashlib
import json
import os
import sys
import time
import uuid

from controls_probe import observed
from interaction_probe import action, capture
from navigation_probe import read_events
from terminal_probe import ROOT, Probe

from amplifier_tui.conversations import resolve_resume


def wait_ready(probe, timeout=60):
    # Restored assistant text can contain "Ready" before module initialization.
    # Only the status row is readiness evidence; admission still belongs to host.
    deadline = time.monotonic() + timeout
    status = ""
    while time.monotonic() < deadline:
        display = probe.screen.display
        controls = [i for i, row in enumerate(display[:-1]) if "[ Actions ]" in row]
        if controls:
            # Content-sized controls may wrap across rows at narrow widths.
            following = display[controls[-1] + 1 :]
            status = next((row for row in following if not row.strip().startswith("[")), "")
        else:
            status = display[-1]
        if status.strip() in ("Ready", "Ready · real modules mounted"):
            return
        probe.read(0.02)
    raise AssertionError(f"Runtime did not become ready: {status}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", required=True, action="store_true")
    parser.parse_args()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        parser.error("Supply ANTHROPIC_API_KEY explicitly; no credential-store import")
    state = ROOT / ".state/questions-live" / uuid.uuid4().hex
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
        marker = "answer-" + uuid.uuid4().hex[:12]
        try:
            wait_ready(probe)
            record = resolve_resume(directory, "latest")
            path = directory / "conversations" / record["id"]
            action(probe, "Workspace changes", "Workspace changes · observed")
            capture(probe, f"questions-live-{preset}-workspace")
            probe.send(b"\x1b")
            assert not any(e["kind"] == "turn.accepted" for e in read_events(path))
            probe.send(
                b'Use only request_user_input, exactly once, to ask these two questions: id scope, question "Which scope should I use?", choices "Small slice" and "Broad pass"; id notes, question "What should I remember?", no offered options. Wait for my tool answers, then reply briefly with both answers. Do not use any other tools, edit files, run commands, or delegate.\r'
            )
            observed(probe, path, "question.updated")
            probe.wait("[ Answer questions 1 ]")
            probe.send(b"Main draft stays mine")
            action(probe, "Questions —", "Questions · clarification")
            probe.send(b"\r")
            probe.wait("Questions · review answers")
            probe.send(b"Which scope\r")
            probe.wait("Question · choose")
            probe.send(b"Small slice\r")
            probe.wait("Answer: Small slice")
            probe.send(b"remember\r")
            probe.wait("Write my own answer")
            probe.send(b"\r")
            probe.wait("Enter review")
            probe.send(marker.encode() + b"\r")
            probe.wait("Submit reviewed answers")
            capture(probe, f"questions-live-{preset}-review")
            assert not any(
                e["kind"] == "question.updated" and e["payload"]["status"] == "answered"
                for e in read_events(path)
            )
            probe.send(b"Submit reviewed\r")
            assert observed(probe, path, "turn.ended")[-1]["payload"]["status"] == "completed"
            answered = [e for e in read_events(path) if e["kind"] == "question.updated"][-1]
            assert answered["payload"]["answers"] == {
                "scope": {"option": "Small slice", "text": ""},
                "notes": {"option": None, "text": marker},
            }
            capture(probe, f"questions-live-{preset}-completed")
        finally:
            probe.close()
        assert json.loads((path / "draft.json").read_text())["text"] == "Main draft stays mine"
        probe = Probe([*command, "--resume", record["id"]], cols=160)
        try:
            wait_ready(probe)
            assert "[ Answer questions" not in probe.text
            probe.send(b"\x01\x0b")  # Select current line start, delete restored draft only.
            probe.send(
                b"Without tools, reply with the exact marker from my answer to your notes question. Do not ask another question or perform any work.\r"
            )
            endings = observed(probe, path, "turn.ended", count=2)
            assert all(e["payload"]["status"] == "completed" for e in endings)
            rows = read_events(path)
            turns = [e for e in rows if e["kind"] == "turn.accepted"]
            assert len(turns) == 2 and marker not in turns[-1]["payload"]["text"]
            second = [e for e in rows if e["turn_id"] == turns[-1]["turn_id"]]
            assert not any(e["kind"] in ("tool.updated", "question.updated") for e in second)
            assert marker in "".join(
                e["payload"]["text"] for e in second if e["kind"] == "text.final"
            )
            capture(probe, f"questions-live-{preset}-recalled")
            results.append(
                {
                    "preset": preset,
                    "completed_turns": 2,
                    "choice_and_free_text_reviewed": True,
                    "main_draft_retained": True,
                    "normal_tool_result_recalled_after_resume": True,
                    "read_only_git_review_without_model_call": True,
                }
            )
            print(json.dumps(results[-1]), flush=True)
        finally:
            probe.close()
    files = [
        *sorted((ROOT / "frontends/ratatui/src").glob("*.rs")),
        *sorted((ROOT / "src/amplifier_tui").rglob("*.py")),
        ROOT / "scripts/run.py",
        ROOT / "scripts/questions_probe.py",
        ROOT / "examples/user-questions.yaml",
        ROOT / "frontends/ratatui/Cargo.lock",
    ]
    receipt = {
        "scope": "Four billed live turns across both presets; structured questions and remembered answers, local Git review. Not full parity or latency evidence.",
        "results": results,
        "source_fingerprints": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files
        },
    }
    (ROOT / "notes/evidence/questions-live.json").write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()

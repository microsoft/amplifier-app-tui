"""Four live parent turns and two child turns: resume, then Stop/exit during a question."""

import argparse
import hashlib
import json
import os
import sys
import uuid
from pathlib import Path

from controls_probe import observed
from interaction_probe import capture
from navigation_probe import read_events
from questions_probe import wait_ready
from terminal_probe import ROOT, Probe

from amplifier_tui.conversations import resolve_resume


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--output", default="notes/evidence/lifecycle-live.json")
    args = parser.parse_args()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        parser.error("Supply the live provider credential explicitly")
    state = ROOT / ".state/lifecycle-live" / uuid.uuid4().hex
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
                b"Use only read_file to read pyproject.toml and report its project name. "
                b"Do not edit, run commands, delegate or use any other tool.\r"
            )
            assert observed(probe, path, "turn.ended")[-1]["payload"]["status"] == "completed"
            probe.wait("[ Send ]")
            assert any(
                e["kind"] == "tool.updated"
                and e["payload"].get("name") == "read_file"
                and e["payload"].get("status") == "succeeded"
                for e in read_events(path)
            )
            capture(probe, f"lifecycle-live-{preset}-completed")
        finally:
            probe.close()
        assert json.loads((path / "checkpoint.json").read_text())["status"] == "ready"
        probe = Probe([*command, "--resume", record["id"]], cols=160)
        try:
            wait_ready(probe)
            assert sum(e["kind"] == "turn.accepted" for e in read_events(path)) == 1
            probe.send(
                b'Use delegate exactly once with agent "self", context_depth "none", '
                b'instruction "Use only request_user_input to ask one question with id scope, '
                b"question Should I proceed?, and options Yes and No. Wait for the answer. "
                b'Do not run commands, edit, read files, delegate or use other tools." '
                b"Omit provider_preferences, model_role and orchestrator overrides. "
                b"Do no other work.\r"
            )
            questions = observed(probe, path, "question.updated")
            assert questions[-1]["payload"]["source"].startswith("Child ")
            probe.wait("[ Answer question ]")
            capture(probe, f"lifecycle-live-{preset}-waiting-child")
            probe.send(b"\x1bOS")
            probe.wait("Search:")
            probe.send(b"Stop active")
            probe.wait("Search: Stop active")
            # Select Stop, then immediately quit. The host must account for the
            # child and persist interruption despite a disappearing view.
            probe.send(b"\r\x11")
        finally:
            probe.close()
        rows = read_events(path)
        endings = [e["payload"]["status"] for e in rows if e["kind"] == "turn.ended"]
        assert endings == ["completed", "interrupted"]
        assert sum(e["kind"] == "turn.accepted" for e in rows) == 2
        questions = [e for e in rows if e["kind"] == "question.updated"]
        assert questions[-1]["payload"]["status"] == "stopped"
        assert not any(e["payload"].get("answers") for e in questions)
        children = [json.loads(p.read_text()) for p in (path / "children").glob("*.json")]
        assert len(children) == 1 and children[0]["status"] == "interrupted"
        assert json.loads((path / "checkpoint.json").read_text())["status"] == "uncertain"
        results.append(
            {
                "preset": preset,
                "completed_read_then_resume_without_replay": True,
                "stop_then_exit_during_child_question": True,
                "one_interrupted_parent_and_child": True,
                "question_stopped_without_answer": True,
                "uncertain_checkpoint_retained": True,
                "clean_terminal_exit": True,
            }
        )
        print(json.dumps(results[-1]), flush=True)
    files = [
        *sorted((ROOT / "src/amplifier_tui").glob("*.py")),
        *sorted((ROOT / "frontends/ratatui/src").glob("*.rs")),
        ROOT / "frontends/ratatui/Cargo.lock",
        Path(__file__).resolve(),
    ]
    receipt = {
        "scope": "Live native resume and child-question Stop/exit; not arbitrary cancellation safety",
        "results": results,
        "source_fingerprints": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files
        },
    }
    (ROOT / args.output).write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()

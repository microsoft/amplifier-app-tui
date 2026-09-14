"""Live terminal gate: delegation, a v2 agent recipe, questions and retained modes.

Six billed parent turns plus four child turns, across the two real presets.
Read-only task instructions are not a sandbox. Private evidence remains ignored.
"""

import argparse
import hashlib
import json
import os
import sys
import uuid

import yaml
from controls_probe import observed
from interaction_probe import action, capture, click
from navigation_probe import read_events
from questions_probe import wait_ready
from terminal_probe import ROOT, Probe

from amplifier_tui.conversations import resolve_resume


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", required=True, action="store_true")
    parser.parse_args()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        parser.error("Supply ANTHROPIC_API_KEY explicitly")
    state = ROOT / ".state/session-repairs-live" / uuid.uuid4().hex
    state.mkdir(parents=True, mode=0o700)
    recipe = state / "read-only.yaml"
    recipe.write_text(
        yaml.safe_dump(
            {
                "name": "read-only-proof",
                "description": "Read one project field",
                "version": "1.0.0",
                "schema_version": 2,
                "dependencies": [
                    {
                        "source": str(ROOT.parent / "amplifier-foundation"),
                        "kind": "bundle",
                        "required_agents": ["foundation:explorer"],
                    }
                ],
                "steps": [
                    {
                        "id": "read",
                        "agent": "foundation:explorer",
                        "output": "project",
                        "prompt": f"Use only read_file to read {ROOT / 'pyproject.toml'}. Reply only with the project name. Do not edit, run commands, delegate or use any other tools.",
                    }
                ],
            }
        )
    )
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
            ready = observed(probe, path, "session.ready")[-1]["payload"]
            assert ready["capabilities"]["delegation"]
            probe.send(
                (
                    "Perform these two read-only checks, then summarize briefly. First use delegate exactly once with the available explorer agent, context_depth none, asking it to use only read_file to read pyproject.toml and report the project name, with no other tools, edits or commands. "
                    f"Second use recipes operation execute with recipe_path {recipe}. "
                    "Do not author or modify a recipe, enter a mode, run commands, or do any other work.\r"
                ).encode()
            )
            assert (
                observed(probe, path, "turn.ended", timeout=240)[-1]["payload"]["status"]
                == "completed"
            )
            children = [json.loads(p.read_text()) for p in (path / "children").glob("*.json")]
            assert len(children) == 2 and all(c["status"] == "completed" for c in children), (
                children
            )
            tools = [e["payload"] for e in read_events(path) if e["kind"] == "tool.updated"]
            for name in ("delegate", "recipes"):
                assert any(t["name"] == name and t["status"] == "succeeded" for t in tools)
            assert all(any(m.get("role") == "tool" for m in c["messages"]) for c in children)
            capture(probe, f"repairs-live-{preset}-children")
            probe.wait("[ Send ]")
            probe.send(
                b'Use only request_user_input once to ask id proceed, question "Should I proceed?", options "Yes, continue" and "No, stop". Wait for the answer, then acknowledge it without doing any other work.\r'
            )
            observed(probe, path, "question.updated")
            probe.wait("[ Answer question ]")
            capture(probe, f"repairs-live-{preset}-question")
            click(probe, "[ Answer question ]")
            probe.wait("Yes, continue")
            probe.send(b"Yes, continue\r")
            probe.wait("Submit reviewed")
            probe.send(b"Submit reviewed\r")
            assert (
                observed(probe, path, "turn.ended", count=2)[-1]["payload"]["status"] == "completed"
            )
            probe.wait("[ Send ]")
            probe.send(
                b"Use only mode with operation set and name explore. Wait for the real user approval, then briefly acknowledge the outcome. No other tools or work.\r"
            )
            probe.wait("Review decision", timeout=90)
            click(probe, "Review decision")
            probe.wait("Options (exact runtime scope)")
            capture(probe, f"repairs-live-{preset}-mode-decision")
            probe.send(b"Change mode\r")
            assert (
                observed(probe, path, "turn.ended", count=3)[-1]["payload"]["status"] == "completed"
            )
            assert json.loads((path / "modes.json").read_text())["mode"] == "explore"
            capture(probe, f"repairs-live-{preset}-mode")
        finally:
            probe.close()
        before = len([r for r in read_events(path) if r["kind"] == "turn.accepted"])
        probe = Probe([*command, "--resume", record["id"]], cols=160)
        try:
            wait_ready(probe)
            action(probe, "Modes —", "Modes · current session policy")
            probe.wait("Current: explore")
            capture(probe, f"repairs-live-{preset}-restored-mode")
            probe.send(b"Default\r")
            probe.wait("Apply default")
            probe.send(b"\r")
            observed(probe, path, "modes.updated")
            probe.wait("Current: default")
            assert json.loads((path / "modes.json").read_text())["mode"] is None
            assert len([r for r in read_events(path) if r["kind"] == "turn.accepted"]) == before
        finally:
            probe.close()
        capture_files = list((directory / "context-intelligence").rglob("*.jsonl"))
        assert capture_files and sum(p.stat().st_size for p in capture_files) > 0
        assert "external dispatch disabled" in ready["storage_policy"]["hook-context-intelligence"]
        results.append(
            {
                "preset": preset,
                "completed_parent_turns": 3,
                "completed_children": 2,
                "v2_agent_recipe": True,
                "direct_question_answer": True,
                "mode_approval_restore_native_clear": True,
                "local_context_capture": True,
                "remote_context_dispatch": False,
            }
        )
        print(json.dumps(results[-1]), flush=True)
    files = [
        *sorted((ROOT / "frontends/ratatui/src").glob("*.rs")),
        *sorted((ROOT / "src/amplifier_tui").rglob("*.py")),
        ROOT / "scripts/run.py",
        ROOT / "scripts/session_repairs_probe.py",
    ]
    receipt = {
        "scope": __doc__,
        "results": results,
        "source_fingerprints": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files
        },
    }
    (ROOT / "notes/evidence/session-repairs-live.json").write_text(
        json.dumps(receipt, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()

"""Bounded live daily-work journey in disposable projects, through the native launcher.

Eight root turns (including one queued turn) and three child turns per preset at
most on the intended path; 240 seconds per turn. Charges are provider-owned; expect
a few dollars for the two-preset run, not a billing guarantee. No personal services.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import yaml
from controls_probe import observed
from experience_probe import Journey
from interaction_probe import action
from navigation_probe import read_events
from questions_probe import wait_ready
from release_wheel import source_fingerprint
from terminal_probe import ROOT

from amplifier_tui.conversations import resolve_resume


def exercise(
    preset,
    directory,
    executable,
    *,
    activity_only=False,
    flow_only=False,
    feedback_only=False,
    capture_prefix="experience-live",
):
    directory.mkdir(parents=True, mode=0o700)
    cwd, state = directory / "project", directory / "state"
    cwd.mkdir()
    subprocess.run(["git", "init", "-q", str(cwd)], check=True)
    (cwd / "summary.py").write_text("def total(values):\n    return values[0]\n")
    (cwd / "test_summary.py").write_text(
        "from summary import total\n\ndef test_total():\n    assert total([5, 7]) == 12\n"
    )
    test_hash = hashlib.sha256((cwd / "test_summary.py").read_bytes()).hexdigest()
    (cwd / "brief.txt").write_text(
        "Build a small total function. Proposal A costs 10 units and needs manual upkeep. "
        "Proposal B costs 15 units and automates upkeep. Prefer ongoing simplicity.\n"
    )
    recipe = cwd / "review.yaml"
    recipe.write_text(
        yaml.safe_dump(
            {
                "name": "brief-review",
                "description": "Read the owned brief",
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
                        "id": "review",
                        "agent": "foundation:explorer",
                        "output": "brief",
                        "prompt": f"Use only read_file to read {cwd / 'brief.txt'}. Summarize it in one sentence. No other tools or changes.",
                    }
                ],
            }
        )
    )
    command = [str(executable), "--no-install", "--state-dir", str(state)]
    journey = Journey([*command, "--preset", preset, "--cwd", str(cwd)], directory / "first")
    p = journey.probe
    count = 0

    def finish():
        nonlocal count
        count += 1
        ended = observed(p, path, "turn.ended", count=count, timeout=240)[-1]
        assert ended["payload"]["status"] == "completed", ended["payload"]["status"]
        p.wait("[ Send ]")
        journey.record("completed", turn=count)
        print(json.dumps({"preset": preset, "completed_root_turn": count}), flush=True)

    def send(prompt):
        assert count < 8, "Root turn budget exceeded"
        journey.send(b"\x1b[200~" + prompt.encode() + b"\x1b[201~\r", label="explicit-send")

    try:
        wait_ready(p, timeout=120)
        record = resolve_resume(state, "latest")
        path = state / "conversations" / record["id"]
        journey.screenshot(f"{capture_prefix}-{preset}-ready")
        action(p, "Getting started", "Getting started")
        p.send(b"\x1b")
        p.wait("Actions / choices", absent=True)
        if feedback_only:
            # Exercise the in-process host replacement, not only process resume.
            action(p, "New conversation", "[ Send ]")
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                candidate = resolve_resume(state, "latest")
                if candidate["id"] != record["id"]:
                    break
                p.read(0.1)
            assert candidate["id"] != record["id"], "New conversation did not open"
            p.wait(candidate["id"][:8], timeout=120)
            p.wait("Ready", timeout=120)
            record = candidate
            path = state / "conversations" / record["id"]
            for prompt in (
                "Use only read_file to read brief.txt. Compare its two proposals in one short paragraph. No other tools, modes, or changes.",
                "Now recommend one of those proposals for a small team prioritizing low ongoing maintenance, with one reason. Do not call tools or change anything.",
            ):
                send(prompt)
                finish()
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                metadata = json.loads((path / "metadata.json").read_text())
                if metadata.get("title_source") == "generated":
                    break
                p.read(0.1)
            assert metadata.get("title_source") == "generated", (
                "Naming hook did not produce a title"
            )
            p.wait(metadata["title"])
            calls = [e for e in read_events(path) if e["payload"].get("usage_scope") == "session"]
            assert calls and all("Session naming" in e["payload"]["text"] for e in calls)
            journey.screenshot(f"{capture_prefix}-{preset}-named")
            p.send(b"Keep this unsent follow-up")
            journey.close()
            journey = Journey([*command, "--resume", record["id"]], directory / "named-return")
            p = journey.probe
            wait_ready(p, timeout=120)
            p.wait("Keep this unsent follow-up")
            p.wait(metadata["title"])
            assert sum(e["kind"] == "turn.accepted" for e in read_events(path)) == 2
            journey.screenshot(f"{capture_prefix}-{preset}-named-resumed")
            return {
                "preset": preset,
                "root_turns": 2,
                "generated_name": True,
                "session_only_utility_calls": len(calls),
                "resume_without_replay": True,
                "scope": "Owned proposal brief; no personal services",
            }
        send(
            (
                "Launch four delegate calls IN PARALLEL, each anchors:explorer and context_depth none. "
                "Give them distinct tasks: read brief.txt and report proposal A; read brief.txt and report proposal B; "
                "read summary.py and report its purpose; read test_summary.py and report its assertion. "
                "Each child must use read_file exactly once, no other tools or changes. Wait for all four to finish. "
                if flow_only
                else "Use delegate exactly once with anchors:explorer and context_depth none to read brief.txt and summarize, no changes. "
            )
            + f"Then use recipes operation execute recipe_path {recipe}. Do not modify the recipe, run shell commands, enter modes, or do other work. Summarize both results briefly."
        )
        observed(p, path, "tool.updated", timeout=120)
        if flow_only:
            observed(p, path, "tool.progress", count=8, timeout=120)
            journey.screenshot(f"{capture_prefix}-{preset}-inline-working")
            action(p, "Interact", "Interact ·")
            p.send(b"\x1b[A\r")
            journey.screenshot(f"{capture_prefix}-{preset}-inline-expanded")
            p.send(b"\x1b")
            p.wait("Interact ·", absent=True)
        action(p, "expand tools", "Activity ·")
        journey.screenshot(f"{capture_prefix}-activity-{preset}-working")
        finish()
        tools = [e["payload"] for e in read_events(path) if e["kind"] == "tool.updated"]
        for tool in ("delegate", "recipes"):
            assert any(t["name"] == tool and t["status"] == "succeeded" for t in tools), tool
        child_rows = [json.loads(child.read_text()) for child in (path / "children").glob("*.json")]
        root_ids = {
            e["item_id"]
            for e in read_events(path)
            if e["kind"] == "tool.updated" and e["payload"].get("name") in ("delegate", "recipes")
        }
        assert len(child_rows) == (5 if flow_only else 2) and all(
            c.get("parent_item_id") in root_ids for c in child_rows
        )
        # Drill into actual nested observations, never replaying a tool.
        p.send("succeeded · delegate\r".encode())
        p.wait("Preview · observed")
        p.send(b"Agent\r")
        p.wait("Activity · delegate / Agent")
        journey.screenshot(f"{capture_prefix}-activity-{preset}-child")
        p.send(b"read_file\r")
        p.wait("Preview · observed")
        journey.screenshot(f"{capture_prefix}-activity-{preset}-child-tool")
        p.send(b"Exact observed\r")
        p.wait("Copy observed evidence")
        journey.screenshot(f"{capture_prefix}-activity-{preset}-child-source")
        p.send(b"\x1b")
        p.wait("Actions / choices", absent=True)
        journey.screenshot(f"{capture_prefix}-{preset}-delegation-recipe")
        if activity_only or flow_only:
            usage_count = 0
            if flow_only:
                from decimal import Decimal

                from amplifier_tui.events import Event
                from amplifier_tui.inspection import CallUsage

                journal = read_events(path)
                calls = [e for e in journal if "usage_call" in e["payload"]]
                usage_count = len(calls)
                assert calls and len({e["item_id"] for e in calls}) == len(calls)
                assert {
                    e["payload"].get("child_id") for e in calls if e["payload"].get("child_id")
                } == {child.stem for child in (path / "children").glob("*.json")}
                ledger = CallUsage(Event(**e) for e in journal)
                expected = sum(
                    (
                        Decimal(e["payload"]["usage_call"]["cost_usd"])
                        for e in calls
                        if "cost_usd" in e["payload"]["usage_call"]
                    ),
                    Decimal(0),
                )
                assert ledger.session["totals"]["cost_usd"] == expected
                summary = [
                    e
                    for e in journal
                    if e["kind"] == "display.message" and e["payload"].get("source") == "usage"
                ][-1]
                assert summary["payload"]["text"] == ledger.costs()
                p.send(b"Unsent return task")
                journey.close()
                journey = Journey([*command, "--resume", record["id"]], directory / "flow-return")
                p = journey.probe
                wait_ready(p, timeout=120)
                p.wait("Unsent return task")
                assert sum(e["kind"] == "turn.accepted" for e in read_events(path)) == 1
                journey.screenshot(f"{capture_prefix}-{preset}-usage-resumed")
            for cols, rows in ((80, 24), (40, 20), (175, 50)):
                journey.resize(cols, rows)
                p.wait("[Activity]")
                journey.screenshot(f"{capture_prefix}-{preset}-{cols}x{rows}")
            return {
                "preset": preset,
                "root_turns": 1,
                "child_turns": len(child_rows),
                "actual_delegate_recipe_activity": True,
                "parent_call_correlated": True,
                "observed_model_calls": usage_count,
                "usage_and_resume": flow_only,
                "scope": "Owned project; read-only inspection, not personal services",
            }
        send(
            "Use only mode operation set name explore. Wait for actual user approval, then acknowledge. No other tools or work."
        )
        p.wait("Review decision", timeout=120)
        action(p, "Decisions", "Options (exact runtime scope)")
        journey.screenshot(f"{capture_prefix}-{preset}-permission")
        p.send(b"Change mode\r")
        finish()
        p.send(b"\x1b[200~/mode off\x1b[201~\r")
        p.wait("Mode command finished · default")
        send(
            'Use only request_user_input exactly once: id rounding, question "Which rounding should the report use?", options "Whole numbers" and "Two decimals". Wait for my answer, then acknowledge briefly. Do no other work.'
        )
        observed(p, path, "question.updated")
        p.wait("[ Answer question ]")
        # A deterministic waiting point while real provider/tool work is live.
        action(p, "Correct active turn", "Correction for this turn only")
        p.send(b"Keep the acknowledgement to one sentence.\r")
        p.wait("Correction for this turn only", absent=True)
        p.wait("Actions / choices", absent=True)
        observed(p, path, "steering.updated")
        p.wait("[ Queue ]")
        p.send(b"\x1b[200~Without tools, repeat my selected rounding.\x1b[201~")
        p.wait("Without tools, repeat my selected rounding.")
        p.send(b"\r")
        p.wait("[Pending 1]")
        action(p, "Pending follow-ups", "Pending follow-ups")
        p.send(b"repeat my selected\r")
        p.wait("Follow-up · inspect")
        p.send(b"Edit waiting\r")
        p.wait("Edit waiting follow-up")
        p.send(b" Use one sentence.\r")
        p.wait("Edit waiting follow-up", absent=True)
        p.wait("(paused)")
        action(p, "Questions —", "Questions · clarification")
        p.send(b"\r")
        p.wait("Questions · review answers")
        p.send(b"rounding\r")
        p.wait("Question · choose")
        p.send(b"Two decimals\r")
        p.wait("Submit reviewed")
        journey.screenshot(f"{capture_prefix}-{preset}-answer")
        p.send(b"Submit reviewed\r")
        finish()
        assert sum(e["kind"] == "turn.accepted" for e in read_events(path)) == count
        action(p, "Pending follow-ups", "Pending follow-ups · paused")
        p.send(b"Run pending\r")
        finish()
        send(
            f"Use bash to run exactly {sys.executable} -m pytest -q --junitxml=before.xml in this working directory. Do not edit anything or run other commands. Report whether the actual test passes."
        )
        finish()
        assert 'failures="1"' in (cwd / "before.xml").read_text()
        journey.screenshot(f"{capture_prefix}-{preset}-failed-test")
        send(
            f"Read summary.py and test_summary.py, fix only summary.py so total sums all values, then use bash to run {sys.executable} -m pytest -q --junitxml=after.xml. Do not modify tests, delete files, install packages, delegate, or change anything outside this project. Report the observed result and show the fixed function as a Python code block."
        )
        finish()
        assert 'failures="0"' in (cwd / "after.xml").read_text()
        assert hashlib.sha256((cwd / "test_summary.py").read_bytes()).hexdigest() == test_hash
        journey.screenshot(f"{capture_prefix}-{preset}-fixed-test")
        action(p, "Workspace changes", "Workspace changes · observed")
        journey.screenshot(f"{capture_prefix}-{preset}-review")
        p.send(b"\x1b")
        p.wait("Actions / choices", absent=True)
        send(
            "Read brief.txt and produce a concise decision brief comparing A and B in a table, recommend one for the stated preference and give one caveat. Do not edit files or use tools other than read_file."
        )
        finish()
        journey.screenshot(f"{capture_prefix}-{preset}-information-work")
        p.send(b"Keep this unsent next task")
    finally:
        journey.close()
    original_calls = sum(e["kind"] == "turn.accepted" for e in read_events(path))
    journey = Journey([*command, "--resume", record["id"]], directory / "return")
    p = journey.probe
    try:
        wait_ready(p, timeout=120)
        p.wait("Keep this unsent next task")
        assert sum(e["kind"] == "turn.accepted" for e in read_events(path)) == original_calls
        journey.screenshot(f"{capture_prefix}-{preset}-resumed")
        p.send(b"\x01\x0b")
        question_count = sum(e["kind"] == "question.updated" for e in read_events(path))
        send(
            'Use delegate exactly once with agent self and context_depth none, asking it to use only request_user_input to ask question "Continue this task?", id continue, options Yes and No. Wait for the answer; do no other work. Omit provider preferences and orchestrator overrides.'
        )
        observed(p, path, "question.updated", count=question_count + 1)
        p.wait("[ Answer question ]")
        journey.screenshot(f"{capture_prefix}-{preset}-child-wait")
        action(p, "Stop active", "Interrupted")
    finally:
        journey.close()
    endings = [e["payload"]["status"] for e in read_events(path) if e["kind"] == "turn.ended"]
    assert endings == ["completed"] * 7 + ["interrupted"], endings
    children = [json.loads(f.read_text()) for f in (path / "children").glob("*.json")]
    assert len(children) == 3 and sum(c["status"] == "completed" for c in children) == 2
    return {
        "preset": preset,
        "root_turns": 8,
        "completed_children": 2,
        "interrupted_child": 1,
        "actual_recipe": True,
        "actual_permission_and_question": True,
        "queue_edit_pause_release": True,
        "failed_then_passing_tests": True,
        "test_source_unchanged": True,
        "information_work": True,
        "resume_without_replay": True,
        "original_state": str(path),
        "scope": "Owned projects, not personal services or a sandbox",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--feedback-only",
        action="store_true",
        help="Two bounded proposal-review turns per preset, ecosystem naming/accounting and resume",
    )
    parser.add_argument(
        "--flow-only",
        action="store_true",
        help="Four parallel delegates plus a recipe, inline interaction, per-call accounting and resume",
    )
    parser.add_argument(
        "--activity-only",
        action="store_true",
        help="One bounded delegate + recipe turn per preset; two children each, no mode/permission journey",
    )
    parser.add_argument(
        "--keep-artifacts",
        action="store_true",
        help="Retain successful private probe state; failed state is always preserved",
    )
    args = parser.parse_args()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        parser.error("Supply ANTHROPIC_API_KEY explicitly")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as output:
        directory = Path(tempfile.mkdtemp(prefix="experience-live-", dir=ROOT / ".state"))
        runs = []
        success = False
        written = False
        try:
            for preset in ("anchors", "anchors-amp-dev"):
                runs.append(
                    exercise(
                        preset,
                        directory / preset,
                        args.executable,
                        activity_only=args.activity_only,
                        flow_only=args.flow_only,
                        feedback_only=args.feedback_only,
                        capture_prefix=args.output.stem,
                    )
                )
                print(json.dumps({"preset": preset, "passed": True}), flush=True)
            success = True
        finally:
            output.write(
                json.dumps(
                    {
                        "runs": runs,
                        "state": str(directory) if args.keep_artifacts or not success else None,
                        "state_retained": args.keep_artifacts or not success,
                        "source_sha256": {
                            str(p.relative_to(ROOT)): source_fingerprint(p)
                            for p in [
                                *sorted((ROOT / "frontends/ratatui/src").glob("*.rs")),
                                *sorted((ROOT / "src/amplifier_tui").glob("*.py")),
                            ]
                        },
                    },
                    indent=2,
                )
                + "\n"
            )
            args.output.chmod(0o600)
            written = True
            if success and written and not args.keep_artifacts:
                shutil.rmtree(directory)


if __name__ == "__main__":
    main()

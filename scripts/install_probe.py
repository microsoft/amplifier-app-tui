"""Exercise an installed native product outside its source checkout; --live bills turns."""

import argparse
import hashlib
import json
import os
import subprocess
import uuid
from pathlib import Path

from controls_probe import observed
from interaction_probe import action, capture
from navigation_probe import read_events
from questions_probe import wait_ready
from terminal_probe import ROOT, Probe

from amplifier_tui.conversations import resolve_resume


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", required=True, type=Path)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output", default="notes/evidence/installed-fixture.json")
    args = parser.parse_args()
    if args.live and not os.environ.get("ANTHROPIC_API_KEY"):
        parser.error("Supply the live provider credential explicitly")
    identity = uuid.uuid4().hex
    work = ROOT.parent / ".install-probe-work" / identity
    work.mkdir(parents=True, mode=0o700)
    marker = "violet-" + uuid.uuid4().hex[:10]
    (work / "note.txt").write_text(marker)
    state = ROOT / ".state/installed-probe" / identity
    guide = subprocess.check_output(
        [str(args.executable.resolve()), "--getting-started"], cwd=work, text=True
    )
    assert "first conversation" in guide and "NOT an AI assistant" in guide
    report = subprocess.check_output(
        [
            str(args.executable.resolve()),
            "--support-report",
            "--fixture",
            "--state-dir",
            str(state / "check-only"),
        ],
        cwd=work,
        text=True,
    )
    assert json.loads(report)["schema"] == 1
    assert str(work) not in report and str(state) not in report and not state.exists()
    results = []
    for preset in ("anchors", "anchors-amp-dev") if args.live else ("fixture",):
        directory = state / preset
        command = [str(args.executable.resolve()), "--state-dir", str(directory)]
        options = ["--preset", preset] if args.live else ["--fixture"]
        probe = Probe([*command, *options], cwd=work, cols=160)
        try:
            wait_ready(probe, timeout=300)
            record = resolve_resume(directory, "latest")
            path = directory / "conversations" / record["id"]
            assert record["launch"]["sources"] is None
            assert record["launch"]["cwd"] == str(work)
            ready = [e for e in read_events(path) if e["kind"] == "session.ready"][-1]
            assert "request_user_input" in ready["payload"]["tools"]
            prompt = (
                'Use delegate exactly once with agent "self" and context_depth "none", '
                'instruction "Use read_file to read note.txt; return its exact marker. No other tools, commands, writes or delegation." '
                "Omit provider_preferences, model_role and orchestrator overrides. Reply briefly with the marker."
                if args.live
                else "Compute a digest"
            )
            probe.send(prompt.encode())
            action(probe, "Getting started", "Help · choose a topic")
            probe.send(b"Queue or steer\r")
            probe.wait("Help · Queue or steer?")
            probe.wait("does not undo")
            capture(probe, f"installed-{preset}-help")
            probe.send(b"\x1b")
            probe.wait("Actions / choices", absent=True)
            assert not any(e["kind"] == "turn.accepted" for e in read_events(path))
            probe.send(b"\r")
            assert (
                observed(probe, path, "turn.ended", timeout=180)[-1]["payload"]["status"]
                == "completed"
            )
            probe.wait("[ Send ]")
            probe.wait(marker if args.live else "Fixture round trip complete")
            if args.live:
                assert any(
                    e["kind"] == "child.observed" and e["payload"].get("status") == "succeeded"
                    for e in read_events(path)
                )
            action(probe, "Activity evidence", "Activity evidence · identified")
            capture(probe, f"installed-{preset}-activity")
        finally:
            probe.close()
        before = sum(e["kind"] == "turn.accepted" for e in read_events(path))
        probe = Probe([*command, "--resume", record["id"]], cwd=work, cols=160)
        try:
            wait_ready(probe, timeout=180)
            assert sum(e["kind"] == "turn.accepted" for e in read_events(path)) == before
            probe.send(
                b"Without tools, repeat the exact marker from your last reply.\r"
                if args.live
                else b"Compute again\r"
            )
            assert (
                observed(probe, path, "turn.ended", count=2, timeout=180)[-1]["payload"]["status"]
                == "completed"
            )
            probe.wait("[ Send ]")
            if args.live:
                finals = [e for e in read_events(path) if e["kind"] == "text.final"]
                assert marker in finals[-1]["payload"]["text"]
            capture(probe, f"installed-{preset}-resumed")
        finally:
            probe.close()
        results.append(
            {
                "preset": preset,
                "outside_checkout": True,
                "remote_sources": True,
                "question_tool_mounted": True,
                "tool_round_trip": True,
                "resume_no_submission": True,
                "second_turn": True,
                "local_guidance_no_state": True,
                "help_no_submission": True,
            }
        )
        print(json.dumps(results[-1]), flush=True)
    doctor = json.loads(subprocess.check_output([str(args.executable.resolve()), "--doctor"]))
    package = Path(doctor["native_binary"]).parents[1]
    receipt = {
        "scope": "Installed native binary, no workspace source map; live calls only with --live",
        "results": results,
        "executable_sha256": hashlib.sha256(args.executable.resolve().read_bytes()).hexdigest(),
        "app_version": doctor["version"],
        "native_sha256": hashlib.sha256(Path(doctor["native_binary"]).read_bytes()).hexdigest(),
        "installed_source_fingerprints": {
            str(p.relative_to(package)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(package.rglob("*.py"))
        },
    }
    (ROOT / args.output).write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()

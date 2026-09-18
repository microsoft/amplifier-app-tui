"""Native configured-policy check in an owned home; --live bills four read-only turns.

No personal settings/history are loaded. Raw state/captures stay private. This is
functional verification, not policy-equivalent latency evidence.
"""

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import yaml
from interaction_probe import action, capture
from release_wheel import source_fingerprint
from terminal_probe import ROOT, Probe


def exercise(preset=None, *, controls=False, keep_artifacts=False):
    from amplifier_tui.cli_compat import session_directory

    base = ROOT / ".state/cli-compat-probe"
    base.mkdir(parents=True, exist_ok=True)
    state = Path(tempfile.mkdtemp(dir=base))
    home, cwd = state / "home", state / "workspace"
    home.mkdir()
    cwd.mkdir()
    (cwd / "probe.txt").write_text("Controlled CLI compatibility marker.\n")
    skill = cwd / ".amplifier/skills/compat-cwd-skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: compat-cwd-skill\ndescription: Controlled cwd discovery marker\nuser-invocable: true\nshortcut: compat-check\n---\nReport SKILL-CHECK-OK and the user's arguments. Do not run tools beyond loading this skill, edit files, or delegate.\n"
    )
    recipe_dir = cwd / "recipes"
    recipe_dir.mkdir()
    (recipe_dir / "review-only.yaml").write_text(
        "name: review-only\n# Filename fixture, not a validated recipe\n"
    )
    sources = {
        k: str((ROOT.parent / v).resolve())
        for k, v in json.loads((ROOT.parent / "tui-sources.json").read_text()).items()
    }
    for repo in (
        "amplifier-bundle-wayfinder",
        "amplifier-bundle-notify",
        "amplifier-bundle-skills",
    ):
        sources[f"https://github.com/microsoft/{repo}"] = str(ROOT.parent / repo)
    (state / "sources.json").write_text(json.dumps(sources))
    bundle = (
        (ROOT.parent / "amplifier-foundation/bundles" / preset)
        if preset
        else (ROOT / "src/amplifier_tui/fixtures/bundle.yaml")
    )
    settings = {"bundle": {"active": str(bundle)}}
    if preset:
        settings["config"] = {
            "providers": [
                {
                    "module": "provider-anthropic",
                    "source": str(ROOT.parent / "amplifier-module-provider-anthropic"),
                    "config": {
                        "api_key": "${ANTHROPIC_API_KEY}",
                        "default_model": "claude-haiku-4-5",
                        "priority": 1,
                    },
                }
            ]
        }
    (home / "settings.yaml").write_text(yaml.safe_dump(settings))
    source = session_directory(home, cwd) / "controlled-cli-session"
    source.mkdir(parents=True)
    (source / "metadata.json").write_text(json.dumps({"name": "Controlled earlier CLI work"}))
    original = (
        json.dumps({"role": "user", "content": "Historical import marker; do not execute."}) + "\n"
    )
    (source / "transcript.jsonl").write_text(original)
    command = [
        sys.executable,
        str(ROOT / "scripts/run.py"),
        "--no-install",
        "--settings-policy",
        "cli",
        "--cli-home",
        str(home),
        "--cwd",
        str(cwd),
        "--state-dir",
        str(state / "tui"),
        "--sources",
        str(state / "sources.json"),
    ]
    probe = Probe(command, cols=160)
    success = False
    try:
        probe.wait("Ready", timeout=120)
        capture(probe, f"cli-compatible-{preset or 'fixture'}-ready")
        if controls:
            # Local setup/clear does not authorize an autonomous provider loop.
            probe.send(b"\x1b[200~/goal --max-turns 1 Verify this owned probe\x1b[201~\r")
            probe.wait("Goal set (max 1 turns)")
            probe.wait("Goal")
            capture(probe, f"cli-controls-{preset or 'fixture'}-goal")
            probe.send(b"\x1b[200~/goal clear\x1b[201~\r")
            probe.wait("Goal cleared")
            probe.send(b"\x1b[200~/config tools\x1b[201~\r")
            probe.wait("Mounted tools:")
            probe.send(b"\x1b[200~/provider auto\x1b[201~\r")
            probe.wait("Conversation provider saved")
        action(probe, "Skills —", "compat-cwd-skill")
        capture(probe, f"cli-compatible-{preset or 'fixture'}-cwd-skill")
        probe.send(b"\x1b")
        probe.wait("Actions / choices", absent=True)
        # Generic skill command discovery/insertion; no call until explicit Send.
        action(probe, "compat-check literal-argument-marker", "Skill command inserted")
        probe.wait("/compat-check literal-argument-marker")
        capture(probe, f"cli-workflows-{preset or 'fixture'}-skill-draft")
        if preset:
            probe.send(b"\r")
            probe.wait_idle(timeout=120)
            probe.wait("SKILL-CHECK-OK")
            probe.wait("literal-argument-marker")
            capture(probe, f"cli-workflows-{preset}-skill-result")
        else:
            probe.send(b"\x01\x0b")
        # File discovery is separate from recipe activity and active runs.
        action(probe, "Recipe files", "Recipe files · local candidates")
        probe.send(b"review-only.yaml\r")
        probe.wait("Recipe file review added to draft")
        probe.wait("Do not execute it until I explicitly confirm")
        capture(probe, f"cli-workflows-{preset or 'fixture'}-recipe-unsent")
        probe.send(b"\x01\x0b")
        # Pasting bypasses slash's action-menu shortcut, exercising host refusal.
        probe.send(b"\x1b[200~/unknown-command\x1b[201~")
        probe.send(b"\r")
        probe.wait("Nothing sent", timeout=10)
        # Clear the retained draft, then submit the one explicitly authorized turn.
        probe.send(b"\x01\x0b")
        if controls and preset:
            probe.send(b"\x1b[200~/mode explore on\x1b[201~\r")
            probe.wait("Mode command finished · explore")
        prompt = (
            (
                "Use read_file to read probe.txt. Report the marker. Do not use other tools, "
                "edit files, run commands or delegate."
            )
            if preset
            else "Compute a digest"
        )
        probe.send(prompt.encode() + b"\r")
        probe.wait_idle(timeout=120)
        probe.wait("▸ Read · done" if preset else "▸ fixture_probe · done")
        if preset:
            probe.wait("Controlled CLI compatibility marker")
        else:
            # Compact rows intentionally omit result bodies. Verify the retained
            # source through the ordinary evidence action, not a transcript leak.
            action(probe, "expand selected", "Evidence ·")
            probe.wait("sha256")
            capture(probe, "cli-compatible-fixture-evidence")
            probe.send(b"\x1b")
            probe.wait("Evidence ·", absent=True)
        capture(probe, f"cli-compatible-{preset or 'fixture'}-tool")
        if controls and preset:
            probe.send(b"\x1b[200~/mode off\x1b[201~\r")
            probe.wait("Mode command finished · default")
        action(probe, "Resume", "CLI sessions")
        capture(probe, f"cli-compatible-{preset or 'fixture'}-resume")
        # Select the actual Resume menu entry, not adjacent Escape/paste bytes
        # whose terminal parsing is timing-dependent.
        probe.send(b"CLI sessions\r")
        probe.wait("Controlled earlier CLI work")
        capture(probe, f"cli-compatible-{preset or 'fixture'}-cli-history")
        probe.send(b"Controlled earlier CLI work\r")
        probe.wait("Import CLI reference")
        capture(probe, f"cli-compatible-{preset or 'fixture'}-import-confirm")
        probe.send(b"\x1b")
        assert (source / "transcript.jsonl").read_text() == original
        success = True
        return {
            "preset": preset,
            "mode": "live" if preset else "fixture",
            "settings_policy": "cli",
            "tool": "read_file" if preset else "fixture_probe",
            "unsupported_command_refused": True,
            "history_confirmation_cancelled": True,
            "source_unchanged": True,
            "skill_command_insertion": True,
            "live_skill_arguments": bool(preset),
            "recipe_file_review_unsent": True,
            "local_goal_config_provider_controls": controls,
            "read_tool_with_explicit_mode": bool(controls and preset),
            "scope": "Controlled configuration; not personal-service or latency parity",
        }
    finally:
        probe.close()
        if success and not keep_artifacts:
            shutil.rmtree(state)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument(
        "--controls",
        action="store_true",
        help="Also exercise local goal/config/provider commands and explicit modes; no extra model turns",
    )
    parser.add_argument(
        "--keep-artifacts",
        action="store_true",
        help="Retain successful private probe state; failed state is always preserved",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Choose a new receipt path")
    if args.live and not os.environ.get("ANTHROPIC_API_KEY"):
        parser.error("Supply ANTHROPIC_API_KEY explicitly")
    runs = []
    for preset in ["anchors", "anchors-amp-dev"] if args.live else [None]:
        runs.append(exercise(preset, controls=args.controls, keep_artifacts=args.keep_artifacts))
        print(json.dumps(runs[-1]), flush=True)
    result = {
        "runs": runs,
        "source_sha256": {
            str(p.relative_to(ROOT)): source_fingerprint(p)
            for p in [
                *sorted((ROOT / "src/amplifier_tui").glob("*.py")),
                *sorted((ROOT / "frontends/ratatui/src").glob("*.rs")),
                Path(__file__).resolve(),
            ]
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()

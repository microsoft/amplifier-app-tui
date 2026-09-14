"""Run the functional Ratatui client with real Amplifier modules, not a design scene.

Installed and workspace launch share composition policy; no implicit CLI migration.
"""

import argparse
import json
import os
import platform
import sys
from importlib.metadata import version
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
FOUNDATION = (
    "git+https://github.com/microsoft/amplifier-foundation@e210edabd947af82d5121a240d6934283ac540b9"
)


def state_directory():
    override = os.environ.get("AMPLIFIER_TUI_STATE_DIR")
    if override:
        return Path(override).expanduser()
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return base / "amplifier-tui"


def executable(workspace=None):
    return (
        (workspace / "frontends/ratatui/target/release/amplifier-ratatui")
        if workspace
        else PACKAGE / "_bin/amplifier-ratatui"
    )


def arguments(argv=None, workspace=None, require_terminal=False):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--version",
        action="version",
        version=f"amplifier-tui {version('amplifier-app-tui')} · Ratatui",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Print local install diagnostics without opening a session",
    )
    parser.add_argument(
        "--getting-started", action="store_true", help="Show the offline first-conversation guide"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Explain local setup blockers without opening a session",
    )
    parser.add_argument(
        "--support-report",
        action="store_true",
        help="Print path-free local diagnostics for sharing; no session reads",
    )
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--preset", choices=["anchors", "anchors-amp-dev"])
    selection.add_argument("--bundle", help="Custom bundle path or URI")
    selection.add_argument(
        "--fixture", action="store_true", help="Real kernel, scripted provider; no live AI"
    )
    parser.add_argument(
        "--overlay",
        action="append",
        default=[],
        help="Ordered overlays; default live preset uses examples/anthropic.yaml",
    )
    parser.add_argument("--sources", type=Path)
    parser.add_argument("--cwd", type=Path)
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=workspace / ".state/work" if workspace else state_directory(),
    )
    parser.add_argument("--no-install", action="store_true")
    parser.add_argument(
        "--no-questions",
        action="store_true",
        help="Omit the default structured-question tool overlay for a new conversation",
    )
    parser.add_argument(
        "--resume",
        nargs="?",
        const="picker",
        help="Choose a saved conversation; optionally supply an ID or latest",
    )
    parser.add_argument(
        "--list-sessions",
        action="store_true",
        help="List saved conversation IDs and working directories",
    )
    parser.add_argument(
        "--export",
        nargs="?",
        const="latest",
        help="Export saved history privately to Markdown without launching a runtime",
    )
    parser.add_argument(
        "--recover",
        nargs="?",
        const="latest",
        help="Create a new conversation from historical context; original unchanged, no replay",
    )
    args = parser.parse_args(argv)
    if args.getting_started:
        from .onboarding import GETTING_STARTED

        print(GETTING_STARTED)
        parser.exit()
    if args.check or args.support_report:
        from .onboarding import local_checks, support_report

        if args.resume or args.recover or args.export or args.list_sessions:
            parser.error(
                "Setup checks inspect a new launch only; omit saved-conversation operations"
            )
        checks = local_checks(args, executable(workspace))
        if args.support_report:
            print(json.dumps(support_report(checks), indent=2))
        else:
            print("Amplifier TUI — local setup checks (no network or session opened)")
            for check in checks:
                print(f"[{check['status'].upper()}] {check['check']}: {check['message']}")
            print(
                "\nNext: amplifier-tui --getting-started. These checks do not prove live readiness."
            )
        parser.exit(1 if any(c["status"] == "error" for c in checks) else 0)
    if args.doctor:
        binary = executable(workspace)
        print(
            json.dumps(
                {
                    "version": version("amplifier-app-tui"),
                    "frontend": "ratatui",
                    "platform": platform.system(),
                    "architecture": platform.machine(),
                    "python": sys.executable,
                    "native_binary": str(binary),
                    "native_available": binary.is_file() and os.access(binary, os.X_OK),
                    "state_directory": str(args.state_dir.resolve()),
                    "shared_cli_state": "not imported",
                    "source_policy": "explicit workspace overrides"
                    if workspace
                    else "remote bundle sources",
                },
                indent=2,
            )
        )
        parser.exit(0 if binary.is_file() and os.access(binary, os.X_OK) else 1)
    if (
        require_terminal
        and not (args.export or args.list_sessions)
        and not (sys.stdin.isatty() and sys.stdout.isatty())
    ):
        parser.error(
            "The native app needs an interactive terminal. Use --getting-started or --check without one; amplifier-tui-host provides headless diagnostics."
        )
    if args.resume and args.recover:
        parser.error("Choose --resume or --recover")
    if (args.resume or args.recover) and (
        args.fixture
        or args.bundle
        or args.preset
        or args.overlay
        or args.cwd
        or args.sources
        or args.no_questions
    ):
        parser.error("--resume/--recover restores composition and cwd; omit composition overrides")
    if args.export:
        from amplifier_tui.recovery import export

        print(export(args.state_dir, args.export))
        parser.exit()
    if args.resume == "picker":
        from .resume_picker import choose

        try:
            selected = choose(args.state_dir)
        except ValueError as exc:
            parser.error(str(exc))
        if selected is None:
            parser.exit()
        args.resume, needs_recovery = selected
        if needs_recovery:
            args.recover, args.resume = args.resume, None
    if args.recover:
        from amplifier_tui.recovery import recover

        if args.resume:
            parser.error("Choose --resume or --recover")
        args.resume = recover(args.state_dir, args.recover)
    if args.list_sessions:
        from amplifier_tui.conversations import catalog

        for entry in catalog(args.state_dir):
            print(f"{entry['id']}  {entry['launch']['cwd']}")
        parser.exit()
    if args.resume:
        from amplifier_tui.conversations import resolve_resume

        if (
            args.fixture
            or args.bundle
            or args.preset
            or args.overlay
            or args.cwd
            or args.sources
            or args.no_questions
        ):
            parser.error(
                "--resume restores composition and cwd; do not supply preset/bundle/overlay/cwd/sources"
            )
        try:
            entry = resolve_resume(args.state_dir, args.resume)
        except ValueError as exc:
            parser.error(str(exc))
        saved = entry["launch"]
        args.resume = entry["id"]
        args.fixture, args.bundle = saved["fixture"], saved["bundle"]
        args.overlay = saved["overlays"]
        args.cwd = Path(saved["cwd"])
        args.sources = Path(saved["sources"]) if saved["sources"] else args.sources
    args.cwd = args.cwd or Path.cwd()
    args.sources = args.sources or (workspace.parent / "tui-sources.json" if workspace else None)
    if not args.cwd.is_dir():
        parser.error("Recorded/requested working directory does not exist")
    host = [sys.executable, "-m", "amplifier_tui", "--bridge"]
    if args.fixture:
        host += ["--fixture"]
    else:
        bundle = args.bundle or (
            str(workspace.parent / "amplifier-foundation/bundles" / (args.preset or "anchors"))
            if workspace
            else FOUNDATION + "#subdirectory=bundles/" + (args.preset or "anchors")
        )
        if workspace and not args.bundle and not Path(bundle).exists():
            parser.error("Preset source is missing; follow README source bootstrap first")
        host += ["--bundle", bundle]
        if not args.bundle and not args.overlay:
            if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
                parser.error(
                    "Set ANTHROPIC_API_KEY for the default live provider, supply --overlay for your provider, or use --fixture (no AI). No CLI credentials are imported."
                )
            args.overlay = [
                str(
                    (workspace / "examples" if workspace else PACKAGE / "assets") / "anthropic.yaml"
                )
            ]
    if not args.resume and not args.no_questions:
        question_overlay = str(
            (workspace / "examples" if workspace else PACKAGE / "assets") / "user-questions.yaml"
        )
        if question_overlay not in [str(Path(p).resolve()) for p in args.overlay]:
            args.overlay.insert(0, question_overlay)
    for overlay in args.overlay:
        host += ["--overlay", overlay]
    if args.sources and args.sources.exists():
        host += ["--sources", str(args.sources.resolve())]
    elif args.sources:
        parser.error("Source map missing; follow README source bootstrap or supply --sources")
    host += ["--cwd", str(args.cwd.resolve()), "--state-dir", str(args.state_dir.resolve())]
    if args.no_install:
        host.append("--no-install")
    if args.resume:
        host += ["--resume", args.resume]
    return parser, host


def main(workspace=None):
    if "--bridge" in sys.argv or "--headless" in sys.argv:
        from .__main__ import main as host_main

        return host_main()
    parser, host = arguments(workspace=workspace, require_terminal=True)
    binary = executable(workspace)
    if not binary.is_file() or not os.access(binary, os.X_OK):
        parser.error(
            "Native binary missing or not executable. Run --check for local setup guidance. Reinstall with Rust/Cargo available, or build the workspace Ratatui frontend."
        )
    os.execv(str(binary), [str(binary), "--host-json", json.dumps(host)])


if __name__ == "__main__":
    main()

"""Launch the connected Ratatui client or the explicit standalone development host."""

import argparse
import json
import os
import platform
import sys
from importlib.metadata import version
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
FOUNDATION = (
    "git+https://github.com/microsoft/amplifier-foundation@8a8e4f11918afd38ea8fe8f69cbec002226324f7"
)
CLI_COMMANDS = frozenset(
    {
        "init",
        "bundle",
        "provider",
        "routing",
        "module",
        "source",
        "agents",
        "allowed-dirs",
        "denied-dirs",
        "notify",
        "session",
        "sessions",
        "resume",
        "continue",
        "tool",
        "run",
        "update",
        "reset",
        "version",
    }
)


def cli_command(argv):
    """Explicit CLI-owned workflows, before importing either runtime or settings.

    Use argv, not a shell; keep cwd, environment, stdio and upstream safety gates.
    No arguments still means the native TUI. `cli` is an escape hatch for future
    CLI options; bare `cli` explains itself instead of starting another REPL.
    """
    if argv and argv[0] == "cli":
        return [sys.executable, "-m", "amplifier_app_cli", *(argv[1:] or ["--help"])]
    if argv and argv[0] in CLI_COMMANDS:
        return [sys.executable, "-m", "amplifier_app_cli", *argv]
    return None


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


def argument_parser(workspace=None):
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="CLI-compatible administration and scripting: amplifier-tui cli --help. "
        "Commands such as provider, bundle, routing, session, tool and run use the pinned CLI "
        "with its existing settings and session store. No arguments opens the native TUI.",
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Create an explicit provider overlay interactively; never asks for or stores keys",
    )
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
    parser.add_argument(
        "--settings-policy",
        choices=("cli", "isolated"),
        help="cli reads existing layered Amplifier settings; isolated uses only explicit presets/overlays",
    )
    parser.add_argument(
        "--cli-home",
        type=Path,
        help="Explicit Amplifier configuration home for CLI-compatible policy",
    )
    parser.add_argument("--cwd", type=Path)
    parser.add_argument(
        "--import-transcript",
        type=Path,
        help="Copy a UTF-8 transcript (up to 1 MiB) as historical reference into a NEW conversation; never canonical resume or implicit Send",
    )
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
        help="Choose a conversation from this directory; optionally supply an ID or latest",
    )
    parser.add_argument(
        "--list-sessions",
        action="store_true",
        help="List saved conversations from this working directory",
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
    housekeeping = parser.add_mutually_exclusive_group()
    housekeeping.add_argument(
        "--archive", metavar="ID", help="Hide a closed conversation; retains all history"
    )
    housekeeping.add_argument(
        "--restore", metavar="ID", help="Restore an archived conversation to Resume"
    )
    housekeeping.add_argument(
        "--list-archived",
        action="store_true",
        help="List archived conversations from this directory",
    )
    parser.add_argument(
        "--confirm", action="store_true", help="Explicitly confirm --archive or --restore"
    )
    return parser


def arguments(argv=None, workspace=None, require_terminal=False):
    parser = argument_parser(workspace)
    args = parser.parse_args(argv)
    if args.archive or args.restore or args.list_archived or args.confirm:
        allowed = {"archive", "restore", "list_archived", "confirm", "state_dir", "cwd", "cli_home"}
        if any(
            value != parser.get_default(name)
            for name, value in vars(args).items()
            if name not in allowed
        ):
            parser.error("Housekeeping is separate; use only --state-dir/--cwd with these options")
        if bool(args.archive or args.restore) != args.confirm:
            parser.error("Archive/restore requires an exact ID and --confirm; no change made")
        from amplifier_foundation.paths.resolution import get_amplifier_home

        from .conversations import archive_conversation, catalog

        try:
            directory = (args.cwd or Path.cwd()).resolve()
            home = (args.cli_home or get_amplifier_home()).resolve()
            if args.list_archived:
                for row in catalog(args.state_dir, cwd=directory, archived=True, cli_home=home):
                    print(f"{row['id']}  {row.get('title', 'Untitled')}")
            else:
                identity = args.archive or args.restore
                archive_conversation(
                    args.state_dir,
                    identity,
                    cwd=directory,
                    archived=bool(args.archive),
                    cli_home=home,
                )
                print(
                    f"{'Archived' if args.archive else 'Restored'} {identity}. History retained; nothing executed."
                )
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
        parser.exit()
    if args.import_transcript and (
        args.resume or args.recover or args.export or args.list_sessions or args.setup
    ):
        parser.error(
            "--import-transcript requires a new conversation; do not combine with resume/recover/export/list/setup"
        )
    if args.setup:
        from .onboarding import setup_provider

        if (
            args.resume
            or args.recover
            or args.export
            or args.list_sessions
            or args.check
            or args.support_report
        ):
            parser.error("--setup is a separate local configuration action")
        try:
            setup_provider()
        except (OSError, ValueError, EOFError, KeyboardInterrupt) as exc:
            parser.error(str(exc) or "Setup cancelled")
        parser.exit()
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
                    "shared_cli_state": "Connected clients share sessions through Unified. Standalone sessions use canonical CLI project history and shared settings unless an isolated home is chosen; only one standalone host may own a session. Diagnostics do not read shared settings/history.",
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
        or args.settings_policy
    ):
        parser.error("--resume/--recover restores composition and cwd; omit composition overrides")
    launch_cwd = (args.cwd or Path.cwd()).resolve()
    from amplifier_foundation.paths.resolution import get_amplifier_home

    discovery_home = (args.cli_home or get_amplifier_home()).resolve()
    if args.export:
        from amplifier_tui.recovery import export

        print(export(args.state_dir, args.export, cwd=launch_cwd, cli_home=discovery_home))
        parser.exit()
    if args.resume == "picker":
        from .resume_picker import choose

        try:
            selected = choose(args.state_dir, cwd=launch_cwd, cli_home=discovery_home)
        except ValueError as exc:
            parser.error(str(exc))
        if selected is None:
            parser.exit()
        args.resume, needs_recovery = selected
        if needs_recovery:
            args.recover, args.resume = args.resume, None
    if args.recover:
        from amplifier_tui.conversations import resolve_resume
        from amplifier_tui.recovery import recover

        if args.resume:
            parser.error("Choose --resume or --recover")
        try:
            entry = resolve_resume(
                args.state_dir, args.recover, cwd=launch_cwd, cli_home=discovery_home
            )
            if entry.get("shared_session"):
                raise ValueError(
                    "Shared recovery is unavailable; export for inspection. Nothing changed."
                )
            args.resume = recover(args.state_dir, args.recover)
        except ValueError as exc:
            parser.error(str(exc))
    if args.list_sessions:
        from amplifier_tui.conversations import catalog

        for entry in catalog(args.state_dir, cwd=launch_cwd, cli_home=discovery_home):
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
            or args.import_transcript
            or args.settings_policy
        ):
            parser.error(
                "--resume restores composition and cwd; do not supply preset/bundle/overlay/cwd/sources"
            )
        try:
            entry = resolve_resume(
                args.state_dir, args.resume, cwd=launch_cwd, cli_home=discovery_home
            )
        except ValueError as exc:
            parser.error(str(exc))
        saved = entry["launch"]
        args.resume = entry["id"]
        args.fixture, args.bundle = saved["fixture"], saved["bundle"]
        args.overlay = saved["overlays"]
        args.cwd = Path(saved["cwd"])
        args.sources = Path(saved["sources"]) if saved["sources"] else args.sources
        args.settings_policy = saved.get("settings_policy", "isolated")
        args.cli_home = Path(saved["cli_home"]) if saved.get("cli_home") else None
    args.cwd = args.cwd or Path.cwd()
    args.sources = args.sources or (workspace.parent / "tui-sources.json" if workspace else None)
    if not args.cwd.is_dir():
        parser.error("Recorded/requested working directory does not exist")
    host = [sys.executable, "-m", "amplifier_tui", "--bridge"]
    # Existing explicit compositions remain isolated; an ordinary new launch uses
    # the user's CLI policy. Saved conversations always retain their recorded choice.
    policy = args.settings_policy or (
        "isolated" if args.fixture or args.bundle or args.preset or args.overlay else "cli"
    )
    if args.fixture and policy == "cli":
        parser.error("--fixture requires isolated settings; no personal hooks may run")
    if args.cli_home and args.fixture:
        parser.error("--fixture cannot use a personal CLI home")
    if policy == "cli":
        host += ["--settings-policy", "cli"]
    if args.cli_home:
        host += ["--cli-home", str(args.cli_home.resolve())]
    if args.fixture:
        host += ["--fixture"]
    elif policy == "cli":
        if args.bundle or args.preset:
            host += ["--bundle", args.bundle or args.preset]
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
    if args.import_transcript:
        host += ["--import-transcript", str(args.import_transcript.absolute())]
    return parser, host


def main(workspace=None):
    # Source development/fixture tools retain their explicit standalone workflow.
    # Installed ordinary launch is a service client and imports no execution runtime.
    standalone = "--standalone" in sys.argv
    if standalone:
        sys.argv.remove("--standalone")
    if not standalone and workspace is None and not any(
        flag in sys.argv for flag in ("--fixture", "--headless", "--setup", "--check",
                                     "--support-report", "--getting-started", "--doctor")
    ) and not os.environ.get("_AMPLIFIER_TUI_COMPLETE"):
        from .connected import main as connected_main
        return connected_main()
    if standalone or any(flag in sys.argv for flag in ("--fixture", "--headless", "--bridge")):
        import importlib.util
        if importlib.util.find_spec("amplifier_core") is None:
            raise SystemExit("Local execution requires the optional standalone extra: reinstall amplifier-app-tui[standalone].")
    instruction = os.environ.get("_AMPLIFIER_TUI_COMPLETE")
    if instruction:
        return shell_completion(instruction, workspace)
    command = cli_command(sys.argv[1:])
    if command:
        return os.execv(command[0], command)
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


def shell_completion(instruction, workspace=None):
    """Click's read-only protocol over CLI commands and our actual native options.

    Set the CLI's import guard *before* importing its command tree; completion must
    never initialize keys, activate environments or execute normal callbacks.
    """
    if instruction not in {
        f"{shell}_{action}"
        for shell in ("bash", "zsh", "fish")
        for action in ("source", "complete")
    }:
        print("Unsupported shell completion instruction", file=sys.stderr)
        raise SystemExit(2)
    previous = os.environ.get("_AMPLIFIER_COMPLETE")
    os.environ["_AMPLIFIER_COMPLETE"] = instruction
    try:
        import click
        from amplifier_app_cli.main import cli

        params = []
        for action in argument_parser(workspace)._actions:
            if not action.option_strings or action.dest == "help":
                continue
            kind = click.Choice(list(action.choices)) if action.choices else click.STRING
            if action.type is Path:
                kind = click.Path()
            params.append(
                click.Option(
                    action.option_strings,
                    type=kind,
                    is_flag=action.nargs == 0,
                    multiple=isinstance(action, argparse._AppendAction),
                    help=action.help,
                )
            )
        commands = {name: command for name, command in cli.commands.items() if name in CLI_COMMANDS}
        commands["cli"] = cli
        command = click.Group(params=params, commands=commands)
        command.main(prog_name="amplifier-tui", complete_var="_AMPLIFIER_TUI_COMPLETE")
    finally:
        if previous is None:
            os.environ.pop("_AMPLIFIER_COMPLETE", None)
        else:
            os.environ["_AMPLIFIER_COMPLETE"] = previous


if __name__ == "__main__":
    main()

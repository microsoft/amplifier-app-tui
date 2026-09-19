from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from contextlib import redirect_stdout
from dataclasses import asdict
from pathlib import Path


def reference(value):
    """Persist local references independently of the launcher's later cwd."""
    if value and "://" not in value and Path(value).exists():
        return str(Path(value).resolve())
    return value


def parser():
    result = argparse.ArgumentParser(description="Amplifier modular terminal host")
    result.add_argument("--bundle", help="Bundle path or URI (explicit; no implicit CLI settings)")
    result.add_argument("--settings-policy", choices=("isolated", "cli"), default="isolated")
    result.add_argument("--cli-home", type=Path)
    result.add_argument("--overlay", action="append", default=[], help="Ordered bundle overlay")
    result.add_argument(
        "--fixture", action="store_true", help="Deterministic provider/tool; no live AI"
    )
    result.add_argument(
        "--sources", type=Path, help="JSON map of Git repository URLs to local paths"
    )
    result.add_argument("--state-dir", type=Path, default=Path(".state"))
    result.add_argument("--cwd", type=Path, default=Path.cwd())
    result.add_argument(
        "--import-transcript",
        type=Path,
        help="Explicit text reference import into a new conversation; requires --bridge",
    )
    result.add_argument(
        "--resume", help="Saved conversation ID (bridge only; use scripts/run.py --resume)"
    )
    result.add_argument(
        "--no-install", action="store_true", help="Use preinstalled module dependencies"
    )
    result.add_argument(
        "--require-tool", action="append", default=[], help="Required exported tool name"
    )
    result.add_argument(
        "--headless", metavar="PROMPT", help="Print identified JSONL events for one turn"
    )
    result.add_argument(
        "--bridge", action="store_true", help="Experimental bidirectional terminal boundary"
    )
    return result


def main():
    args = parser().parse_args()
    args.bundle = reference(args.bundle)
    args.overlay = [reference(value) for value in args.overlay]
    if not args.cwd.is_dir():
        parser().error("Working directory does not exist")
    if args.bridge and args.headless is not None:
        parser().error("--bridge and --headless are mutually exclusive")
    if args.resume and not args.bridge:
        parser().error("--resume requires --bridge")
    if args.import_transcript and (args.resume or not args.bridge):
        parser().error(
            "--import-transcript requires a new --bridge conversation; cannot combine with --resume or --headless"
        )
    if bool(args.bundle or args.settings_policy == "cli") == args.fixture:
        parser().error("Choose exactly one of --fixture or --bundle")
    if args.bridge:
        from .frontend_bridge import RuntimeOutput

        # Capture before importing runtime modules: they may print during import.
        with RuntimeOutput() as runtime_output:
            return run(args, runtime_output)
    return run(args)


def run(args, runtime_output=None):
    # Explicit process-level storage policy, before importing Foundation. Library
    # imports remain side-effect free; embedders choose their own environment.
    if args.settings_policy == "cli":
        from amplifier_foundation.paths.resolution import get_amplifier_home

        # CLI modules may intentionally resolve relative config against process cwd
        # (not every module consumes session.working_dir). Own this only in the
        # dedicated host process; normalize launch paths before changing it.
        args.cwd = args.cwd.resolve()
        args.state_dir = args.state_dir.resolve()
        args.sources = args.sources.resolve() if args.sources else None
        args.import_transcript = (
            args.import_transcript.resolve() if args.import_transcript else None
        )
        args.cli_home = args.cli_home.resolve() if args.cli_home else get_amplifier_home()
        os.environ["AMPLIFIER_HOME"] = str(args.cli_home)
        os.chdir(args.cwd)
    else:
        args.cli_home = (
            args.cli_home.resolve() if args.cli_home else args.state_dir.resolve() / "foundation"
        )
        os.environ["AMPLIFIER_HOME"] = str(args.cli_home)
        os.environ["AMPLIFIER_CONTEXT_INTELLIGENCE_BASE_PATH"] = str(
            args.state_dir.resolve() / "context-intelligence"
            if args.fixture
            else args.cli_home / "projects"
        )
    from .composition import SourceMap, prepare
    from .host import SessionHost

    source = (
        str(Path(__file__).parent / "fixtures" / "bundle.yaml") if args.fixture else args.bundle
    )
    sources = SourceMap.read(args.sources)
    host = SessionHost()

    async def opener(target):
        prepared, report = await prepare(
            source,
            args.overlay,
            args.state_dir.resolve(),
            sources,
            install_deps=not args.no_install,
            progress=target.background,
            native_home=args.cli_home if not args.fixture else None,
            cli_policy={
                "cwd": args.cwd.resolve(),
                "home": args.cli_home,
                "session_id": target.session_id,
            }
            if args.settings_policy == "cli"
            else None,
        )
        report["fixture"] = args.fixture
        required = (
            target.store.metadata["launch"].get("required_tools", args.require_tool)
            if target.store
            else args.require_tool
        )
        report["required_tools"] = required + (["fixture_probe"] if args.fixture else [])
        await target.open(prepared, report, args.cwd.resolve())

    if args.bridge:
        from .conversations import open_conversation
        from .frontend_bridge import serve
        from .navigation import WorkspaceBridge

        def store_factory():
            # Open inside backend.open so storage errors reach the terminal.
            required = args.require_tool
            if args.resume and not required:
                from .conversations import resolve_resume

                required = resolve_resume(
                    args.state_dir,
                    args.resume,
                    cwd=args.cwd,
                    cli_home=args.cli_home if not args.fixture else None,
                )["launch"].get("required_tools", [])
            imported = None
            if args.import_transcript:
                from .recovery import import_reference

                imported = import_reference(args.import_transcript)
            store = open_conversation(
                args.state_dir,
                {
                    "fixture": args.fixture,
                    "bundle": args.bundle,
                    "overlays": args.overlay,
                    "sources": str(args.sources.resolve()) if args.sources else None,
                    "cwd": str(args.cwd.resolve()),
                    **(
                        {
                            "settings_policy": args.settings_policy,
                            "cli_home": str(args.cli_home),
                            "shared_session": True,
                        }
                        if not args.fixture
                        else {}
                    ),
                    **({"required_tools": required} if required else {}),
                },
                args.resume,
            )
            if imported:
                from .conversations import atomic_json

                try:
                    atomic_json(store.path / "imported-reference.json", imported)
                except BaseException:
                    store.close()
                    raise
            return store

        async def open_launch(target, launch):
            fixture = launch["fixture"]
            source = (
                str(Path(__file__).parent / "fixtures/bundle.yaml") if fixture else launch["bundle"]
            )
            prepared, report = await prepare(
                source,
                launch["overlays"],
                args.state_dir.resolve(),
                SourceMap.read(Path(launch["sources"]) if launch["sources"] else None),
                install_deps=not args.no_install,
                progress=target.background,
                native_home=Path(launch["cli_home"]) if not fixture else None,
                cli_policy={
                    "cwd": Path(launch["cwd"]),
                    "home": Path(launch["cli_home"]),
                    "session_id": target.session_id,
                }
                if launch.get("settings_policy") == "cli"
                else None,
            )
            report["fixture"] = fixture
            report["required_tools"] = launch.get("required_tools", []) + (
                ["fixture_probe"] if fixture else []
            )
            await target.open(prepared, report, Path(launch["cwd"]))

        asyncio.run(
            serve(
                lambda emit: WorkspaceBridge(
                    host,
                    opener,
                    emit,
                    args.fixture,
                    args.cwd,
                    store_factory,
                    state_dir=args.state_dir.resolve(),
                    open_launch=open_launch,
                ),
                runtime_output.protocol,
                runtime_output=runtime_output,
            )
        )
        return
    if args.headless is not None:
        output = sys.stdout
        with redirect_stdout(sys.stderr):
            raise SystemExit(asyncio.run(headless(host, opener, args.headless, output)))
    from .app import AmplifierApp

    AmplifierApp(host, opener).run()


async def headless(host, opener, prompt, output=None):
    output = output or sys.stdout
    # This must be installed before opening: modules may request approval at
    # mount time, before the event-draining loop can start.
    host.auto_deny_approvals = True
    try:
        await opener(host)
        accepted, reason = host.submit(prompt)
        if not accepted:
            raise RuntimeError(reason)
        while True:
            event = await host.next_event()
            print(json.dumps(asdict(event), default=str), file=output, flush=True)
            if event.kind == "turn.ended":
                return 0 if event.payload["status"] == "completed" else 1
    except Exception as exc:
        print(
            json.dumps({"kind": "session.failed", "error": f"{type(exc).__name__}: {exc}"}),
            file=output,
        )
        return 1
    finally:
        await host.close()


if __name__ == "__main__":
    main()

"""Capture prepared policy hashes in an isolated app home; never execute a turn.

Run with the respective CLI/TUI interpreter. Comparing prepared policies is a
necessary gate, not sufficient proof of matching request-time policies or latency.
Keep receipts private: module IDs and guessable configuration hashes can disclose
identity. Hashing is not anonymization or a publication scrubber.
"""

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def policy(plan, instruction):
    # No raw config, instruction, source URI, path or credential value in receipts.
    def redact(value):
        if isinstance(value, dict):
            return {
                k: "<credential omitted>"
                if any(
                    part in k.lower().replace("-", "_")
                    for part in (
                        "api_key",
                        "password",
                        "secret",
                        "authorization",
                        "access_token",
                        "auth_token",
                    )
                )
                else redact(v)
                for k, v in value.items()
            }
        if isinstance(value, list):
            return [redact(v) for v in value]
        return value

    sections = {}
    for slot in ("providers", "tools", "hooks"):
        sections[slot] = [
            {
                "module": e.get("module"),
                "source_sha256": digest(e.get("source")),
                "config_sha256": digest(redact(e.get("config", {}))),
            }
            for e in plan.get(slot, [])
        ]
    sections["session_sha256"] = digest(redact(plan.get("session", {})))
    sections["instruction_sha256"] = digest(instruction)
    return sections


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=("cli", "tui"), required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sources", type=Path)
    parser.add_argument("--bundle", help="Explicit bundle URI; default is the controlled fixture")
    args = parser.parse_args()
    args.sources = args.sources.resolve() if args.sources else None
    args.output = args.output.resolve()
    if args.output.exists():
        parser.error("Choose a new output receipt; previous evidence is preserved")
    root = Path(__file__).resolve().parents[1]
    state = args.state.resolve()
    if not state.is_relative_to(root / ".state") or state == root / ".state":
        parser.error("Use a new isolated subdirectory of this checkout's .state")
    state.mkdir(mode=0o700, parents=True, exist_ok=False)
    os.environ["AMPLIFIER_HOME"] = str(state)
    os.chdir(state)
    source = args.bundle or (root / "src/amplifier_tui/fixtures/bundle.yaml").as_uri()
    if args.kind == "cli":
        from amplifier_app_cli.lib.settings import AppSettings
        from amplifier_app_cli.runtime.config import resolve_bundle_config

        plan, prepared = await resolve_bundle_config(source, AppSettings())
        package = "amplifier-app-cli"
    else:
        from amplifier_tui.composition import SourceMap, prepare

        sources = SourceMap.read(args.sources)
        prepared, _ = await prepare(source, [], state, sources, install_deps=False)
        plan = prepared.mount_plan
        package = "amplifier-app-tui"
    result = {
        "scope": "Prepared policy only; no session, provider request or tool execution. No equivalence verdict.",
        "kind": args.kind,
        "package_version": importlib.metadata.version(package),
        "core_version": importlib.metadata.version("amplifier-core"),
        "policy": policy(plan, prepared.bundle.instruction),
        "normalization": "Common credential-named config fields omitted before hashing; not a universal secret scrubber. No storage/source differences normalized away. Keep this receipt private.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with os.fdopen(
        os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w"
    ) as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"kind": args.kind, "captured": True}))


if __name__ == "__main__":
    asyncio.run(main())

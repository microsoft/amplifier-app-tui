"""One design, two engines (not two visual proposals). Default: simulated preview."""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "frontend", choices=["ratatui", "opentui"], help="Rendering engine for the same UI"
    )
    parser.add_argument("--history", type=int, default=0)
    parser.add_argument("--rate", type=int)
    parser.add_argument("--trace", type=Path)
    parser.add_argument(
        "--runtime",
        nargs=argparse.REMAINDER,
        help="Real host arguments: --fixture ... or --bundle ...",
    )
    args = parser.parse_args()
    if args.runtime is not None:
        host = [sys.executable, "-m", "amplifier_tui", "--bridge", *args.runtime]
    else:
        host = [
            sys.executable,
            "-m",
            "amplifier_tui.frontend_bridge",
            "--scene",
            str(ROOT / "scenes/retry.json"),
            "--history",
            str(args.history),
        ]
        if args.rate:
            host += ["--rate", str(args.rate)]
        if args.trace:
            host += ["--trace", str(args.trace)]
    launch(args.frontend, host, parser)


def launch(frontend, host, parser):
    if frontend == "ratatui":
        executable = ROOT / "frontends/ratatui/target/release/amplifier-ratatui"
        if not executable.exists():
            parser.error(
                "Build first: cargo build --release --manifest-path frontends/ratatui/Cargo.toml"
            )
        command = [str(executable)]
    else:
        bun = shutil.which("bun")
        if not bun:
            parser.error("Bun is required; see frontends/README.md")
        command = [bun, "run", str(ROOT / "frontends/opentui/src/main.ts")]
    os.execv(command[0], [*command, "--host-json", json.dumps(host)])


if __name__ == "__main__":
    main()

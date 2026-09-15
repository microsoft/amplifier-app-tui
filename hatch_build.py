"""Build the selected native client into a platform-specific Python wheel."""

import os
import shlex
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class NativeBuild(BuildHookInterface):
    def initialize(self, version, build_data):
        if version == "editable":
            # The workspace launcher uses its explicitly built target/release binary.
            return
        if sys.platform not in ("linux", "darwin"):
            raise RuntimeError("Amplifier TUI requires Linux/macOS (Windows: use WSL2)")
        cargo = shutil.which("cargo")
        if not cargo:
            raise RuntimeError(
                "Installing Amplifier TUI from Git requires Rust/Cargo (tested with Rust 1.93) and a C linker"
            )
        root = Path(self.root)
        target = root / "frontends/ratatui/target"
        encoded = os.environ.get("CARGO_ENCODED_RUSTFLAGS")
        flags = encoded.split("\x1f") if encoded else shlex.split(os.environ.get("RUSTFLAGS", ""))
        for source, replacement in (
            (Path.home(), "/user"),
            (Path(os.environ.get("CARGO_HOME", Path.home() / ".cargo")), "/cargo"),
            (root, "/source"),
        ):
            flags.append(f"--remap-path-prefix={source.resolve()}={replacement}")
        subprocess.run(
            [
                cargo,
                "build",
                "--locked",
                "--release",
                "--manifest-path",
                str(root / "frontends/ratatui/Cargo.toml"),
            ],
            env={
                **os.environ,
                "CARGO_TARGET_DIR": str(target),
                "CARGO_ENCODED_RUSTFLAGS": "\x1f".join(flags),
            },
            check=True,
        )
        binary = target / "release/amplifier-ratatui"
        build_data["force_include"][str(binary)] = "amplifier_tui/_bin/amplifier-ratatui"
        build_data["pure_python"] = False
        build_data["tag"] = "py3-none-" + sysconfig.get_platform().replace("-", "_").replace(
            ".", "_"
        )

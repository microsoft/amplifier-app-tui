"""Build the selected native client into a platform-specific Python wheel."""

import os
import platform
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


def wheel_target(system, machine, mac_version):
    """Describe the native executable, not a possibly universal Python interpreter."""
    if system == "linux" and machine in ("aarch64", "x86_64"):
        return f"linux_{machine}", {}
    if system == "darwin" and machine in ("arm64", "x86_64"):
        major, minor = (int(part) for part in mac_version.split(".")[:2])
        floor = f"{major}.{0 if major >= 11 else minor}"
        return f"macosx_{floor.replace('.', '_')}_{machine}", {"MACOSX_DEPLOYMENT_TARGET": floor}
    raise RuntimeError("Native wheels support Linux/macOS ARM64 and x86-64 only")


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
        wheel_platform, target_env = wheel_target(
            sys.platform, platform.machine(), platform.mac_ver()[0]
        )
        if os.environ.get("CARGO_BUILD_TARGET"):
            raise RuntimeError("Cross-compilation is not supported by this wheel build hook")
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
                **target_env,
                "CARGO_TARGET_DIR": str(target),
                "CARGO_ENCODED_RUSTFLAGS": "\x1f".join(flags),
            },
            check=True,
        )
        binary = target / "release/amplifier-ratatui"
        if sys.platform == "darwin":
            architectures = subprocess.check_output(["lipo", "-archs", str(binary)], text=True)
            if architectures.split() != [platform.machine()]:
                raise RuntimeError("Native executable architecture does not match wheel target")
        build_data["force_include"][str(binary)] = "amplifier_tui/_bin/amplifier-ratatui"
        build_data["pure_python"] = False
        build_data["tag"] = "py3-none-" + wheel_platform

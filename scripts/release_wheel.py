"""Build an identified candidate wheel and exercise installation with no Cargo on PATH.

Run separately on each supported OS/architecture. This is a packaging gate, not
terminal, live-provider or arbitrary bundle compatibility evidence. Only wheel and
allowlisted receipt go into dist/release; temporary install data is removed.
"""

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


def checked(command, **kwargs):
    """Build/install logs may contain configured index credentials; never upload them."""
    result = subprocess.run(command, capture_output=True, text=True, **kwargs)
    if result.returncode:
        raise RuntimeError(
            f"{Path(command[0]).name} exited {result.returncode}; output withheld by release gate"
        )
    return result


def verify_payload(data):
    shapes = (
        rb"/(?:home|Users)/[A-Za-z0-9_.-]+/",
        rb"(?:sk-ant-|sk-proj-|ghp_|github_pat_)[A-Za-z0-9_-]{16,}",
        rb"https?://[^/\s:@]{1,128}:[^/\s@]{1,256}@",
    )
    identities = [str(Path.home()), socket.gethostname()]
    identities += [
        value
        for key, value in os.environ.items()
        if any(part in key.upper() for part in ("TOKEN", "SECRET", "PASSWORD", "API_KEY"))
        and len(value) >= 12
    ]
    if any(re.search(pattern, data) for pattern in shapes) or any(
        len(value) >= 4 and value.encode() in data for value in identities
    ):
        raise RuntimeError(
            "Release privacy scan failed; artifact withheld (matched values not disclosed)"
        )


def terminal_smoke(command, stage, env):
    """Installed fixture runtime, real PTY, no sibling sources or model credentials."""
    from terminal_probe import Probe

    state = stage / "terminal-state"
    launch = [str(command), "--state-dir", str(state)]
    identity = None
    for resumed in (False, True):
        probe = Probe(
            [*launch, *(["--resume", identity] if resumed else ["--fixture"])],
            cwd=stage,
            env=env,
            cols=120,
            guard_terminal_modes=True,
        )
        try:
            # Current status row, not a Ready word in a historical reply.
            import time

            deadline = time.monotonic() + 300
            while time.monotonic() < deadline:
                probe.read()
                if any(line.strip().startswith("Ready") for line in probe.text.splitlines()[-2:]):
                    break
            else:
                raise AssertionError("Installed fixture did not reach current readiness")
            metadata = next((state / "conversations").glob("*/metadata.json"))
            path = metadata.parent
            record = json.loads(metadata.read_text())
            identity = record["id"]
            assert record["launch"]["sources"] is None

            def events():
                return [
                    json.loads(line) for line in (path / "events.jsonl").read_text().splitlines()
                ]

            assert sum(e["kind"] == "turn.accepted" for e in events()) == int(resumed)
            probe.send(b"Compute a digest")
            probe.wait("Compute a digest")
            probe.send(b"\x1bOS")
            probe.wait("Search:")
            probe.send(b"Getting started\r")
            probe.wait("Help · choose a topic")
            probe.send(b"\x1b")
            probe.wait("Actions / choices", absent=True)
            assert sum(e["kind"] == "turn.accepted" for e in events()) == int(resumed)
            probe.send(b"\r")
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                probe.read()
                ended = [e for e in events() if e["kind"] == "turn.ended"]
                if len(ended) == int(resumed) + 1:
                    assert ended[-1]["payload"]["status"] == "completed"
                    break
            else:
                raise AssertionError("Installed fixture turn did not complete")
            assert any(
                e["kind"] == "tool.updated" and e["payload"].get("status") == "succeeded"
                for e in events()
            )
        finally:
            probe.close()  # Includes actual termios restoration and bounded clean exit.
    return {
        "fixture_tool_round_trip": True,
        "resume_without_submission": True,
        "second_turn": True,
        "help_preserves_draft_without_submission": True,
        "terminal_modes_restored": True,
        "scope": "Installed native PTY fixture on this runner; not live-provider, physical terminal, clipboard or tmux certification",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--terminal", action="store_true", help="Also exercise installed fixture PTY; requires pyte"
    )
    args = parser.parse_args()
    uv = shutil.which("uv")
    if not uv:
        raise SystemExit("uv is required")
    output = ROOT / "dist/release"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tui-release-") as temporary:
        stage = Path(temporary)
        checked([uv, "build", "--wheel", "--out-dir", str(stage)], cwd=ROOT)
        (wheel,) = stage.glob("*.whl")
        if platform.system() == "Darwin":
            # A universal2 Python does not make our Rust executable universal.
            floor = platform.mac_ver()[0].split(".")[0] + "_0"
            assert wheel.name.endswith(f"-macosx_{floor}_{platform.machine()}.whl")
        with ZipFile(wheel) as archive:
            binary = archive.read("amplifier_tui/_bin/amplifier-ratatui")
            assert not any(
                name.endswith(".zip") or "/.state/" in name for name in archive.namelist()
            )
            for name in archive.namelist():
                verify_payload(name.encode())
                verify_payload(archive.read(name))
        env = {
            **os.environ,
            "PYTHONDONTWRITEBYTECODE": "1",
            "UV_TOOL_DIR": str(stage / "tools"),
            "UV_TOOL_BIN_DIR": str(stage / "bin"),
            "AMPLIFIER_TUI_STATE_DIR": str(stage / "state"),
        }
        env["PATH"] = os.pathsep.join(
            directory
            for directory in os.get_exec_path()
            if not (Path(directory) / "cargo").exists()
        )
        env.pop("PYTHONPATH", None)
        assert shutil.which("cargo", path=env["PATH"]) is None
        checked([uv, "tool", "install", str(wheel)], env=env)
        command = stage / "bin/amplifier-tui"
        doctor = checked(
            [str(command), "--doctor"],
            env=env,
            cwd=stage,
        )
        report = json.loads(doctor.stdout)
        assert report["native_available"] and report["shared_cli_state"] == "not imported"
        assert not (stage / "state").exists()
        installed_binary = Path(report["native_binary"]).read_bytes()
        assert installed_binary == binary
        if platform.system() == "Darwin":
            arches = checked(["lipo", "-archs", report["native_binary"]]).stdout.split()
            assert arches == [platform.machine()]
        # Doctor verifies presence, not whether the OS can load the executable.
        # With no host command the native client refuses before opening a terminal.
        loaded = subprocess.run(
            [report["native_binary"]], capture_output=True, env=env, cwd=stage, timeout=10
        )
        assert loaded.returncode == 1
        assert b"Use scripts/compare.py ratatui to launch" in loaded.stderr
        checked([str(command), "--getting-started"], env=env, cwd=stage)
        terminal = terminal_smoke(command, stage, env) if args.terminal else None
        receipt = {
            "scope": "Native wheel installation/diagnostics; not runtime or terminal conformance",
            "platform": platform.system(),
            "architecture": platform.machine(),
            "build_os_release": platform.mac_ver()[0]
            if platform.system() == "Darwin"
            else platform.freedesktop_os_release().get("VERSION_ID", "unknown"),
            "version": report["version"],
            "wheel": wheel.name,
            "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
            "native_sha256": hashlib.sha256(binary).hexdigest(),
            "cargo_available_during_install": False,
            "doctor_passed": True,
            "state_untouched": True,
            "installed_native_bytes_match": True,
            "installed_native_load_passed": True,
            "artifact_privacy_scan_passed": True,
            "terminal_fixture": terminal,
        }
        verify_payload(json.dumps(receipt).encode())
        shutil.copy2(wheel, output / wheel.name)
        receipt_path = output / (wheel.name + ".receipt.json")
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as stream:
                stream.write(
                    f"wheel=dist/release/{wheel.name}\nreceipt=dist/release/{receipt_path.name}\n"
                )
        print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()

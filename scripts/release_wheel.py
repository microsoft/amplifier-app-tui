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
import stat
import subprocess
import tempfile
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
MAX_SOURCE_FILES = 128
MAX_SOURCE_FILE_BYTES = 4 * 1024 * 1024


def source_fingerprint(path):
    """Hash one stable regular source file without materializing it in memory."""
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise RuntimeError(f"Candidate source is not a regular file: {path.relative_to(ROOT)}")
    if before.st_size > MAX_SOURCE_FILE_BYTES:
        raise RuntimeError(
            f"Candidate source exceeds {MAX_SOURCE_FILE_BYTES} bytes: {path.relative_to(ROOT)}"
        )
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        if (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns) != (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
        ):
            raise RuntimeError(
                f"Candidate source changed while fingerprinting: {path.relative_to(ROOT)}"
            )
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    after = path.lstat()
    if (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) != (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    ):
        raise RuntimeError(
            f"Candidate source changed while fingerprinting: {path.relative_to(ROOT)}"
        )
    return digest.hexdigest()


def source_fingerprints():
    """Identify a bounded regular dirty candidate without claiming HEAD contains its bytes."""
    files = [
        *sorted(
            p
            for p in (ROOT / "src/amplifier_tui").rglob("*")
            if p.suffix in {".py", ".yaml", ".yml", ".md", ".json", ".toml"}
            and "__pycache__" not in p.parts
        ),
        *sorted((ROOT / "frontends/ratatui/src").glob("*.rs")),
        *(
            ROOT / name
            for name in (
                "pyproject.toml",
                "uv.lock",
                "README.md",
                "hatch_build.py",
                "frontends/ratatui/Cargo.toml",
                "frontends/ratatui/Cargo.lock",
            )
        ),
    ]
    if len(files) > MAX_SOURCE_FILES:
        raise RuntimeError(f"Candidate source set exceeds {MAX_SOURCE_FILES} files")
    return {str(p.relative_to(ROOT)): source_fingerprint(p) for p in files}


def checked(command, *, failure_log=None, **kwargs):
    """Build/install logs may contain configured index credentials; never upload them."""
    result = subprocess.run(command, capture_output=True, text=True, **kwargs)
    if result.returncode:
        if failure_log is not None:
            # Explicit local diagnostics only. Never include this file in receipts
            # or release uploads; output may contain private dependency settings.
            fd = os.open(failure_log, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "w") as stream:
                stream.write((result.stdout + "\n" + result.stderr)[-1024 * 1024 :])
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


def verify_prior_wheel(path):
    """Require the downloaded release's paired receipt before installing its code."""
    receipt = path.with_name(path.name + ".receipt.json")
    if receipt.stat().st_size > 1024 * 1024 or path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("Prior release evidence exceeds its bound")
    record = json.loads(receipt.read_text())
    if (
        record.get("wheel") != path.name
        or record.get("wheel_sha256") != hashlib.sha256(path.read_bytes()).hexdigest()
    ):
        raise ValueError("Prior release wheel does not match its receipt")
    verify_payload(receipt.read_bytes())
    with ZipFile(path) as archive:
        for name in archive.namelist():
            verify_payload(name.encode())
            verify_payload(archive.read(name))


def terminal_smoke(command, stage, env, *, upgrade=False, standalone=True):
    """Installed fixture runtime, real PTY, no sibling sources or model credentials."""
    from benchmark_candidates import wait_edit
    from terminal_probe import Probe

    state = stage / "terminal-state"
    launch = [str(command), *(["--standalone"] if standalone else []), "--state-dir", str(state)]
    identity = None
    retained = None
    if upgrade:
        (metadata,) = (state / "conversations").glob("*/metadata.json")
        identity = json.loads(metadata.read_text())["id"]
        retained = (metadata.parent / "events.jsonl").read_bytes()
    previous_tool_events = sum(
        json.loads(line)["kind"].startswith("tool.") for line in (retained or b"").splitlines()
    )
    readiness = []
    draft = "retained-install-draft"
    for index in range(2):
        resumed = upgrade or index > 0
        expected_turns = (2 if upgrade else 0) + index
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
            readiness.append(
                {"resumed": resumed, "ready_ms": (time.monotonic_ns() - probe.start) / 1e6}
            )
            metadata = next((state / "conversations").glob("*/metadata.json"))
            path = metadata.parent
            record = json.loads(metadata.read_text())
            identity = record["id"]
            assert record["launch"]["sources"] is None

            def events():
                return [
                    json.loads(line) for line in (path / "events.jsonl").read_text().splitlines()
                ]

            assert sum(e["kind"] == "turn.accepted" for e in events()) == expected_turns
            assert sum(e["kind"].startswith("tool.") for e in events()) == previous_tool_events
            if retained is not None:
                assert (path / "events.jsonl").read_bytes().startswith(retained)
            if resumed:
                wait_edit(probe, draft)
                probe.send(b"\x1b[F" + b"\x7f" * len(draft))
                probe.wait(draft, absent=True)
            probe.send(b"Compute a digest")
            probe.wait("Compute a digest")
            probe.send(b"\x1bOS")
            probe.wait("Search:")
            probe.send(b"Getting started\r")
            probe.wait("Help · choose a topic")
            probe.send(b"\x1b")
            probe.wait("Actions / choices", absent=True)
            assert sum(e["kind"] == "turn.accepted" for e in events()) == expected_turns
            assert sum(e["kind"].startswith("tool.") for e in events()) == previous_tool_events
            before_send = len(events())
            probe.send(b"\r")
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                probe.read()
                ended = [e for e in events() if e["kind"] == "turn.ended"]
                if len(ended) == expected_turns + 1:
                    assert ended[-1]["payload"]["status"] == "completed"
                    break
            else:
                raise AssertionError("Installed fixture turn did not complete")
            assert any(
                e["kind"] == "tool.updated" and e["payload"].get("status") == "succeeded"
                for e in events()[before_send:]
            )
            previous_tool_events = sum(e["kind"].startswith("tool.") for e in events())
            probe.wait("[ Send ]")
            probe.send(draft.encode())
            wait_edit(probe, draft)
        finally:
            probe.close()  # Includes actual termios restoration and bounded clean exit.
    return {
        "fixture_tool_round_trip": True,
        "resume_without_submission": True,
        "second_turn": True,
        "help_preserves_draft_without_submission": True,
        "unsent_draft_retained_across_restart": True,
        "terminal_modes_restored": True,
        "prior_release_history_preserved": True if upgrade else None,
        "startup_observations": readiness,
        "startup_scope": (
            "Two resumed launches after replacing a prior release in the same tool environment. "
            if upgrade
            else "One first isolated-state launch and one resumed launch. "
        )
        + "Source/dependency resolution included as needed; global caches not purged, not a cold-cache benchmark.",
        "scope": "Installed native PTY fixture on this runner; not live-provider, physical terminal, clipboard or tmux certification",
    }


def scripting_smoke(command, stage, env, python, uv, failure_log=None):
    """Actual pinned CLI subprocesses in the isolated installed environment."""
    package = Path(
        json.loads(
            checked(
                [
                    python,
                    "-c",
                    "import amplifier_tui,json; print(json.dumps(amplifier_tui.__path__[0]))",
                ],
                env=env,
                cwd=stage,
            ).stdout
        )
    )
    fixture = package / "fixtures"
    # Installs are confined to the disposable tool environment, not the running
    # developer/user environment. No foreign-home guard is bypassed.
    checked(
        [
            uv,
            "pip",
            "install",
            "--python",
            python,
            "--no-deps",
            str(fixture / "provider-fixture"),
            str(fixture / "tool-fixture"),
        ],
        env=env,
    )
    home = stage / "terminal-state/foundation"
    home.mkdir(parents=True, exist_ok=True)
    (home / "settings.yaml").write_text(
        json.dumps(
            {
                "config": {
                    "providers": [
                        {
                            "module": "provider-fixture",
                            "source": str(fixture / "provider-fixture"),
                            "config": {"priority": 1},
                        }
                    ]
                },
                "updates": {"auto_prompt": False},
            }
        )
    )
    isolated = {
        key: value
        for key, value in env.items()
        if not any(term in key.upper() for term in ("API_KEY", "TOKEN", "SECRET", "PASSWORD"))
    }
    isolated["AMPLIFIER_HOME"] = str(home)
    outcomes = []
    for output, stdin in (("text", False), ("json", True), ("json-trace", False)):
        prompt = f"Synthetic installed {output} {'stdin' if stdin else 'argument'} marker"
        argv = [
            str(command),
            "--standalone",
            "run",
            "--bundle",
            (fixture / "bundle.yaml").as_uri(),
            "--output-format",
            output,
        ]
        result = checked(
            [*argv, *([] if stdin else [prompt])],
            input=prompt if stdin else "",
            env=isolated,
            cwd=stage,
            timeout=300,
            failure_log=failure_log,
        )
        if output == "text":
            assert "Fixture round trip complete" in result.stdout
        else:
            payload = json.loads(result.stdout)
            assert payload["status"] == "success"
            assert "Fixture round trip complete" in payload["response"]
            if output == "json-trace":
                assert any(
                    call.get("tool") == "fixture_probe"
                    and isinstance(call.get("result"), dict)
                    and call["result"].get("success") is True
                    and call["result"].get("output", {}).get("sha256")
                    == hashlib.sha256(b"fixture payload").hexdigest()
                    for call in payload["execution_trace"]
                )
        transcripts = list((home / "projects").rglob("transcript.jsonl"))
        assert any(prompt in path.read_text() for path in transcripts)
        outcomes.append(
            {"format": output, "input": "stdin" if stdin else "argument", "passed": True}
        )
    for shell in ("bash", "zsh", "fish"):
        result = checked(
            [str(command)],
            env={**isolated, "_AMPLIFIER_TUI_COMPLETE": f"{shell}_source"},
            cwd=stage,
            timeout=20,
        )
        assert "_AMPLIFIER_TUI_COMPLETE" in result.stdout
    return {
        "cases": outcomes,
        "completion_shells": ["bash", "zsh", "fish"],
        "scope": "Installed pinned CLI and deterministic provider/tool; original CLI store, no native launch or paid model calls",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--terminal", action="store_true", help="Also exercise installed fixture PTY; requires pyte"
    )
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist/release")
    parser.add_argument(
        "--upgrade-from",
        type=Path,
        help="Verified prior wheel: seed fixture history, replace in the same isolated install and resume",
    )
    parser.add_argument(
        "--private-failure-log",
        type=Path,
        help="New private diagnostic file on CLI failure; may contain secrets, never upload",
    )
    parser.add_argument(
        "--scripting",
        action="store_true",
        help="Exercise installed CLI prompt/stdin/text/JSON/trace and completion with deterministic modules",
    )
    parser.add_argument(
        "--ci-clipboard",
        action="store_true",
        help="Exercise the disposable macOS CI pasteboard; never use on a personal desktop",
    )
    args = parser.parse_args()
    if args.upgrade_from and not args.terminal:
        parser.error("--upgrade-from requires --terminal")
    previous = args.upgrade_from.resolve() if args.upgrade_from else None
    if previous and (not previous.is_file() or previous.suffix != ".whl"):
        parser.error("--upgrade-from requires an existing reviewed wheel")
    if previous:
        verify_prior_wheel(previous)
    uv = shutil.which("uv")
    if not uv:
        raise SystemExit("uv is required")
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    sources = source_fingerprints()
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
        connected = stage / "connected"
        checked([uv, "venv", str(connected)], env=env)
        connected_python = str(connected / "bin/python")
        checked([uv, "pip", "install", "--python", connected_python, "--no-sources", str(wheel)], env=env)
        checked([connected_python, "-c", "import importlib.util; import amplifier_tui.connected; "
                 "assert all(importlib.util.find_spec(n) is None for n in "
                 "('amplifier_core','amplifier_foundation','amplifier_app_cli'))"], env=env, cwd=stage)
        checked([str(connected / "bin/amplifier-tui"), "--help"], env=env, cwd=stage)
        command = stage / "bin/amplifier-tui"
        upgrade_seed = None
        if previous is not None:
            # Existing release artifact, not a guessed checkpoint fixture. Only the
            # disposable tool environment is replaced; the user's command is untouched.
            checked([uv, "tool", "install", "--no-sources", str(previous)], env=env)
            prior_report = json.loads(
                checked([str(command), "--doctor"], env=env, cwd=stage).stdout
            )
            terminal_smoke(command, stage, env, standalone=False)
            upgrade_seed = {
                "version": prior_report["version"],
                "wheel_sha256": hashlib.sha256(previous.read_bytes()).hexdigest(),
            }
        # The pinned CLI's development source table follows Foundation main.
        # Resolve published requirements, including our exact Foundation pin,
        # rather than importing that dependency's development checkout policy.
        checked(
            [
                uv,
                "tool",
                "install",
                "--no-sources",
                *(["--reinstall"] if previous else []),
                str(wheel) + "[standalone]",
            ],
            env=env,
        )
        doctor = checked(
            [str(command), "--doctor"],
            env=env,
            cwd=stage,
        )
        report = json.loads(doctor.stdout)
        assert report["native_available"]
        assert "diagnostics do not read shared settings/history" in report["shared_cli_state"]
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
        terminal = (
            terminal_smoke(command, stage, env, upgrade=previous is not None)
            if args.terminal
            else None
        )
        scripting = (
            scripting_smoke(command, stage, env, report["python"], uv, args.private_failure_log)
            if args.scripting
            else None
        )
        clipboard = None
        if args.ci_clipboard and platform.system() == "Darwin":
            if os.environ.get("GITHUB_ACTIONS") != "true":
                raise RuntimeError("Clipboard mutation is restricted to disposable CI runners")
            # Installed package and actual OS pasteboard, not a mocked subprocess.
            # No prior clipboard content is read or published from this owned runner.
            program = """
import asyncio, base64, hashlib, io, subprocess
from PIL import Image
from amplifier_tui.file_input import clipboard_image
stream = io.BytesIO()
Image.new('RGB', (8, 8), 'blue').save(stream, format='PNG')
raw = stream.getvalue()
try:
    subprocess.run(['osascript', '-e', 'set the clipboard to «data PNGf' + raw.hex() + '»'], check=True, capture_output=True, timeout=5)
    value = asyncio.run(clipboard_image())
    assert value['media_type'] == 'image/png'
    assert base64.b64decode(value['data']) == raw
    assert value['sha256'] == hashlib.sha256(raw).hexdigest()
finally:
    subprocess.run(['osascript', '-e', 'set the clipboard to ""'], check=True, capture_output=True, timeout=5)
"""
            checked([report["python"], "-c", program], env=env, cwd=stage, timeout=20)
            clipboard = {
                "actual_macos_png_pasteboard": True,
                "original_bytes_preserved": True,
                "scope": "Disposable CI runner; not a physical desktop, remote clipboard or tmux proof",
            }
        receipt = {
            "scope": "Native wheel installation/diagnostics; not runtime or terminal conformance",
            "platform": platform.system(),
            "source_commit": checked(["git", "rev-parse", "HEAD"], cwd=ROOT).stdout.strip(),
            "tracked_source_clean": not checked(
                ["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT
            ).stdout.strip(),
            "source_sha256": sources,
            "architecture": platform.machine(),
            "build_os_release": platform.mac_ver()[0]
            if platform.system() == "Darwin"
            else platform.freedesktop_os_release().get("VERSION_ID", "unknown"),
            "version": report["version"],
            "wheel": wheel.name,
            "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
            "native_sha256": hashlib.sha256(binary).hexdigest(),
            "cargo_available_during_install": False,
            "dependency_resolution": "published metadata (--no-sources); exact direct pins retained",
            "doctor_passed": True,
            "state_untouched": True,
            "connected_install_without_execution_dependencies": True,
            "installed_native_bytes_match": True,
            "installed_native_load_passed": True,
            "artifact_privacy_scan_passed": True,
            "terminal_fixture": terminal,
            "upgrade_from": upgrade_seed,
            "scripting_fixture": scripting,
            "clipboard_fixture": clipboard,
        }
        assert sources == source_fingerprints(), "Candidate sources changed during verification"
        verify_payload(json.dumps(receipt).encode())
        shutil.copy2(wheel, output / wheel.name)
        receipt_path = output / (wheel.name + ".receipt.json")
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as stream:
                stream.write(f"wheel={output / wheel.name}\nreceipt={receipt_path}\n")
        print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()

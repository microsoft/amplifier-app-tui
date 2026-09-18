"""Actual CLI -> native TUI -> CLI -> native TUI, using an owned fixture home.

The CLI executable must belong to a disposable test environment (module preparation
can install dependencies). No paid models, personal settings or user sessions are used.
Captures and state remain private; the receipt contains assertion results only.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from interaction_probe import capture
from terminal_probe import ROOT, Probe


def run(cli=None):
    from amplifier_tui.cli_compat import session_directory

    base = ROOT / ".state/shared-session-probes"
    base.mkdir(parents=True, exist_ok=True)
    state = Path(tempfile.mkdtemp(dir=base))
    home, cwd = state / "home", state / "project"
    home.mkdir()
    cwd.mkdir()
    fixture = ROOT / "src/amplifier_tui/fixtures"
    workspace = ROOT.parent
    if cli is None:
        environment = state / "cli-env"
        subprocess.run(["uv", "venv", str(environment)], check=True, capture_output=True)
        subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(environment / "bin/python"),
                str(workspace / "amplifier-app-cli"),
                str(fixture / "provider-fixture"),
                str(fixture / "tool-fixture"),
            ],
            check=True,
            capture_output=True,
            timeout=300,
        )
        cli = environment / "bin/amplifier"
    sources = {
        f"https://github.com/microsoft/{path.name}": str(path)
        for path in workspace.glob("amplifier-*")
        if path.is_dir()
    }
    (state / "sources.json").write_text(json.dumps(sources))
    settings = {
        "bundle": {"active": (fixture / "bundle.yaml").as_uri()},
        "sources": {
            "bundles": {url: Path(path).as_uri() for url, path in sources.items()},
            "modules": {
                path.name.removeprefix("amplifier-module-"): str(path)
                for path in workspace.glob("amplifier-module-*")
                if path.is_dir()
            },
        },
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
    (home / "settings.yaml").write_text(json.dumps(settings))
    env = {
        k: v
        for k, v in os.environ.items()
        if not any(t in k.upper() for t in ("API_KEY", "TOKEN", "SECRET", "PASSWORD"))
    }
    env.update(
        AMPLIFIER_HOME=str(home),
        PYTHONDONTWRITEBYTECODE="1",
        TERM="xterm-256color",
        COLORTERM="truecolor",
    )
    env.pop("NO_COLOR", None)
    env["AMPLIFIER_TUI_THEME"] = "dark"

    def command(arguments, name):
        result = subprocess.run(
            [str(cli), *arguments], cwd=cwd, env=env, capture_output=True, timeout=180
        )
        # Diagnostics are private and may contain local source configuration.
        path = state / f"{name}.log"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write((result.stdout + result.stderr)[-1024 * 1024 :])
        assert result.returncode == 0, f"{name} failed; inspect private probe log"

    command(
        ["run", "--bundle", (fixture / "bundle.yaml").as_uri(), "CLI first shared marker"],
        "cli-first",
    )
    root = session_directory(home, cwd)
    sessions = [
        p for p in root.iterdir() if (p / "transcript.jsonl").is_file() and "_" not in p.name
    ]
    assert len(sessions) == 1
    session = sessions[0]
    identity = session.name

    def transcript():
        return [
            json.loads(line)
            for line in (session / "transcript.jsonl").read_text().splitlines()
            if line.strip()
        ]

    initial = transcript()
    assert any(m.get("role") == "tool" for m in initial)
    launch = [
        sys.executable,
        str(ROOT / "scripts/run.py"),
        "--state-dir",
        str(state / "tui"),
        "--no-install",
        "--resume",
        identity,
    ]
    for index, size in enumerate(((175, 50), (40, 20))):
        before = transcript()
        p = Probe(
            launch[:-1] if index == 0 else launch,
            cwd=cwd,
            env=env,
            cols=size[0],
            rows=size[1],
            guard_terminal_modes=True,
        )
        try:
            if index == 0:
                p.wait("Resume conversation", timeout=30)
                p.wait(identity[:8])
                capture(p, "shared-session-picker-175")
                p.send(b"\r")
            p.wait("Ready", timeout=120)
            assert len(transcript()) == len(before), "Resume executed or changed message count"
            p.wait("CLI first shared marker" if index == 0 else "CLI return marker")
            p.wait("fixture_probe")
            assert "<system-reminders>" not in p.text
            capture(p, f"shared-session-resume-{size[0]}")
            if index == 0:
                p.send(b"TUI continuation marker\r")
                p.wait_idle(timeout=60)
                assert any(m.get("content") == "TUI continuation marker" for m in transcript())
                capture(p, "shared-session-completed-175")
        finally:
            p.close()
        if index == 0:
            command(["continue", "CLI return marker"], "cli-return")
            assert any(m.get("content") == "TUI continuation marker" for m in transcript())
            assert any(m.get("content") == "CLI return marker" for m in transcript())
    assert (
        len([p for p in root.iterdir() if (p / "transcript.jsonl").is_file() and "_" not in p.name])
        == 1
    )
    original_bytes = (session / "transcript.jsonl").read_bytes()
    new_launch = [
        sys.executable,
        str(ROOT / "scripts/run.py"),
        "--state-dir",
        str(state / "tui"),
        "--no-install",
    ]
    p = Probe(new_launch, cwd=cwd, env=env, cols=175, rows=50, guard_terminal_modes=True)
    try:
        p.wait("Ready", timeout=120)
        p.send(b"New TUI shared marker\r")
        p.wait_idle(timeout=60)
        capture(p, "shared-session-new-tui-175")
    finally:
        p.close()
    other = [
        p
        for p in root.iterdir()
        if p != session and (p / "transcript.jsonl").is_file() and "_" not in p.name
    ]
    assert len(other) == 1
    command(["continue", "CLI after new TUI marker"], "cli-after-new-tui")
    new_messages = [
        json.loads(line)
        for line in (other[0] / "transcript.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert any(m.get("content") == "New TUI shared marker" for m in new_messages)
    assert any(m.get("content") == "CLI after new TUI marker" for m in new_messages)
    assert (session / "transcript.jsonl").read_bytes() == original_bytes
    # Explicit policy isolation changes composition/home, never the live format.
    prior_ids = {p.name for p in root.iterdir()}
    custom_launch = [
        *new_launch,
        "--settings-policy",
        "isolated",
        "--cli-home",
        str(home),
        "--bundle",
        (fixture / "bundle.yaml").as_uri(),
    ]
    p = Probe(custom_launch, cwd=cwd, env=env, cols=80, rows=30, guard_terminal_modes=True)
    try:
        p.wait("Ready", timeout=120)
        p.send(b"Explicit composition shared marker\r")
        p.wait_idle(timeout=60)
    finally:
        p.close()
    custom = [p for p in root.iterdir() if p.name not in prior_ids and "_" not in p.name]
    assert len(custom) == 1 and (custom[0] / "transcript.jsonl").is_file()
    assert not (state / "tui/conversations").exists()
    resumed = [*new_launch, "--cli-home", str(home), "--resume", custom[0].name]
    before = (custom[0] / "transcript.jsonl").read_bytes()
    p = Probe(resumed, cwd=cwd, env=env, cols=80, rows=30, guard_terminal_modes=True)
    try:
        p.wait("Ready", timeout=120)
        p.wait("Explicit composition shared marker")
        assert (custom[0] / "transcript.jsonl").read_bytes() == before
    finally:
        p.close()
    return {
        "cli_to_tui_to_cli_to_tui": True,
        "same_identity": True,
        "ordinary_startup_picker": True,
        "new_tui_to_cli": True,
        "explicit_composition_uses_same_format": True,
        "no_implicit_resume_turn": True,
        "terminal_sizes": [[175, 50], [40, 20]],
        "scope": "Actual entrypoints and app behaviors; deterministic provider and tool; sequential clients only",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cli-executable", type=Path, help="Otherwise create a fresh owned CLI environment"
    )
    args = parser.parse_args()
    print(json.dumps(run(args.cli_executable.resolve() if args.cli_executable else None), indent=2))

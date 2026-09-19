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
import uuid
from decimal import Decimal
from importlib.metadata import requires
from pathlib import Path

from interaction_probe import action, capture, click
from terminal_probe import ROOT, Probe

READING_REPLY = """## Shared project review

1. **Preserve conversation identity.** Continue the same conversation in either client. The transcript retains the person's words, tool results and replies; opening history does not execute them again.
   - Keep the original source for copying and inspection, including references and Unicode: 界 café.
   - Keep the draft separate from submitted conversation history.
2. **Review the evidence.** Inspect earlier calls in Activity, then make an explicit next request.

   A continuation paragraph remains aligned with its numbered item, even when it wraps across several terminal rows.

> Readable output is part of correctness. A wrapped quotation retains its visible scope instead of appearing to become ordinary conversation text.

### Sources

[README](docs/README.md#L12), <https://example.test/guide>, and [`src/lib.rs`](src/lib.rs).

```python
def identity(value):
    return value
```

Reading check complete.
"""


def run(cli=None):
    from amplifier_foundation.session import SharedSessionStore

    from amplifier_tui.cli_compat import session_directory

    base = ROOT / ".state/shared-session-probes"
    base.mkdir(parents=True, exist_ok=True)
    state = Path(tempfile.mkdtemp(dir=base))
    home, cwd = state / "home", state / "project"
    home.mkdir()
    cwd.mkdir()
    fixture = ROOT / "src/amplifier_tui/fixtures"
    workspace = ROOT.parent
    bundle = state / "shared-fixture.yaml"
    bundle.write_text(
        json.dumps(
            {
                "bundle": {"name": "shared-reading-fixture", "version": "1.0.0"},
                "includes": [{"bundle": (fixture / "bundle.yaml").as_uri()}],
                "hooks": [
                    {
                        "module": "hooks-logging",
                        "source": str(workspace / "amplifier-module-hooks-logging"),
                        "config": {
                            "session_log_template": str(
                                home / "projects/{project}/sessions/{session_id}/events.jsonl"
                            ),
                            "strip_raw": True,
                        },
                    }
                ],
            }
        )
    )
    if cli is None:
        cli_requirement = next(
            requirement
            for requirement in requires("amplifier-app-tui") or ()
            if requirement.startswith("amplifier-app-cli @")
        )
        environment = state / "cli-env"
        subprocess.run(["uv", "venv", str(environment)], check=True, capture_output=True)
        subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(environment / "bin/python"),
                cli_requirement,
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
        "bundle": {"active": bundle.as_uri()},
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
                    "config": {
                        "priority": 1,
                        "reply": READING_REPLY,
                        "usage": {"input_tokens": 100, "output_tokens": 10, "cost_usd": "0.025"},
                    },
                }
            ],
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
        AMPLIFIER_SESSION_STATE_HOME=str(state / "owners"),
        PYTHONDONTWRITEBYTECODE="1",
        TERM="xterm-256color",
        COLORTERM="truecolor",
    )
    env.pop("NO_COLOR", None)
    env["AMPLIFIER_TUI_THEME"] = "dark"

    def command(arguments, name, *, busy=False):
        result = subprocess.run(
            [str(cli), *arguments], cwd=cwd, env=env, capture_output=True, timeout=180
        )
        # Diagnostics are private and may contain local source configuration.
        path = state / f"{name}.log"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write((result.stdout + result.stderr)[-1024 * 1024 :])
        if busy:
            assert result.returncode != 0, "Concurrent CLI writer was admitted"
            output = (result.stdout + result.stderr).decode(errors="replace").lower()
            assert "busy" in output or "already owned" in output, (
                f"{name} did not report ownership refusal; inspect private probe log"
            )
        else:
            assert result.returncode == 0, f"{name} failed; inspect private probe log"

    command(
        ["run", "--bundle", bundle.as_uri(), "CLI first shared marker"],
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
    held = SharedSessionStore(cwd, identity, root=state / "owners").acquire(app="fixture-owner")
    before_busy = (session / "transcript.jsonl").read_bytes()
    p = Probe(launch, cwd=cwd, env=env, cols=175, rows=50, guard_terminal_modes=True)
    try:
        p.wait("Startup failed", timeout=60)
        p.wait("open in another Amplifier client")
        p.send(b"Keep this unsent while busy\r")
        p.wait("Keep this unsent while busy")
        p.wait("Session not ready")
        assert (session / "transcript.jsonl").read_bytes() == before_busy
        capture(p, "shared-session-busy-draft-175")
    finally:
        p.close()
        held.release()
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
            if index == 0:
                canonical_before = {
                    name: (session / name).read_bytes()
                    for name in ("transcript.jsonl", "metadata.json", "events.jsonl")
                }
                command(["continue", "Rejected concurrent marker"], "cli-busy", busy=True)
                assert all(
                    (session / name).read_bytes() == value
                    for name, value in canonical_before.items()
                ), "Refused CLI startup changed canonical history or executed work"
                p.wait("CLI first shared marker")
                p.wait("fixture_probe")
            else:
                p.wait("Reading check complete.")
                assert any(m.get("content") == "CLI return marker" for m in transcript())
            assert "<system-reminders>" not in p.text
            assert not (session / ".tui/events.jsonl").exists(), (
                "Native history must not be copied into an imported TUI journal"
            )
            canonical_calls = [
                json.loads(line)
                for line in (session / "events.jsonl").read_text().splitlines()
                if line.strip()
            ]
            canonical_calls = [r for r in canonical_calls if r.get("event") == "llm:response"]
            expected = sum(
                (Decimal(str(r["data"]["usage"]["cost_usd"])) for r in canonical_calls), Decimal(0)
            )
            assert expected > 0
            p.wait(f"On resume · Session: ${expected:.2f}")
            capture(p, f"shared-session-resume-{size[0]}")
            if index == 0:
                action(p, "expand tools", "Activity ·")
                p.send(b"Earlier session usage\r")
                p.wait("▸ observed · Usage")
                capture(p, "shared-session-earlier-usage-175")
                p.send(b"Usage\r")
                p.wait("Earlier session usage / Recorded model call")
                p.wait("Preview · observed content")
                p.send(b"Preview\r")
                p.wait("Preview · Usage")
                p.wait("Input: 100")
                p.wait("Cost: $0.025000")
                capture(p, "shared-session-earlier-call-175")
                p.send(b"\x1b")
                p.wait("Actions / choices", absent=True)
                action(p, "expand tools", "Activity ·")
                p.send(b"fixture_probe\r")
                p.wait("Activity · fixture_probe")
                p.wait("tool:post")
                capture(p, "shared-session-tool-observations-175")
                p.send(b"tool:post\r")
                p.wait("fixture_probe / tool:post")
                p.wait("Preview · observed content")
                p.send(b"Preview\r")
                p.wait("Preview · tool:post")
                p.wait("Saved message")
                capture(p, "shared-session-tool-detail-175")
                p.send(b"\x1b")
                p.wait("Actions / choices", absent=True)
                assert transcript() == before, "Inspecting historical usage executed work"
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
    # Exercise the actual native entrypoint above former import quotas. Only
    # synthetic repeated tool results; never copy a personal transcript fixture.
    from amplifier_foundation.session import SessionHistoryStore

    large_id = str(uuid.uuid4())
    large_path = root / large_id
    large_messages = [{"role": "user", "content": "Large native fixture request"}]
    for _ in range(5500):
        large_messages.extend(
            [
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "reused-in-later-batch",
                            "type": "function",
                            "function": {
                                "name": "fixture_probe",
                                "arguments": "{}",
                            },
                        },
                    ],
                },
                {"role": "tool", "tool_call_id": "reused-in-later-batch", "content": "x" * 12800},
            ]
        )
    large_messages.append({"role": "assistant", "content": "Large native history ready marker"})
    SessionHistoryStore(large_path, session_id=large_id).save(
        large_messages,
        {
            "session_id": large_id,
            "working_dir": str(cwd),
            "bundle": bundle.as_uri(),
            "extension": "x" * (900 * 1024),
        },
    )
    del large_messages
    large_transcript = large_path / "transcript.jsonl"
    before = (large_transcript.stat().st_size, large_transcript.stat().st_mtime_ns)
    assert before[0] > 66 * 1024 * 1024
    p = Probe(
        [*new_launch, "--resume", large_id],
        cwd=cwd,
        env=env,
        cols=175,
        rows=50,
        guard_terminal_modes=True,
    )
    try:
        p.wait("Ready", timeout=120)
        p.wait("Large native history ready marker", timeout=60)
        p.send(b"Retained draft, not submitted")
        p.wait("Retained draft, not submitted")
        capture(p, "shared-session-large-native-175")
        assert "latest 100 of" in p.raw.decode(errors="replace")
        action(p, "Earlier history", "Earlier history ·")
        p.wait("Older 100 items")
        capture(p, "shared-session-history-page-175")
        click(p, "Older 100 items")
        p.wait("Earlier history · 5203–5302 of 5502")
        click(p, "Newer 100 items")
        p.wait("Earlier history · 5303–5402 of 5502")
        p.send(b"fixture_probe\r")
        p.wait("History preview · tool")
        p.wait("Copy displayed source")
        capture(p, "shared-session-history-preview-175")
        p.resize(40, 20)
        p.wait("History preview · tool")
        capture(p, "shared-session-history-preview-40")
        click(p, "Copy displayed source")
        p.wait("copied")
        p.send(b"\x1b")
        p.wait("Actions / choices", absent=True)
        p.wait("Retained draft, not submitted")
        assert (large_transcript.stat().st_size, large_transcript.stat().st_mtime_ns) == before
        assert not (large_path / ".tui/events.jsonl").exists()
    finally:
        p.close()
    return {
        "cli_to_tui_to_cli_to_tui": True,
        "same_identity": True,
        "historical_costs_reconciled": True,
        "structural_markdown_reply": True,
        "ordinary_startup_picker": True,
        "new_tui_to_cli": True,
        "explicit_composition_uses_same_format": True,
        "no_implicit_resume_turn": True,
        "actual_cli_refuses_live_tui_owner": True,
        "busy_tui_keeps_draft_without_execution": True,
        "shared_activity_snapshot_inspected": True,
        "large_native_entrypoint_no_replay": True,
        "history_pages_preview_copy_and_draft": True,
        "terminal_sizes": [[175, 50], [40, 20]],
        "scope": "Actual CLI/TUI entrypoints and ownership contention; deterministic provider and tool; no full web-client proof",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cli-executable", type=Path, help="Otherwise create a fresh owned CLI environment"
    )
    args = parser.parse_args()
    print(json.dumps(run(args.cli_executable.resolve() if args.cli_executable else None), indent=2))

"""Installed launch configuration must not depend on the development workspace."""

import asyncio
import json
import sys
from pathlib import Path

import pytest
from test_host import ending

from amplifier_tui.conversations import ConversationStore
from amplifier_tui.delivery import EventDelivery
from amplifier_tui.events import Event
from amplifier_tui.host import SessionHost
from amplifier_tui.launcher import CLI_COMMANDS, PACKAGE, arguments, cli_command, state_directory


def test_prior_release_upgrade_requires_matching_reviewed_artifact(tmp_path, monkeypatch):
    import hashlib
    from zipfile import ZipFile

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    from release_wheel import verify_prior_wheel

    wheel = tmp_path / "example-0.1-py3-none-any.whl"
    with ZipFile(wheel, "w") as archive:
        archive.writestr("example/__init__.py", "# Synthetic prior-release artifact\n")
    receipt = wheel.with_name(wheel.name + ".receipt.json")
    with pytest.raises(FileNotFoundError):
        verify_prior_wheel(wheel)
    payload = {"wheel": wheel.name, "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest()}
    receipt.write_text(json.dumps(payload))
    verify_prior_wheel(wheel)
    receipt.write_text(json.dumps({**payload, "wheel_sha256": "0" * 64}))
    with pytest.raises(ValueError, match="does not match"):
        verify_prior_wheel(wheel)
    receipt.write_text(json.dumps({**payload, "wheel": "different.whl"}))
    with pytest.raises(ValueError, match="does not match"):
        verify_prior_wheel(wheel)
    receipt.write_text(" " * (1024 * 1024 + 1))
    with pytest.raises(ValueError, match="exceeds"):
        verify_prior_wheel(wheel)


def test_cli_compatibility_entrypoint_preserves_argv_and_default_tui(monkeypatch):
    from amplifier_tui import launcher

    assert cli_command([]) is None
    assert cli_command(["--resume"]) is None
    assert cli_command(["--headless", "--prompt", "run"]) is None
    assert cli_command(["cli"])[-1] == "--help"
    for name in CLI_COMMANDS:
        assert cli_command([name, "--help"])[3:] == [name, "--help"]
    args = ["run", "literal $(no-shell) ; && `no-execution`", "--output-format", "json"]
    assert cli_command(args) == [sys.executable, "-m", "amplifier_app_cli", *args]
    invoked = []
    monkeypatch.setattr(sys, "argv", ["amplifier-tui", "--standalone", "cli", *args])
    monkeypatch.setattr(
        launcher.os, "execv", lambda executable, argv: invoked.append((executable, argv))
    )
    launcher.main()
    assert invoked == [(sys.executable, cli_command(args))]


def test_real_cli_help_through_entrypoint_has_no_native_or_session_start(tmp_path):
    import os
    import subprocess

    home = tmp_path / "home"
    home.mkdir()
    root = Path(__file__).resolve().parents[1]
    env = {
        **os.environ,
        "HOME": str(home),
        "AMPLIFIER_HOME": str(home / ".amplifier"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    for command in (
        ["cli", "--help"],
        ["run", "--help"],
        ["provider", "--help"],
        ["session", "--help"],
    ):
        result = subprocess.run(
            [sys.executable, str(root / "scripts/run.py"), *command],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "Usage:" in result.stdout
        assert "Native binary" not in result.stderr
    assert not list(home.rglob("transcript.jsonl"))
    assert not list(home.rglob("events.jsonl"))


def test_launcher_resume_and_listing_never_fall_back_to_another_directory(
    tmp_path, monkeypatch, capsys
):
    state, work, foreign = tmp_path / "state", tmp_path / "work", tmp_path / "elsewhere"
    work.mkdir()
    foreign.mkdir()
    saved = []
    for directory in (work, foreign):
        store = ConversationStore(
            state,
            {
                "fixture": True,
                "bundle": None,
                "overlays": [],
                "sources": None,
                "cwd": str(directory),
            },
        )
        saved.append(store.identity)
        store.close()
    monkeypatch.chdir(work)
    base = ["--state-dir", str(state), "--no-install"]
    for identity in ("latest", saved[0]):
        _, command = arguments([*base, "--resume", identity])
        assert command[command.index("--resume") + 1] == saved[0]
        assert command[command.index("--cwd") + 1] == str(work)
    with pytest.raises(SystemExit) as listed:
        arguments([*base, "--list-sessions"])
    assert listed.value.code == 0
    output = capsys.readouterr().out
    assert saved[0] in output and saved[1] not in output
    before = {p: p.read_bytes() for p in state.rglob("*") if p.is_file()}
    for op in ("--resume", "--recover"):
        with pytest.raises(SystemExit) as rejected:
            arguments([*base, op, saved[1]])
        assert rejected.value.code == 2
        assert "not found in this working directory" in capsys.readouterr().err
    monkeypatch.chdir(tmp_path)  # Parent is a different workspace, not a recursive scope.
    for resume in (["latest"], []):
        with pytest.raises(SystemExit) as rejected:
            arguments([*base, "--resume", *resume])
        assert rejected.value.code == 2
        assert "this working directory" in capsys.readouterr().err
    assert before == {p: p.read_bytes() for p in state.rglob("*") if p.is_file()}


def test_resolved_launch_directory_matches_cli_project_identity(tmp_path, monkeypatch):
    import amplifier_app_cli.session_store as cli_store
    from amplifier_app_cli.project_utils import get_project_slug
    from amplifier_app_cli.session_store import SessionStore

    monkeypatch.setattr(cli_store, "get_amplifier_home", lambda: tmp_path / "cli-home")
    work = tmp_path / "project"
    work.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(work, target_is_directory=True)
    monkeypatch.chdir(work)
    slug, directory = get_project_slug(), SessionStore().base_dir
    monkeypatch.chdir(alias)
    assert get_project_slug() == slug and SessionStore().base_dir == directory
    monkeypatch.chdir(tmp_path)
    assert get_project_slug() != slug and SessionStore().list_sessions() == []


def test_candidate_fingerprints_include_fixture_policy_and_native_source(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    from release_wheel import source_fingerprints

    fields = source_fingerprints()
    assert "src/amplifier_tui/fixtures/bundle.yaml" in fields
    assert "src/amplifier_tui/assets/user-questions.yaml" in fields
    assert "frontends/ratatui/src/native.rs" in fields
    assert all(
        not Path(name).is_absolute() and len(digest) == 64 for name, digest in fields.items()
    )


def test_candidate_fingerprint_rejects_symlinked_source(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    import release_wheel

    root = tmp_path / "candidate"
    source = root / "src/amplifier_tui"
    source.mkdir(parents=True)
    (source / "module.py").symlink_to(tmp_path / "outside.py")
    (tmp_path / "outside.py").write_text("outside = True\n")
    native = root / "frontends/ratatui/src"
    native.mkdir(parents=True)
    for path in (
        root / "pyproject.toml",
        root / "uv.lock",
        root / "README.md",
        root / "hatch_build.py",
        root / "frontends/ratatui/Cargo.toml",
        root / "frontends/ratatui/Cargo.lock",
    ):
        path.write_text("fixture\n")
    monkeypatch.setattr(release_wheel, "ROOT", root)
    with pytest.raises(RuntimeError, match="not a regular file"):
        release_wheel.source_fingerprints()


def test_default_remote_launch_and_packaged_overlays(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fixture-value-not-a-credential")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    _, command = arguments(["--settings-policy", "isolated"])
    assert command[command.index("--bundle") + 1].startswith("git+https://")
    assert "#subdirectory=bundles/anchors" in command[command.index("--bundle") + 1]
    assert "--sources" not in command
    assert str(PACKAGE / "assets/user-questions.yaml") in command
    assert str(PACKAGE / "assets/anthropic.yaml") in command
    assert state_directory() == tmp_path / "data/amplifier-tui"
    assert not (tmp_path / "data").exists()


def test_ordinary_launch_uses_cli_policy_without_reading_or_copying_settings(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    _, command = arguments([])
    assert command[command.index("--settings-policy") + 1] == "cli"
    assert "--bundle" not in command
    assert str(PACKAGE / "assets/anthropic.yaml") not in command
    assert str(PACKAGE / "assets/user-questions.yaml") in command
    assert list(tmp_path.iterdir()) == []


def test_doctor_does_not_write_state_or_reveal_credentials(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "private-fixture-marker")
    with pytest.raises(SystemExit):
        arguments(["--doctor", "--state-dir", str(tmp_path / "missing")])
    text = capsys.readouterr().out
    assert json.loads(text)["frontend"] == "ratatui"
    assert "private-fixture-marker" not in text
    assert not (tmp_path / "missing").exists()


def test_packaged_question_source_exists():
    import yaml

    file = PACKAGE / "assets/user-questions.yaml"
    value = yaml.safe_load(file.read_text())
    assert (file.parent / value["tools"][0]["source"] / "pyproject.toml").is_file()
    assert Path(value["tools"][0]["source"]).is_absolute() is False


def test_explicit_transcript_import_is_a_new_launch_not_resume(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _, command = arguments(["--fixture", "--import-transcript", "old.md"])
    assert command[command.index("--import-transcript") + 1] == str(tmp_path / "old.md")
    assert "--resume" not in command
    with pytest.raises(SystemExit):
        arguments(["--resume", "a" * 32, "--import-transcript", "old.md"])


async def test_tool_failure_summary_does_not_override_turn_completion(host):
    host.session.coordinator.get("tools")["fixture_probe"].config["fail"] = True
    host.submit("Compute")
    event = (await ending(host))[-1]
    assert event.payload["status"] == "completed"
    assert event.payload["tools"]["root"]["failed"] == 1
    assert "1 failed" in event.payload["message"]
    assert "See Activity evidence" in event.payload["message"]
    host.session.coordinator.get("tools")["fixture_probe"].config["fail"] = False
    host.submit("Again")
    event = (await ending(host))[-1]
    assert event.payload["tools"]["root"]["failed"] == 0
    assert event.payload["message"] == "Turn complete."


async def test_child_observation_summary_counts_calls_not_events(host):
    host.emit(
        "child.observed", "activity:child:1:call:tool:pre", event="tool:pre", status="running"
    )
    host.emit(
        "child.observed", "activity:child:1:call:tool:post", event="tool:post", status="failed"
    )
    assert host.observed_tools["children"] == {"activity:child:1:call": "failed"}


async def test_source_delivery_overload_is_bounded_durable_and_stops_admission(prepared, tmp_path):
    store = ConversationStore(tmp_path, {})
    host = SessionHost(store)
    try:
        await host.open(*prepared, tmp_path)
        assert host.submit("No automatic retry")[0]
        for index in range(4100):
            host.emit("display.message", f"burst-{index}", text="Observed before failure")
        await host.task
        assert host.events.qsize() == 4096
        assert host.delivery_failed.is_set()
        assert not host.ready and not host.submit("Must not run")[0]
        assert not host.session.coordinator.get("providers")["fixture"].calls
        with pytest.raises(RuntimeError, match="backlog exceeded"):
            await host.next_event()
        rows = [json.loads(line) for line in (store.path / "events.jsonl").read_text().splitlines()]
        assert sum(r["kind"] == "display.message" for r in rows) == 4100
        assert rows[-1]["kind"] == "turn.ended"
        assert rows[-1]["payload"]["status"] == "interrupted"
        assert json.loads((store.path / "checkpoint.json").read_text())["status"] == "uncertain"
    finally:
        await host.close()


async def test_delivery_byte_bound_and_budget_release():
    queue = EventDelivery(maxsize=2, max_bytes=400)
    event = Event("session", 1, "turn", "text.delta", "item", {"text": "small"})
    queue.put_nowait(event)
    assert 0 < queue.pending_bytes < 400
    assert await queue.get() == event
    assert queue.pending_bytes == 0
    with pytest.raises(asyncio.QueueFull):
        queue.put_nowait(Event("session", 2, "turn", "text.final", "large", {"text": "x" * 500}))
    assert queue.empty() and queue.pending_bytes == 0


async def test_bridge_exits_on_source_failure_with_input_still_open():
    # Fault producer only, not a replacement runtime conformance claim. Keeping
    # stdin open proves shutdown follows source failure rather than input EOF.
    code = """
import asyncio
from pathlib import Path
from amplifier_tui.frontend_bridge import serve
from amplifier_tui.host import RuntimeBridge, SessionHost
async def open_host(host):
    for i in range(4100):
        host.emit('display.message', str(i), text='overload fault')
asyncio.run(serve(lambda emit: RuntimeBridge(SessionHost(), open_host, emit, True, Path.cwd())))
"""
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        code,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        async with asyncio.timeout(5):
            output, error = await asyncio.gather(process.stdout.read(), process.stderr.read())
            assert await process.wait() != 0
        assert b"Source event delivery exceeded" in error
        assert b"Runtime event delivery failed; no work retried" in error
        assert b"snapshot" in output
    finally:
        if process.returncode is None:
            process.kill()
        await process.wait()


@pytest.mark.parametrize("extra,expected", [(None, False), ("standalone", True), ("other", False)])
def test_prior_connected_release_explicitly_qualifies_standalone_upgrade(tmp_path, extra, expected):
    from zipfile import ZipFile

    from release_wheel import prior_has_standalone_extra
    wheel = tmp_path / "prior.whl"
    with ZipFile(wheel, "w") as archive:
        content = "Metadata-Version: 2.3\nName: amplifier-app-tui\nVersion: 0.4.0rc1\n"
        if extra:
            content += "Provides-Extra: " + extra + "\n"
        archive.writestr("amplifier_app_tui-0.4.0rc1.dist-info/METADATA", content)
    assert prior_has_standalone_extra(wheel) is expected

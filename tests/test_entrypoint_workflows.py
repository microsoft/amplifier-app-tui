"""Read-only shell completion and reversible, directory-local housekeeping."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from amplifier_tui.conversations import (
    ConversationStore,
    archive_conversation,
    catalog,
    resolve_resume,
)
from amplifier_tui.launcher import arguments

ROOT = Path(__file__).resolve().parents[1]


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_archive_is_reversible_closed_directory_local_and_content_preserving(tmp_path):
    directory, state = tmp_path / "work", tmp_path / "state"
    directory.mkdir()
    store = ConversationStore(state, {"cwd": str(directory)})
    identity = store.identity
    store.checkpoint([], 0, "synthetic-fingerprint", True)
    store.save_draft("Synthetic retained draft")
    before = snapshot(store.path)
    with pytest.raises(ValueError, match="Close the conversation"):
        archive_conversation(state, identity, cwd=directory, archived=True)
    assert snapshot(store.path) == before
    store.close()
    for wrong in (tmp_path, directory / "subdirectory"):
        with pytest.raises(ValueError, match="this working directory"):
            archive_conversation(state, identity, cwd=wrong, archived=True)
    archive_conversation(state, identity, cwd=directory, archived=True)
    assert catalog(state, cwd=directory) == []
    assert catalog(state, cwd=directory, archived=True)[0]["id"] == identity
    with pytest.raises(ValueError, match="not found"):
        resolve_resume(state, identity, cwd=directory)
    with pytest.raises(ValueError, match="archived"):
        ConversationStore(state, {"cwd": str(directory)}, identity)
    after = snapshot(store.path)
    assert {k: v for k, v in before.items() if k != "metadata.json"} == {
        k: v for k, v in after.items() if k != "metadata.json"
    }
    archive_conversation(state, identity, cwd=directory, archived=False)
    restored = ConversationStore(state, {"cwd": str(directory)}, identity)
    try:
        assert restored.draft == "Synthetic retained draft"
        assert catalog(state, cwd=directory)[0]["id"] == identity
    finally:
        restored.close()


def test_housekeeping_launcher_requires_confirmation_and_does_not_launch(
    tmp_path, capsys, monkeypatch
):
    from amplifier_tui.conversations import SharedConversationStore

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("AMPLIFIER_HOME", str(home))
    state = tmp_path / "state"
    store = SharedConversationStore(
        state,
        {
            "cwd": str(tmp_path),
            "cli_home": str(home),
            "bundle": "synthetic-bundle",
            "settings_policy": "cli",
            "shared_session": True,
            "fixture": False,
        },
    )
    identity = store.identity
    store.close()
    base = ["--state-dir", str(state), "--cwd", str(tmp_path)]
    before = snapshot(home)
    for extra in (
        ["--archive", identity],
        ["--archive", "latest", "--confirm"],
        ["--confirm"],
        ["--archive", identity, "--fixture", "--confirm"],
    ):
        with pytest.raises(SystemExit) as error:
            arguments([*base, *extra], require_terminal=True)
        assert error.value.code == 2
        assert snapshot(home) == before
    for extra in (
        ["--archive", identity, "--confirm"],
        ["--list-archived"],
        ["--restore", identity, "--confirm"],
    ):
        with pytest.raises(SystemExit) as done:
            arguments([*base, *extra], require_terminal=True)
        assert done.value.code == 0
        assert identity in capsys.readouterr().out


def complete(tmp_path, instruction, words="amplifier-tui ", index=1):
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts/run.py")],
        cwd=tmp_path,
        env={
            **os.environ,
            "AMPLIFIER_HOME": str(tmp_path / "config"),
            "AMPLIFIER_TUI_STATE_DIR": str(tmp_path / "state"),
            "_AMPLIFIER_TUI_COMPLETE": instruction,
            "COMP_WORDS": words,
            "COMP_CWORD": str(index),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        capture_output=True,
        text=True,
        timeout=20,
    )


@pytest.mark.parametrize("shell", ["bash", "zsh", "fish"])
def test_completion_source_is_native_protocol_without_session_or_settings_writes(tmp_path, shell):
    before = snapshot(tmp_path)
    result = complete(tmp_path, f"{shell}_source")
    assert result.returncode == 0, result.stderr
    assert "_AMPLIFIER_TUI_COMPLETE" in result.stdout and "amplifier-tui" in result.stdout
    assert "Starting" not in result.stdout
    assert not result.stderr
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize(
    "words,index,expected",
    [
        ("amplifier-tui --fi", 1, "plain,--fixture"),
        ("amplifier-tui ru", 1, "plain,run"),
        ("amplifier-tui run --out", 2, "plain,--output-format"),
        ("amplifier-tui run --output-format j", 3, "plain,json-trace"),
        ("amplifier-tui cli run --out", 3, "plain,--output-format"),
        ("amplifier-tui --settings-policy i", 2, "plain,isolated"),
        ("amplifier-tui run --provider syn", 3, "plain,synthetic"),
    ],
)
def test_completion_uses_actual_cli_grammar_and_native_options_read_only(
    tmp_path, words, index, expected
):
    config = tmp_path / "config"
    config.mkdir()
    (config / "settings.yaml").write_text(
        json.dumps(
            {"config": {"providers": [{"module": "provider-synthetic", "name": "synthetic"}]}}
        )
    )
    (config / "keys.env").write_text("COMPLETION_FIXTURE_KEY=synthetic-value\n")
    before = snapshot(tmp_path)
    result = complete(tmp_path, "bash_complete", words, index)
    assert result.returncode == 0, result.stderr
    assert expected in result.stdout.splitlines()
    assert not result.stderr
    assert "synthetic-value" not in result.stdout
    assert snapshot(tmp_path) == before


def test_invalid_completion_instruction_never_falls_through_to_launch(tmp_path):
    result = complete(tmp_path, "bash_execute")
    assert result.returncode == 2
    assert not result.stdout
    assert "Unsupported shell completion" in result.stderr
    assert not snapshot(tmp_path)


def test_completion_never_initializes_keys_or_session_store(tmp_path):
    program = """
from amplifier_app_cli.key_manager import KeyManager
from amplifier_app_cli.session_store import SessionStore
def forbidden(*args, **kwargs):
    raise AssertionError('Completion initialized runtime state')
KeyManager.__init__ = forbidden
SessionStore.__init__ = forbidden
from amplifier_tui.launcher import main
main()
"""
    result = subprocess.run(
        [sys.executable, "-c", program],
        env={
            **os.environ,
            "AMPLIFIER_HOME": str(tmp_path / "config"),
            "_AMPLIFIER_TUI_COMPLETE": "bash_complete",
            "COMP_WORDS": "amplifier-tui run --resume ",
            "COMP_CWORD": "3",
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert not result.stderr
    assert not snapshot(tmp_path)

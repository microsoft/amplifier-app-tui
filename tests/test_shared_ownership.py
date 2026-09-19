"""Real Foundation ownership/history contracts, with synthetic private sessions."""

import asyncio
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from amplifier_foundation.session import SessionBusyError, SessionHistoryStore, SharedSessionStore

from amplifier_tui.cli_compat import session_directory
from amplifier_tui.conversations import SharedConversationStore, archive_conversation
from amplifier_tui.events import Event
from amplifier_tui.host import RuntimeBridge, SessionHost


@pytest.fixture
def native(tmp_path, monkeypatch):
    home, cwd = tmp_path / "home", tmp_path / "project"
    home.mkdir()
    cwd.mkdir()
    monkeypatch.setenv("AMPLIFIER_HOME", str(home))
    monkeypatch.setenv("AMPLIFIER_SESSION_STATE_HOME", str(tmp_path / "shared-state"))
    identity = str(uuid.uuid4())
    path = session_directory(home, cwd) / identity
    history = SessionHistoryStore(path)
    messages = [
        {"role": "user", "content": "Synthetic shared request"},
        {"role": "assistant", "content": "Synthetic shared answer"},
    ]
    history.save(
        messages,
        {
            "session_id": identity,
            "working_dir": str(cwd),
            "bundle": "synthetic-bundle",
            "third_party": {"retain": [1, 2]},
        },
    )
    launch = dict(
        fixture=False,
        bundle="synthetic-bundle",
        overlays=[],
        sources=None,
        cwd=str(cwd),
        settings_policy="cli",
        cli_home=str(home),
        shared_session=True,
    )
    return launch, identity, history, messages


def contender(launch, identity):
    """Independent process uses the same public API as CLI and Unified."""
    code = """
import sys
from amplifier_foundation.session import SessionBusyError, SharedSessionStore
store = SharedSessionStore(sys.argv[1], sys.argv[2])
try:
    held = store.acquire(app="synthetic-contender")
except SessionBusyError as error:
    print("busy", error.owner["app"])
else:
    held.release()
    print("acquired")
"""
    result = subprocess.run(
        [sys.executable, "-c", code, launch["cwd"], identity],
        capture_output=True,
        text=True,
        timeout=15,
        env=os.environ.copy(),
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_shared_owner_blocks_before_any_history_read_or_sidecar(native, tmp_path, monkeypatch):
    launch, identity, history, _ = native
    held = SharedSessionStore(launch["cwd"], identity).acquire(app="synthetic-cli")
    before = history.transcript_path.read_bytes()

    def forbidden_read(*args, **kwargs):
        raise AssertionError("History read before acquiring ownership")

    monkeypatch.setattr(SessionHistoryStore, "load", forbidden_read)
    try:
        with pytest.raises(BlockingIOError, match="another Amplifier client"):
            SharedConversationStore(tmp_path, launch, identity)
        assert not (history.session_dir / ".tui").exists()
        assert history.transcript_path.read_bytes() == before
    finally:
        held.release()


def test_idle_tui_blocks_real_other_process_until_close(native, tmp_path):
    launch, identity, history, _ = native
    store = SharedConversationStore(tmp_path, launch, identity)
    try:
        assert contender(launch, identity) == "busy amplifier-tui"
        shared = SharedSessionStore(launch["cwd"], identity)
        assert not shared.checkpoint_path.exists()  # Never introduce duplicate authority.
        assert not history.events_path.exists()  # Reading installs no logger.
    finally:
        store.close()
    assert contender(launch, identity) == "acquired"


def test_new_session_owns_lock_before_first_native_write(native, tmp_path, monkeypatch):
    launch, _, _, _ = native
    original = SessionHistoryStore.save
    writes = []

    def save(history, *args, **kwargs):
        writes.append(history.session_id)
        assert contender(launch, history.session_id) == "busy amplifier-tui"
        return original(history, *args, **kwargs)

    monkeypatch.setattr(SessionHistoryStore, "save", save)
    store = SharedConversationStore(tmp_path, launch)
    try:
        assert writes == [store.identity]
    finally:
        store.close()


def test_failed_resume_releases_ownership_and_never_seeds_empty_history(native, tmp_path):
    launch, identity, history, _ = native
    history.transcript_path.write_text("{invalid\n")
    with pytest.raises(ValueError, match="Cannot read valid"):
        SharedConversationStore(tmp_path, launch, identity)
    assert history.transcript_path.read_text() == "{invalid\n"
    assert not (history.session_dir / ".tui").exists()
    assert contender(launch, identity) == "acquired"


@pytest.mark.parametrize("primary", ["corrupt", "missing"])
def test_native_backup_recovery_preserves_canonical_bytes_and_provider_fields(
    native, tmp_path, primary
):
    launch, identity, history, messages = native
    messages[-1].update(
        content_blocks=[{"type": "text", "text": "Provider retained content"}],
        thinking_block={"text": "Public fixture thinking", "signature": "synthetic-signature"},
        provider_continuation={"opaque_id": "synthetic-continuation", "nullable": None},
    )
    history.save(messages, history.load_metadata())
    history.save(messages, history.load_metadata())
    backup = history.transcript_path.with_suffix(".jsonl.backup")
    metadata_backup = history.metadata_path.with_suffix(".json.backup")
    if primary == "corrupt":
        history.transcript_path.write_text("{invalid\n")
        history.metadata_path.write_text("{invalid\n")
    else:
        history.transcript_path.unlink()
        history.metadata_path.unlink()
    before = {
        p: p.read_bytes() if p.exists() else None
        for p in (history.transcript_path, history.metadata_path, backup, metadata_backup)
    }
    store = SharedConversationStore(tmp_path, launch, identity)
    try:
        assert store.saved["messages"] == messages
        assert any(d.code == "recovered_backup" for d in store.history_diagnostics)
        assert all((p.read_bytes() if p.exists() else None) == data for p, data in before.items())
        frames = []
        bridge = RuntimeBridge(SessionHost(store), None, frames.append, False, Path(launch["cwd"]))
        journal = (store.path / "events.jsonl").read_bytes()
        bridge.snapshot()
        bridge.snapshot()
        for frame in frames:
            warning = next(row for row in frame["items"] if row["id"] == "shared:backup-recovery")
            assert "Recovered" in warning["text"]
            assert "transcript" in warning["text"] and "metadata" in warning["text"]
            assert warning["status"] == "warning"
            assert json.loads(warning["detail"])["level"] == "warning"
        assert (store.path / "events.jsonl").read_bytes() == journal
        assert all((p.read_bytes() if p.exists() else None) == data for p, data in before.items())
        store.checkpoint(messages, len(store.restored_events), None, True)
        assert history.load_messages() == messages
        assert history.load_metadata()["third_party"] == {"retain": [1, 2]}
        assert backup.read_bytes() == before[backup]  # Damaged primary never rotates onto it.
    finally:
        store.close()


def test_missing_authority_never_substitutes_empty_history(native, tmp_path):
    launch, identity, history, _ = native
    history.transcript_path.unlink()
    with pytest.raises(ValueError, match="transcript is missing"):
        SharedConversationStore(tmp_path, launch, identity)
    assert not (history.session_dir / ".tui").exists()
    assert contender(launch, identity) == "acquired"


def test_backup_symlink_is_not_a_recovery_source(native, tmp_path):
    launch, identity, history, _ = native
    outside = tmp_path / "not-a-session.jsonl"
    outside.write_text('{"role":"user","content":"do not adopt"}\n')
    history.transcript_path.with_suffix(".jsonl.backup").symlink_to(outside)
    with pytest.raises((OSError, ValueError)):
        SharedConversationStore(tmp_path, launch, identity)
    assert not (history.session_dir / ".tui").exists()
    assert contender(launch, identity) == "acquired"


def test_released_callbacks_cannot_borrow_a_new_owner(native, tmp_path):
    launch, identity, history, messages = native
    first = SharedConversationStore(tmp_path, launch, identity)
    first.close()
    second = SharedConversationStore(tmp_path, launch, identity)
    try:
        paths = [history.transcript_path, history.metadata_path, second.path / "draft.json"]
        before = {path: path.read_bytes() for path in paths}
        actions = [
            lambda: first.checkpoint(messages, len(first.restored_events), None, True),
            lambda: first.save_draft("stale draft"),
            lambda: first.set_title("stale name"),
            lambda: first.naming_metadata(7),
            lambda: first.record(Event(identity, 99, None, "display.message", "late", {})),
        ]
        for action in actions:
            with pytest.raises(RuntimeError, match="no longer active"):
                action()
        assert all(path.read_bytes() == data for path, data in before.items())
        first.close()  # Idempotent stale close never releases the new owner.
        assert contender(launch, identity) == "busy amplifier-tui"
    finally:
        second.close()


def test_housekeeping_respects_common_owner_before_creating_sidecar(native, tmp_path):
    launch, identity, history, _ = native
    held = SharedSessionStore(launch["cwd"], identity).acquire(app="synthetic-unified")
    try:
        with pytest.raises(ValueError, match="Close the conversation"):
            archive_conversation(
                tmp_path, identity, cwd=launch["cwd"], cli_home=launch["cli_home"], archived=True
            )
        assert not (history.session_dir / ".tui").exists()
    finally:
        held.release()


async def test_ownership_survives_runtime_cleanup_await(native, prepared, tmp_path):
    launch, identity, _, _ = native
    store = SharedConversationStore(tmp_path, launch, identity)
    host = SessionHost(store)
    await host.open(*prepared, tmp_path)
    entered, finish = asyncio.Event(), asyncio.Event()

    async def delayed_cleanup():
        entered.set()
        await finish.wait()

    host.session.coordinator.register_cleanup(delayed_cleanup)
    closing = asyncio.create_task(host.close())
    try:
        await asyncio.wait_for(entered.wait(), 5)
        with pytest.raises(SessionBusyError):
            SharedSessionStore(launch["cwd"], identity).acquire(app="synthetic-contender")
    finally:
        finish.set()
        await asyncio.wait_for(closing, 5)
    held = SharedSessionStore(launch["cwd"], identity).acquire(app="synthetic-contender")
    held.release()


def test_process_death_releases_lock_without_replaying_history(native, tmp_path):
    launch, identity, history, messages = native
    code = """
import json, os, sys
from amplifier_tui.conversations import SharedConversationStore
store = SharedConversationStore(sys.argv[1], json.loads(sys.argv[2]), sys.argv[3])
os._exit(23)
"""
    before = history.transcript_path.read_bytes()
    result = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path), json.dumps(launch), identity],
        capture_output=True,
        timeout=15,
        env=os.environ.copy(),
    )
    assert result.returncode == 23, result.stderr
    resumed = SharedConversationStore(tmp_path, launch, identity)
    try:
        assert resumed.saved["messages"] == messages
        assert history.transcript_path.read_bytes() == before
    finally:
        resumed.close()


def test_real_unified_storage_adapter_round_trip_and_contention(native, tmp_path, monkeypatch):
    """Third-client storage proof, not a Unified web/worker runtime certification.

    Unified's storage adapter does not acquire ownership itself. This reproduces
    its worker's explicit Foundation acquire/check/release composition, without
    importing a worker, mounting modules, or executing a recorded tool.
    """
    import builtins

    source = (
        Path(os.environ.get("AMPLIFIER_TUI_SOURCE_ROOT", Path(__file__).resolve().parents[2]))
        / "amplifier-unified"
    )
    if not (source / "amplifier_web/host/storage.py").is_file():
        pytest.skip("Real Unified checkout unavailable; third-client adapter gate not exercised")
    monkeypatch.syspath_prepend(str(source))
    original_import = builtins.__import__

    def no_runtime(name, *args, **kwargs):
        assert name not in ("amplifier_web.runtime_worker", "amplifier_web.host.session")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_runtime)
    from amplifier_web.host import storage
    from amplifier_web.session_files import sessions_dir
    from amplifier_web.shared_state import shared_state_home

    assert Path(storage.__file__).resolve() == source / "amplifier_web/host/storage.py"
    launch, identity, history, messages = native
    workspace = Path(launch["cwd"])
    assert sessions_dir(workspace) == history.session_dir.parent
    assert shared_state_home() == Path(os.environ["AMPLIFIER_SESSION_STATE_HOME"])
    unified = storage.SessionStore.for_app(tmp_path / "unified-home", workspace)
    common = SharedSessionStore(workspace, identity)

    tui = SharedConversationStore(tmp_path, launch, identity)
    provider_fields = {
        "content_blocks": [{"type": "opaque", "provider": "synthetic"}],
        "thinking_block": {"text": "Fixture thought", "signature": "fixture-signature"},
        "provider_continuation": {"id": "fixture-opaque", "nullable": None},
    }
    messages[-1].update(provider_fields)
    messages += [
        {
            "role": "assistant",
            "tool_calls": [{"id": "fixture-call", "tool": "never_execute", "arguments": {}}],
        },
        {"role": "tool", "tool_call_id": "fixture-call", "content": "Stored outcome"},
        {"role": "assistant", "content": "Stored completion"},
    ]
    try:
        tui.checkpoint(messages, len(tui.restored_events), None, True)
        with pytest.raises(SessionBusyError):
            common.acquire(app="amplifier-unified")
        before = history.transcript_path.read_bytes()
        assert unified.load(identity)[0] == messages  # Read-only browsing remains available.
        assert history.transcript_path.read_bytes() == before
    finally:
        tui.close()

    held = common.acquire(app="amplifier-unified")
    try:
        with pytest.raises(BlockingIOError):
            SharedConversationStore(tmp_path, launch, identity)
        restored, metadata = unified.load(identity)
        assert restored == messages
        assert metadata["third_party"] == {"retain": [1, 2]}
        restored += [
            {"role": "user", "content": "Synthetic Unified continuation"},
            {"role": "assistant", "content": "Synthetic Unified answer"},
        ]
        held.check()
        unified.save(identity, restored, {"third_client": {"preserve": True}})
        assert not common.checkpoint_path.exists()
        assert not history.events_path.exists()
    finally:
        held.release()

    # The actual CLI native adapter reads the exact same ID and provider fields.
    from amplifier_app_cli.session_store import SessionStore as CLIStore

    cli = CLIStore(base_dir=history.session_dir.parent)
    cli_messages, cli_metadata = cli.load(identity)
    assert cli_messages == restored
    assert cli_metadata["third_party"] == {"retain": [1, 2]}
    assert cli_metadata["third_client"] == {"preserve": True}
    before = history.transcript_path.read_bytes()
    resumed = SharedConversationStore(tmp_path, launch, identity)
    try:
        assert resumed.saved["messages"] == restored
        assert all(
            resumed.saved["messages"][1][key] == value for key, value in provider_fields.items()
        )
        assert history.transcript_path.read_bytes() == before
        assert len(list(history.session_dir.parent.iterdir())) == 1
        assert not (tmp_path / "unified-home/sessions").exists()
    finally:
        resumed.close()

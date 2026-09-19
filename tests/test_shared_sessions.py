"""Synthetic CLI/TUI round trips; never use personal settings or history."""

import json
import uuid

import pytest

from amplifier_tui.cli_compat import session_directory, settings_for
from amplifier_tui.conversations import (
    SharedConversationStore,
    catalog,
    portable_history,
    resolve_resume,
)
from amplifier_tui.host import SessionHost
from amplifier_tui.input_history import recall
from amplifier_tui.navigation import session_choices


@pytest.fixture
def shared(tmp_path, monkeypatch):
    from amplifier_app_cli.session_store import SessionStore

    home, cwd = tmp_path / "home", tmp_path / "project"
    home.mkdir()
    cwd.mkdir()
    monkeypatch.setenv("AMPLIFIER_HOME", str(home))
    monkeypatch.chdir(cwd)
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
    cli = SessionStore(base_dir=session_directory(home, cwd))
    identity = str(uuid.uuid4())
    messages = [
        {"role": "user", "content": "Shared violet lantern question"},
        {"role": "assistant", "content": "Canonical CLI answer"},
    ]
    cli.save(
        identity,
        messages,
        {
            "session_id": identity,
            "working_dir": str(cwd),
            "bundle": "synthetic-bundle",
            "name": "Shared fixture",
            "third_party": {"preserve": True},
        },
    )
    return launch, cli, identity, messages


def test_cli_sessions_in_ordinary_directory_picker_search_and_recall(shared, tmp_path):
    launch, cli, identity, messages = shared
    home, cwd = launch["cli_home"], launch["cwd"]
    # Same-project child sessions are not root resume candidates.
    cli.save(identity + "_child", messages, {})
    entries = catalog(tmp_path, cwd=cwd, cli_home=home)
    assert [e["id"] for e in entries] == [identity]
    assert resolve_resume(tmp_path, "latest", cwd=cwd, cli_home=home)["id"] == identity
    choices = session_choices(
        tmp_path / "new-search-cache", None, cwd=cwd, cli_home=home, query="violet"
    )
    assert [r["id"] for r in choices["sessions"]] == [identity]
    assert "shared CLI/TUI" in choices["sessions"][0]["status"]
    assert recall(tmp_path, cwd, None, cli_home=home)["entries"] == [messages[0]["content"]]
    assert catalog(tmp_path, cwd=tmp_path, cli_home=home) == []
    assert not (cli.base_dir / identity / ".tui").exists()  # Discovery never adopts/writes.


def test_product_never_discovers_or_archives_retired_live_journals(shared, tmp_path):
    from amplifier_tui.conversations import ConversationStore, archive_conversation

    launch, _, canonical_id, _ = shared
    journal = ConversationStore(tmp_path, {**launch, "shared_session": False})
    old_id = journal.identity
    journal.close()
    home, cwd = launch["cli_home"], launch["cwd"]
    assert [e["id"] for e in catalog(tmp_path, cwd=cwd, cli_home=home)] == [canonical_id]
    with pytest.raises(ValueError, match="not found"):
        resolve_resume(tmp_path, old_id, cwd=cwd, cli_home=home)
    with pytest.raises(FileNotFoundError):
        archive_conversation(tmp_path, old_id, cwd=cwd, cli_home=home, archived=True)
    assert not json.loads((journal.path / "metadata.json").read_text()).get("archived")


def test_every_live_factory_uses_canonical_storage_even_with_isolated_policy(shared, tmp_path):
    from amplifier_tui.conversations import open_conversation

    launch, cli, _, _ = shared
    launch = {**launch, "settings_policy": "isolated"}
    launch.pop("shared_session")
    store = open_conversation(tmp_path, launch)
    try:
        assert isinstance(store, SharedConversationStore)
        assert store.identity in cli.list_sessions()
        assert not (tmp_path / "conversations").exists()
    finally:
        store.close()


async def test_cli_tui_cli_tui_same_identity_context_and_no_replay(shared, prepared, tmp_path):
    launch, cli, identity, messages = shared
    first = SharedConversationStore(tmp_path, launch, identity)
    host = SessionHost(first)
    await host.open(*prepared, tmp_path)
    try:
        assert host.session_id == identity
        provider = host.session.coordinator.get("providers")["fixture"]
        tool = host.session.coordinator.get("tools")["fixture_probe"]
        assert not provider.calls and tool.calls == 0
        assert host.submit("TUI next request")[0]
        await host.task
        assert host.outcome == "success"
        first.save_draft("Unsent TUI draft")
    finally:
        await host.close()
    canonical, metadata = cli.load(identity)
    assert portable_history(canonical[:2]) == messages
    assert any(m.get("role") == "tool" for m in canonical)
    assert metadata["third_party"] == {"preserve": True}
    assert metadata["name"] == "Shared fixture"
    marker = json.loads((first.path / "checkpoint.json").read_text())
    assert "messages" not in marker
    assert not (tmp_path / "conversations" / identity).exists()

    # A real CLI save advances the shared history while TUI is closed.
    canonical += [
        {"role": "user", "content": "CLI continuation"},
        {"role": "assistant", "content": "CLI continuation result"},
    ]
    cli.save(identity, canonical, {**metadata, "name": "CLI renamed"})
    # The CLI applies its own native sanitizer; read the actual saved source,
    # rather than assuming it retains every JSON field (for example nulls).
    canonical, _ = cli.load(identity)
    second = SharedConversationStore(tmp_path, launch, identity)
    resumed = SessionHost(second)
    try:
        assert second.saved["messages"] == canonical
        assert second.draft == "Unsent TUI draft"
        assert second.metadata["title"] == "CLI renamed"
        assert sum(i["text"] == "CLI continuation" for i in second.projection()) == 1
        assert list((second.path / "views").iterdir())  # Old observations retained.
        await resumed.open(*prepared, tmp_path)
        assert not resumed.session.coordinator.get("providers")["fixture"].calls
        assert resumed.session.coordinator.get("tools")["fixture_probe"].calls == 0
        assert resumed.session_id == identity
    finally:
        await resumed.close()


async def test_new_tui_conversation_is_native_cli_session(shared, prepared, tmp_path):
    launch, cli, _, _ = shared
    store = SharedConversationStore(tmp_path, launch)
    host = SessionHost(store)
    try:
        await host.open(*prepared, tmp_path)
        assert host.submit("New shared conversation")[0]
        await host.task
        assert host.outcome == "success"
        assert store.set_title("Chosen shared title")
    finally:
        await host.close()
    assert store.identity in cli.list_sessions()
    messages, metadata = cli.load(store.identity)
    assert messages[0]["content"] == "New shared conversation"
    assert metadata["name"] == "Chosen shared title"
    assert metadata["working_dir"] == launch["cwd"]


def test_shared_lock_conflict_and_stale_write_preserve_cli_bytes(shared, tmp_path):
    launch, cli, identity, messages = shared
    store = SharedConversationStore(tmp_path, launch, identity)
    try:
        with pytest.raises(BlockingIOError):
            SharedConversationStore(tmp_path, launch, identity)
        cli.save(identity, messages + [{"role": "user", "content": "External change"}], {})
        before = (store.canonical_path / "transcript.jsonl").read_bytes()
        with pytest.raises(ValueError, match="changed while"):
            store.checkpoint(messages, len(store.restored_events), None, True)
        assert (store.canonical_path / "transcript.jsonl").read_bytes() == before
    finally:
        store.close()


def test_session_settings_override_local_without_mutating_any_scope(shared):
    launch, cli, identity, _ = shared
    path = cli.base_dir / identity / "settings.yaml"
    path.write_text("bundle:\n  active: session-fixture\n")
    before = path.read_bytes()
    assert (
        settings_for(launch["cwd"], launch["cli_home"], identity).get_active_bundle()
        == "session-fixture"
    )
    assert path.read_bytes() == before


def test_wrong_project_and_unpaired_cli_history_refuse_before_sidecar(shared, tmp_path):
    launch, cli, identity, messages = shared
    cli.update_metadata(identity, {"working_dir": str(tmp_path)})
    with pytest.raises(ValueError, match="another working directory"):
        SharedConversationStore(tmp_path, launch, identity)
    cli.save(
        identity,
        messages + [{"role": "assistant", "tool_calls": [{"id": "unfinished"}]}],
        {"working_dir": launch["cwd"]},
    )
    with pytest.raises(ValueError, match="Unfinished"):
        SharedConversationStore(tmp_path, launch, identity)
    assert not (cli.base_dir / identity / ".tui").exists()


def test_native_launcher_selects_shared_cli_session(shared, tmp_path):
    from amplifier_tui.launcher import arguments

    launch, _, identity, _ = shared
    _, command = arguments(["--state-dir", str(tmp_path), "--resume", identity])
    assert command[command.index("--resume") + 1] == identity
    assert command[command.index("--bundle") + 1] == "synthetic-bundle"
    assert command[command.index("--cli-home") + 1] == launch["cli_home"]
    assert "--legacy-store" not in command


def test_shared_observations_hide_only_injected_reminders_and_keep_tool_details(shared, tmp_path):
    launch, cli, identity, messages = shared
    reminder = {
        "role": "user",
        "content": '<system-reminder source="fixture">hidden reminder</system-reminder>',
        "metadata": {"ephemeral": True, "persisted": True},
    }
    messages += [
        reminder,
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": "fixture-call", "tool": "fixture_probe", "arguments": {"text": "retained"}}
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "fixture-call",
            "content": '{"success":true,"output":"retained result"}',
        },
    ]
    cli.save(identity, messages, {"working_dir": launch["cwd"]})
    store = SharedConversationStore(tmp_path, launch, identity)
    try:
        assert reminder in store.saved["messages"]
        items = store.projection()
        assert not any("hidden reminder" in i["text"] for i in items)
        tool = next(i for i in items if i["kind"] == "tool")
        assert tool["status"] == "succeeded"
        assert "fixture_probe" in tool["text"] and "retained result" in tool["detail"]
    finally:
        store.close()
    assert recall(tmp_path, launch["cwd"], None, cli_home=launch["cli_home"])["entries"] == [
        messages[0]["content"]
    ]


def test_shared_export_and_archive_are_source_preserving(shared, tmp_path):
    from amplifier_tui.conversations import archive_conversation
    from amplifier_tui.recovery import export

    launch, cli, identity, _ = shared
    kwargs = {"cwd": launch["cwd"], "cli_home": launch["cli_home"]}
    original = (cli.base_dir / identity / "transcript.jsonl").read_bytes()
    target = export(tmp_path, identity, **kwargs)
    assert "Canonical CLI answer" in target.read_text()
    archive_conversation(tmp_path, identity, archived=True, **kwargs)
    assert not catalog(tmp_path, **kwargs)
    archive_conversation(tmp_path, identity, archived=False, **kwargs)
    store = SharedConversationStore(tmp_path, launch, identity)
    try:
        assert store.saved["messages"]
        with pytest.raises(ValueError, match="Close the conversation"):
            archive_conversation(tmp_path, identity, archived=True, **kwargs)
    finally:
        store.close()
    assert (cli.base_dir / identity / "transcript.jsonl").read_bytes() == original


def test_shared_uncertain_marker_or_ahead_journal_refuses_without_rewriting(shared, tmp_path):
    from amplifier_tui.conversations import atomic_json

    launch, cli, identity, messages = shared
    store = SharedConversationStore(tmp_path, launch, identity)
    path = store.path / "checkpoint.json"
    store.close()
    marker = json.loads(path.read_text())
    atomic_json(path, {**marker, "status": "uncertain"})
    original = (cli.base_dir / identity / "transcript.jsonl").read_bytes()
    with pytest.raises(ValueError, match="uncertain/incomplete"):
        SharedConversationStore(tmp_path, launch, identity)
    assert (cli.base_dir / identity / "transcript.jsonl").read_bytes() == original
    atomic_json(path, {**marker, "sequence": 0})
    cli.save(identity, messages + [{"role": "user", "content": "Later CLI request"}], {})
    with pytest.raises(ValueError, match="incomplete work"):
        SharedConversationStore(tmp_path, launch, identity)


def test_shared_symlink_and_corrupt_metadata_do_not_overwrite_sources(shared, tmp_path):
    launch, cli, identity, messages = shared
    store = SharedConversationStore(tmp_path, launch, identity)
    try:
        metadata = cli.base_dir / identity / "metadata.json"
        metadata.write_text("{broken")
        before = (cli.base_dir / identity / "transcript.jsonl").read_bytes()
        with pytest.raises(ValueError):
            store.checkpoint(messages, len(store.restored_events), None, True)
        assert (cli.base_dir / identity / "transcript.jsonl").read_bytes() == before
    finally:
        store.close()
    # Foundation correctly refuses to overwrite corruption without a backup.
    # Restore the synthetic metadata explicitly before the independent link test.
    metadata.write_text(json.dumps({"working_dir": launch["cwd"]}))
    cli.save(identity, messages, {"working_dir": launch["cwd"]})
    (store.path / "draft.json").unlink()
    external = tmp_path / "untouched"
    external.write_text('{"text":"external"}')
    (store.path / "draft.json").symlink_to(external)
    with pytest.raises(ValueError, match="symlink"):
        SharedConversationStore(tmp_path, launch, identity)
    assert external.read_text() == '{"text":"external"}'


async def test_new_shared_branch_accepts_explicit_public_context(shared, prepared, tmp_path):
    from amplifier_tui.conversations import atomic_json
    from amplifier_tui.recovery import context_transfer

    launch, cli, identity, messages = shared
    store = SharedConversationStore(tmp_path, launch)
    atomic_json(store.path / "imported-context.json", context_transfer(messages, identity))
    host = SessionHost(store)
    try:
        await host.open(*prepared, tmp_path)
        assert (
            portable_history(await host.session.coordinator.get("context").get_messages())
            == messages
        )
        assert not host.session.coordinator.get("providers")["fixture"].calls
    finally:
        await host.close()
    assert portable_history(cli.load(store.identity)[0]) == messages


def test_read_only_discovery_does_not_bootstrap_cli_keys(shared, tmp_path):
    import os
    import subprocess
    import sys

    launch, _, identity, _ = shared
    code = """
import builtins, sys
original = builtins.__import__
def guarded(name, *args, **kwargs):
    assert not name.startswith("amplifier_app_cli"), "Read-only discovery imported CLI bootstrap"
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from amplifier_tui.launcher import arguments
arguments(["--state-dir", sys.argv[1], "--list-sessions"])
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path)],
        cwd=launch["cwd"],
        env={**os.environ, "AMPLIFIER_HOME": launch["cli_home"]},
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert identity in result.stdout


@pytest.mark.parametrize(
    "content",
    [
        "plain user text",
        "",
        None,
        '<system-reminder source="fixture">injected</system-reminder>',
        "<system-reminders><system-reminder>injected</system-reminder></system-reminders>",
        "<system-reminder>one</system-reminder><system-reminder>two</system-reminder>",
        "<system-reminders>injected</system-reminders> and actual text",
        "<system-reminder>incomplete",
        [{"type": "text", "text": "<system-reminder>injected</system-reminder>"}],
        [{"type": "text", "text": "   "}],
        [{"type": "image", "text": "<system-reminder>not a text envelope</system-reminder>"}],
    ],
)
def test_display_filter_matches_pinned_cli_without_changing_canonical_content(content):
    import copy

    from amplifier_app_cli.ui.message_renderer import is_displayable_session_message

    from amplifier_tui.cli_compat import session_message_visible

    for role in ("user", "assistant", "tool", "system"):
        for metadata in ({}, {"ephemeral": True, "persisted": True}, {"ephemeral": True}):
            message = {"role": role, "content": content, "metadata": metadata}
            before = copy.deepcopy(message)
            assert session_message_visible(message) == is_displayable_session_message(message)
            assert message == before


async def test_shared_graceful_stop_is_resumable_without_tool_replay(shared, prepared, tmp_path):
    import asyncio

    launch, cli, identity, _ = shared
    host = SessionHost(SharedConversationStore(tmp_path, launch, identity))
    try:
        await host.open(*prepared, tmp_path)
        tool = host.session.coordinator.get("tools")["fixture_probe"]
        tool.config["delay"] = 0.2
        assert host.submit("Stop shared fixture work")[0]
        async with asyncio.timeout(5):
            while not tool.calls:
                await asyncio.sleep(0.01)
        host.stop()
        await asyncio.wait_for(host.task, 5)
        assert host.store.saved["status"] == "ready"
    finally:
        await host.close()
    assert any(m.get("role") == "tool" for m in cli.load(identity)[0])
    resumed = SessionHost(SharedConversationStore(tmp_path, launch, identity))
    try:
        await resumed.open(*prepared, tmp_path)
        assert not resumed.session.coordinator.get("providers")["fixture"].calls
        assert resumed.session.coordinator.get("tools")["fixture_probe"].calls == 0
    finally:
        await resumed.close()


@pytest.mark.parametrize("loop", ["loop-streaming", "loop-basic"])
@pytest.mark.parametrize("context", ["context-simple", "context-persistent"])
async def test_shared_independent_context_preserves_private_history(
    shared, prepared, tmp_path, loop, context
):
    import copy
    from dataclasses import replace
    from pathlib import Path

    pytest.importorskip("amplifier_module_" + loop.replace("-", "_"))
    pytest.importorskip("amplifier_module_" + context.replace("-", "_"))
    launch, cli, identity, messages = shared
    value, report = prepared
    plan = copy.deepcopy(value.mount_plan)
    workspace = Path(__file__).resolve().parents[2]
    private = tmp_path / "owned-module-context.jsonl"
    private_message = {"role": "system", "content": "Synthetic module-owned instruction"}
    for slot, name in (("orchestrator", loop), ("context", context)):
        plan["session"][slot] = {
            "module": name,
            "source": str(workspace / f"amplifier-module-{name}"),
            "config": {},
        }
    if context == "context-persistent":
        private.write_text("".join(json.dumps(m) + "\n" for m in [private_message, *messages]))
        plan["session"]["context"]["config"] = {
            "transcript_path": str(private),
            "memory_files": [],
        }
    value = replace(value, mount_plan=plan)
    for turn in range(2):
        host = SessionHost(SharedConversationStore(tmp_path, launch, identity))
        try:
            await host.open(value, report, tmp_path)
            assert not host.session.coordinator.get("providers")["fixture"].calls
            assert host.session.coordinator.get("tools")["fixture_probe"].calls == 0
            restored = await host.session.coordinator.get("context").get_messages()
            if context == "context-persistent":
                assert private_message in restored
            assert host.submit(f"Independent shared turn {turn}")[0]
            await host.task
            assert host.outcome == "success"
            assert host.store.saved["status"] == "ready"
        finally:
            await host.close()
        public, _ = cli.load(identity)
        assert all(m["role"] not in ("system", "developer") for m in public)
        assert any(m.get("content") == f"Independent shared turn {turn}" for m in public)

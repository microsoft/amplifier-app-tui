"""Native history enters real runtime contexts without a private display checkpoint."""

import copy
import json
import os
from pathlib import Path

import pytest
from test_shared_sessions import shared as shared

from amplifier_tui.conversations import SharedConversationStore, portable_history
from amplifier_tui.host import SessionHost
from amplifier_tui.recovery import native_resume_messages


def native_call(identity="same", **extra):
    return {
        "role": "assistant",
        "tool_calls": [{"id": identity, "tool": "fixture_probe", "arguments": {}}],
        **extra,
    }


def native_result(identity="same", **extra):
    return {"role": "tool", "tool_call_id": identity, "content": "done", **extra}


@pytest.mark.parametrize(
    "instruction",
    [
        {"role": "system", "content": "Module instruction"},
        {"role": "developer", "content": "Module instruction"},
        {"role": "user", "content": '<system-reminder source="fixture">Reminder</system-reminder>'},
        {"role": "user", "content": "Injected", "metadata": {"ephemeral": True}},
    ],
)
def test_native_pairing_ignores_instructions_not_tool_outcomes(instruction):
    messages = [native_call(), instruction, native_result()]
    original = copy.deepcopy(messages)
    assert native_resume_messages(messages) is messages
    assert messages == original  # No synthetic closing assistant or repair.


@pytest.mark.parametrize("metadata", [None, "opaque", 7, [], {"ephemeral": True}])
def test_native_pairing_preserves_optional_json_metadata(metadata):
    messages = [native_call(metadata=metadata), native_result(metadata=metadata)]
    assert native_resume_messages(messages) is messages
    with pytest.raises(ValueError, match="Unfinished tool calls"):
        native_resume_messages(messages[:1])


def test_native_pairing_reused_ids_are_scoped_to_completed_calls():
    messages = [native_call(), native_result(), native_call(), native_result()]
    assert native_resume_messages(messages) is messages
    with pytest.raises(ValueError, match="Unfinished tool calls"):
        native_resume_messages([native_call(), {"role": "user", "content": "Next"}, *messages])
    with pytest.raises(ValueError, match="duplicate pending"):
        native_resume_messages(
            [{"role": "assistant", "tool_calls": native_call()["tool_calls"] * 2}]
        )
    with pytest.raises(ValueError, match="Unpaired tool result"):
        native_resume_messages([native_call(), native_result(), native_result()])


def test_native_pairing_has_no_public_import_size_or_message_caps():
    messages = [{"role": "assistant", "content": "x" * (8 * 1024 * 1024)}]
    messages += [{"role": "user", "content": "Earlier request"} for _ in range(10001)]
    assert native_resume_messages(messages) is messages


def test_native_projection_full_payload_budget_includes_notices(shared, tmp_path):
    from amplifier_foundation.session import SessionHistoryStore

    launch, cli, identity, _ = shared
    native = SessionHistoryStore(cli.base_dir / identity)
    messages = [
        {"role": "assistant", "content": f"Item {index:04d}: " + "\\" * 65500}
        for index in range(130)
    ]
    native.save_messages(messages)
    before = native.transcript_path.read_bytes()
    store = SharedConversationStore(tmp_path, launch, identity)
    try:
        items = store.projection()
        assert len(json.dumps(items, ensure_ascii=False).encode()) <= 8 * 1024 * 1024
        assert any(item["id"] == "history:window" for item in items)
        answers = [item for item in items if item["kind"] == "assistant"]
        assert answers and answers[-1]["text"] == messages[-1]["content"]
        assert len(answers) < 100  # Escaping reaches the byte bound before the item bound.
        first = store.history_page()
        second = store.history_page(first["next_offset"])
        third = store.history_page(second["next_offset"])
        assert second["previous_offset"] == 0
        assert third["previous_offset"] == second["offset"]
        assert store.history_page(third["previous_offset"]) == second
        assert third["next_offset"] is None
        assert sum(len(page["items"]) for page in (first, second, third)) == len(messages)
        assert store.canonical_messages == messages
        assert native.transcript_path.read_bytes() == before
    finally:
        store.close()


def test_resume_history_pages_are_complete_bounded_and_stable(shared, tmp_path):
    from amplifier_foundation.session import SessionHistoryStore

    from amplifier_tui.events import Event

    launch, cli, identity, _ = shared
    native = SessionHistoryStore(cli.base_dir / identity)
    messages = [{"role": "assistant", "content": f"History marker {i:03d}"} for i in range(253)]
    native.save_messages(messages)
    before = (native.transcript_path.read_bytes(), native.transcript_path.stat().st_mtime_ns)
    store = SharedConversationStore(tmp_path, launch, identity)
    try:
        initial = store.projection()
        answers = [row for row in initial if row["kind"] == "assistant"]
        assert len(answers) == 100
        assert answers[0]["text"] == "History marker 153"
        assert answers[-1]["text"] == "History marker 252"
        assert "latest 100 of 253" in initial[0]["text"]
        assert "Earlier history" in initial[0]["text"]
        assert json.loads(initial[0]["detail"])["next_offset"] == 100
        pages, offset = [], 0
        while True:
            page = store.history_page(offset)
            assert len(page["items"]) <= 100
            assert page["end"] - page["start"] + 1 == len(page["items"])
            pages.append(page)
            if page["next_offset"] is None:
                break
            offset = page["next_offset"]
        all_items = [item for page in reversed(pages) for item in page["items"]]
        assert [row["text"] for row in all_items] == [m["content"] for m in messages]
        assert len({row["id"] for row in all_items}) == 253
        store.record(Event(identity, 900, "new", "text.final", "new", {"text": "Live update"}))
        assert store.history_page(100) == pages[1]  # Live work cannot shift saved offsets.
        for invalid in (-1, True, "100", 254):
            with pytest.raises(ValueError, match="[Hh]istory page"):
                store.history_page(invalid)
        assert store.canonical_messages == messages
        assert (
            native.transcript_path.read_bytes(),
            native.transcript_path.stat().st_mtime_ns,
        ) == before
        assert not (store.path / "events.jsonl").exists()
    finally:
        store.close()


async def test_history_page_protocol_is_scoped_and_read_only(shared, tmp_path):
    from amplifier_tui.navigation import WorkspaceBridge

    launch, _, identity, _ = shared
    store = SharedConversationStore(tmp_path, launch, identity)
    host = SessionHost(store)
    frames = []
    bridge = WorkspaceBridge(
        host,
        lambda _: None,
        frames.append,
        False,
        Path(launch["cwd"]),
        state_dir=tmp_path,
        open_launch=lambda *_: None,
    )
    try:
        request = {"op": "history_page", "session_id": identity, "request_id": "page", "offset": 0}
        assert bridge.command(request)[0]
        await bridge.lookup_task
        assert frames[-1] == {
            "type": "history_page",
            "session_id": identity,
            "request_id": "page",
            **store.history_page(),
        }
        assert not host.session and not host.task  # No module or execution mounted.
        assert not bridge.command({**request, "session_id": "different"})[0]
        for invalid in (-1, True, "100"):
            assert not bridge.command({**request, "offset": invalid})[0]
        assert bridge.command({**request, "offset": 999999})[0]
        await bridge.lookup_task
        assert "outside" in frames[-1]["error"]
    finally:
        store.close()


async def test_native_runtime_restores_all_json_fields(shared, prepared, tmp_path):
    from amplifier_foundation.session import SessionHistoryStore

    launch, cli, identity, messages = shared
    fields = {
        "content_blocks": [{"type": "text", "text": "Native continuation"}],
        "thinking_block": {"type": "thinking", "thinking": "Synthetic retained field"},
        "provider_state": {"continuation": "fixture"},
        "nullable": None,
    }
    messages[-1].update(fields)
    native = SessionHistoryStore(cli.base_dir / identity)
    native.save_messages(messages)
    host = SessionHost(SharedConversationStore(tmp_path, launch, identity))
    try:
        await host.open(*prepared, tmp_path)
        restored = await host.session.coordinator.get("context").get_messages()
        assert portable_history(restored) == messages
        assert not host.session.coordinator.get("providers")["fixture"].calls
        assert all(native.load_messages()[-1][key] == value for key, value in fields.items())
    finally:
        await host.close()


@pytest.mark.parametrize("recover_backup", [False, True])
async def test_native_open_and_close_do_not_rewrite_primary_or_backup(
    shared, prepared, tmp_path, recover_backup
):
    launch, cli, identity, messages = shared
    root = cli.base_dir / identity
    paths = []
    for name in ("metadata.json", "transcript.jsonl"):
        primary = root / name
        backup = primary.with_suffix(primary.suffix + ".backup")
        backup.write_bytes(primary.read_bytes())
        if recover_backup:
            primary.write_text("{incomplete")
        paths.extend((primary, backup))

    def snapshot():
        return {path.name: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths}

    before = snapshot()
    host = SessionHost(SharedConversationStore(tmp_path, launch, identity))
    try:
        await host.open(*prepared, tmp_path)
        context = host.session.coordinator.get("context")
        assert portable_history(await context.get_messages()) == messages
        assert not host.session.coordinator.get("providers")["fixture"].calls
        assert snapshot() == before
    finally:
        await host.close()
    assert snapshot() == before


async def test_native_runtime_refuses_lossy_context_readback(
    shared, prepared, tmp_path, monkeypatch
):
    from amplifier_foundation import sanitize_message
    from amplifier_foundation.session import SessionHistoryStore

    from amplifier_tui import composition

    launch, cli, identity, messages = shared
    native = SessionHistoryStore(cli.base_dir / identity)
    messages[-1]["content_blocks"] = [{"type": "text", "text": "Retain exactly"}]
    native.save_messages(messages)
    original = composition.create_owned_session
    providers = []

    async def lossy_context(*args, **kwargs):
        session = await original(*args, **kwargs)
        context = session.coordinator.get("context")
        set_messages = context.set_messages
        providers.append(session.coordinator.get("providers")["fixture"])

        async def drop_fields(values):
            await set_messages([sanitize_message(message) for message in values])

        monkeypatch.setattr(context, "set_messages", drop_fields)
        return session

    monkeypatch.setattr(composition, "create_owned_session", lossy_context)
    host = SessionHost(SharedConversationStore(tmp_path, launch, identity))
    before = native.transcript_path.read_bytes()
    try:
        with pytest.raises(RuntimeError, match="did not restore canonical history"):
            await host.open(*prepared, tmp_path)
        assert native.transcript_path.read_bytes() == before
        assert not providers[0].calls
    finally:
        await host.close()


@pytest.mark.parametrize("resume,empty", [(False, True), (True, False), (True, True)])
async def test_native_runtime_emits_correct_lifecycle(shared, prepared, tmp_path, resume, empty):
    from amplifier_foundation.session import SessionHistoryStore

    bundle, report = prepared
    bundle = copy.copy(bundle)
    bundle.mount_plan = copy.deepcopy(bundle.mount_plan)
    workspace = Path(
        os.environ.get("AMPLIFIER_TUI_SOURCE_ROOT", Path(__file__).resolve().parents[2])
    )
    log = tmp_path / "lifecycle.jsonl"
    bundle.mount_plan.setdefault("hooks", []).append(
        {
            "module": "hooks-logging",
            "source": (workspace / "amplifier-module-hooks-logging").as_uri(),
            "config": {"session_log_template": str(log)},
        }
    )
    launch, cli, identity, _ = shared
    if resume and empty:
        SessionHistoryStore(cli.base_dir / identity).save_messages([])
    store = SharedConversationStore(tmp_path, launch, identity if resume else None)
    host = SessionHost(store)
    try:
        await host.open(bundle, report, tmp_path)
        provider = host.session.coordinator.get("providers")["fixture"]
        assert not provider.calls
        # Core emits lifecycle on first execution, not on merely opening history.
        for text in ("Explicit first fixture turn", "Explicit second fixture turn"):
            assert host.submit(text)[0]
            assert await host.task == "completed"
        events = [json.loads(line) for line in log.read_text().splitlines()]
        events = [row for row in events if row["event"] in ("session:start", "session:resume")]
        assert [row["event"] for row in events] == ["session:resume" if resume else "session:start"]
        assert events[0]["session_id"] == host.session_id
        assert len(provider.calls) == 4
    finally:
        await host.close()


async def test_native_naming_counts_real_prior_turns(shared, prepared, tmp_path):
    from amplifier_foundation.session import SessionHistoryStore

    launch, cli, identity, messages = shared
    messages += [
        {"role": "user", "content": '<system-reminder source="fixture">Reminder</system-reminder>'},
        {"role": "user", "content": "Injected observation", "metadata": {"ephemeral": True}},
        {"role": "user", "content": "Second real request"},
        {"role": "assistant", "content": "Second answer"},
    ]
    native = SessionHistoryStore(cli.base_dir / identity)
    native.save_messages(messages)
    # The canonical messages, not a stale metadata counter or display journal,
    # determine the hook's prior-turn count.
    native.save_metadata({**native.load_metadata(), "turn_count": 999})
    bundle, report = prepared
    bundle = copy.copy(bundle)
    bundle.mount_plan = copy.deepcopy(bundle.mount_plan)
    workspace = Path(
        os.environ.get("AMPLIFIER_TUI_SOURCE_ROOT", Path(__file__).resolve().parents[2])
    )
    module = workspace / "amplifier-foundation/modules/hooks-session-naming"
    bundle.mount_plan.setdefault("hooks", []).append(
        {"module": "hooks-session-naming", "source": module.as_uri()}
    )
    host = SessionHost(SharedConversationStore(tmp_path, launch, identity))
    try:
        await host.open(bundle, report, tmp_path)
        assert host.naming_turns == 2
        metadata = json.loads((host.store.path / "naming/metadata.json").read_text())
        assert metadata["turn_count"] == 2
        assert not host.session.coordinator.get("providers")["fixture"].calls
    finally:
        await host.close()


async def test_native_restore_preserves_mounted_static_instructions(
    shared, prepared, tmp_path, monkeypatch
):
    from amplifier_tui import composition

    original = composition.create_owned_session
    instruction = {"role": "system", "content": "Synthetic mounted static instruction"}
    mounted = []

    async def static_context(*args, **kwargs):
        session = await original(*args, **kwargs)
        context = session.coordinator.get("context")
        await context.add_message(instruction)
        mounted.extend(copy.deepcopy(await context.get_messages()))
        return session

    monkeypatch.setattr(composition, "create_owned_session", static_context)
    launch, _, identity, messages = shared
    host = SessionHost(SharedConversationStore(tmp_path, launch, identity))
    try:
        await host.open(*prepared, tmp_path)
        restored = await host.session.coordinator.get("context").get_messages()
        assert portable_history(restored) == portable_history([*mounted, *messages])
        assert not any(m["role"] == "system" for m in host.store.canonical_messages)
    finally:
        await host.close()

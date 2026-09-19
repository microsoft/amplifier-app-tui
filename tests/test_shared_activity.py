"""On-demand shared activity through real Foundation, without execution or log copies."""

import json
from pathlib import Path

import pytest
from test_shared_sessions import shared as shared
from test_shared_usage import ci_logs, receipt

from amplifier_tui.cli_compat import read_session_activity
from amplifier_tui.conversations import SharedConversationStore
from amplifier_tui.events import Event
from amplifier_tui.host import SessionHost
from amplifier_tui.inspection import Inspection
from amplifier_tui.navigation import WorkspaceBridge


def capture(shared):
    launch, cli, identity, _ = shared
    messages = [
        {"role": "user", "content": "Inspect the fixture"},
        {"role": "assistant", "tool_calls": [{"id": "fixture-call", "tool": "read_file"}]},
        {"role": "tool", "tool_call_id": "fixture-call", "content": "Fixture result"},
    ]
    cli.save(identity, messages, cli.get_metadata(identity))
    path = ci_logs(
        cli,
        identity,
        [
            {
                "event": "tool:post",
                "session_id": identity,
                "data": {
                    "tool_call_id": "fixture-call",
                    "tool_name": "read_file",
                    "result": "Fixture result",
                },
            },
            receipt(identity, 0),
            receipt(identity, 1, purpose="session-naming"),
        ],
    )
    activity = read_session_activity(launch["cli_home"], launch["cwd"], identity, messages)
    return messages, path, activity


def test_shared_activity_groups_exact_turns_auxiliary_and_unassociated_separately(shared):
    messages, _, activity = capture(shared)
    root = Inspection.shared_activity_view(activity, messages)
    assert root["snapshot"] is True and not root["partial"]
    assert [row["label"] for row in root["rows"]] == [
        "Turn 1",
        "Unassociated observations",
        "Utility calls",
    ]
    turn = Inspection.shared_activity_view(activity, messages, root["rows"][0]["id"])
    assert len(turn["rows"]) == 1
    assert turn["rows"][0]["label"] == "tool:post · read_file"
    leaf = Inspection.shared_activity_view(activity, messages, turn["rows"][0]["id"])
    assert not leaf["rows"]
    assert "Saved message 3" in leaf["focus"]["preview"]
    assert "exact tool_call_id" in leaf["focus"]["preview"]
    assert "Fixture result" in leaf["focus"]["detail"]
    assert leaf["parent"] == turn["node"]
    assert leaf["breadcrumb"] == "Shared session history / Turn 1 / tool:post · read_file"
    unassociated = Inspection.shared_activity_view(activity, messages, root["rows"][1]["id"])
    assert "Unassociated observation" in unassociated["rows"][0]["preview"]
    assert "Usage · fixture/fixture-model" in unassociated["rows"][0]["preview"]
    assert "$0.250000" in unassociated["rows"][0]["preview"]


def test_shared_activity_does_not_project_provider_requests_media_or_private_reasoning(shared):
    launch, cli, identity, messages = shared
    ci_logs(
        cli,
        identity,
        [
            receipt(
                identity,
                0,
                request={"messages": [{"content": "private-request-marker"}]},
                raw={"thinking": "private-reasoning-marker"},
                response="provider-body-marker",
                input="provider-input-marker",
                result="provider-result-marker",
                images=["image-body-marker"],
            )
        ],
    )
    activity = read_session_activity(launch["cli_home"], launch["cwd"], identity, messages)
    group = Inspection.shared_activity_view(activity, messages)["rows"][0]["id"]
    view = Inspection.shared_activity_view(activity, messages, group)
    assert "private-request-marker" not in json.dumps(view)
    assert "private-reasoning-marker" not in json.dumps(view)
    assert "provider-body-marker" not in json.dumps(view)
    assert "provider-input-marker" not in json.dumps(view)
    assert "provider-result-marker" not in json.dumps(view)
    assert "image-body-marker" not in json.dumps(view)
    assert "omitted" in view["scope"]


def test_shared_activity_pages_are_bounded_without_losing_event_identity(shared):
    launch, cli, identity, messages = shared
    ci_logs(cli, identity, [receipt(identity, index) for index in range(205)])
    activity = read_session_activity(launch["cli_home"], launch["cwd"], identity, messages)
    group = Inspection.shared_activity_view(activity, messages)["rows"][0]["id"]
    rows, offset = [], 0
    while True:
        page = Inspection.shared_activity_view(activity, messages, group, offset)
        assert len(page["rows"]) <= 100
        assert len(json.dumps(page).encode()) < 1024 * 1024
        assert not page["partial"]
        rows += page["rows"]
        if page["next_offset"] is None:
            break
        offset = page["next_offset"]
    assert len(rows) == len({row["id"] for row in rows}) == 205


def test_missing_or_stale_shared_activity_stays_inspectable_and_disclosed(shared):
    launch, _, identity, messages = shared
    activity = read_session_activity(launch["cli_home"], launch["cwd"], identity, messages)
    root = Inspection.shared_activity_view(activity, messages)
    assert root["partial"] and root["snapshot"] and not root["rows"]
    assert "conversation history is unaffected" in root["focus"]["preview"]
    missing = Inspection.shared_activity_view(activity, messages, "shared:history:event:999")
    assert missing["partial"] and missing["focus"] is None
    assert missing["parent"] == "shared:history"


async def bridge_for(shared, state):
    launch, _, identity, _ = shared
    store = SharedConversationStore(state, launch, identity)
    emitted = []

    async def cannot_execute(*_):
        pytest.fail("Activity inspection must not initialize a runtime")

    bridge = WorkspaceBridge(
        SessionHost(store),
        cannot_execute,
        emitted.append,
        False,
        Path(launch["cwd"]),
        state_dir=state,
        open_launch=cannot_execute,
    )
    return bridge, emitted


async def inspect(bridge, emitted, node=None, offset=0):
    request = {
        "op": "inspect",
        "category": "activity_tree",
        "child": node,
        "offset": offset,
        "session_id": bridge.host.session_id,
        "request_id": f"request-{len(emitted)}",
    }
    accepted, _ = bridge.command(request)
    assert accepted
    await bridge.lookup_task
    return emitted[-1]


async def test_activity_source_is_lazy_cached_in_memory_and_explicitly_refreshed(
    shared, tmp_path, monkeypatch
):
    import amplifier_tui.cli_compat as compat

    messages, path, _ = capture(shared)
    bridge, emitted = await bridge_for(shared, tmp_path)
    store = bridge.host.store
    journal = store.path / "events.jsonl"
    original = journal.read_bytes()
    source = path.read_bytes()
    calls, read = [], compat.read_session_activity

    def observed_read(*args, **kwargs):
        calls.append(args[2])
        return read(*args, **kwargs)

    monkeypatch.setattr(compat, "read_session_activity", observed_read)
    try:
        root = await inspect(bridge, emitted)
        assert root["rows"][0]["id"] == "shared:history" and not calls
        shared_root = await inspect(bridge, emitted, "shared:history")
        group = shared_root["rows"][0]["id"]
        assert shared_root["snapshot"] and len(calls) == 1
        detail = await inspect(bridge, emitted, group)
        await inspect(bridge, emitted, detail["rows"][0]["id"])
        assert len(calls) == 1
        assert journal.read_bytes() == original and path.read_bytes() == source
        assert store.canonical_messages == messages
        assert bridge.host.session is None and bridge.host.task is None
        # Reopen through the ordinary root explicitly refreshes the snapshot.
        await inspect(bridge, emitted)
        await inspect(bridge, emitted, "shared:history")
        assert len(calls) == 2
        assert journal.read_bytes() == original
    finally:
        store.close()


async def test_root_entry_does_not_drop_or_duplicate_native_activity_page_rows(shared, tmp_path):
    bridge, emitted = await bridge_for(shared, tmp_path)
    store = bridge.host.store
    try:
        start = len(store.restored_events)
        for index in range(103):
            store.record(
                Event(
                    store.identity,
                    start + index + 1,
                    "fixture-turn",
                    "tool.updated",
                    f"tool-{index}",
                    {"name": "fixture_tool", "status": "succeeded"},
                )
            )
        store.journal.flush()
        original = store.path.joinpath("events.jsonl").read_bytes()
        first = await inspect(bridge, emitted)
        assert len(first["rows"]) == 100 and first["next_offset"] == 99
        second = await inspect(bridge, emitted, offset=first["next_offset"])
        identities = [row["id"] for row in first["rows"][1:] + second["rows"]]
        assert len(identities) == len(set(identities))
        assert set(f"tool-{index}" for index in range(103)) <= set(identities)
        assert store.path.joinpath("events.jsonl").read_bytes() == original
    finally:
        store.close()


async def test_missing_shared_capture_does_not_hide_native_activity(shared, tmp_path):
    bridge, emitted = await bridge_for(shared, tmp_path)
    try:
        root = await inspect(bridge, emitted)
        assert root["rows"][0]["id"] == "shared:history"
        missing = await inspect(bridge, emitted, "shared:history")
        assert missing["partial"] and missing["snapshot"]
        restored = await inspect(bridge, emitted)
        assert restored["rows"] == root["rows"]
        assert bridge.host.session is None
    finally:
        bridge.host.store.close()


@pytest.mark.parametrize("damage", ["huge-duration", "surrogate", "huge-event"])
def test_hostile_optional_activity_stays_bounded_and_openable(shared, damage):
    launch, cli, identity, messages = shared
    path = ci_logs(cli, identity, [receipt(identity, 0)])
    event = json.loads(path.read_text())
    if damage == "huge-duration":
        event["data"]["duration_ms"] = 10**500
    elif damage == "surrogate":
        event["data"]["error"] = "\ud800"
    else:
        event["event"] = "large-name" * 120000
    path.write_text(json.dumps(event) + "\n")
    activity = read_session_activity(launch["cli_home"], launch["cwd"], identity, messages)
    group = Inspection.shared_activity_view(activity, messages)["rows"][0]["id"]
    page = Inspection.shared_activity_view(activity, messages, group)
    assert page["rows"] and page["rows"][0]["partial"]
    leaf = Inspection.shared_activity_view(activity, messages, page["rows"][0]["id"])
    assert len(json.dumps(leaf, ensure_ascii=False).encode("utf-8")) < 1024 * 1024
    assert len(leaf["focus"]["label"]) <= 282
    assert "snapshot" in leaf


async def test_optional_activity_projection_failure_returns_a_safe_view(
    shared, tmp_path, monkeypatch
):
    import amplifier_tui.cli_compat as compat

    bridge, emitted = await bridge_for(shared, tmp_path)

    def unreadable(*_):
        raise ValueError("Private failure details must not be displayed")

    monkeypatch.setattr(compat, "read_session_activity", unreadable)
    try:
        value = await inspect(bridge, emitted, "shared:history")
        assert value["partial"] and value["snapshot"]
        assert "could not be projected" in value["scope"]
        assert "Private failure details" not in json.dumps(value)
        assert bridge.shared_activity_snapshot is None
    finally:
        bridge.host.store.close()


def test_activity_keeps_valid_prefix_when_the_optional_reader_fails_later(shared, monkeypatch):
    from amplifier_foundation.session import SessionHistoryStore

    launch, cli, identity, messages = shared
    ci_logs(cli, identity, [receipt(identity, 0)])
    original = SessionHistoryStore.iter_events

    def fail_after_real_records(self, **limits):
        yield from original(self, **limits)
        raise RecursionError("Injected optional decoder failure after a valid prefix")

    monkeypatch.setattr(SessionHistoryStore, "iter_events", fail_after_real_records)
    activity = read_session_activity(launch["cli_home"], launch["cwd"], identity, messages)
    assert activity["partial"] and len(activity["events"]) == 1

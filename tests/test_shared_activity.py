"""Ordinary Activity uses native canonical/history/live data, with no import workflow."""

import asyncio
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
    events = SharedConversationStore.observations(messages, identity)
    return messages, path, activity, events


def test_ordinary_activity_shows_canonical_tool_with_exact_ci_details(shared):
    messages, _, activity, events = capture(shared)
    root = Inspection.native_activity(events, activity, messages)
    assert root["snapshot"] is True and not root["partial"]
    assert [row["label"] for row in root["rows"]] == [
        "read_file",
        "Unassociated observations",
        "Utility calls",
    ]
    tool = root["rows"][0]
    assert tool["children"] == 1
    detail = Inspection.native_activity(events, activity, messages, tool["id"])
    assert detail["focus"]["label"] == "read_file"
    assert detail["rows"][0]["label"] == "tool:post · read_file"
    leaf = Inspection.native_activity(events, activity, messages, detail["rows"][0]["id"])
    assert not leaf["rows"]
    assert "Saved message 3" in leaf["focus"]["preview"]
    assert "exact tool_call_id" in leaf["focus"]["preview"]
    assert "Fixture result" in leaf["focus"]["detail"]
    assert leaf["parent"] == tool["id"]
    assert "Shared session history" not in json.dumps(root)
    unassociated = Inspection.native_activity(
        events, activity, messages, "observations:unassociated"
    )
    assert "Usage · fixture/fixture-model" in unassociated["rows"][0]["preview"]


def test_native_activity_does_not_project_provider_request_bodies(shared):
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
    view = Inspection.native_activity([], activity, messages, "observations:unassociated")
    for marker in (
        "private-request-marker",
        "private-reasoning-marker",
        "provider-body-marker",
        "provider-input-marker",
        "provider-result-marker",
        "image-body-marker",
    ):
        assert marker not in json.dumps(view)
    assert "omitted" in view["scope"]


def test_large_history_keeps_current_live_work_in_bounded_activity_tail():
    def observations():
        for sequence in range(22000):
            yield Event("synthetic", sequence, "old", "text.final", str(sequence), {})
        yield Event(
            "synthetic",
            22000,
            "now",
            "tool.updated",
            "current-call",
            {"name": "read_file", "status": "running", "tool_call_id": "current-call"},
        )

    view = Inspection.native_activity(
        observations(), {"events": [], "associations": [], "partial": False}, [], active=True
    )
    assert view["partial"] and not view["snapshot"]
    assert [row["id"] for row in view["rows"]] == ["current-call"]
    assert "latest 20,000" in view["scope"]


def test_large_tool_history_keeps_latest_identities_without_capping_source():
    events = [
        Event("synthetic", index, "turn", "tool.updated", f"call-{index}", {"name": "read_file"})
        for index in range(11000)
    ]
    activity = {"events": [], "associations": [], "partial": False}
    first = Inspection.native_activity(events, activity, [])
    last = Inspection.native_activity(events, activity, [], offset=9900)
    assert first["partial"] and last["partial"]
    assert first["rows"][0]["id"] == "call-1000"
    assert last["rows"][-1]["id"] == "call-10999"
    assert last["next_offset"] is None
    assert len(events) == 11000


def test_native_activity_pages_are_bounded_without_losing_receipt_identity(shared):
    launch, cli, identity, messages = shared
    ci_logs(cli, identity, [receipt(identity, index) for index in range(205)])
    activity = read_session_activity(launch["cli_home"], launch["cwd"], identity, messages)
    rows, offset = [], 0
    while True:
        page = Inspection.native_activity(
            [], activity, messages, "observations:unassociated", offset
        )
        assert len(page["rows"]) <= 100
        assert len(json.dumps(page).encode()) < 1024 * 1024
        assert not page["partial"]
        rows += page["rows"]
        if page["next_offset"] is None:
            break
        offset = page["next_offset"]
    assert len(rows) == len({row["id"] for row in rows}) == 205


def test_missing_optional_activity_keeps_canonical_tools_visible(shared):
    messages, path, _, events = capture(shared)
    path.unlink()
    launch, _, identity, _ = shared
    activity = read_session_activity(launch["cli_home"], launch["cwd"], identity, messages)
    root = Inspection.native_activity(events, activity, messages)
    assert root["partial"] and root["snapshot"]
    assert [row["label"] for row in root["rows"]] == ["read_file"]
    missing = Inspection.native_activity(events, activity, messages, "observation:999")
    assert missing["partial"] and missing["focus"] is None and missing["parent"] is None


def test_exact_parallel_tool_association_does_not_join_neighboring_calls(shared):
    launch, cli, identity, _ = shared
    messages = [
        {"role": "user", "content": "Inspect two fixtures"},
        {
            "role": "assistant",
            "tool_calls": [{"id": "first", "tool": "read_file"}, {"id": "second", "tool": "grep"}],
        },
    ]
    ci_logs(
        cli,
        identity,
        [
            {
                "event": "tool:pre",
                "session_id": identity,
                "data": {"tool_call_id": "second", "tool_name": "grep"},
            }
        ],
    )
    activity = read_session_activity(launch["cli_home"], launch["cwd"], identity, messages)
    events = SharedConversationStore.observations(messages, identity)
    root = Inspection.native_activity(events, activity, messages)
    assert [(row["label"], row["children"]) for row in root["rows"]] == [
        ("read_file", 0),
        ("grep", 1),
    ]


def test_reused_tool_ids_never_attach_ci_to_a_guessed_turn(shared):
    launch, cli, identity, _ = shared
    messages = [
        {"role": "user", "content": "First fixture"},
        {"role": "assistant", "tool_calls": [{"id": "reused", "tool": "read_file"}]},
        {"role": "tool", "tool_call_id": "reused", "content": "First result"},
        {"role": "user", "content": "Second fixture"},
        {"role": "assistant", "tool_calls": [{"id": "reused", "tool": "read_file"}]},
        {"role": "tool", "tool_call_id": "reused", "content": "Second result"},
    ]
    ci_logs(
        cli,
        identity,
        [
            {
                "event": "tool:post",
                "session_id": identity,
                "data": {"tool_call_id": "reused", "tool_name": "read_file"},
            }
        ],
    )
    activity = read_session_activity(launch["cli_home"], launch["cwd"], identity, messages)
    events = SharedConversationStore.observations(messages, identity)
    root = Inspection.native_activity(events, activity, messages)
    tools = [row for row in root["rows"] if row["label"] == "read_file"]
    assert len(tools) == 2 and tools[0]["id"] != tools[1]["id"]
    assert all(row["children"] == 0 for row in tools)
    assert any(row["label"] == "Unassociated observations" for row in root["rows"])


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


async def inspect(bridge, emitted, node=None, offset=0, *, refresh=False):
    request = {
        "op": "inspect",
        "category": "activity_tree",
        "child": node,
        "offset": offset,
        "session_id": bridge.host.session_id,
        "request_id": f"request-{len(emitted)}",
        "refresh_history": refresh,
    }
    accepted, _ = bridge.command(request)
    assert accepted
    await bridge.lookup_task
    return emitted[-1]


async def test_ordinary_activity_reads_native_history_without_journal_or_extra_chooser(
    shared, tmp_path, monkeypatch
):
    import amplifier_tui.cli_compat as compat

    messages, path, _, _ = capture(shared)
    bridge, emitted = await bridge_for(shared, tmp_path)
    store = bridge.host.store
    before = {file: file.read_bytes() for file in store.canonical_path.rglob("*") if file.is_file()}
    calls, read = [], compat.read_session_activity

    def observed_read(*args, **kwargs):
        calls.append(args[2])
        return read(*args, **kwargs)

    monkeypatch.setattr(compat, "read_session_activity", observed_read)
    try:
        root = await inspect(bridge, emitted, refresh=True)
        assert root["rows"][0]["label"] == "read_file" and len(calls) == 1
        # Calls already restored from these exact CI receipts are not projected
        # a second time as unassociated or utility observations.
        assert not {"observations:unassociated", "observations:utility"}.intersection(
            row["id"] for row in root["rows"]
        )
        assert "Shared session history" not in json.dumps(root)
        assert not (store.path / "events.jsonl").exists()
        tool = root["rows"][0]
        detail = await inspect(bridge, emitted, tool["id"])
        await inspect(bridge, emitted, detail["rows"][0]["id"])
        assert len(calls) == 1
        assert store.canonical_messages == messages
        assert bridge.host.session is None and bridge.host.task is None
        await inspect(bridge, emitted, refresh=True)
        assert len(calls) == 2
        assert {
            file: file.read_bytes() for file in store.canonical_path.rglob("*") if file.is_file()
        } == before
    finally:
        store.close()


async def test_live_activity_refreshes_from_memory_without_polling_capture(
    shared, tmp_path, monkeypatch
):
    import amplifier_tui.cli_compat as compat

    capture(shared)
    bridge, emitted = await bridge_for(shared, tmp_path)
    store = bridge.host.store
    release = asyncio.Event()
    bridge.host.task = asyncio.create_task(release.wait())
    calls, read = [], compat.read_session_activity

    def observed_read(*args, **kwargs):
        calls.append(args[2])
        return read(*args, **kwargs)

    monkeypatch.setattr(compat, "read_session_activity", observed_read)
    try:
        first = await inspect(bridge, emitted, refresh=True)
        assert not first["snapshot"]
        sequence = store.saved["sequence"] + 1
        store.record(
            Event(
                store.identity,
                sequence,
                "live",
                "tool.updated",
                "live-tool",
                {"name": "fixture_tool", "status": "running", "tool_call_id": "live-call"},
            )
        )
        second = await inspect(bridge, emitted)
        assert any(row["id"] == "live-tool" for row in second["rows"])
        assert len(calls) == 1
        release.set()
        await bridge.host.task
        final = await inspect(bridge, emitted)
        assert final["snapshot"] and len(calls) == 1
    finally:
        release.set()
        await bridge.host.task
        store.close()


async def test_native_activity_pages_do_not_drop_or_duplicate_live_rows(shared, tmp_path):
    bridge, emitted = await bridge_for(shared, tmp_path)
    store = bridge.host.store
    try:
        start = store.saved["sequence"]
        for index in range(203):
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
        rows, offset = [], 0
        while True:
            page = await inspect(bridge, emitted, offset=offset)
            rows += page["rows"]
            if page["next_offset"] is None:
                break
            offset = page["next_offset"]
        identities = [row["id"] for row in rows]
        assert len(identities) == len(set(identities))
        assert set(f"tool-{index}" for index in range(203)) <= set(identities)
        assert not (store.path / "events.jsonl").exists()
    finally:
        store.close()


@pytest.mark.parametrize("damage", ["huge-duration", "surrogate", "surrogate-event", "huge-event"])
def test_hostile_optional_activity_stays_bounded_and_openable(shared, damage):
    launch, cli, identity, messages = shared
    path = ci_logs(cli, identity, [receipt(identity, 0)])
    event = json.loads(path.read_text())
    if damage == "huge-duration":
        event["data"]["duration_ms"] = 10**500
    elif damage == "surrogate":
        event["data"]["error"] = "\ud800"
    elif damage == "surrogate-event":
        event["event"] = "\ud800"
    else:
        event["event"] = "large-name" * 120000
    path.write_text(json.dumps(event) + "\n")
    activity = read_session_activity(launch["cli_home"], launch["cwd"], identity, messages)
    page = Inspection.native_activity([], activity, messages, "observations:unassociated")
    assert page["rows"] and page["rows"][0]["partial"]
    leaf = Inspection.native_activity([], activity, messages, page["rows"][0]["id"])
    assert len(json.dumps(leaf, ensure_ascii=False).encode("utf-8")) < 1024 * 1024
    assert len(leaf["focus"]["label"]) <= 282


async def test_optional_projection_failure_keeps_native_activity_and_does_not_retry_in_timer(
    shared, tmp_path, monkeypatch
):
    import amplifier_tui.cli_compat as compat

    capture(shared)
    bridge, emitted = await bridge_for(shared, tmp_path)
    calls = []

    def unreadable(*_):
        calls.append(True)
        raise ValueError("Private failure details must not be displayed")

    monkeypatch.setattr(compat, "read_session_activity", unreadable)
    try:
        value = await inspect(bridge, emitted, refresh=True)
        assert value["partial"] and value["snapshot"]
        assert value["rows"][0]["label"] == "read_file"
        assert "could not be projected" in value["scope"]
        assert "Private failure details" not in json.dumps(value)
        await inspect(bridge, emitted)
        assert len(calls) == 1
        await inspect(bridge, emitted, refresh=True)
        assert len(calls) == 2
    finally:
        bridge.host.store.close()

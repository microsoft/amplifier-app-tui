"""Identified activity projection; actual loop/children, never timing attribution."""

import asyncio
import json
from types import MethodType

import pytest

from amplifier_tui.events import Event
from amplifier_tui.inspection import Inspection


async def test_activity_wrapper_preserves_instance_bound_execution_guard(host, monkeypatch):
    from amplifier_core import ToolResult

    tool = host.session.coordinator.get("tools")["fixture_probe"]
    guarded = []

    async def guard(self, arguments):
        assert self is tool
        guarded.append(arguments)
        return ToolResult(success=False, error={"message": "Controlled instance guard denial"})

    monkeypatch.setattr(tool, "execute", MethodType(guard, tool))
    host.children.register(host.session)
    assert host.submit("Exercise the guarded tool")[0]
    await host.task
    assert len(guarded) == 1
    calls = [r for r in host.inspection.rows.values() if r["kind"] == "tool.updated"]
    assert len(calls) == 1 and calls[0]["status"] == "failed"
    assert "Controlled instance guard denial" in str(calls[0])


async def test_actual_tool_task_correlates_parallel_spawned_children(host, monkeypatch):
    tool = host.session.coordinator.get("tools")["fixture_probe"]

    async def execute(arguments):
        results = await asyncio.gather(
            *(
                host.children.spawn("probe", f"Compute {n}", host.session, {"probe": {}})
                for n in range(2)
            )
        )
        return {"success": True, "output": str(len(results))}

    monkeypatch.setattr(tool, "execute", execute)
    host.children.register(host.session)
    assert host.submit("Delegate two controlled calculations")[0]
    await host.task
    roots = [
        r for r in host.inspection.rows.values() if r["kind"] == "tool.updated" and not r["child"]
    ]
    assert len(roots) == 1
    assert len(host.children.records) == 2
    assert {r.get("parent_item_id") for r in host.children.records.values()} == {roots[0]["id"]}
    tree = host.inspection.activity_tree(roots[0]["id"])
    assert len(tree["rows"]) == 2
    for child in tree["rows"]:
        calls = host.inspection.activity_tree(child["id"])["rows"]
        tools = [r for r in calls if r["event"].startswith("tool:")]
        assert len(tools) == 1 and tools[0]["status"] == "succeeded"


async def test_parallel_parent_calls_and_nested_children_never_cross_link(host, monkeypatch):
    from amplifier_core import ToolCall

    provider = host.session.coordinator.get("providers")["fixture"]
    complete = provider.complete

    async def two_calls(request, **kwargs):
        response = await complete(request, **kwargs)
        if response.tool_calls:
            response.tool_calls = [
                ToolCall(id=f"call-{n}", name="fixture_probe", arguments={"text": str(n)})
                for n in range(2)
            ]
        return response

    monkeypatch.setattr(provider, "complete", two_calls)
    register = host.children.register
    parents_started, release = set(), asyncio.Event()

    def register_nested(session):
        if (
            session.session_id != host.session_id
            and host.children.records[session.session_id]["depth"] == 1
        ):

            async def nested(arguments):
                result = await host.children.spawn(
                    "probe", "Nested calculation", session, {"probe": {}}
                )
                return {"success": True, "output": result["output"]}

            session.coordinator.get("tools")["fixture_probe"].execute = nested
        register(session)

    monkeypatch.setattr(host.children, "register", register_nested)

    async def spawn(arguments):
        parents_started.add(arguments["text"])
        if len(parents_started) == 2:
            release.set()
        await asyncio.wait_for(release.wait(), 5)
        result = await host.children.spawn("probe", arguments["text"], host.session, {"probe": {}})
        return {"success": True, "output": result["output"]}

    monkeypatch.setattr(host.session.coordinator.get("tools")["fixture_probe"], "execute", spawn)
    register(host.session)
    assert host.submit("Run two nested delegates")[0]
    await asyncio.wait_for(host.task, 15)
    assert len(host.children.records) == 4
    for child_id, row in host.children.records.items():
        if row["depth"] == 1:
            assert row["parent_item_id"] == f"{host.turn_id}:tool:call-{row['instruction']}"
        else:
            parent = host.inspection.rows[row["parent_item_id"]]
            assert parent["child"] == row["parent"]
            assert parent["parent"] == f"child:{row['parent']}"
        assert row["status"] == "completed", child_id
    from amplifier_tui.events import Transcript

    transcript = Transcript()
    while not host.events.empty():
        transcript.apply(host.events.get_nowait())
    assert not any(item.id.startswith("activity:") for item in transcript.items.values()), (
        "Nested progress must not create stray top-level tool cards"
    )


async def test_unobserved_spawn_does_not_guess_previous_tool(host):
    assert host.submit("Complete a tool first")[0]
    await host.task
    result = await host.children.spawn(
        "probe", "Explicit uncorrelated child", host.session, {"probe": {}}
    )
    assert host.children.records[result["session_id"]]["parent_item_id"] is None
    root = host.inspection.activity_tree()
    assert any("Originating call unavailable" in r["preview"] for r in root["rows"])


def test_activity_stable_order_recursive_status_unknown_parent_and_thinking():
    inspection = Inspection()
    sequence = 0

    def emit(identity, kind="tool.updated", **payload):
        nonlocal sequence
        sequence += 1
        inspection.observe(Event("session", sequence, "turn", kind, identity, payload))

    emit("a", name="delegate", status="running", arguments={"agent": "research"})
    emit("b", name="read_file", status="running")
    emit("child:c", name="Agent · research", child_id="c", parent_item_id="a", status="running")
    emit(
        "tool:c",
        "child.observed",
        name="bash",
        event="tool:pre",
        parent_item_id="child:c",
        child_id="c",
        status="running",
    )
    emit("b", name="read_file", status="succeeded")
    emit(
        "tool:c",
        "child.observed",
        name="bash",
        event="tool:post",
        parent_item_id="child:c",
        child_id="c",
        status="failed",
    )
    emit("a", name="delegate", status="succeeded")
    emit(
        "thought", "display.message", source="thinking", text="## Compare\n\n**Public** observation"
    )
    emit("orphan", name="Agent", child_id="unknown", parent_item_id="missing", status="unknown")
    root = inspection.activity_tree()
    assert [r["id"] for r in root["rows"]] == ["a", "b", "thought", "orphan"]
    assert "1 failed" in root["rows"][0]["summary"]
    assert root["rows"][2]["markdown"] and root["rows"][2]["thinking"]
    leaf = inspection.activity_tree("tool:c")
    assert leaf["breadcrumb"] == "delegate / Agent · research / bash"
    assert not leaf["rows"] and leaf["parent"] == "child:c"


def test_long_public_thinking_keeps_markdown_excerpt_with_explicit_limit():
    inspection = Inspection()
    inspection.observe(
        Event(
            "s",
            1,
            "t",
            "display.message",
            "thinking",
            {"source": "thinking", "text": "## Public heading\n\n" + "observed " * 4000},
        )
    )
    row = inspection.activity_tree()["rows"][0]
    assert row["thinking"] and row["markdown"] and row["partial"]
    assert row["preview"].startswith("## Public heading")
    assert "excerpt: 8192" in row["preview"]


def test_activity_detail_is_projected_before_serializing_a_large_tool_result():
    inspection = Inspection()
    inspection.observe(
        Event(
            "s",
            1,
            "t",
            "tool.updated",
            "tool",
            {
                "name": "large_tool",
                "status": "succeeded",
                "result": {"output": "x" * 100000},
            },
        )
    )
    row = inspection.activity_tree()["rows"][0]
    detail = json.loads(row["detail"])
    assert row["partial"]
    assert len(row["detail"].encode()) <= 16384
    assert detail["result"]["output"] == "x" * 4096


async def test_successful_child_completion_does_not_hide_failed_child_tool(host, monkeypatch):
    from amplifier_core import ToolResult

    tool = host.session.coordinator.get("tools")["fixture_probe"]

    async def fail(self, arguments):
        return ToolResult(success=False, error={"message": "Controlled failure"})

    monkeypatch.setattr(type(tool), "execute", fail)
    result = await host.children.spawn("probe", "Compute once", host.session, {"probe": {}})
    assert host.children.records[result["session_id"]]["status"] == "completed"
    events = []
    while not host.events.empty():
        events.append(host.events.get_nowait())
    warnings = [
        e
        for e in events
        if e.kind == "display.message" and e.payload.get("source") == "child activity"
    ]
    assert not warnings  # Warnings belong to the observed agent, not flat notices.
    summaries = [e.payload["child_progress"] for e in events if e.kind == "tool.progress"]
    assert summaries[-1][0]["warnings"]["failed"] == 1
    assert summaries[-1][0]["agent"] == "probe #1"
    assert summaries[-1][0]["activity"] == "succeeded"
    evidence = host.inspection.activity_tree(f"child:{result['session_id']}")["rows"]
    assert any(r["status"] == "failed" and "Controlled failure" in r["detail"] for r in evidence)


async def test_tool_progress_is_grouped_but_warnings_remain_in_conversation(host, monkeypatch):
    tool = host.session.coordinator.get("tools")["fixture_probe"]
    original = tool.execute

    async def progress(arguments):
        host.show_message("Step one", source="recipe")
        host.show_message("Step two", source="recipe")
        host.show_message("Keep this warning visible", source="recipe", level="warning")
        return await original(arguments)

    monkeypatch.setattr(tool, "execute", progress)
    host.children.register(host.session)
    assert host.submit("Observe progress")[0]
    await host.task
    rows = [r for r in host.inspection.rows.values() if r["kind"] == "activity.observed"]
    assert len(rows) == 1
    assert rows[0]["parent"] in host.inspection.rows
    assert rows[0]["public_text"] == "Step two"
    events = []
    while not host.events.empty():
        events.append(host.events.get_nowait())
    displayed = [e.payload["text"] for e in events if e.kind == "display.message"]
    assert "Step one" not in displayed and "Step two" not in displayed
    assert "Keep this warning visible" in displayed


@pytest.mark.parametrize("source", ["fixture-hook", "thinking", "usage"])
async def test_parallel_child_startup_and_tool_notices_keep_ownership(
    host, monkeypatch, tmp_path, source
):
    from dataclasses import asdict

    from amplifier_core import ToolResult

    from amplifier_tui import composition

    create = composition.create_owned_session
    proxies = {}

    async def create_with_notice(prepared, **kwargs):
        proxy = kwargs["display_system"]
        proxies[kwargs["session_id"]] = proxy
        # A module may announce itself during mounting, before proxy.session exists.
        proxy.show_message("Controlled startup notice", source=source)
        return await create(prepared, **kwargs)

    monkeypatch.setattr(composition, "create_owned_session", create_with_notice)
    register = host.children.register

    def register_notices(session):
        proxy = proxies[session.session_id]

        async def execute(arguments):
            proxy.show_message("Controlled tool progress", source=source)
            await asyncio.sleep(0)
            proxy.show_message("Controlled hook warning", source=source, level="warning")
            proxy.show_message("Controlled hook error", source=source, level="error")
            return ToolResult(success=True, output="Controlled result")

        session.coordinator.get("tools")["fixture_probe"].execute = execute
        register(session)

    monkeypatch.setattr(host.children, "register", register_notices)
    await asyncio.gather(
        *(
            host.children.spawn(
                "self",
                "Controlled child notices",
                host.session,
                {},
                sub_session_id=f"shared-prefix-child-{n}",
                session_metadata={"is_forked_skill_session": True, "skill_name": "fixture-review"},
            )
            for n in range(2)
        )
    )
    events = []
    while not host.events.empty():
        events.append(host.events.get_nowait())
    assert not [
        e
        for e in events
        if e.kind == "display.message" and "Controlled" in str(e.payload.get("text", ""))
    ]
    journal = tmp_path / "controlled-notices.jsonl"
    journal.write_text("".join(json.dumps(asdict(e)) + "\n" for e in events))
    for identity in proxies:
        notices = [
            e
            for e in events
            if e.payload.get("child_id") == identity and e.payload.get("event") == "display.message"
        ]
        assert len(notices) == 4
        assert notices[0].payload["parent_item_id"] == f"child:{identity}"
        tool_notices = notices[1:]
        assert len({e.payload["parent_item_id"] for e in tool_notices}) == 1
        parent = tool_notices[0].payload["parent_item_id"]
        assert host.inspection.rows[parent]["child"] == identity
        tree = host.inspection.activity_tree(parent)
        assert {r["preview"] for r in tree["rows"]} == {
            "Controlled tool progress",
            "Controlled hook warning",
            "Controlled hook error",
        }
        saved = Inspection.journal_activity(journal, parent)
        assert {r["preview"] for r in saved["rows"]} == {r["preview"] for r in tree["rows"]}
        assert {r["status"] for r in saved["rows"]} == {"observed", "warning", "error"}
        assert "1 warning" in saved["focus"]["summary"] and "1 error" in saved["focus"]["summary"]
        summary = host.children.summary(identity)
        assert summary["agent"].startswith("Skill · fixture-review #")
        assert summary["notices"] == {"warning": 1, "error": 1}
        assert summary["warnings"]["failed"] == 0  # Hook errors are not failed tool calls.

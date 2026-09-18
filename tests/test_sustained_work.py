"""Controlled sustained-work regressions; no captured user-session data."""

import asyncio
import json
import threading
from dataclasses import asdict

import pytest
from test_navigation import bridge_for

from amplifier_tui.events import Event
from amplifier_tui.inspection import Inspection


async def test_resumed_parent_summary_does_not_recount_previous_nested_work(host, monkeypatch):
    from decimal import Decimal

    from amplifier_core import ToolResult

    provider = host.session.coordinator.get("providers")["fixture"]
    complete = type(provider).complete

    async def metered(self, request, **kwargs):
        response = await complete(self, request, **kwargs)
        await self.coordinator.hooks.emit("llm:response", {"usage": {"cost_usd": "0.01"}})
        return response

    monkeypatch.setattr(type(provider), "complete", metered)
    original = host.children.register
    nested = True

    def register(session):
        if (
            session.session_id != host.session_id
            and host.children.records[session.session_id]["depth"] == 1
        ):

            async def execute(arguments):
                if nested:
                    await host.children.spawn(
                        "probe", "Nested controlled work", session, {"probe": {}}
                    )
                return ToolResult(success=True, output="Controlled parent complete")

            session.coordinator.get("tools")["fixture_probe"].execute = execute
        original(session)

    monkeypatch.setattr(host.children, "register", register)
    first = await host.children.spawn("probe", "First controlled task", host.session, {"probe": {}})
    identity = first["session_id"]
    before = host.children.summary(identity)
    assert before["calls"] == 4 and Decimal(before["cost_usd"]) == Decimal("0.04")
    nested = False
    await host.children.resume(identity, "Continue without delegation")
    after = host.children.summary(identity)
    assert after["calls"] == 2 and Decimal(after["cost_usd"]) == Decimal("0.02")
    assert host.call_usage.session["totals"]["cost_usd"] == Decimal("0.06")
    host.children.tool_outcomes["reused"] = "succeeded"
    assert host.children.observed_outcome("reused", "tool:pre", "running")[0] == "running"
    assert host.children.observed_outcome("reused", "tool:post", "unknown")[0] == "unknown"


async def test_resumed_nested_work_with_reused_provider_ids_keeps_distinct_calls(host, monkeypatch):
    from amplifier_core import ToolResult

    provider = host.session.coordinator.get("providers")["fixture"]
    complete = type(provider).complete

    async def reused(self, request, **kwargs):
        response = await complete(self, request, **kwargs)
        for call in response.tool_calls or []:
            call.id = "reused-call"
        return response

    monkeypatch.setattr(type(provider), "complete", reused)
    register = host.children.register

    def register_nested(session):
        row = host.children.records[session.session_id]
        # Optional dispatch/request counters are not a globally unique execution ID.
        row["request_index"] = 0
        if row["depth"] == 1:

            async def execute(arguments):
                await host.children.spawn("probe", "Nested work", session, {"probe": {}})
                return ToolResult(success=True, output="Nested task complete")

            session.coordinator.get("tools")["fixture_probe"].execute = execute
        register(session)

    monkeypatch.setattr(host.children, "register", register_nested)
    first = await host.children.spawn("probe", "First task", host.session, {"probe": {}})
    identity = first["session_id"]
    old = next(r for r in host.children.records.values() if r["parent"] == identity)
    old_parent = old["parent_item_id"]
    await host.children.resume(identity, "Second task with nested work")
    children = [(k, r) for k, r in host.children.records.items() if r["parent"] == identity]
    assert len(children) == 2
    current_id, current = children[-1]
    assert host.children.summary(current_id)["task_title"] == "Nested work"
    assert host.children.summary(identity)["task_title"] == "Second task with nested work"
    assert current["parent_item_id"] != old_parent
    assert host.inspection.rows[old_parent]["status"] == "succeeded"
    assert host.inspection.rows[current["parent_item_id"]]["status"] == "succeeded"
    # A legacy/colliding link must still be guarded independently by execution identity.
    old["parent_item_id"] = current["parent_item_id"]
    while not host.events.empty():
        host.events.get_nowait()
    host.children.progress(current_id, "Current nested task")
    events = []
    while not host.events.empty():
        events.append(host.events.get_nowait())
    progress = next(e for e in events if e.item_id == current["parent_item_id"])
    assert [r["child_id"] for r in progress.payload["child_progress"]] == [current_id]
    old_id = children[0][0]
    host.children.progress(old_id, "Late obsolete observation")
    late = []
    while not host.events.empty():
        late.append(host.events.get_nowait())
    assert [e.item_id for e in late] == [f"child:{old_id}"]


async def test_four_sustained_actual_children_keep_accounting_and_warning_identity(
    prepared, tmp_path, monkeypatch
):
    from decimal import Decimal

    from amplifier_core import ChatResponse, TextBlock, ToolCall, ToolResult
    from test_runtime_controls import records

    bridge, _ = await bridge_for(prepared, tmp_path, tmp_path)
    try:
        host = bridge.host
        provider = host.session.coordinator.get("providers")["fixture"]
        complete = type(provider).complete

        async def metered(self, request, **kwargs):
            await self.coordinator.hooks.emit(
                "llm:request", {"provider": "fixture", "model": "sustained-fixture"}
            )
            if self is provider:
                response = await complete(self, request, **kwargs)
            else:
                n = len(self.calls)
                self.calls.append(request)
                response = (
                    ChatResponse(content=[TextBlock(text="Controlled child completed")])
                    if n == 19
                    else ChatResponse(
                        content=[],
                        tool_calls=[
                            ToolCall(
                                id=f"call-{n}-{i}",
                                name="fixture_probe",
                                arguments={"fail": n == 0 and i == 0},
                            )
                            for i in range(3)
                        ],
                    )
                )
            await self.coordinator.hooks.emit(
                "llm:response",
                {
                    "provider": "fixture",
                    "model": "sustained-fixture",
                    "duration_ms": 10,
                    "usage": {"input_tokens": 100, "output_tokens": 5, "cost_usd": "0.01"},
                },
            )
            return response

        monkeypatch.setattr(type(provider), "complete", metered)
        tool = host.session.coordinator.get("tools")["fixture_probe"]

        async def child_tool(self, arguments):
            await asyncio.sleep(0)
            return ToolResult(
                success=not arguments["fail"],
                output="Controlled observation",
                error={"message": "Controlled missing file"} if arguments["fail"] else None,
            )

        async def delegate(arguments):
            await asyncio.gather(
                *(
                    host.children.spawn(
                        "probe",
                        f"Inspect controlled area {n}",
                        host.session,
                        {"probe": {}},
                        orchestrator_config={"max_iterations": 24},
                    )
                    for n in range(4)
                )
            )
            return ToolResult(success=True, output="Four controlled tasks completed")

        monkeypatch.setattr(type(tool), "execute", child_tool)
        monkeypatch.setattr(tool, "execute", delegate)
        host.children.register(host.session)
        assert host.submit("Four sustained controlled tasks")[0]
        assert await asyncio.wait_for(host.task, 30) == "completed"
        journal = records(host)
        calls = [e for e in journal if e["payload"].get("usage_call")]
        assert len(calls) == 82 and sum(bool(e["payload"].get("child_id")) for e in calls) == 80
        assert host.call_usage.session["totals"]["cost_usd"] == Decimal("0.82")
        parent = next(
            e["item_id"]
            for e in journal
            if e["kind"] == "tool.updated" and e["payload"].get("name") == "fixture_probe"
        )
        groups = [
            e["payload"]["child_progress"]
            for e in journal
            if e["kind"] == "tool.progress" and e["item_id"] == parent
        ][-1]
        assert len(groups) == 4
        assert {g["agent"] for g in groups} == {f"probe #{n}" for n in range(1, 5)}
        assert all(
            g["calls"] == 20 and g["tools_completed"] == 57 and g["warnings"]["failed"] == 1
            for g in groups
        )
        assert not any(e["payload"].get("source") == "child activity" for e in journal)
        for child in host.children.records:
            page = Inspection.journal_activity(host.store.path / "events.jsonl", f"child:{child}")
            assert not page["partial"]
            assert len([r for r in page["rows"] if r["label"] == "Usage"]) == 20
            assert len([r for r in page["rows"] if r["status"] == "failed"]) == 1
        # The same public records survive restoration; no provider execution.
        restored = Inspection.journal_activity(host.store.path / "events.jsonl", parent)
        assert len(restored["rows"]) == 4
    finally:
        await bridge.close()


@pytest.mark.parametrize("success,policy_error", [(True, False), (False, False), (True, True)])
async def test_invocation_status_survives_processed_output_without_leaking_it(
    host, monkeypatch, success, policy_error
):
    from amplifier_core import HookResult, ToolResult

    tool = host.session.coordinator.get("tools")["fixture_probe"]

    async def execute(self, arguments):
        return ToolResult(success=success, output="PRE_POLICY_ONLY" * 6000)

    async def truncate(event, data):
        processed = (
            {"success": False, "error": "Policy refused result"}
            if policy_error
            else "[output truncated] {broken envelope"
        )
        return HookResult(action="modify", data={**data, "result": processed})

    monkeypatch.setattr(type(tool), "execute", execute)
    original = host.children.register

    def register(session):
        original(session)
        session.coordinator.hooks.register(
            "tool:post", truncate, priority=100, name="controlled-truncation"
        )

    monkeypatch.setattr(host.children, "register", register)
    register(host.session)
    assert host.submit("Controlled truncation")[0]
    await host.task
    await host.children.spawn("probe", "Controlled child truncation", host.session, {"probe": {}})
    events = []
    while not host.events.empty():
        events.append(host.events.get_nowait())
    outcomes = [
        e
        for e in events
        if e.kind in ("tool.updated", "child.observed")
        and e.payload.get("name", "").endswith("fixture_probe")
        and e.payload.get("result") is not None
        and e.payload.get("status") != "running"
    ]
    assert len(outcomes) == 2
    expected = "failed" if policy_error or not success else "succeeded"
    assert {e.payload["status"] for e in outcomes} == {expected}
    assert all((e.payload["outcome_source"] == "event") == policy_error for e in outcomes)
    assert "PRE_POLICY_ONLY" not in str([e.payload for e in events])
    assert not host.children.tool_outcomes
    # Unsupported/unobserved invocation cannot turn malformed text into success.
    assert host.children.observed_outcome("missing", "tool:post", "unknown")[0] == "unknown"


async def test_switch_cancels_lookup_and_new_lookup_is_not_blocked(prepared, tmp_path, monkeypatch):
    import amplifier_tui.navigation as navigation

    bridge, frames = await bridge_for(prepared, tmp_path, tmp_path)
    entered, release = threading.Event(), threading.Event()
    original = navigation.file_candidates

    def delayed(*args):
        entered.set()
        assert release.wait(10)
        return original(*args)

    monkeypatch.setattr(navigation, "file_candidates", delayed)
    try:
        old = bridge.host.session_id
        bridge.lookup_task = asyncio.create_task(
            bridge.lookup({"op": "completion", "request_id": "obsolete", "query": "./"})
        )
        assert await asyncio.to_thread(entered.wait, 3)
        stale = bridge.lookup_task
        await bridge.switch("new", "switch-controlled")
        assert bridge.host.session_id != old and stale.cancelled()
        assert bridge.lookup_task is None
        release.set()
        await bridge.lookup({"op": "completion", "request_id": "current", "query": "./"})
        assert any(f.get("request_id") == "current" for f in frames)
        assert not any(f.get("request_id") == "obsolete" for f in frames)
    finally:
        release.set()
        await bridge.close()


@pytest.mark.parametrize(
    "override", [["--settings-policy", "isolated"], ["--cli-home", "controlled-home"]]
)
def test_invalid_recovery_overrides_refuse_before_any_recovery_write(
    monkeypatch, tmp_path, override
):
    import amplifier_tui.recovery as recovery
    from amplifier_tui.launcher import arguments

    def forbidden(*args):
        pytest.fail("Recovery was invoked before validating overrides")

    monkeypatch.setattr(recovery, "recover", forbidden)
    with pytest.raises(SystemExit) as error:
        arguments(["--recover", "controlled-session", "--state-dir", str(tmp_path), *override])
    assert error.value.code == 2
    assert not list(tmp_path.iterdir())


def test_saved_activity_pages_retain_early_calls_after_hot_index_eviction(tmp_path):
    events = []

    def emit(kind, key, **payload):
        events.append(Event("controlled", len(events) + 1, "turn", kind, key, payload))

    emit("tool.updated", "delegate", name="delegate", status="running")
    emit(
        "tool.updated",
        "child:c",
        name="Agent · probe #1",
        status="running",
        child_id="c",
        parent_item_id="delegate",
    )
    for n in range(350):
        emit(
            "display.message",
            f"usage-{n}",
            source="usage",
            text=f"Call {n} · model-controlled · $0.01",
            usage_call={"cost_usd": "0.01"},
            child_id="c",
            parent_item_id="child:c",
        )
        emit(
            "child.observed",
            f"tool-{n}",
            name="read_file",
            event="tool:post",
            status="failed" if n == 0 else "succeeded",
            result={"success": n != 0},
            child_id="c",
            parent_item_id="child:c",
        )
    emit("tool.updated", "delegate", name="delegate", status="succeeded")
    path = tmp_path / "events.jsonl"
    path.write_text("".join(json.dumps(asdict(e)) + "\n" for e in events))
    memory = Inspection()
    for e in events:
        memory.observe(e)
    assert memory.partial and "usage-0" not in memory.rows
    root = Inspection.journal_activity(path)
    assert [r["id"] for r in root["rows"]] == ["delegate"]
    assert root["rows"][0]["summary"] == "1 running · 1 failed"
    offset, seen = 0, []
    while offset is not None:
        page = Inspection.journal_activity(path, "child:c", offset)
        assert not page["partial"]
        assert page["breadcrumb"] == "delegate / Agent · probe #1"
        assert page["focus"]["children"] == 700
        seen.extend(r["id"] for r in page["rows"])
        offset = page["next_offset"]
    assert len(seen) == len(set(seen)) == 700
    assert seen[:2] == ["usage-0", "tool-0"]
    leaf = Inspection.journal_activity(path, "usage-0")
    assert "Call 0" in leaf["focus"]["preview"]
    assert "unavailable" not in leaf["focus"]["preview"]
    assert leaf["parent"] == "child:c"


def test_activity_archive_refuses_symlink_and_partial_record(tmp_path):
    source = tmp_path / "events.jsonl"
    source.write_text('{"incomplete":')
    assert Inspection.journal_activity(source)["partial"]
    link = tmp_path / "linked"
    link.symlink_to(source)
    with pytest.raises(OSError):
        Inspection.journal_activity(link)


async def test_activity_refresh_reuses_an_unchanged_saved_page(prepared, tmp_path, monkeypatch):
    bridge, _ = await bridge_for(prepared, tmp_path / "state", tmp_path)
    original = Inspection.journal_activity
    reads = []

    def counted(*args, **kwargs):
        reads.append(args)
        return original(*args, **kwargs)

    monkeypatch.setattr(Inspection, "journal_activity", staticmethod(counted))
    try:
        bridge.host.emit("tool.updated", "tool", name="read_file", status="running")

        def request(number):
            return {
                "op": "inspect",
                "category": "activity_tree",
                "session_id": bridge.host.session_id,
                "request_id": f"activity-{number}",
            }

        assert bridge.command(request(1))[0]
        await bridge.lookup_task
        assert bridge.command(request(2))[0]
        await bridge.lookup_task
        assert len(reads) == 1

        bridge.host.emit("tool.updated", "tool", name="read_file", status="succeeded")
        assert bridge.command(request(3))[0]
        await bridge.lookup_task
        assert len(reads) == 2
    finally:
        await bridge.close()

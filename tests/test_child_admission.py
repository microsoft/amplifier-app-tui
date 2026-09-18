"""Actual host/module child admission; invented work, no live service or device."""

import asyncio
import json
from types import SimpleNamespace

import pytest
from amplifier_core import ToolResult
from test_navigation import bridge_for

from amplifier_tui.children import Children


async def until(predicate):
    async with asyncio.timeout(10):
        while not predicate():
            await asyncio.sleep(0.005)


async def test_long_session_archives_context_without_limiting_execution(
    prepared, tmp_path, monkeypatch
):
    bridge, _ = await bridge_for(prepared, tmp_path, tmp_path)
    host = bridge.host
    provider = host.session.coordinator.get("providers")["fixture"]
    complete = type(provider).complete

    async def quick(self, request, **kwargs):
        self.config["delay"] = 0
        return await complete(self, request, **kwargs)

    monkeypatch.setattr(type(provider), "complete", quick)
    try:
        ids = []
        for index in range(40):
            result = await host.children.spawn("self", f"Controlled work {index}", host.session, {})
            ids.append(result["session_id"])
        assert len(host.children.records) == 40
        assert sum("messages" in r for r in host.children.records.values()) == 32
        assert sum("prepared" in r for r in host.children.records.values()) == 32
        assert host.children.records[ids[0]]["archived"]
        assert host.children.label(ids[0]) == "self #1"
        receipt = host.store.path / "children" / f"{ids[0]}.json"
        before = json.loads(receipt.read_text())
        assert before["messages"] and "archived" not in before
        resumed = await host.children.resume(ids[0], "Continue the earliest controlled work")
        assert resumed["session_id"] == ids[0]
        assert host.children.label(ids[0]) == "self #1"
        assert len(host.children.records[ids[0]]["messages"]) > len(before["messages"])
        assert sum("messages" in r for r in host.children.records.values()) == 32
        assert not host.children.active and not host.children.tasks
    finally:
        await bridge.close()


@pytest.mark.parametrize("stop", [False, "graceful", "immediate"])
async def test_parallel_capacity_waits_and_graceful_stop_never_starts_waiters(
    prepared, tmp_path, monkeypatch, stop
):
    monkeypatch.setenv("AMPLIFIER_TUI_CHILD_CONCURRENCY", "2")
    bridge, _ = await bridge_for(prepared, tmp_path, tmp_path)
    host = bridge.host
    provider = host.session.coordinator.get("providers")["fixture"]
    complete = type(provider).complete
    entered, release = set(), asyncio.Event()

    async def controlled(self, request, **kwargs):
        self.config["delay"] = 0
        if self is not provider:
            entered.add(self.coordinator.session_id)
            await release.wait()
        return await complete(self, request, **kwargs)

    monkeypatch.setattr(type(provider), "complete", controlled)

    async def fanout(_args):
        await asyncio.gather(
            *(
                host.children.spawn("self", f"Controlled branch {n}", host.session, {})
                for n in range(10)
            )
        )
        return ToolResult(success=True, output="All controlled branches finished")

    host.session.coordinator.get("tools")["fixture_probe"].execute = fanout
    host.children.register(host.session)
    try:
        assert host.submit("Exercise ten parallel fixture children")[0]
        await until(lambda: len(entered) == 2 and len(host.children.waiting) == 8)
        assert len([s for s in host.children.active.values() if s is not None]) == 2
        if stop:
            assert host.stop(immediate=stop == "immediate")
            await until(lambda: not host.children.waiting)
            assert len(entered) == 2
            if stop == "graceful":
                assert not host.task.done()
        release.set()
        assert await asyncio.wait_for(host.task, 15) == ("interrupted" if stop else "completed")
        assert len(entered) == (2 if stop else 10)
        assert not host.children.active and not host.children.tasks
        assert all(
            r["status"] == ("interrupted" if stop else "completed")
            for r in host.children.records.values()
        )
    finally:
        release.set()
        await bridge.close()


async def test_nested_capacity_is_independent_and_named_depth_is_not_self_depth(host, monkeypatch):
    host.children.capacity = 1
    register = host.children.register
    seen = set()
    reported_depths = []
    provider = host.session.coordinator.get("providers")["fixture"]
    complete = type(provider).complete

    async def observed(self, request, **kwargs):
        reported_depths.append(self.coordinator.get_capability("self_delegation_depth"))
        return await complete(self, request, **kwargs)

    monkeypatch.setattr(type(provider), "complete", observed)

    def nested(session):
        if session.session_id != host.session_id:
            depth = host.children.records[session.session_id]["depth"]
            if depth < 5:

                async def next_child(_args):
                    result = await host.children.spawn(
                        "probe", "Nested fixture work", session, {"probe": {}}
                    )
                    return ToolResult(success=True, output=result["output"])

                session.coordinator.get("tools")["fixture_probe"].execute = next_child
            seen.add((session.session_id, depth))
        register(session)

    monkeypatch.setattr(host.children, "register", nested)
    result = await asyncio.wait_for(
        host.children.spawn("probe", "Root fixture branch", host.session, {"probe": {}}), 15
    )
    assert result["output"] and max(d for _, d in seen) == 5
    assert all(r["self_depth"] == 0 for r in host.children.records.values())
    assert reported_depths and set(reported_depths) == {0}
    assert not host.children.active


@pytest.mark.parametrize("value", ["0", "-1", "65", "invalid"])
def test_invalid_admission_configuration_fails_clearly(monkeypatch, value):
    monkeypatch.setenv("AMPLIFIER_TUI_CHILD_CONCURRENCY", value)
    with pytest.raises(ValueError, match="must be between 1 and 64"):
        Children(SimpleNamespace(session_id="fixture"), None, None)


def test_progress_preview_bounds_keep_live_work_and_all_accounting():
    rows = [
        {
            "child_id": str(i),
            "status": "succeeded",
            "calls": 2,
            "cost_usd": "0.01",
            "cost_partial": False,
            "warnings": {"failed": 1},
        }
        for i in range(100)
    ]
    rows[0]["status"] = "running"
    value = Children.progress_payload(rows)
    assert value["child_progress"][0]["child_id"] == "0"
    assert len(value["child_progress"]) == 32 and value["child_progress_omitted"] == 68
    assert value["child_calls"] == 200 and value["child_count"] == 100
    assert value["child_cost_display"] == "$1.00" and not value["child_cost_partial"]
    assert value["child_totals"]["warnings"]["failed"] == 100
    for row in rows:
        row["status"] = "waiting_capacity"
    crowded = Children.progress_payload(rows)
    assert len(crowded["child_progress"]) == 64
    assert crowded["child_progress_omitted"] == 36 and crowded["child_calls"] == 200


@pytest.mark.parametrize("cold", [False, True])
async def test_cancelled_capacity_wait_does_not_invalidate_completed_receipt(
    prepared, tmp_path, monkeypatch, cold
):
    bridge, _ = await bridge_for(prepared, tmp_path, tmp_path)
    host = bridge.host
    try:
        result = await host.children.spawn("self", "Initial fixture work", host.session, {})
        identity = result["session_id"]
        receipt = host.store.path / "children" / f"{identity}.json"
        before = receipt.read_bytes()
        if cold:
            host.children.records[identity]["archived"] = True
            host.children.records[identity].pop("prepared")
            host.children.records[identity].pop("messages")
        slot = asyncio.Semaphore(0)
        host.children.slots[host.session_id] = slot
        task = asyncio.create_task(host.children.resume(identity, "Not yet admitted"))
        await until(lambda: identity in host.children.waiting)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert host.children.records[identity]["status"] == "completed"
        assert receipt.read_bytes() == before
        slot.release()
        continued = await host.children.resume(identity, "Explicit admitted continuation")
        assert continued["session_id"] == identity and continued["metadata"]["status"] == "success"
    finally:
        await bridge.close()

import asyncio

import pytest


async def test_real_child_execution_and_resume_are_isolated(host):
    parent = await host.session.coordinator.get("context").get_messages()
    result = await host.children.spawn("probe", "Compute a digest", host.session, {"probe": {}})
    assert "Fixture round trip" in result["output"]
    assert not host.children.active
    row = host.children.records[result["session_id"]]
    assert row["status"] == "completed"
    assert "fixture_probe" in row["tools"]
    assert await host.session.coordinator.get("context").get_messages() == parent
    again = await host.children.resume(result["session_id"], "Again")
    assert again["session_id"] == result["session_id"]
    assert len(row["messages"]) > 4


async def test_child_cancel_closes_and_cannot_resume(host):
    host.children.prepared.bundle.providers[0].setdefault("config", {})["delay"] = 10
    task = asyncio.create_task(host.children.spawn("probe", "wait", host.session, {"probe": {}}))
    async with asyncio.timeout(5):
        while not any(host.children.active.values()):
            await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not host.children.active
    identity = next(iter(host.children.records))
    with pytest.raises(ValueError, match="incomplete"):
        await host.children.resume(identity, "again")


async def test_child_unknown_and_unsupported_scope_refuse(host):
    with pytest.raises(ValueError, match="Unknown"):
        await host.children.spawn("missing", "x", host.session, {})
    with pytest.raises(ValueError, match="Subprocess"):
        await host.children.spawn("self", "x", host.session, {}, use_subprocess=True)
    assert not host.children.records
    with pytest.raises(ValueError, match="Unknown tools inheritance"):
        await host.children.spawn("self", "x", host.session, {}, tool_inheritance={"allow": []})

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


async def test_child_cancel_closes_and_valid_canonical_context_can_resume(host):
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
    row = host.children.records[identity]
    assert row["status"] == "interrupted" and row["resumable"]
    row["prepared"].mount_plan["providers"][0]["config"]["delay"] = 0
    result = await host.children.resume(identity, "Explicit new instruction")
    assert result["session_id"] == identity and row["status"] == "completed"


async def test_child_unknown_and_unsupported_scope_refuse(host):
    with pytest.raises(ValueError, match="Unknown"):
        await host.children.spawn("missing", "x", host.session, {})
    with pytest.raises(ValueError, match="boolean"):
        await host.children.spawn("self", "x", host.session, {}, use_subprocess="yes")
    assert not host.children.records
    with pytest.raises(ValueError, match="Unknown tools inheritance"):
        await host.children.spawn("self", "x", host.session, {}, tool_inheritance={"allow": []})


async def test_custom_orchestrator_configuration_survives_guarded_child_restart(prepared, tmp_path):
    import json

    from amplifier_tui.conversations import ConversationStore
    from amplifier_tui.host import SessionHost

    store = ConversationStore(tmp_path, {})
    host = SessionHost(store)
    config = {"max_iterations": 7}
    try:
        await host.open(*prepared, tmp_path)
        result = await host.children.spawn(
            "self", "Compute once", host.session, {}, orchestrator_config=config
        )
        child = result["session_id"]
        config["max_iterations"] = 99
        saved = json.loads((store.path / "children" / f"{child}.json").read_text())
        assert saved["restart_policy"]["orchestrator"] == {"max_iterations": 7}
        assert host.submit("Checkpoint the parent after directly exercising its child capability")[
            0
        ]
        await host.task
    finally:
        await host.close()
    restored = SessionHost(ConversationStore(tmp_path, {}, store.identity))
    try:
        await restored.open(*prepared, tmp_path)
        assert not restored.children.active
        assert not restored.session.coordinator.get("providers")["fixture"].calls
        result = await restored.children.resume(child, "Explicit continuation")
        assert result["session_id"] == child
        assert restored.children.records[child]["restart_policy"]["orchestrator"] == {
            "max_iterations": 7
        }
        assert restored.children.records[child]["status"] == "completed"
    finally:
        await restored.close()

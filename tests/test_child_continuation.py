"""Routing and canonical continuation through real modules with invented fixture work."""

import asyncio
import copy
import json

import pytest
from test_child_admission import until
from test_navigation import bridge_for

from amplifier_tui.conversations import ConversationStore
from amplifier_tui.host import SessionHost


@pytest.mark.parametrize("cold", [False, True])
async def test_explicit_routing_keeps_identity_context_and_durable_precedence(
    prepared, tmp_path, monkeypatch, cold
):
    bridge, _ = await bridge_for(prepared, tmp_path, tmp_path)
    host = bridge.host
    provider = host.session.coordinator.get("providers")["fixture"]
    complete, observed = type(provider).complete, []

    async def capture(self, request, **kwargs):
        self.config["delay"] = 0
        observed.append(
            (self.config.get("default_model"), self.coordinator.config.get("model_role"))
        )
        return await complete(self, request, **kwargs)

    monkeypatch.setattr(type(provider), "complete", capture)
    resumed = None
    try:
        root_plan = copy.deepcopy(host.children.prepared.mount_plan)
        initial = await host.children.spawn(
            "self",
            "Initial fixture leg",
            host.session,
            {},
            provider_preferences=[{"provider": "fixture", "model": "fixture-first"}],
        )
        identity = initial["session_id"]
        prior = copy.deepcopy(host.children.records[identity]["messages"])
        if cold:
            assert host.submit("Checkpoint the fixture root")[0]
            await host.task
            store_id = host.store.identity
            launch = host.store.metadata["launch"]
            await bridge.close()
            resumed = SessionHost(ConversationStore(tmp_path, launch, store_id))
            await resumed.open(*prepared, tmp_path)
            host = resumed
            assert not host.session.coordinator.get("providers")["fixture"].calls
        observed.clear()
        result = await host.children.resume(
            identity,
            "Explicit second fixture leg",
            provider_preferences=[{"provider": "fixture", "model": "fixture-second"}],
            model_role=["review"],
        )
        assert result["session_id"] == identity
        assert observed and all(row == ("fixture-second", ["review"]) for row in observed)
        row = host.children.records[identity]
        assert row["messages"][: len(prior)] == prior
        assert host.children.prepared.mount_plan == root_plan
        receipt = json.loads((host.store.path / "children" / f"{identity}.json").read_text())
        assert "_routing_base" not in receipt and "prepared" not in receipt
        assert receipt["routing"][0]["model"] == "fixture-second"
        observed.clear()
        # Force the real disk restoration path; omitted overrides retain the caller chain.
        row["archived"] = True
        row.pop("prepared")
        row.pop("messages")
        await host.children.resume(identity, "Explicit third fixture leg")
        assert observed and all(row == ("fixture-second", ["review"]) for row in observed)
    finally:
        if resumed:
            await resumed.close()
        await bridge.close()


@pytest.mark.parametrize("invalid", [False, True])
async def test_unresolved_routing_is_visible_and_does_not_change_parent(host, invalid):
    result = await host.children.spawn("self", "Initial leg", host.session, {})
    identity = result["session_id"]
    parent = copy.deepcopy(host.session.config)
    await host.children.resume(
        identity,
        "Explicit fallback leg",
        provider_preferences=[{"provider": "absent-fixture-provider", "model": "fixture"}]
        if not invalid
        else ["invalid fixture preference"],
    )
    row = host.children.records[identity]
    assert row["routing_fallback"] == (
        "invalid_provider_preferences" if invalid else "preferred_provider_not_mounted"
    )
    assert row["notices"]["warning"] == 1 and row["status"] == "completed"
    assert host.session.config == parent


@pytest.mark.parametrize("fault", ["tool_policy", "mount_digest"])
async def test_routing_override_cannot_bypass_changed_tool_policy(prepared, tmp_path, fault):
    bridge, _ = await bridge_for(prepared, tmp_path, tmp_path)
    host = bridge.host
    try:
        result = await host.children.spawn("self", "Initial fixture leg", host.session, {})
        identity = result["session_id"]
        receipt = host.store.path / "children" / f"{identity}.json"
        row = host.children.records[identity]
        row["archived"] = True
        if fault == "tool_policy":
            host.children.prepared.bundle.tools[0].setdefault("config", {})["approval"] = True
        else:
            value = json.loads(receipt.read_text())
            value["mount_fingerprint"] = "f" * 64
            receipt.write_text(json.dumps(value))
        original = receipt.read_bytes()
        with pytest.raises(ValueError, match="composition changed|metadata is inconsistent"):
            await host.children.resume(
                identity,
                "Do not bypass tool policy",
                provider_preferences=[{"provider": "fixture", "model": "fixture-second"}],
            )
        assert receipt.read_bytes() == original and not host.children.active
    finally:
        await bridge.close()


async def test_legacy_completed_receipt_validates_before_explicit_routing_change(
    prepared, tmp_path
):
    bridge, _ = await bridge_for(prepared, tmp_path, tmp_path)
    host = bridge.host
    try:
        result = await host.children.spawn(
            "self",
            "Legacy controlled leg",
            host.session,
            {},
            provider_preferences=[{"provider": "fixture", "model": "fixture-first"}],
        )
        identity = result["session_id"]
        receipt = host.store.path / "children" / f"{identity}.json"
        value = json.loads(receipt.read_text())
        for field in ("policy_fingerprint", "routing_checkpoint", "parent_mode", "model_role"):
            value.pop(field, None)
        receipt.write_text(json.dumps(value))
        host.children.records[identity]["archived"] = True
        continued = await host.children.resume(
            identity,
            "Explicit legacy continuation",
            provider_preferences=[{"provider": "fixture", "model": "fixture-second"}],
        )
        assert continued["session_id"] == identity
        assert host.children.records[identity]["routing"][0]["model"] == "fixture-second"
    finally:
        await bridge.close()


@pytest.mark.parametrize("fault", ["uncertain", "missing_result", "cleanup"])
async def test_incomplete_child_state_refuses_implicit_repair(host, monkeypatch, fault):
    result = await host.children.spawn("self", "Initial fixture leg", host.session, {})
    row = host.children.records[result["session_id"]]
    row["status"], row["resumable"] = "interrupted", True
    if fault == "uncertain":
        row["execution_uncertain"] = True
    elif fault == "cleanup":
        row["resumable"] = False
    else:
        row["messages"].append(
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "unresolved-fixture",
                        "function": {"name": "fixture_probe", "arguments": "{}"},
                    }
                ],
            }
        )
    before = copy.deepcopy(row["messages"])
    with pytest.raises(ValueError):
        await host.children.resume(result["session_id"], "Do not repair implicitly")
    assert row["messages"] == before and not host.children.active


@pytest.mark.parametrize("cold", [False, True])
@pytest.mark.parametrize("force", [False, True])
async def test_drained_child_continues_without_replaying_previous_tool(
    prepared, tmp_path, monkeypatch, cold, force
):
    from amplifier_core import ToolResult

    bridge, _ = await bridge_for(prepared, tmp_path, tmp_path)
    host = bridge.host
    register = host.children.register
    entered, release = asyncio.Event(), asyncio.Event()
    effects = []

    def controlled(session):
        if session.session_id != host.session_id:

            async def effect(_args):
                effects.append(session.session_id)
                entered.set()
                await release.wait()
                return ToolResult(success=True, output="Controlled child effect finished")

            session.coordinator.get("tools")["fixture_probe"].execute = effect
        register(session)

    monkeypatch.setattr(host.children, "register", controlled)
    resumed = None
    task = asyncio.create_task(
        host.children.spawn("self", "Controlled stopped leg", host.session, {})
    )
    try:
        await asyncio.wait_for(entered.wait(), 5)
        identity = next(iter(host.children.active))
        if force:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            host.children.active[identity].coordinator.cancellation.request_graceful()
            release.set()
            result = await asyncio.wait_for(task, 5)
            assert result["metadata"]["status"] == "cancelled"
        row = host.children.records[identity]
        assert row["status"] == "interrupted" and row["resumable"]
        prior = copy.deepcopy(row["messages"])
        assert len(effects) == 1 and not host.children.active
        if cold:
            assert host.submit("Checkpoint the fixture root")[0]
            await host.task
            store_id, launch = host.store.identity, host.store.metadata["launch"]
            await bridge.close()
            resumed = SessionHost(ConversationStore(tmp_path, launch, store_id))
            await resumed.open(*prepared, tmp_path)
            host = resumed
            assert not host.session.coordinator.get("providers")["fixture"].calls
            assert not host.children.active and len(effects) == 1
        release.set()
        result = await host.children.resume(identity, "Explicit new child instruction")
        assert result["session_id"] == identity
        assert host.children.records[identity]["messages"][: len(prior)] == prior
        assert host.children.records[identity]["status"] == "completed"
        assert len(effects) == (1 if cold else 2)
    finally:
        release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        if resumed:
            await resumed.close()
        await bridge.close()


async def test_cancelled_routing_admission_does_not_persist_or_arm_new_choice(prepared, tmp_path):
    bridge, _ = await bridge_for(prepared, tmp_path, tmp_path)
    host = bridge.host
    try:
        result = await host.children.spawn("self", "Initial fixture leg", host.session, {})
        identity = result["session_id"]
        row = host.children.records[identity]
        before = copy.deepcopy(row["routing"])
        receipt = host.store.path / "children" / f"{identity}.json"
        original = receipt.read_bytes()
        host.children.slots[host.session_id] = asyncio.Semaphore(0)
        task = asyncio.create_task(
            host.children.resume(
                identity,
                "Not admitted",
                provider_preferences=[{"provider": "fixture", "model": "not-applied"}],
            )
        )
        await until(lambda: identity in host.children.waiting)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert row["routing"] == before and receipt.read_bytes() == original
        assert row["status"] == "completed"
    finally:
        await bridge.close()

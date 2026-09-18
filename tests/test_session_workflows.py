"""Explicit session operations over real core/Foundation with offline providers."""

import asyncio
import hashlib
import json
from unittest.mock import AsyncMock

import pytest
from test_cli_controls import local
from test_navigation import bridge_for

from amplifier_tui.conversations import ConversationStore
from amplifier_tui.host import SessionHost
from amplifier_tui.recovery import export


async def turn(host, text):
    accepted, reason = host.submit(text)
    assert accepted, reason
    await host.task
    assert host.outcome == "success"


async def test_context_clear_is_explicit_durable_and_preserves_history(prepared, tmp_path):
    bridge, _ = await bridge_for(prepared, tmp_path / "state", tmp_path)
    host = bridge.host
    identity, launch = host.session_id, host.store.metadata["launch"]
    try:
        await turn(host, "Synthetic retained history marker")
        before = await host.session.coordinator.get("context").get_messages()
        await local(host, "/goal --max-turns 2 Synthetic goal")
        host.store.save_draft("Unsent draft")
        bridge.followups.command({"op": "queue_pause"})
        assert bridge.followups.command({"op": "queue", "text": "Held instruction"})[0]
        assert not host.submit("/clear")[0]
        assert not bridge.command({"op": "clear_context", "session_id": identity})[0]
        assert await host.session.coordinator.get("context").get_messages() == before
        accepted, reason = bridge.command(
            {"op": "clear_context", "session_id": identity, "confirm": True}
        )
        assert accepted, reason
        await host.task
        assert host.ready and host.session_id == identity
        assert await host.session.coordinator.get("context").get_messages() == []
        assert host.session.coordinator.session_state["goal"] is None
        assert host.store.draft == "Unsent draft"
        assert bridge.followups.paused and len(bridge.followups.rows) == 1
        backup = json.loads(next((host.store.path / "context-clears").glob("*.json")).read_text())
        assert backup["messages"] == before
        assert backup["goal"]["condition"] == "Synthetic goal"
        assert (
            "Synthetic retained history marker" in export(tmp_path / "state", identity).read_text()
        )
    finally:
        await bridge.close()
    restored = SessionHost(ConversationStore(tmp_path / "state", launch, identity))
    try:
        await restored.open(*prepared, tmp_path)
        assert await restored.session.coordinator.get("context").get_messages() == []
        assert restored.session.coordinator.session_state["goal"] is None
        assert not restored.session.coordinator.get("providers")["fixture"].calls
    finally:
        await restored.close()


async def test_ineffective_clear_keeps_backup_and_refuses_execution(
    prepared, tmp_path, monkeypatch
):
    bridge, _ = await bridge_for(prepared, tmp_path / "state", tmp_path)
    host = bridge.host
    try:
        await turn(host, "Synthetic marker before failed clear")
        monkeypatch.setattr(host.session.coordinator.get("context"), "clear", AsyncMock())
        await local(host, "/clear --confirm")
        assert not host.ready
        assert json.loads(host.local_commands.path.read_text())["status"] == "pending"
        assert list((host.store.path / "context-clears").glob("*.json"))
        assert not host.submit("Must not execute")[0]
    finally:
        await bridge.close()


async def test_turn_branch_validates_public_history_and_never_replays(prepared, tmp_path):
    from amplifier_foundation.session import count_turns

    bridge, _ = await bridge_for(prepared, tmp_path / "state", tmp_path)
    source = bridge.host
    original_id = source.session_id
    try:
        await turn(source, "Synthetic first turn")
        await turn(source, "Synthetic later turn")
        original = await source.session.coordinator.get("context").get_messages()
        assert count_turns(original) == 2
        await local(source, "/fork")
        request = {
            "op": "switch",
            "request_id": "branch-fixture",
            "session_id": original_id,
            "target": "new",
            "fork_turn": 1,
            "fork_name": "Synthetic branch",
            "draft": "Retained unsent draft",
        }
        assert not bridge.command(request)[0]
        accepted, reason = bridge.command({**request, "confirm_fork": True})
        assert accepted, reason
        await bridge.switch_task
        branch = bridge.host
        assert branch.session_id != original_id
        assert branch.store.metadata["title"] == "Synthetic branch"
        messages = await branch.session.coordinator.get("context").get_messages()
        assert count_turns(messages) == 1
        assert "Synthetic first turn" in str(messages)
        assert "Synthetic later turn" not in str(messages)
        assert not branch.session.coordinator.get("providers")["fixture"].calls
        assert branch.session.coordinator.get("tools")["fixture_probe"].calls == 0
        assert branch.store.draft == "Retained unsent draft"
        checkpoint = json.loads((source.store.path / "checkpoint.json").read_text())
        assert checkpoint["messages"] == original
        imported = json.loads((branch.store.path / "imported-context.json").read_text())
        assert imported["fork_turn"] == 1 and imported["source_session"] == original_id
        await turn(branch, "A new explicitly sent instruction")
        assert branch.session.coordinator.get("tools")["fixture_probe"].calls == 1
    finally:
        await bridge.close()


async def test_invalid_branch_retains_source_without_mount_or_execution(prepared, tmp_path):
    bridge, _ = await bridge_for(prepared, tmp_path / "state", tmp_path)
    host = bridge.host
    try:
        await turn(host, "Only one synthetic turn")
        assert bridge.command(
            {
                "op": "switch",
                "request_id": "bad-branch",
                "session_id": host.session_id,
                "target": "new",
                "fork_turn": 3,
                "confirm_fork": True,
                "draft": "Retained",
            }
        )[0]
        await bridge.switch_task
        assert bridge.host is host and host.ready
        assert host.store.draft == "Retained"
        assert len(list((tmp_path / "state/conversations").iterdir())) == 1
    finally:
        await bridge.close()


async def test_structured_export_is_projection_not_module_configuration(prepared, tmp_path):
    bridge, _ = await bridge_for(prepared, tmp_path / "state", tmp_path)
    host = bridge.host
    try:
        host.emit(
            "session.ready",
            "export-fixture",
            deliberately_private_config="SYNTHETIC-CONFIG-NOT-FOR-EXPORT",
        )
        await turn(host, "Synthetic exported conversation")
        host.emit("text.delta", "partial-fixture", text="Unfinished synthetic stream")
        calls = len(host.session.coordinator.get("providers")["fixture"].calls)
        path = export(tmp_path / "state", host.session_id, "json")
        document = json.loads(path.read_text())
        assert document["format"] == "amplifier-tui-observations"
        assert document["source_session"] == host.session_id
        assert "SYNTHETIC-CONFIG-NOT-FOR-EXPORT" not in path.read_text()
        partial = next(i for i in document["items"] if i["id"] == "partial-fixture")
        assert partial["stream_complete"] is False
        assert any(i["kind"] == "tool" and i["detail"] for i in document["items"])
        assert len(host.session.coordinator.get("providers")["fixture"].calls) == calls
        assert path.stat().st_mode & 0o777 == 0o600
        with pytest.raises(ValueError, match="markdown or json"):
            export(tmp_path / "state", host.session_id, "invalid")
    finally:
        await bridge.close()


@pytest.mark.parametrize("policy", ["allow", "deny", "modify"])
async def test_direct_tool_uses_kernel_hooks_without_a_root_model_or_naming(host, policy):
    from amplifier_core import HookResult

    coordinator = host.session.coordinator
    calls = []

    async def pre(_event, data):
        calls.append("pre")
        if policy == "deny":
            return HookResult(action="deny", reason="Synthetic policy refusal")
        if policy == "modify":
            return HookResult(
                action="modify", data={**data, "tool_input": {"text": "synthetic-modified"}}
            )
        return HookResult()

    async def post(_event, data):
        calls.append("post")
        return HookResult()

    async def naming(_event, _data):
        calls.append("naming")
        return HookResult()

    coordinator.hooks.register("tool:pre", pre, priority=0, name="fixture-direct-policy")
    coordinator.hooks.register("tool:post", post, priority=0, name="fixture-direct-post")
    coordinator.hooks.register("prompt:complete", naming, name="fixture-no-direct-naming")
    await local(host, "/tool info fixture_probe")
    await local(host, '/tool invoke fixture_probe {"text":"synthetic-original"}')
    assert coordinator.get("tools")["fixture_probe"].calls == (0 if policy == "deny" else 1)
    assert not coordinator.get("providers")["fixture"].calls
    assert calls == ["pre", "post"]
    assert host.outcome == "success"  # Tool outcome remains independent of dispatch completion.
    if policy == "deny":
        assert "Direct tool · fixture_probe · failed" in str(
            await coordinator.get("context").get_messages()
        )
    if policy != "deny":
        text = "synthetic-modified" if policy == "modify" else "synthetic-original"
        assert hashlib.sha256(text.encode()).hexdigest() in str(
            await coordinator.get("context").get_messages()
        )


@pytest.mark.parametrize("decision", ["allow", "deny"])
@pytest.mark.parametrize("mechanism", ["tool", "hook"])
async def test_direct_tool_keeps_actual_interactive_approval(host, decision, mechanism):
    from amplifier_core import HookResult

    tool = host.session.coordinator.get("tools")["fixture_probe"]
    if mechanism == "tool":
        tool.config["approval"] = True
    else:

        async def ask(_event, _data):
            return HookResult(
                action="ask_user",
                approval_prompt="Synthetic direct hook approval?",
                approval_options=["allow", "deny"],
                approval_default="deny",
            )

        host.session.coordinator.hooks.register(
            "tool:pre", ask, priority=0, name="fixture-direct-approval"
        )
    assert host.submit('/tool invoke fixture_probe {"text":"synthetic-approval"}')[0]
    async with asyncio.timeout(5):
        while True:
            event = await host.next_event()
            if event.kind == "approval.requested":
                break
    assert tool.calls == 0
    assert host.answer(event.item_id, decision)
    await host.task
    assert tool.calls == int(decision == "allow")
    assert not host.session.coordinator.get("providers")["fixture"].calls


async def test_direct_tool_known_failure_and_modified_result_remain_resumable(prepared, tmp_path):
    from amplifier_core import HookResult

    bridge, _ = await bridge_for(prepared, tmp_path / "state", tmp_path)
    host = bridge.host
    identity, launch = host.session_id, host.store.metadata["launch"]

    async def deny(_event, _data):
        return HookResult(action="deny", reason="Synthetic refusal")

    async def redact(_event, data):
        return HookResult(action="modify", data={**data, "result": "Synthetic redacted result"})

    try:
        host.session.coordinator.hooks.register("tool:pre", deny, priority=0)
        host.session.coordinator.hooks.register("tool:post", redact, priority=0)
        await turn(host, '/tool invoke fixture_probe {"text":"synthetic-denied"}')
        messages = await host.session.coordinator.get("context").get_messages()
        assert "Synthetic redacted result" in str(messages)
        assert "Synthetic refusal" not in str(messages)
        assert "fixture_probe · failed" in str(messages)
    finally:
        await bridge.close()
    restored = SessionHost(ConversationStore(tmp_path / "state", launch, identity))
    try:
        await restored.open(*prepared, tmp_path)
        assert restored.ready
        assert await restored.session.coordinator.get("context").get_messages() == messages
        assert restored.session.coordinator.get("tools")["fixture_probe"].calls == 0
        assert not restored.session.coordinator.get("providers")["fixture"].calls
    finally:
        await restored.close()


@pytest.mark.parametrize("force", [False, True])
async def test_direct_tool_cancellation_owns_and_drains_work(prepared, tmp_path, force):
    bridge, _ = await bridge_for(prepared, tmp_path / "state", tmp_path)
    host = bridge.host
    try:
        tool = host.session.coordinator.get("tools")["fixture_probe"]
        tool.config["delay"] = 10 if force else 0.1
        assert host.submit('/tool invoke fixture_probe {"text":"synthetic-cancel"}')[0]
        async with asyncio.timeout(5):
            while tool.calls == 0:
                await asyncio.sleep(0.001)
        host.stop(immediate=False)
        if force:
            host.stop(immediate=True)
        await asyncio.wait_for(host.task, 5)
        assert not host.children.active
        assert not host.session.coordinator.get("providers")["fixture"].calls
        assert host.ready is not force
    finally:
        await bridge.close()

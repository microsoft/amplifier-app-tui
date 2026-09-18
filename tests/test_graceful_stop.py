"""Real Foundation/core cancellation trees with controlled, offline operations."""

import asyncio
import copy
import json
import os
from dataclasses import replace
from pathlib import Path

import pytest
from amplifier_core import ToolResult
from test_navigation import bridge_for

from amplifier_tui.conversations import ConversationStore
from amplifier_tui.host import SessionHost


async def until(predicate):
    async with asyncio.timeout(5):
        while not predicate():
            await asyncio.sleep(0.005)


@pytest.mark.parametrize("loop", ["loop-streaming", "loop-basic"])
@pytest.mark.parametrize("context", ["context-simple", "context-persistent"])
@pytest.mark.parametrize("boundary", ["model", "tool"])
async def test_graceful_keeps_current_operation_and_blocks_next(
    prepared, tmp_path, monkeypatch, loop, context, boundary
):
    if (loop == "loop-basic" or context == "context-persistent") and os.environ.get(
        "TUI_TEST_SWAPS"
    ) != "1":
        pytest.skip("Independent packages require TUI_TEST_SWAPS")
    value, report = prepared
    plan = copy.deepcopy(value.mount_plan)
    for slot, module in (("orchestrator", loop), ("context", context)):
        plan["session"][slot] = {
            "module": module,
            "source": str(Path(__file__).resolve().parents[2] / f"amplifier-module-{module}"),
            "config": {},
        }
    if context == "context-persistent":
        plan["session"]["context"]["config"] = {
            "transcript_path": str(tmp_path / "context.jsonl"),
            "memory_files": [],
        }
    value = replace(value, mount_plan=plan)
    store = ConversationStore(tmp_path / "state", {})
    host = SessionHost(store)
    entered, release = asyncio.Event(), asyncio.Event()
    finished = []
    try:
        await host.open(value, report, tmp_path)
        coordinator = host.session.coordinator
        provider = coordinator.get("providers")["fixture"]
        tool = coordinator.get("tools")["fixture_probe"]
        target, method = (provider, "complete") if boundary == "model" else (tool, "execute")
        original = getattr(type(target), method)

        async def gated(self, *args, **kwargs):
            entered.set()
            await release.wait()
            result = await original(self, *args, **kwargs)
            finished.append(boundary)
            return result

        monkeypatch.setattr(type(target), method, gated)
        host.submit("Stop at a controlled boundary")
        await asyncio.wait_for(entered.wait(), 5)
        assert host.stop(immediate=False)
        assert coordinator.cancellation.is_graceful
        # Graceful is not the old 250 ms force timeout.
        await asyncio.sleep(0.35)
        assert not host.task.done() and finished == []
        release.set()
        assert await asyncio.wait_for(host.task, 5) == "interrupted"
        assert finished == [boundary] and len(provider.calls) == 1
        assert tool.calls == (1 if boundary == "tool" else 0)
        history = await coordinator.get("context").get_messages()
        assert any(m["role"] == "tool" for m in history)
        assert json.loads((store.path / "checkpoint.json").read_text())["status"] == "ready"
        assert not host.children.active
    finally:
        release.set()
        await host.close()
    restored = SessionHost(ConversationStore(tmp_path / "state", {}, store.identity))
    try:
        await restored.open(value, report, tmp_path)
        assert restored.ready
        assert await restored.session.coordinator.get("context").get_messages() == history
        assert not restored.session.coordinator.get("providers")["fixture"].calls
    finally:
        await restored.close()


@pytest.mark.parametrize("force", [False, True])
async def test_nested_parallel_children_resolve_upward_or_force_join(
    prepared, tmp_path, monkeypatch, force
):
    bridge, events = await bridge_for(prepared, tmp_path, tmp_path)
    host = bridge.host
    gates = {name: asyncio.Event() for name in ("sibling", "grandchild")}
    entered, finished, cancelled, providers = set(), [], [], {}
    register = host.children.register
    complete = type(host.session.coordinator.get("providers")["fixture"]).complete

    async def observed(self, *args, **kwargs):
        providers[self.coordinator.session_id] = self
        return await complete(self, *args, **kwargs)

    monkeypatch.setattr(
        type(host.session.coordinator.get("providers")["fixture"]), "complete", observed
    )

    def register_tree(session):
        identity = session.session_id
        label = (
            "root"
            if identity == host.session_id
            else host.children.records[identity]["instruction"]
        )

        async def execute(arguments):
            entered.add(label)
            try:
                if label == "root":
                    await asyncio.gather(
                        *(
                            host.children.spawn("probe", name, session, {"probe": {}})
                            for name in ("branch", "sibling")
                        )
                    )
                elif label == "branch":
                    await host.children.spawn("probe", "grandchild", session, {"probe": {}})
                else:
                    await gates[label].wait()
                finished.append(label)
                return ToolResult(success=True, output=f"{label} current result")
            except asyncio.CancelledError:
                cancelled.append(label)
                raise

        session.coordinator.get("tools")["fixture_probe"].execute = execute
        register(session)

    monkeypatch.setattr(host.children, "register", register_tree)
    register_tree(host.session)
    try:
        assert host.submit("Nested controlled delegation")[0]
        await until(lambda: entered == {"root", "branch", "sibling", "grandchild"})
        sessions = list(host.children.active.values())
        assert len(sessions) == 3
        # Verify the public token links, not merely the app's flat fallback loop.
        host.session.coordinator.cancellation.request_graceful()
        assert all(s.coordinator.cancellation.is_graceful for s in sessions)
        assert bridge.command({"op": "stop"})[0]
        assert host.stop_stage == "graceful"
        assert all(s.coordinator.cancellation.is_graceful for s in sessions)
        await asyncio.sleep(0.35)
        assert not host.task.done() and not cancelled and not finished
        assert any(e.get("cancellation") == "graceful" for e in events)
        if force:
            assert bridge.command({"op": "stop"})[0]
            assert host.stop_stage == "immediate"
            assert all(s.coordinator.cancellation.is_immediate for s in sessions)
        else:
            gates["grandchild"].set()
            await until(lambda: "branch" in finished)
            assert not host.task.done() and not cancelled
            assert finished.index("grandchild") < finished.index("branch")
            assert all(s.coordinator.cancellation.is_graceful for s in sessions)
            gates["sibling"].set()
        assert await asyncio.wait_for(host.task, 5) == "interrupted"
        assert not host.children.active and not host.children.tasks
        assert all(r["status"] == "interrupted" for r in host.children.records.values())
        assert all(len(p.calls) == 1 for p in providers.values())
        assert len(providers) == 4
        if force:
            assert set(cancelled) == {"root", "branch", "sibling", "grandchild"}
        else:
            assert not cancelled and finished[-1] == "root"
            assert (
                json.loads((host.store.path / "checkpoint.json").read_text())["status"] == "ready"
            )
        rows = [
            json.loads(line) for line in (host.store.path / "events.jsonl").read_text().splitlines()
        ]
        assert sum(r["kind"] == "turn.ended" for r in rows) == 1
    finally:
        for gate in gates.values():
            gate.set()
        await bridge.close()


async def test_graceful_during_child_initialization_does_not_start_model(
    prepared, tmp_path, monkeypatch
):
    from amplifier_tui import composition

    bridge, _ = await bridge_for(prepared, tmp_path, tmp_path)
    host = bridge.host
    entered, release = asyncio.Event(), asyncio.Event()
    original = composition.create_owned_session
    created = []

    async def delayed(*args, **kwargs):
        session = await original(*args, **kwargs)
        created.append(session)
        entered.set()
        await release.wait()
        return session

    monkeypatch.setattr(composition, "create_owned_session", delayed)

    async def delegate(arguments):
        result = await host.children.spawn("probe", "Delayed child", host.session, {"probe": {}})
        assert result["metadata"]["status"] == "cancelled"
        return ToolResult(success=True, output=result["output"])

    host.session.coordinator.get("tools")["fixture_probe"].execute = delegate
    host.children.register(host.session)
    try:
        host.submit("Initialize a controlled child")
        await asyncio.wait_for(entered.wait(), 5)
        assert bridge.command({"op": "stop"})[0]
        release.set()
        assert await asyncio.wait_for(host.task, 5) == "interrupted"
        assert not created[0].coordinator.get("providers")["fixture"].calls
        assert not host.children.active
        assert json.loads((host.store.path / "checkpoint.json").read_text())["status"] == "ready"
    finally:
        release.set()
        await bridge.close()


@pytest.mark.parametrize("boundary", ["policy", "late_approval", "stream"])
async def test_stop_at_async_policy_or_stream_boundary(host, monkeypatch, boundary):
    from amplifier_core import HookResult

    entered, release = asyncio.Event(), asyncio.Event()
    coordinator = host.session.coordinator
    tool = coordinator.get("tools")["fixture_probe"]
    provider = coordinator.get("providers")["fixture"]
    finished = []

    if boundary == "policy":

        async def policy(event, data):
            entered.set()
            await release.wait()
            return HookResult()

        coordinator.hooks.register("tool:pre", policy, priority=50, name="controlled-wait")
    elif boundary == "late_approval":

        async def execute(self, arguments):
            entered.set()
            await release.wait()
            answer = await coordinator.approval_system.request_approval(
                "Late approval", ["allow", "deny"], 30, "allow"
            )
            assert answer == "deny"
            finished.append(answer)
            return ToolResult(success=False, error={"message": "Denied"})

        monkeypatch.setattr(type(tool), "execute", execute)
    else:

        async def stream(self, request, **kwargs):
            self.calls.append(request)
            yield {"content": "Partial stream "}
            entered.set()
            await release.wait()
            yield {"content": "completed gracefully."}
            finished.append("stream")

        monkeypatch.setattr(type(provider), "stream", stream, raising=False)
    try:
        host.submit("Controlled boundary")
        await asyncio.wait_for(entered.wait(), 5)
        host.stop(immediate=False)
        release.set()
        assert await asyncio.wait_for(host.task, 5) == "interrupted"
        assert tool.calls == 0 and len(provider.calls) == 1
        assert not host._pending
        if boundary == "stream":
            assert finished == ["stream"]
            assert "Partial stream completed gracefully." in str(
                await coordinator.get("context").get_messages()
            )
        elif boundary == "late_approval":
            assert finished == ["deny"]
    finally:
        release.set()


@pytest.mark.parametrize("child", [False, True])
async def test_graceful_intent_does_not_hide_a_reported_failure(host, monkeypatch, child):
    entered, release = asyncio.Event(), asyncio.Event()
    module = host.session.coordinator.get("orchestrator").module

    async def failed(self, prompt, context, providers, tools, hooks, coordinator):
        await context.add_message({"role": "user", "content": prompt})
        entered.set()
        await release.wait()
        await hooks.emit("orchestrator:complete", {"status": "error"})
        return "Controlled reported failure"

    monkeypatch.setattr(type(module), "execute", failed)
    if child:
        task = asyncio.create_task(
            host.children.spawn("probe", "Controlled failure", host.session, {"probe": {}})
        )
    else:
        host.submit("Controlled failure")
        task = host.task
    try:
        await asyncio.wait_for(entered.wait(), 5)
        if child:
            host.session.coordinator.cancellation.request_graceful()
        else:
            host.stop(immediate=False)
        release.set()
        if child:
            with pytest.raises(RuntimeError, match="did not complete: error"):
                await asyncio.wait_for(task, 5)
            assert [r["status"] for r in host.children.records.values()] == ["failed"]
        else:
            assert await asyncio.wait_for(task, 5) == "failed"
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)


async def test_force_during_graceful_checkpoint_does_not_cancel_its_owner(
    prepared, tmp_path, monkeypatch
):
    bridge, _ = await bridge_for(prepared, tmp_path, tmp_path)
    host = bridge.host
    entered, release = asyncio.Event(), asyncio.Event()
    context = host.session.coordinator.get("context")
    original = context.get_messages

    async def checkpoint():
        if host._finalizing:
            entered.set()
            await release.wait()
        return await original()

    monkeypatch.setattr(context, "get_messages", checkpoint)
    tool = host.session.coordinator.get("tools")["fixture_probe"]
    tool.config["delay"] = 0.1
    try:
        host.submit("Stop before owned checkpoint")
        await until(lambda: tool.calls == 1)
        assert bridge.command({"op": "stop"})[0]
        await asyncio.wait_for(entered.wait(), 5)
        assert bridge.command({"op": "stop"})[0]
        assert host.stop_stage == "immediate"
        assert not host.task.done() and not host.task.cancelling()
        assert bridge.command({"op": "stop"})[0]
        release.set()
        assert await asyncio.wait_for(host.task, 5) == "interrupted"
        assert json.loads((host.store.path / "checkpoint.json").read_text())["status"] == "ready"
    finally:
        release.set()
        await bridge.close()

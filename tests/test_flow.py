"""Continuous work/accounting: synthetic observations over real session execution."""

import asyncio
import copy
import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from test_navigation import bridge_for
from test_runtime_controls import correction, records, wait_for

from amplifier_tui.events import Event, Transcript
from amplifier_tui.inspection import CallUsage, call_usage_text, usage_values


async def test_observed_model_phases_are_transient_scoped_and_cleared(
    prepared, tmp_path, monkeypatch
):
    bridge, frames = await bridge_for(prepared, tmp_path, tmp_path)
    try:
        host = bridge.host
        provider = host.session.coordinator.get("providers")["fixture"]
        original = type(provider).complete
        phases = []

        async def complete(self, request, **kwargs):
            hooks = self.coordinator.hooks
            # Exercise actual core dispatch into the host, not its callback alone.
            await hooks.emit("llm:request", {})
            phases.append(host.model_activity)
            for event, data in (
                ("llm:stream_block_start", {"block_type": "thinking", "block_index": 5}),
                ("llm:stream_block_end", {"block_type": "thinking", "block_index": 5}),
                ("llm:stream_block_start", {"block_type": "text", "block_index": 6}),
            ):
                await hooks.emit(event, data)
                phases.append(host.model_activity)
            return await original(self, request, **kwargs)

        monkeypatch.setattr(type(provider), "complete", complete)
        assert bridge.command(
            {"op": "submit", "text": "Controlled observed phases", "session_id": host.session_id}
        )[0]
        await asyncio.wait_for(host.task, 10)
        await asyncio.sleep(0)
        assert phases[:4] == ["Waiting for model", "Thinking", "", "Responding"]
        activity = [v for v in frames if v["type"] == "model_activity"]
        assert activity and activity[-1]["phase"] == ""
        assert all(
            v["session_id"] == host.session_id and v["turn_id"] == host.turn_id for v in activity
        )
        assert not any(e["kind"] == "model_activity" for e in records(host))
        # Same phase coalesces; neither child nor naming can replace foreground.
        before = len(frames)
        await host._observe("llm:request", {"session_id": "foreign-child"})
        assert len(frames) == before
        host.activity("Thinking")
        host.activity("Thinking")
        assert len(frames) == before + 1
        host.activity("")
        # Switching invalidates callbacks from the previous host instance.
        assert bridge.command(
            {
                "op": "switch",
                "target": "new",
                "draft": "",
                "request_id": "phase-switch",
                "session_id": host.session_id,
            }
        )[0]
        await bridge.switch_task
        before = len(frames)
        host.activity("Obsolete")
        assert len(frames) == before
    finally:
        await bridge.close()


async def test_host_waits_for_provider_budget_before_first_turn(host, monkeypatch):
    provider = host.session.coordinator.get("providers")["fixture"]
    started, release = asyncio.Event(), asyncio.Event()
    probes = []

    # Like a native token-count capability: a synchronous method returns a
    # coroutine. The real core/loop must await it, not validate the coroutine.
    def request_budget(request, *, context_estimate):
        async def count():
            probes.append(request)
            started.set()
            await release.wait()
            return {
                "estimated_input_tokens": 10,
                "input_limit_tokens": 100_000,
                "context_token_budget": context_estimate,
            }

        return count()

    monkeypatch.setattr(provider, "request_budget", request_budget, raising=False)
    assert host.submit("Controlled budget check")[0]
    try:
        await asyncio.wait_for(started.wait(), 2)
        assert not host.task.done()
        assert provider.calls == []
        release.set()
        assert await asyncio.wait_for(host.task, 5) == "completed"
        assert len(probes) >= 1
        assert provider.calls
    finally:
        release.set()


async def test_correction_waits_but_stop_interrupts_cooperative_tool(prepared, tmp_path):
    bridge, _ = await bridge_for(prepared, tmp_path, tmp_path)
    try:
        host = bridge.host
        tool = host.session.coordinator.get("tools")["fixture_probe"]
        tool.config["delay"] = 30
        assert host.submit("Controlled long tool")[0]
        await wait_for(lambda: tool.calls == 1)
        assert bridge.command(correction(host))[0]
        await asyncio.sleep(0.05)
        assert [
            e["payload"]["status"] for e in records(host) if e["kind"] == "steering.updated"
        ] == ["pending"]
        host.store.save_draft("Keep this draft")
        assert bridge.command({"op": "stop", "session_id": host.session_id})[0]
        assert host.stop_stage == "graceful" and not host.task.done()
        assert bridge.command({"op": "stop", "session_id": host.session_id})[0]
        assert await asyncio.wait_for(host.task, 3) == "interrupted"
        assert host.store.draft == "Keep this draft"
        assert [
            e["payload"]["status"] for e in records(host) if e["kind"] == "steering.updated"
        ] == ["pending", "unconfirmed"]
    finally:
        await bridge.close()


@pytest.mark.parametrize("manual,switch", [(False, False), (True, False), (False, True)])
async def test_real_naming_hook_background_accounting_and_manual_rename(
    prepared, tmp_path, monkeypatch, manual, switch
):
    from amplifier_core import ChatResponse, TextBlock

    from amplifier_tui.conversations import ConversationStore
    from amplifier_tui.host import SessionHost

    bundle, report = prepared
    bundle = copy.copy(bundle)
    bundle.mount_plan = copy.deepcopy(bundle.mount_plan)
    workspace = Path(
        os.environ.get("AMPLIFIER_TUI_SOURCE_ROOT", Path(__file__).resolve().parents[2])
    )
    module = workspace / "amplifier-foundation/modules/hooks-session-naming"
    bundle.mount_plan.setdefault("hooks", []).append(
        {
            "module": "hooks-session-naming",
            "source": module.as_uri(),
            "config": {"initial_trigger_turn": 2, "model_role": None},
        }
    )
    prepared = bundle, report
    bridge, frames = await bridge_for(prepared, tmp_path, tmp_path)
    gate, started = asyncio.Event(), asyncio.Event()
    try:
        if switch:
            old = bridge.host
            assert bridge.command(
                {
                    "op": "switch",
                    "target": "new",
                    "draft": "",
                    "request_id": "new-for-naming",
                    "session_id": old.session_id,
                }
            )[0]
            await bridge.switch_task
            assert bridge.host is not old
            before = len(frames)
            old.background("Obsolete host")
            old.title_callback("Obsolete title")
            assert len(frames) == before
        host = bridge.host
        provider = host.session.coordinator.get("providers")["fixture"]
        original = type(provider).complete

        async def complete(self, request, **kwargs):
            if (getattr(request, "metadata", None) or {}).get("stream") is not False:
                return await original(self, request, **kwargs)
            await self.coordinator.hooks.emit("llm:request", {"model": "fixture-namer"})
            started.set()
            await gate.wait()
            # Public utility events must not change the foreground request or
            # leak utility text into the conversation, even with a late stream.
            await self.coordinator.hooks.emit(
                "llm:stream_block_delta",
                {"block_index": 0, "block_type": "text", "text": "UTILITY-ONLY"},
            )
            await self.coordinator.hooks.emit(
                "llm:response",
                {
                    "provider": "fixture",
                    "model": "fixture-namer",
                    "duration_ms": 25,
                    "usage": {"input_tokens": 30, "output_tokens": 12, "cost_usd": "0.07"},
                },
            )
            return ChatResponse(
                content=[
                    TextBlock(
                        text=json.dumps(
                            {
                                "action": "set",
                                "name": "Organize release notes",
                                "description": "Controlled naming fixture",
                            }
                        )
                    )
                ]
            )

        monkeypatch.setattr(type(provider), "complete", complete)
        for text in ("Hello", "Organize the release notes"):
            assert host.submit(text)[0]
            await host.task
        await asyncio.wait_for(started.wait(), 3)
        await wait_for(lambda: any(f.get("phase") == "Naming conversation" for f in frames))
        request_index = host._request_index
        if manual:
            assert bridge.command(
                {"op": "rename", "text": "My chosen name", "session_id": host.session_id}
            )[0]
        gate.set()
        sidecar = host.store.path / "naming/metadata.json"
        await wait_for(
            lambda: json.loads(sidecar.read_text()).get("name") == "Organize release notes"
        )
        expected = "My chosen name" if manual else "Organize release notes"
        assert host.store.metadata["title"] == expected
        assert host._request_index == request_index
        journal = records(host)
        assert not any("UTILITY-ONLY" in str(e) for e in journal)
        calls = [e for e in journal if e["payload"].get("usage_scope") == "session"]
        assert len(calls) == 1 and "session-only" in calls[0]["payload"]["text"]
        assert host.call_usage.session["totals"]["cost_usd"] == Decimal("0.07")
        assert host.call_usage.turn["requests"] == 0
        assert host.store.saved["sequence"] == len(journal)
        identity, launch = host.session_id, host.store.metadata["launch"]
        assert any(f.get("type") == "title" and f.get("text") == expected for f in frames)
    finally:
        gate.set()
        await bridge.close()
    restored = SessionHost(ConversationStore(tmp_path, launch, identity))
    try:
        await restored.open(*prepared, tmp_path)
        assert restored.store.metadata["title"] == expected
        assert restored.call_usage.session["totals"]["cost_usd"] == Decimal("0.07")
        assert restored.session.coordinator.get("providers")["fixture"].calls == []
    finally:
        await restored.close()


def test_cache_aliases_formatting_and_unknowns():
    values = usage_values(
        {
            "input_tokens": 7,
            "cache_write_tokens": 12000,
            "cache_read_tokens": 0,
            "output_tokens": 81,
            "cost_usd": "0.125",
        }
    )
    text = call_usage_text(
        values,
        {"provider": "test", "model": "model-a", "basis": "pinned"},
        duration_ms=2300,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    assert "Input: 12,007 (caching)" in text and "Total: 12,088" in text
    assert "test/model-a · pinned · 2.3s" in text and "2026-01-01" in text
    assert "not billing" not in text
    assert usage_values({"cache_read_input_tokens": 20, "cache_read_tokens": 30}) == {
        "cache_read_input_tokens": 20
    }
    text = call_usage_text(usage_values({"input_tokens": 100, "cache_read_tokens": 25}), {})
    assert "100 (25% cached)" in text and "Total: not reported" in text


def test_late_naming_usage_does_not_reset_the_new_turn():
    ledger = CallUsage()
    ledger.add("first", "turn-1", {"cost_usd": "0.10"})
    ledger.add("next", "turn-2", {"cost_usd": "0.20"})
    ledger.add("namer", "turn-1", {"cost_usd": "0.03"}, session_only=True)
    assert ledger.turn_id == "turn-2"
    assert ledger.costs() == "Turn: $0.20 · Session: $0.33"


def test_working_totals_reset_cache_semantics_partial_and_utility_scope():
    ledger = CallUsage()
    assert ledger.progress("new")["turn"] == {
        "calls": 0,
        "tokens": None,
        "tokens_partial": False,
        "cost": "pending",
    }
    values = {
        "input_tokens": 100,
        "output_tokens": 20,
        "cache_read_tokens": 90,
        "cache_write_tokens": 30,
        "cost_usd": "0.004",
    }
    ledger.add("root", "turn", values)
    assert ledger.progress("turn")["turn"]["tokens"] == 150  # reads aren't added twice
    assert ledger.progress("turn")["turn"]["cost"] == "<$0.01"
    ledger.add("child", "turn", values)
    assert not ledger.add("child", "turn", values)
    ledger.add("naming", "old-turn", {"cost_usd": "1"}, session_only=True)
    summary = ledger.progress("turn")
    assert summary["turn"]["tokens"] == 300 and summary["turn"]["calls"] == 2
    assert summary["session"]["cost"] == "$1.01"
    assert ledger.progress("next")["turn"]["tokens"] is None
    assert ledger.progress("next")["session"] == summary["session"]
    ledger.add("unknown", "turn", {"input_tokens": 5})
    summary = ledger.progress("turn")
    assert summary["turn"]["tokens"] == 305 and summary["turn"]["tokens_partial"]
    assert summary["turn"]["cost"] == "<$0.01 (partial)"
    assert summary["session"]["cost"] == "$1.01 (partial)"
    ledger.legacy = True
    assert ledger.progress("turn")["earlier_usage_unavailable"]
    json.dumps(summary)  # no Decimal crosses the frontend boundary


async def test_active_turn_metrics_during_quiet_tool_reset_and_restore(prepared, tmp_path):
    from amplifier_tui.conversations import ConversationStore
    from amplifier_tui.host import SessionHost

    bridge, frames = await bridge_for(prepared, tmp_path, tmp_path)
    host = bridge.host
    identity, launch = host.session_id, host.store.metadata["launch"]
    try:
        host.session.coordinator.get("tools")["fixture_probe"].config["delay"] = 30
        assert host.submit("Controlled metering turn")[0]
        await wait_for(
            lambda: any(
                f.get("type") == "turn_metrics" and f.get("turn_id") == host.turn_id for f in frames
            )
        )
        host._turn_started -= 125
        for key, cost, child in (
            ("root-call", "1.25", None),
            ("child-call", "2.50", "controlled-child"),
        ):
            host.observe_usage(
                key,
                {"usage": {"input_tokens": 100, "output_tokens": 10, "cost_usd": cost}},
                {},
                child_id=child,
            )
        host.observe_usage("naming-call", {"usage": {"cost_usd": "0.05"}}, {}, session_only=True)
        await wait_for(
            lambda: any(
                f.get("type") == "turn_metrics" and f["session"]["cost"] == "$3.80" for f in frames
            )
        )
        meter = [f for f in frames if f.get("type") == "turn_metrics"][-1]
        assert meter["turn"]["tokens"] == 220 and meter["turn"]["cost"] == "$3.75"
        assert meter["elapsed_seconds"] >= 125
        before = host.sequence
        bridge.turn_metrics()
        assert host.sequence == before  # transient; does not become transcript/history
        host.stop()
        await host.task
        host.session.coordinator.get("tools")["fixture_probe"].config["delay"] = 0.1
        assert host.submit("Next controlled turn")[0]
        await wait_for(
            lambda: any(
                f.get("type") == "turn_metrics" and f.get("turn_id") == host.turn_id for f in frames
            )
        )
        meter = [f for f in frames if f.get("type") == "turn_metrics"][-1]
        assert meter["elapsed_seconds"] < 5
        assert meter["turn"]["tokens"] is None and meter["turn"]["cost"] == "pending"
        assert meter["session"]["cost"] == "$3.80"
        assert await host.task == "completed"
    finally:
        await bridge.close()
    restored = SessionHost(ConversationStore(tmp_path, launch, identity))
    try:
        await restored.open(*prepared, tmp_path)
        assert restored.call_usage.progress("next")["session"]["cost"] == "$3.80"
        assert restored.call_usage.progress("next")["turn"]["cost"] == "pending"
        assert not restored.session.coordinator.get("providers")["fixture"].calls
    finally:
        await restored.close()


def test_auxiliary_checkpoint_does_not_make_uncertain_work_resumable(tmp_path):
    from amplifier_tui.conversations import ConversationStore

    launch = {"fixture": True}
    store = ConversationStore(tmp_path, launch)
    identity = store.identity
    messages = [{"role": "user", "content": "Keep canonical context"}]
    try:
        store.checkpoint(messages, 0, {"fixture": "controlled"}, False)
        store.record(
            Event(identity, 1, "turn-1", "display.message", "utility", {"text": "Session: $0.03"})
        )
        store.checkpoint_auxiliary(1)
        assert store.saved["messages"] == messages
        assert store.saved["sequence"] == 1
        assert store.saved["status"] == "uncertain"
    finally:
        store.close()
    with pytest.raises(ValueError, match="uncertain/incomplete"):
        ConversationStore(tmp_path, launch, identity)


def test_usage_replay_deduplicates_children_and_marks_partial_costs():
    events = [
        Event("s", n, "t", "display.message", f"call-{n}", {"usage_call": values})
        for n, values in enumerate(({"cost_usd": "0.10"}, {"cost_usd": "0.20"}, {}))
    ]
    ledger = CallUsage(events + events)
    assert ledger.session["requests"] == 3
    assert ledger.session["totals"]["cost_usd"] == Decimal("0.30")
    assert ledger.costs() == "Turn: $0.30 (partial) · Session: $0.30 (partial)"
    ledger.add("next", "next-turn", {"cost_usd": "0.15"})
    assert ledger.costs() == "Turn: $0.15 · Session: $0.45 (partial)"


def test_usage_dedupe_window_is_bounded_without_losing_new_accounting():
    ledger = CallUsage()
    for index in range(CallUsage.MAX_SEEN * 4):
        assert ledger.add(f"call-{index}", "turn", {"cost_usd": "0.01"})
    assert len(ledger.seen) == CallUsage.MAX_SEEN
    assert ledger.session["requests"] == CallUsage.MAX_SEEN * 4
    assert not ledger.add(f"call-{CallUsage.MAX_SEEN * 4 - 1}", "turn", {})


def test_child_progress_cost_uses_a_decimal_host_aggregate():
    from amplifier_tui.children import Children

    payload = Children.progress_payload(
        [
            {"cost_usd": "0.105", "cost_partial": False},
            {"cost_usd": "0.2", "cost_partial": False},
        ]
    )
    assert payload["child_cost_usd"] == "0.305"
    assert payload["child_cost_display"] == "$0.30"
    assert not payload["child_cost_partial"]


async def test_retry_attempts_do_not_discard_success_usage_or_invent_pin(host):
    await host._observe("provider:request", {})
    await host._observe(
        "provider:resolve",
        {
            "scope": "conversation",
            "provider": "fixture",
            "model": "controlled",
            "basis": "priority",
        },
    )
    await host._observe("llm:request", {})
    await host._observe("llm:response", {"status": "error"})
    await host._observe("llm:request", {})
    await host._observe("llm:response", {"status": "ok", "usage": {"cost_usd": "0.12"}})
    assert host.call_usage.session["requests"] == 2
    assert host.call_usage.session["totals"]["cost_usd"] == Decimal("0.12")
    events = []
    while not host.events.empty():
        events.append(host.events.get_nowait())
    assert "pinned" not in str([e.payload.get("text") for e in events])
    assert CallUsage(events).costs() == host.call_usage.costs()
    legacy = CallUsage([Event("s", 1, "t", "context.observed", "old", {"event": "llm:response"})])
    assert "earlier usage unavailable" in legacy.costs()


async def test_overlapping_responses_are_distinct_without_iteration_or_request_ids(host):
    await host._observe("llm:request", {})
    await host._observe("llm:request", {})
    await host._observe("llm:response", {"usage": {"cost_usd": "0.03"}})
    await host._observe("llm:response", {"usage": {"cost_usd": "0.04"}})
    assert host.call_usage.session["requests"] == 2
    assert host.call_usage.session["totals"]["cost_usd"] == Decimal("0.07")


async def test_background_phases_are_transient_and_do_not_mutate_journal(host, tmp_path):
    from amplifier_tui.host import RuntimeBridge

    frames = []
    RuntimeBridge(host, None, frames.append, True, tmp_path)
    before = host.sequence
    host.background("Preparing controlled modules")
    host.background("")
    assert host.sequence == before
    assert [frame["phase"] for frame in frames] == ["Preparing controlled modules", ""]


async def test_four_concurrent_children_publish_progress_and_count_every_call(host, monkeypatch):
    provider = host.session.coordinator.get("providers")["fixture"]
    original = type(provider).complete

    async def metered(self, request, **kwargs):
        await self.coordinator.hooks.emit(
            "llm:request", {"provider": "fixture", "model": "controlled"}
        )
        response = await original(self, request, **kwargs)
        await self.coordinator.hooks.emit(
            "llm:response",
            {
                "provider": "fixture",
                "model": "controlled",
                "duration_ms": 100,
                "usage": {
                    "input_tokens": 10,
                    "cache_write_tokens": 20,
                    "output_tokens": 5,
                    "cost_usd": "0.01",
                },
            },
        )
        return response

    monkeypatch.setattr(type(provider), "complete", metered)
    tool = host.session.coordinator.get("tools")["fixture_probe"]

    async def delegate(arguments):
        results = await asyncio.gather(
            *(
                host.children.spawn("probe", f"Inspect area {n}", host.session, {"probe": {}})
                for n in range(4)
            )
        )
        return {"success": True, "output": str(len(results))}

    monkeypatch.setattr(tool, "execute", delegate)
    host.children.register(host.session)
    assert host.submit("Run four controlled delegates")[0]
    await asyncio.wait_for(host.task, 15)
    events = []
    while not host.events.empty():
        events.append(host.events.get_nowait())
    calls = [e for e in events if "usage_call" in e.payload]
    assert len(calls) == 10  # two root calls plus two calls per real child
    assert len({e.item_id for e in calls}) == 10
    assert sum(bool(e.payload.get("child_id")) for e in calls) == 8
    assert host.call_usage.costs() == "Turn: $0.10 · Session: $0.10"
    meter = host.call_usage.progress(host.turn_id)
    assert meter["turn"]["tokens"] == 350 and meter["turn"]["calls"] == 10
    assert meter["turn"]["cost"] == "$0.10" and meter["session"]["cost"] == "$0.10"
    progress = [e for e in events if e.kind == "tool.progress"]
    assert any(len(e.payload["child_progress"]) == 4 for e in progress)
    grouped = next(
        e.payload
        for e in progress
        if len(e.payload["child_progress"]) == 4 and e.payload["child_cost_display"]
    )
    assert grouped["child_cost_usd"] == "0.01"
    assert grouped["child_cost_display"] == "$0.01"
    assert grouped["child_cost_partial"]
    assert any("fixture_probe · running" in str(e.payload) for e in progress)
    transcript = Transcript()
    for e in events:
        transcript.apply(e)
    parent = transcript.items[progress[-1].item_id]
    assert parent.status == "succeeded" and parent.detail["arguments"]
    assert len(parent.detail["child_progress"]) == 4
    restored = CallUsage(events)
    assert restored.costs() == host.call_usage.costs()
    assert all("Total: 35" in e.payload["text"] for e in calls)

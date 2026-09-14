import asyncio
import hashlib

import pytest

from amplifier_tui.events import Transcript
from amplifier_tui.host import SessionHost


async def ending(host):
    events = []
    async with asyncio.timeout(5):
        while True:
            event = await host.events.get()
            events.append(event)
            if event.kind == "turn.ended":
                return events


async def test_real_kernel_round_trip_and_second_turn(host):
    assert host.submit("Compute a digest")[0]
    events = await ending(host)
    projection = Transcript()
    for event in events + events:
        projection.apply(event)
    tools = [item for item in projection.items.values() if item.kind == "tool"]
    texts = [item.text for item in projection.items.values() if item.kind == "assistant"]
    assert len(tools) == 1
    assert tools[0].status == "succeeded"
    assert (
        tools[0].detail["result"]["output"]["sha256"]
        == hashlib.sha256(b"fixture payload").hexdigest()
    )
    assert texts == ["Fixture round trip complete. Inspect the tool result for evidence."]
    assert events[-1].payload["status"] == "completed"
    assert [e.sequence for e in events] == list(range(1, len(events) + 1))
    assert sum(e.kind == "text.delta" for e in events) == 3
    first_id = host.turn_id
    assert host.submit("Again")[0]
    await ending(host)
    assert host.turn_id != first_id
    provider = host.session.coordinator.get("providers")["fixture"]
    assert len(provider.calls) == 4
    assert any(m.role == "assistant" for m in provider.calls[2].messages)


async def test_competing_submissions_are_rejected(host):
    assert host.submit("first")[0]
    accepted, reason = host.submit("correction")
    assert not accepted and "retained" in reason
    await ending(host)


async def test_failed_tool_survives_confident_answer(host):
    host.session.coordinator.get("tools")["fixture_probe"].config["fail"] = True
    host.submit("Compute")
    projection = Transcript()
    for event in await ending(host):
        projection.apply(event)
    assert next(i for i in projection.items.values() if i.kind == "tool").status == "failed"
    assert next(i for i in projection.items.values() if i.kind == "outcome").status == "completed"


async def test_provider_error_is_not_completion(host):
    host.session.coordinator.get("providers")["fixture"].config["raise_error"] = True
    host.submit("Fail")
    events = await ending(host)
    assert events[-1].payload["status"] == "failed"


async def test_missing_critical_mount_refuses_admission(prepared, tmp_path):
    value, report = prepared
    value.mount_plan["tools"][0]["config"] = {"skip_mount": True}
    host = SessionHost()
    with pytest.raises(RuntimeError, match="initialization reported a failure"):
        await host.open(value, report, tmp_path)
    assert not host.submit("Must not run")[0]
    assert host.session is None


async def test_cancel_and_stale_approval(host):
    tool = host.session.coordinator.get("tools")["fixture_probe"]
    tool.config["approval"] = True
    host.submit("Ask")
    async with asyncio.timeout(5):
        while True:
            request = await host.events.get()
            if request.kind == "approval.requested":
                break
    assert not host.answer("wrong-request", "allow")
    assert host.stop()
    events = await ending(host)
    assert events[-1].payload["status"] == "interrupted"
    assert not host.answer(request.item_id, "allow")
    assert tool.calls == 0


async def test_approval_allow_is_correlated_and_once(host):
    host.session.coordinator.get("tools")["fixture_probe"].config["approval"] = True
    host.submit("Ask")
    async with asyncio.timeout(5):
        while True:
            event = await host.events.get()
            if event.kind == "approval.requested":
                break
    assert not host.answer(event.item_id, "forever")
    assert host.answer(event.item_id, "allow")
    assert not host.answer(event.item_id, "allow")
    assert (await ending(host))[-1].payload["status"] == "completed"


async def test_unknown_completion_is_not_success(host):
    # A replacement orchestrator may return useful text without the optional
    # observed lifecycle schema. Exercise that compatibility boundary explicitly.
    async def execute(*args, **kwargs):
        return "A replacement response"

    host.session.coordinator.get("orchestrator").execute = execute
    host.submit("unknown")
    assert (await ending(host))[-1].payload["status"] == "unknown"


async def test_cancel_during_tool_preserves_partial_outcome(host):
    tool = host.session.coordinator.get("tools")["fixture_probe"]
    tool.config["delay"] = 10
    host.submit("slow")
    async with asyncio.timeout(5):
        while not tool.calls:
            await asyncio.sleep(0.01)
    host.stop()
    events = await ending(host)
    assert tool.calls == 1
    assert events[-1].payload["status"] == "interrupted"
    assert "nothing was undone" in events[-1].payload["message"]


async def test_stop_before_first_execution_step_still_ends(host):
    assert host.submit("Stop immediately")[0]
    assert host.stop()
    events = await ending(host)
    assert events[-1].payload["status"] == "interrupted"
    assert not host.session.coordinator.get("providers")["fixture"].calls
    assert sum(e.kind == "turn.ended" for e in events) == 1


async def test_close_before_first_execution_step_cleans_up(host):
    assert host.submit("Close immediately")[0]
    await host.close()
    assert host.session is None
    assert (await ending(host))[-1].payload["status"] == "interrupted"


async def test_failed_hook_refuses_readiness(prepared, tmp_path):
    value, report = prepared
    # Real loader failure, not a mocked success: the tool's protocol is invalid
    # when used as a hook. Other mounts would otherwise allow execution.
    value.mount_plan["hooks"] = [{**value.mount_plan["tools"][0], "module": "hooks-invalid"}]
    target = SessionHost()
    with pytest.raises(RuntimeError, match="initialization reported a failure"):
        await target.open(value, report, tmp_path)
    assert not target.ready and target.session is None


async def test_approval_timeout_denies_without_execution(host):
    assert await host.request_approval("Confirm?", ["allow", "deny"], 0.01, "allow") == "deny"
    assert not host._pending

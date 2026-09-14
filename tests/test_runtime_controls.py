"""Public controls exercised through the real loop, core, context and fixture modules."""

import asyncio
import copy
import json

import pytest
from test_navigation import bridge_for

from amplifier_tui.conversations import ConversationStore, atomic_json
from amplifier_tui.frontend_bridge import Admission
from amplifier_tui.host import SessionHost


async def wait_for(test):
    for _ in range(300):
        if test():
            return
        await asyncio.sleep(0.005)
    raise AssertionError("Expected runtime observation did not arrive")


def records(host):
    return [
        json.loads(line) for line in (host.store.path / "events.jsonl").read_text().splitlines()
    ]


def correction(host, text="Use this correction", **extra):
    return {
        "op": "steer",
        "text": text,
        "turn_id": host.turn_id,
        "session_id": host.session_id,
        **extra,
    }


def selection(host, name, **extra):
    return {
        "op": "provider_select",
        "provider": name,
        "session_id": host.session_id,
        "revision": host.controls.state["revision"],
        "current": host.controls.pin.current(),
        **extra,
    }


def multiple(prepared):
    bundle, report = prepared
    entry = copy.deepcopy(bundle.mount_plan["providers"][0])
    bundle.mount_plan["providers"] += [
        {
            **entry,
            "instance_id": "fixture-alternate",
            "config": {"default_model": "fixture-alternate", "priority": 200},
        },
        {**entry, "instance_id": "other-vendor", "config": {"vendor": "other", "priority": 300}},
    ]
    return bundle, report


async def test_correction_admission_insertion_and_resume_without_replay(prepared, tmp_path):
    bridge, _ = await bridge_for(prepared, tmp_path, tmp_path)
    try:
        host = bridge.host
        tool = host.session.coordinator.get("tools")["fixture_probe"]
        tool.config["delay"] = 0.15
        host.submit("Original work")
        assert not bridge.command(correction(host))[0]  # Upstream clears at start.
        await wait_for(lambda: tool.calls == 1)
        admission = Admission()
        request = correction(
            host,
            "Unique correction 🧭\nOnly this active turn",
            version=1,
            request_id="correction-1",
        )
        reply = admission.apply(request, bridge.command)
        assert reply["accepted"]
        assert admission.apply(request, bridge.command) == reply
        await host.task
        observations = [e for e in records(host) if e["kind"] == "steering.updated"]
        assert [e["payload"]["status"] for e in observations] == ["pending", "applied"]
        assert observations[0]["item_id"] == observations[1]["item_id"]
        assert len([e for e in records(host) if e["kind"] == "turn.accepted"]) == 1
        messages = await host.session.coordinator.get("context").get_messages()
        assert sum("Unique correction" in str(m) for m in messages) == 1
        identity, launch = host.session_id, host.store.metadata["launch"]
    finally:
        await bridge.close()
    restored = SessionHost(ConversationStore(tmp_path, launch, identity))
    try:
        await restored.open(*prepared, tmp_path)
        assert restored.session.coordinator.get("providers")["fixture"].calls == []
        projected = [i for i in restored.store.projection() if i["kind"] == "correction"]
        assert len(projected) == 1 and projected[0]["status"] == "applied"
    finally:
        await restored.close()


async def test_stale_bounded_and_stopped_corrections_never_queue(prepared, tmp_path):
    bridge, _ = await bridge_for(prepared, tmp_path, tmp_path)
    try:
        host = bridge.host
        host.session.coordinator.get("tools")["fixture_probe"].config["delay"] = 0.5
        host.submit("work")
        await wait_for(lambda: host._request_index)
        assert not bridge.command(correction(host, turn_id="stale"))[0]
        assert not bridge.command(correction(host, session_id="stale"))[0]
        assert not bridge.command(correction(host, "x" * 65537))[0]
        assert bridge.command(correction(host))[0]
        bridge.command({"op": "stop"})
        assert not bridge.command(correction(host))[0]
        await host.task
        assert bridge.followups.rows == []
        assert [
            e["payload"]["status"] for e in records(host) if e["kind"] == "steering.updated"
        ] == ["pending", "unconfirmed"]
    finally:
        await bridge.close()


async def test_final_stream_correction_continues_same_turn_and_is_not_duplicated(
    prepared, tmp_path
):
    bridge, _ = await bridge_for(prepared, tmp_path, tmp_path)
    try:
        host = bridge.host
        host.submit("first")
        await wait_for(lambda: bool(host.blocks))
        assert bridge.command(correction(host, "Final stream marker"))[0]
        await host.task
        assert [
            e["payload"]["status"] for e in records(host) if e["kind"] == "steering.updated"
        ] == ["pending", "applied"]
        assert len([e for e in records(host) if e["kind"] == "turn.accepted"]) == 1
        host.submit("second")
        await host.task
        messages = await host.session.coordinator.get("context").get_messages()
        assert sum("Final stream marker" in str(m) for m in messages) == 1
    finally:
        await bridge.close()


async def test_provider_failure_leaves_pending_correction_unconfirmed(prepared, tmp_path):
    bridge, _ = await bridge_for(prepared, tmp_path, tmp_path)
    try:
        host = bridge.host
        host.session.coordinator.get("providers")["fixture"].config.update(
            delay=0.2, raise_error=True
        )
        host.submit("will fail")
        await wait_for(lambda: bool(host._request_index))
        assert bridge.command(correction(host))[0]
        await host.task
        assert [
            e["payload"]["status"] for e in records(host) if e["kind"] == "steering.updated"
        ] == ["pending", "unconfirmed"]
        assert bridge.followups.rows == []
    finally:
        await bridge.close()


async def test_provider_pin_executed_restored_and_guarded(prepared, tmp_path):
    prepared = multiple(prepared)
    bridge, _ = await bridge_for(prepared, tmp_path, tmp_path)
    try:
        host = bridge.host
        providers = host.session.coordinator.get("providers")
        assert set(host.controls.pin.available()) == {
            "fixture",
            "fixture-alternate",
            "other-vendor",
        }
        assert not bridge.command(selection(host, "other-vendor"))[0]
        assert host.ready and host.controls.pin.current() is None
        request = selection(host, "fixture-alternate", request_id="choose-alternate")
        assert bridge.command(request)[0]
        assert bridge.followups.paused
        assert not bridge.command(request)[0]  # Stale menu revision.
        assert all(not p.calls for p in providers.values())
        host.submit("Use the alternate")
        assert not bridge.command(selection(host, None))[0]
        await host.task
        assert providers["fixture-alternate"].calls and not providers["fixture"].calls
        identity, launch = host.session_id, host.store.metadata["launch"]
    finally:
        await bridge.close()
    restored = SessionHost(ConversationStore(tmp_path, launch, identity))
    try:
        await restored.open(*prepared, tmp_path)
        assert restored.controls.pin.current() == "fixture-alternate"
        assert all(not p.calls for p in restored.session.coordinator.get("providers").values())
        assert restored.controls.select(selection(restored, None))[0]
        assert restored.controls.pin.current() is None
    finally:
        await restored.close()


@pytest.mark.parametrize("damage", ["pending", "missing", "corrupt"])
async def test_invalid_provider_state_refuses_resume(prepared, tmp_path, damage):
    bridge, _ = await bridge_for(prepared, tmp_path, tmp_path)
    host = bridge.host
    identity, launch, path = host.session_id, host.store.metadata["launch"], host.controls.path
    await bridge.close()
    if damage == "missing":
        path.unlink()
    elif damage == "pending":
        value = json.loads(path.read_text())
        atomic_json(path, {**value, "status": "pending"})
    else:
        atomic_json(path, {"version": 99})
    restored = SessionHost(ConversationStore(tmp_path, launch, identity))
    with pytest.raises(ValueError, match="controls"):
        await restored.open(*prepared, tmp_path)
    assert not restored.ready and restored.session is None


async def test_failed_final_provider_save_disables_session(prepared, tmp_path, monkeypatch):
    bridge, _ = await bridge_for(multiple(prepared), tmp_path, tmp_path)
    try:
        host = bridge.host
        original = atomic_json
        calls = 0

        def fail_final(path, value):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("deliberate final save failure")
            original(path, value)

        monkeypatch.setattr("amplifier_tui.runtime_controls.atomic_json", fail_final)
        assert not bridge.command(selection(host, "fixture-alternate"))[0]
        assert not host.ready
        assert json.loads(host.controls.path.read_text())["status"] == "pending"
        assert not host.submit("must not execute")[0]
    finally:
        await bridge.close()


async def test_unsupported_controls_are_not_simulated(host):
    host.controls.pin = None
    host.controls.steer_cap = None
    assert not host.controls.catalog()["supported"]
    assert not host.controls.select({})[0]
    assert not host.controls.steer({"text": "correction"})[0]


async def test_correction_limit_and_foreign_insertion_cannot_mark_applied(prepared, tmp_path):
    bridge, _ = await bridge_for(prepared, tmp_path, tmp_path)
    try:
        host = bridge.host
        host.session.coordinator.get("tools")["fixture_probe"].config["delay"] = 0.5
        host.submit("active")
        await wait_for(lambda: bool(host._request_index))
        for index in range(20):
            assert bridge.command(correction(host, f"Correction {index}"))[0]
        assert not bridge.command(correction(host, "Overflow"))[0]
        wire = next(iter(host.controls.pending))
        await host._observe(
            "orchestrator:steering_injected", {"session_id": "another-session", "content": wire}
        )
        assert len(host.controls.pending) == 20
        bridge.command({"op": "stop"})
        await host.task
        assert {
            e["payload"]["status"] for e in records(host) if e["kind"] == "steering.updated"
        } == {"pending", "unconfirmed"}
    finally:
        await bridge.close()

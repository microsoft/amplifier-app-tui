"""Actual Foundation/core turns; durable queue boundaries and local metadata."""

import asyncio
import json

import pytest
from test_navigation import bridge_for

from amplifier_tui.conversations import atomic_json
from amplifier_tui.followups import Followups
from amplifier_tui.frontend_bridge import Admission


async def settled(bridge):
    for _ in range(200):
        await asyncio.sleep(0.01)
        if (not bridge.host.task or bridge.host.task.done()) and not any(
            r["state"] == "dispatched" for r in bridge.followups.rows
        ):
            return
    raise AssertionError("Follow-ups did not settle")


def texts(host):
    return [
        json.loads(line)["payload"]["text"]
        for line in (host.store.path / "events.jsonl").read_text().splitlines()
        if json.loads(line)["kind"] == "turn.accepted"
    ]


async def test_queue_runs_sequentially_with_identified_admission(prepared, tmp_path):
    bridge, events = await bridge_for(prepared, tmp_path, tmp_path)
    try:
        bridge.host.session.coordinator.get("tools")["fixture_probe"].config["delay"] = 0.1
        assert bridge.command({"op": "submit", "text": "first"})[0]
        for text in ("second", "third"):
            assert bridge.command({"op": "queue", "text": text})[0]
        assert texts(bridge.host) == ["first"]
        await settled(bridge)
        assert texts(bridge.host) == ["first", "second", "third"]
        assert bridge.followups.rows == []
        assert bridge.host.session.coordinator.get("tools")["fixture_probe"].calls == 3
        accepted = [e for e in events if e.get("kind") == "user"]
        assert len({e["input_id"] for e in accepted[1:]}) == 2
    finally:
        await bridge.close()


async def test_stop_holds_waiting_inputs_before_execution_starts(prepared, tmp_path):
    bridge, _ = await bridge_for(prepared, tmp_path, tmp_path)
    try:
        bridge.command({"op": "submit", "text": "first"})
        bridge.command({"op": "queue", "text": "never automatically run"})
        assert bridge.command({"op": "stop"})[0]
        await settled(bridge)
        assert bridge.followups.paused
        assert texts(bridge.host) == ["first"]
        assert bridge.followups.rows[0]["text"] == "never automatically run"
        assert bridge.host.session.coordinator.get("tools")["fixture_probe"].calls == 0
    finally:
        await bridge.close()


async def test_pause_remove_run_and_restore_do_not_replay(prepared, tmp_path):
    bridge, _ = await bridge_for(prepared, tmp_path, tmp_path)
    try:
        bridge.command({"op": "queue_pause"})
        bridge.command({"op": "queue", "text": "remove me"})
        identity = bridge.followups.rows[0]["id"]
        assert bridge.command({"op": "queue_remove", "id": identity})[0]
        assert not bridge.command({"op": "queue_remove", "id": identity})[0]
        bridge.command({"op": "queue", "text": "retained"})
        original = bridge.host.session_id
        bridge.command({"op": "switch", "target": "new", "draft": "scratch", "request_id": "s1"})
        await bridge.switch_task
        assert bridge.followups.rows == []
        bridge.command(
            {
                "op": "switch",
                "target": original,
                "draft": "",
                "request_id": "s2",
                "session_id": bridge.host.session_id,
            }
        )
        await bridge.switch_task
        assert bridge.followups.paused and bridge.followups.rows[0]["text"] == "retained"
        assert bridge.host.session.coordinator.get("providers")["fixture"].calls == []
        assert bridge.command({"op": "queue_run", "session_id": original})[0]
        await settled(bridge)
        assert texts(bridge.host) == ["retained"]
    finally:
        await bridge.close()


async def test_queue_is_bounded_and_failed_write_does_not_admit(prepared, tmp_path, monkeypatch):
    bridge, _ = await bridge_for(prepared, tmp_path, tmp_path)
    try:
        bridge.command({"op": "queue_pause"})
        for _ in range(20):
            assert bridge.command({"op": "queue", "text": "pending"})[0]
        assert not bridge.command({"op": "queue", "text": "overflow"})[0]
        assert not bridge.command({"op": "queue", "text": "x" * 65537})[0]
        assert texts(bridge.host) == []

        def fail(*args):
            raise OSError("deliberate storage failure")

        monkeypatch.setattr("amplifier_tui.followups.atomic_json", fail)
        with pytest.raises(OSError):
            bridge.command({"op": "queue_remove", "id": bridge.followups.rows[0]["id"]})
        assert len(bridge.followups.rows) == 20
    finally:
        await bridge.close()


async def test_dispatched_uncertainty_is_never_automatically_retried(prepared, tmp_path):
    bridge, _ = await bridge_for(prepared, tmp_path, tmp_path)
    try:
        queue = bridge.followups
        queue.save([{"id": "uncertain", "text": "possibly admitted", "state": "dispatched"}])
        restored = Followups(bridge.host, lambda value: None)
        restored.advance()
        assert restored.paused
        assert not restored.command({"op": "queue_run"})[0]
        assert texts(bridge.host) == []
    finally:
        await bridge.close()


async def test_rename_preserves_identity_and_context(prepared, tmp_path):
    bridge, _ = await bridge_for(prepared, tmp_path, tmp_path)
    try:
        identity = bridge.host.session_id
        before = await bridge.host.session.coordinator.get("context").get_messages()
        assert bridge.command({"op": "rename", "text": "Readable name 🧭"})[0]
        assert bridge.host.store.metadata["title"] == "Readable name 🧭"
        assert bridge.host.session_id == identity
        assert before == await bridge.host.session.coordinator.get("context").get_messages()
        assert not bridge.command({"op": "rename", "text": "bad\nname"})[0]
        assert not bridge.command({"op": "rename", "text": "bad", "session_id": "wrong"})[0]
        bridge.command({"op": "submit", "text": "first prompt"})
        await bridge.host.task
        assert bridge.host.store.metadata["title"] == "Readable name 🧭"
    finally:
        await bridge.close()


async def test_corrupt_queue_target_does_not_close_source(prepared, tmp_path):
    bridge, _ = await bridge_for(prepared, tmp_path, tmp_path)
    original = bridge.host.session_id
    try:
        bridge.command({"op": "switch", "target": "new", "draft": "", "request_id": "s1"})
        await bridge.switch_task
        source = bridge.host
        atomic_json(tmp_path / "conversations" / original / "followups.json", {"version": 999})
        bridge.command(
            {
                "op": "switch",
                "target": original,
                "draft": "stay",
                "request_id": "s2",
                "session_id": source.session_id,
            }
        )
        await bridge.switch_task
        assert bridge.host is source and source.ready
        assert source.store.draft == "stay"
    finally:
        await bridge.close()


async def test_provider_failure_holds_queue(prepared, tmp_path):
    bridge, _ = await bridge_for(prepared, tmp_path, tmp_path)
    try:
        bridge.host.session.coordinator.get("providers")["fixture"].config["raise_error"] = True
        bridge.command({"op": "submit", "text": "will fail"})
        bridge.command({"op": "queue", "text": "must stay waiting"})
        await settled(bridge)
        assert bridge.followups.paused
        assert texts(bridge.host) == ["will fail"]
        assert bridge.followups.rows[0]["state"] == "queued"
    finally:
        await bridge.close()


async def test_duplicate_queue_request_does_not_duplicate_intent(prepared, tmp_path):
    bridge, _ = await bridge_for(prepared, tmp_path, tmp_path)
    try:
        bridge.command({"op": "queue_pause"})
        admission = Admission()
        request = {"version": 1, "request_id": "one", "op": "queue", "text": "one input"}
        first = admission.apply(request, bridge.command)
        assert first["accepted"]
        assert admission.apply(request, bridge.command) == first
        assert len(bridge.followups.rows) == 1
    finally:
        await bridge.close()


async def test_edit_waiting_input_never_changes_admitted_work(prepared, tmp_path):
    bridge, _ = await bridge_for(prepared, tmp_path, tmp_path)
    try:
        bridge.command({"op": "queue_pause"})
        bridge.command({"op": "queue", "text": "original"})
        identity = bridge.followups.rows[0]["id"]
        assert bridge.command({"op": "queue_edit", "id": identity, "text": "corrected\nfollow-up"})[
            0
        ]
        assert bridge.followups.rows[0]["text"] == "corrected\nfollow-up"
        bridge.command({"op": "queue_run"})
        assert not bridge.command({"op": "queue_edit", "id": identity, "text": "too late"})[0]
        assert not bridge.command({"op": "queue_remove", "id": identity})[0]
        await settled(bridge)
        assert texts(bridge.host) == ["corrected\nfollow-up"]
    finally:
        await bridge.close()

import asyncio
import json
import os

from test_navigation import bridge_for

from amplifier_tui.input_history import recall


def journal(state, cwd, identity, texts, stamp):
    path = state / "conversations" / identity
    path.mkdir(parents=True)
    metadata = path / "metadata.json"
    metadata.write_text(json.dumps({"version": 1, "id": identity, "launch": {"cwd": str(cwd)}}))
    os.utime(metadata, ns=(stamp, stamp))
    (path / "events.jsonl").write_text(
        "\n".join(
            json.dumps({"session_id": identity, "kind": "turn.accepted", "payload": {"text": text}})
            for text in texts
        )
        + "\n"
    )
    return path


def test_recall_scopes_directory_not_context_or_current_session(tmp_path):
    cwd = tmp_path / "work"
    cwd.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(cwd, target_is_directory=True)
    journal(tmp_path, cwd, "a" * 32, ["alpha", "beta"], 1)
    journal(tmp_path, alias, "b" * 32, ["gamma"], 2)
    journal(tmp_path, tmp_path, "c" * 32, ["other directory"], 3)
    journal(tmp_path, cwd, "d" * 32, ["current excluded"], 4)
    assert recall(tmp_path, cwd, "d" * 32) == {
        "entries": ["alpha", "beta", "gamma"],
        "partial": False,
    }


def test_recall_bounds_and_bad_journal_are_disclosed(tmp_path):
    path = journal(tmp_path, tmp_path, "a" * 32, [str(i) for i in range(1100)], 1)
    with (path / "events.jsonl").open("a") as stream:
        stream.write("null\n[]\n")
        stream.write(
            '{broken\n{"session_id":"wrong","kind":"turn.accepted","payload":{"text":"wrong"}}\n'
        )
    result = recall(tmp_path, tmp_path, "current")
    assert result["partial"] and len(result["entries"]) == 1000
    assert result["entries"][0] == "100" and result["entries"][-1] == "1099"
    (path / "events.jsonl").write_text(
        "x" * (2 * 1024 * 1024)
        + "\n"
        + json.dumps(
            {"session_id": "a" * 32, "kind": "turn.accepted", "payload": {"text": "recent"}}
        )
    )
    assert recall(tmp_path, tmp_path, "current") == {"entries": ["recent"], "partial": True}


async def test_switch_history_is_local_recall_not_context(prepared, tmp_path):
    bridge, events = await bridge_for(prepared, tmp_path, tmp_path)
    try:
        identity = bridge.host.session_id
        assert bridge.command({"op": "submit", "text": "Prior input", "session_id": identity})[0]
        await bridge.host.task
        assert bridge.command(
            {
                "op": "switch",
                "target": "new",
                "draft": "kept",
                "session_id": identity,
                "request_id": "new",
            }
        )[0]
        await bridge.switch_task
        recall_event = [e for e in events if e["type"] == "input_history"][-1]
        assert recall_event["session_id"] == bridge.host.session_id
        assert recall_event["entries"] == ["Prior input"]
        context = bridge.host.session.coordinator.get("context")
        assert "Prior input" not in str(await context.get_messages())
        assert bridge.host.session.coordinator.get("providers")["fixture"].calls == []
    finally:
        await bridge.close()


async def test_child_mode_observation_cannot_replace_parent_badge(prepared, tmp_path):
    bridge, events = await bridge_for(prepared, tmp_path, tmp_path)
    try:
        before = len([e for e in events if e["type"] == "mode_status"])
        bridge.host.emit("mode.status", "child:example:mode-status", current="plan", supported=True)
        await asyncio.sleep(0)
        assert len([e for e in events if e["type"] == "mode_status"]) == before
        bridge.host.emit("mode.status", "mode-status", current="explore", supported=True)
        await asyncio.sleep(0)
        status = [e for e in events if e["type"] == "mode_status"][-1]
        assert status["current"] == "explore" and status["session_id"] == bridge.host.session_id
    finally:
        await bridge.close()

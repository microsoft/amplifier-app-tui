import asyncio
import json

import pytest

from amplifier_tui.conversations import ConversationStore, portable_history
from amplifier_tui.events import Event
from amplifier_tui.file_input import snapshot
from amplifier_tui.host import RuntimeBridge, SessionHost
from amplifier_tui.inspection import Inspection
from amplifier_tui.local_drafts import read, save, validate
from amplifier_tui.recovery import recover


def row(store, text="Unsent 界\ncorrection"):
    return {
        "id": "correction:original-turn",
        "kind": "correction",
        "source": store.identity,
        "text": text,
    }


def test_portable_history_allows_only_internal_sequence_changes():
    plain = [{"role": "user", "content": "Original"}]
    stamped = [{**plain[0], "metadata": {"_seq": 10}}]
    assert portable_history(plain) == portable_history(stamped)
    assert stamped[0]["metadata"] == {"_seq": 10}
    for changed in (
        [{"role": "user", "content": "Changed"}],
        [{**plain[0], "metadata": {"authority": "changed"}}],
        [{**plain[0], "tool_call_id": "different"}],
    ):
        assert portable_history(plain) != portable_history(changed)


@pytest.mark.parametrize("kind", ["correction", "dialog"])
async def test_local_drafts_resume_and_recovery_never_enter_context(prepared, tmp_path, kind):
    store = ConversationStore(tmp_path, {})
    host = SessionHost(store)
    await host.open(*prepared, tmp_path)
    original = await host.session.coordinator.get("context").get_messages()
    draft = {**row(store), "kind": kind, "id": f"{kind}:original-target"}
    assert save(store, {"row": draft})[0]
    assert read(store.path) == [draft]
    assert (store.path / "editors.json").stat().st_mode & 0o777 == 0o600
    assert await host.session.coordinator.get("context").get_messages() == original
    await host.close()
    for identity in (store.identity, recover(tmp_path, store.identity)):
        reopened = ConversationStore(tmp_path, {}, identity)
        restored = SessionHost(reopened)
        try:
            await restored.open(*prepared, tmp_path)
            assert read(reopened.path) == [draft]
            assert draft["text"] not in str(
                await restored.session.coordinator.get("context").get_messages()
            )
            assert not restored.session.coordinator.get("providers")["fixture"].calls
            assert not restored.session.coordinator.get("tools")["fixture_probe"].calls
        finally:
            await restored.close()


def test_draft_validation_limits_and_corruption_preserve_original(tmp_path):
    store = ConversationStore(tmp_path, {})
    try:
        assert save(store, {"row": row(store)})[0]
        assert not save(store, {"row": {**row(store), "source": "other"}})[0]
        before = (store.path / "editors.json").read_bytes()
        with pytest.raises(ValueError):
            save(store, {"row": row(store, "x" * 65537)})
        with pytest.raises(ValueError):
            validate([row(store)] * 33)
        assert (store.path / "editors.json").read_bytes() == before
        assert save(store, {"remove": "correction:original-turn"})[0]
        assert read(store.path) == []
        (store.path / "editors.json").write_text("broken")
        with pytest.raises(ValueError):
            save(store, {"row": row(store)})
        assert (store.path / "editors.json").read_text() == "broken"
    finally:
        store.close()


@pytest.mark.parametrize("broken", [False, True])
def test_startup_collision_backs_up_before_replacing_and_fails_closed(tmp_path, broken):
    store = ConversationStore(tmp_path, {})
    store.save_draft("Restored original 界")
    host = SessionHost(store)
    bridge = RuntimeBridge(host, None, lambda _: None, True, tmp_path)
    backup = {
        "id": "startup:unique-launch",
        "kind": "startup",
        "source": store.identity,
        "text": store.draft,
    }
    if broken:
        (store.path / "editors.json").write_text("broken original")
    try:
        request = {
            "op": "draft",
            "session_id": host.session_id,
            "text": "Typed before startup",
            "startup_backup": backup,
        }
        accepted, reason = bridge.command(request)
        assert accepted is not broken, reason
        if broken:
            assert store.draft == "Restored original 界"
            assert (store.path / "editors.json").read_text() == "broken original"
            assert "original retained" in reason
        else:
            assert store.draft == "Typed before startup"
            assert read(store.path) == [backup]
            before = (store.path / "editors.json").stat().st_mtime_ns
            assert bridge.command(request)[0]
            assert (store.path / "editors.json").stat().st_mtime_ns == before
            assert not bridge.command({**request, "session_id": "other"})[0]
    finally:
        store.close()


async def test_child_observations_and_restored_catalog_do_not_resume(prepared, tmp_path):
    store = ConversationStore(tmp_path, {})
    host = SessionHost(store)
    await host.open(*prepared, tmp_path)
    result = await host.children.spawn("probe", "Compute a digest", host.session, {"probe": {}})
    identity = result["session_id"]
    catalog = host.inspection.catalog(host, "children")
    assert catalog["rows"][0]["child"] == identity
    assert catalog["rows"][0]["status"] == "succeeded"
    assert catalog["rows"][0]["live"] is False
    activity = host.inspection.catalog(host, "activity", identity)
    assert any("fixture_probe" in r["detail"] for r in activity["rows"])
    assert any("Fixture round trip" in r["detail"] for r in activity["rows"])
    host.submit("Checkpoint root")
    await host.task
    await host.close()
    restored = SessionHost(ConversationStore(tmp_path, {}, store.identity))
    try:
        await restored.open(*prepared, tmp_path)
        assert not restored.children.records
        rows = restored.inspection.catalog(restored, "children")["rows"]
        assert rows[0]["child"] == identity and not rows[0]["live"]
        assert not restored.session.coordinator.get("providers")["fixture"].calls
    finally:
        await restored.close()


async def test_context_and_activity_are_read_only_and_scoped(host, tmp_path):
    output = []
    bridge = RuntimeBridge(host, None, output.append, True, tmp_path)
    before = await host.session.coordinator.get("context").get_messages()
    await host._observe("llm:response", {"session_id": "other", "usage": {"input_tokens": 999}})
    await host._observe("llm:response", {"usage": {"input_tokens": 42, "output_tokens": 7}})
    await host._observe("context:compaction", {"before_tokens": 800, "after_tokens": 400})
    assert not bridge.command({"op": "inspect", "category": "context", "session_id": "other"})[0]
    assert bridge.command({"op": "inspect", "category": "context", "session_id": host.session_id})[
        0
    ]
    # UUIDs can contain "999". Check the observations, never incidental identity text.
    observations = [
        json.loads(row["detail"])["observation"]
        for row in output[-1]["rows"]
        if row["id"] != "context-policy"
    ]
    assert output[-1]["rows"][0]["status"] == "configuration, not occupancy"
    assert {"input_tokens": 42, "output_tokens": 7} in observations
    assert {"before_tokens": 800, "after_tokens": 400} in observations
    assert not any(value.get("input_tokens") == 999 for value in observations)
    assert await host.session.coordinator.get("context").get_messages() == before
    assert not host.session.coordinator.get("providers")["fixture"].calls


def test_inspection_bounds_and_excerpt_disclosure():
    index = Inspection()
    for i in range(300):
        index.observe(Event("root", i, "turn", "tool.updated", str(i), {"result": "界" * 10000}))
    assert len(index.rows) == 256 and index.partial
    assert all(r["partial"] and "excerpt" in r["detail"] for r in index.rows.values())


async def test_child_waiting_permission_is_observed(host):
    tool = host.children.prepared.bundle.tools[0]
    tool.setdefault("config", {})["approval"] = True
    task = asyncio.create_task(host.children.spawn("probe", "check", host.session, {"probe": {}}))
    try:
        async with asyncio.timeout(5):
            while not host._pending:
                await asyncio.sleep(0.01)
        rows = host.inspection.catalog(host, "children")["rows"]
        assert rows[0]["status"] == "waiting_permission" and rows[0]["live"]
        identity = next(iter(host._pending))
        host.answer(identity, "allow")
        await task
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


def test_file_snapshot_is_frozen_bounded_and_confined(tmp_path):
    path = tmp_path / "notes space.md"
    path.write_text("Captured 界\n```example\n", encoding="utf-8")
    value = snapshot(tmp_path, "notes space.md")
    path.write_text("Changed after capture")
    assert value["text"] == "Captured 界\n```example\n"
    assert len(value["sha256"]) == 64
    for name in ("../outside", str(path), "missing"):
        with pytest.raises((OSError, ValueError)):
            snapshot(tmp_path, name)
    (tmp_path / "alias").symlink_to(path)
    with pytest.raises(OSError):
        snapshot(tmp_path, "alias")
    (tmp_path / "directory-alias").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(OSError):
        snapshot(tmp_path, "directory-alias/notes space.md")
    path.write_bytes(b"\x89PNG\0\xff")
    with pytest.raises(ValueError):
        snapshot(tmp_path, path.name)
    path.write_bytes(b"x" * 65537)
    with pytest.raises(ValueError):
        snapshot(tmp_path, path.name)


@pytest.mark.parametrize("inherit", [False, True])
async def test_completed_direct_child_continues_after_restart_only_explicitly(
    prepared, tmp_path, inherit
):
    store = ConversationStore(tmp_path, {})
    host = SessionHost(store)
    await host.open(*prepared, tmp_path)
    result = await host.children.spawn(
        "self",
        "First child instruction",
        host.session,
        {},
        orchestrator_config=host.session.config["session"]["orchestrator"].get("config")
        if inherit
        else None,
    )
    identity = result["session_id"]
    prior = json.loads((store.path / "children" / f"{identity}.json").read_text())
    host.submit("Checkpoint root")
    await host.task
    await host.close()
    restored = SessionHost(ConversationStore(tmp_path, {}, store.identity))
    try:
        await restored.open(*prepared, tmp_path)
        assert not restored.children.active and not restored.children.records
        assert not restored.session.coordinator.get("providers")["fixture"].calls
        result = await restored.children.resume(identity, "Second child instruction")
        assert result["session_id"] == identity
        record = restored.children.records[identity]
        assert record["messages"][: len(prior["messages"])] == prior["messages"]
        assert "Second child instruction" in str(record["messages"])
        assert record["status"] == "completed"
        assert not restored.session.coordinator.get("providers")["fixture"].calls
    finally:
        await restored.close()


@pytest.mark.parametrize(
    "change", ["status", "parent", "mount_fingerprint", "mode", "restart_policy"]
)
async def test_child_continuation_refuses_changed_or_uncertain_receipt(prepared, tmp_path, change):
    store = ConversationStore(tmp_path, {})
    host = SessionHost(store)
    await host.open(*prepared, tmp_path)
    result = await host.children.spawn("self", "First", host.session, {})
    identity = result["session_id"]
    path = store.path / "children" / f"{identity}.json"
    record = json.loads(path.read_text())
    record[change] = "changed"
    path.write_text(json.dumps(record))
    before = path.read_bytes()
    host.children.records.clear()  # Exercise lazy disk continuation on a ready root.
    try:
        with pytest.raises(ValueError):
            await host.children.resume(identity, "Must not execute")
        assert path.read_bytes() == before
        assert not host.children.active and not host.children.records
    finally:
        await host.close()

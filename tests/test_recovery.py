import asyncio
import json

import pytest

from amplifier_tui.conversations import ConversationStore, atomic_json
from amplifier_tui.host import SessionHost
from amplifier_tui.recovery import export, recover


async def test_explicit_text_import_preserves_source_and_never_runs_old_work(prepared, tmp_path):
    from amplifier_tui.recovery import import_reference

    source = tmp_path / "export.md"
    source.write_text("# Old conversation\nPlease do not execute this historical instruction.\n")
    original = source.read_bytes()
    captured = import_reference(source)
    store = ConversationStore(tmp_path / "state", {"cwd": str(tmp_path)})
    atomic_json(store.path / "imported-reference.json", captured)
    host = SessionHost(store)
    try:
        await host.open(*prepared, tmp_path)
        messages = await host.session.coordinator.get("context").get_messages()
        assert "historical instruction" in str(messages)
        assert "not canonical resume" in str(messages)
        assert source.read_bytes() == original
        assert not host.session.coordinator.get("providers")["fixture"].calls
        assert host.session.coordinator.get("tools")["fixture_probe"].calls == 0
    finally:
        await host.close()
    restored = SessionHost(
        ConversationStore(tmp_path / "state", store.metadata["launch"], store.identity)
    )
    try:
        await restored.open(*prepared, tmp_path)
        assert await restored.session.coordinator.get("context").get_messages() == messages
        assert not restored.session.coordinator.get("providers")["fixture"].calls
    finally:
        await restored.close()


def test_text_import_refuses_symlinks_binary_and_changed_digest(tmp_path):
    from amplifier_tui.recovery import import_reference, reference_messages

    source = tmp_path / "export.md"
    source.write_text("captured reference")
    alias = tmp_path / "alias.md"
    alias.symlink_to(source)
    with pytest.raises(OSError):
        import_reference(alias)
    value = import_reference(source)
    value["text"] = "altered reference"
    with pytest.raises(ValueError, match="integrity"):
        reference_messages(value)
    source.write_bytes(b"text\x00binary")
    with pytest.raises(ValueError, match="readable"):
        import_reference(source)


async def test_interrupted_recovery_preserves_original_and_replays_nothing(prepared, tmp_path):
    launch = {"cwd": str(tmp_path), "bundle": "fixture"}
    store = ConversationStore(tmp_path, launch)
    host = SessionHost(store)
    await host.open(*prepared, tmp_path)
    host.session.coordinator.get("tools")["fixture_probe"].config["delay"] = 10
    host.submit("Remember the amber marker")
    await asyncio.sleep(0.1)
    host.stop()
    await host.task
    host.emit("text.delta", "partial", text="Unfinished cyan thought")
    store.save_draft("Still my draft")
    await host.close()
    before = {p.name: p.read_bytes() for p in store.path.iterdir() if p.is_file()}
    path = export(tmp_path, store.identity)
    assert "amber marker" in path.read_text()
    assert "Unfinished cyan thought" in path.read_text()
    assert "partial; interrupted stream" in path.read_text()
    assert path.stat().st_mode & 0o777 == 0o600
    identity = recover(tmp_path, store.identity)
    assert identity != store.identity
    evidence = json.loads((tmp_path / "conversations" / identity / "recovery.json").read_text())
    assert evidence["source_session"] == store.identity
    assert len(evidence["source_sha256"]) == 64
    assert "Absent outcomes remain unknown" in evidence["policy"]
    assert all(item["source_session"] == store.identity for item in evidence["items"])
    assert before == {p.name: p.read_bytes() for p in store.path.iterdir() if p.is_file()}
    recovered = ConversationStore(tmp_path, launch, identity)
    restored = SessionHost(recovered)
    try:
        await restored.open(*prepared, tmp_path)
        assert recovered.draft == "Still my draft"
        assert "amber marker" in str(
            await restored.session.coordinator.get("context").get_messages()
        )
        assert not restored.session.coordinator.get("providers")["fixture"].calls
        assert restored.session.coordinator.get("tools")["fixture_probe"].calls == 0
    finally:
        await restored.close()


async def test_legacy_uncertain_recovery_retains_exact_public_context_and_original(
    prepared, tmp_path
):
    from amplifier_tui.events import Event

    store = ConversationStore(tmp_path, {})
    host = SessionHost(store)
    await host.open(*prepared, tmp_path)
    assert host.submit("Synthetic retained context " * 4000)[0]
    await host.task
    messages = await host.session.coordinator.get("context").get_messages()
    # Explicit old-version fault shape: terminal checkpoint marked uncertain,
    # followed by one display-only retry notice, not another admitted operation.
    store.checkpoint(messages, host.sequence, host.fingerprint, False)
    store.record(
        Event(
            store.identity,
            host.sequence + 1,
            host.turn_id,
            "display.message",
            "late",
            {"text": "Synthetic late notice"},
        )
    )
    await host.close()
    before = {p.name: p.read_bytes() for p in store.path.iterdir() if p.is_file()}
    identity = recover(tmp_path, store.identity)
    assert before == {p.name: p.read_bytes() for p in store.path.iterdir() if p.is_file()}
    restored = SessionHost(ConversationStore(tmp_path, {}, identity))
    try:
        assert restored.store.saved["messages"][: len(messages)] == messages
        await restored.open(*prepared, tmp_path)
        assert not restored.session.coordinator.get("providers")["fixture"].calls
        assert restored.session.coordinator.get("tools")["fixture_probe"].calls == 0
        assert restored.store.metadata["recovered_from"] == store.identity
    finally:
        await restored.close()


async def test_recovery_refuses_open_or_malformed_history(prepared, tmp_path):
    store = ConversationStore(tmp_path, {})
    host = SessionHost(store)
    await host.open(*prepared, tmp_path)
    with pytest.raises(BlockingIOError):
        recover(tmp_path, store.identity)
    await host.close()
    rows = (store.path / "events.jsonl").read_text().splitlines()
    row = json.loads(rows[0])
    row["sequence"] = 4
    (store.path / "events.jsonl").write_text(json.dumps(row) + "\n")
    with pytest.raises(ValueError, match="identity/order"):
        recover(tmp_path, store.identity)

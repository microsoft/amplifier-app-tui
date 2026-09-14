import asyncio
import json

import pytest

from amplifier_tui.conversations import ConversationStore
from amplifier_tui.host import SessionHost
from amplifier_tui.recovery import export, recover


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

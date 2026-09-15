import base64
import json
import sys

import pytest
from PIL import Image
from test_navigation import bridge_for

from amplifier_tui.file_input import ImageDraft, image_snapshot
from amplifier_tui.followups import Followups


async def attach(bridge, events, tmp_path, name, color):
    path = tmp_path / name
    Image.new("RGB", (8, 8), color).save(path)
    original = path.read_bytes()
    identity = bridge.host.session_id
    assert bridge.command({"op": "image_snapshot", "session_id": identity, "path": name})[0]
    await bridge.lookup_task
    preview = events[-1]
    assert bridge.command({"op": "image_select", "session_id": identity, "id": preview["id"]})[0]
    path.write_bytes(b"replaced source")
    return original


async def test_multi_image_queue_reopen_and_delivery_preserve_exact_bytes(prepared, tmp_path):
    bridge, events = await bridge_for(prepared, tmp_path / "state", tmp_path)
    try:
        provider = bridge.host.session.coordinator.get("providers")["fixture"]
        provider.config["capabilities"] = ["vision"]
        originals = [
            await attach(bridge, events, tmp_path, f"{color}.png", color)
            for color in ("red", "blue")
        ]
        media = bridge.host.images.public()
        assert len(media["images"]) == 2 and "data" not in json.dumps(media)
        assert ImageDraft(bridge.host.store).public() == media
        assert bridge.command({"op": "queue", "text": "Inspect both", "image_id": media["id"]})[0]
        assert not provider.calls  # Selecting attachments holds the queue.
        assert bridge.host.images.value["state"] == "dispatched"
        reopened = Followups(bridge.host, events.append)
        assert reopened.paused and reopened.rows == bridge.followups.rows
        reopened.publish()
        assert "data" not in json.dumps(events[-1])
        assert not bridge.command({"op": "queue", "text": "No repeat", "image_id": media["id"]})[0]
        assert bridge.command({"op": "queue_run"})[0]
        await bridge.host.task
        blocks = [
            block
            for msg in provider.calls[0].model_dump()["messages"]
            if isinstance(msg["content"], list)
            for block in msg["content"]
            if block["type"] == "image"
        ]
        assert [base64.b64decode(b["source"]["data"]) for b in blocks] == originals
        accepted = [
            json.loads(line)
            for line in (bridge.host.store.path / "events.jsonl").read_text().splitlines()
            if json.loads(line)["kind"] == "turn.accepted"
        ]
        assert len(accepted) == 1 and "data" not in json.dumps(accepted[0]["payload"]["image"])
    finally:
        await bridge.close()


async def test_image_set_limit_stale_removal_and_provider_rejection(prepared, tmp_path):
    bridge, events = await bridge_for(prepared, tmp_path / "state", tmp_path)
    try:
        provider = bridge.host.session.coordinator.get("providers")["fixture"]
        provider.config["capabilities"] = ["vision"]
        for color in ("red", "blue", "green", "yellow"):
            await attach(bridge, events, tmp_path, f"{color}.png", color)
        before = bridge.host.images.public()
        fifth = tmp_path / "fifth.png"
        Image.new("RGB", (8, 8), "white").save(fifth)
        bridge.host.images.preview = image_snapshot(fifth.read_bytes(), "fifth.png")
        with pytest.raises(ValueError, match="four"):
            bridge.host.images.select(bridge.host.images.preview["id"])
        assert bridge.host.images.public() == before
        item = before["images"][1]
        bridge.host.images.remove(before["id"], item["id"])
        after = bridge.host.images.public()
        assert len(after["images"]) == 3 and after["id"] != before["id"]
        with pytest.raises(ValueError, match="changed"):
            bridge.host.images.remove(before["id"])
        provider.config["capabilities"] = []
        assert not bridge.command(
            {"op": "submit", "text": "Reject without vision", "image_id": after["id"]}
        )[0]
        assert bridge.host.images.public() == after
    finally:
        await bridge.close()


async def test_unavailable_clipboard_does_not_acquire_or_submit(prepared, tmp_path, monkeypatch):
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.delenv("DISPLAY", raising=False)
    bridge, events = await bridge_for(prepared, tmp_path / "state", tmp_path)
    try:
        provider = bridge.host.session.coordinator.get("providers")["fixture"]
        provider.config["capabilities"] = ["vision"]
        assert bridge.command({"op": "clipboard_image", "session_id": bridge.host.session_id})[0]
        await bridge.lookup_task
        assert "Host clipboard image unavailable" in events[-1]["error"]
        assert not bridge.host.images.value and not provider.calls
    finally:
        await bridge.close()


async def test_explicit_clipboard_utility_produces_bounded_preview(tmp_path, monkeypatch):
    from amplifier_tui.file_input import clipboard_image

    path = tmp_path / "sample.png"
    Image.new("RGB", (12, 12), "red").save(path)
    original = path.read_bytes()
    utility = tmp_path / "wl-paste"
    utility.write_text(f"#!{sys.executable}\nimport sys\nsys.stdout.buffer.write({original!r})\n")
    utility.chmod(0o700)
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setenv("WAYLAND_DISPLAY", "fixture")
    result = await clipboard_image()
    assert base64.b64decode(result["data"]) == original
    assert result["thumbnail"]["pixels"][0] == [255, 0, 0]
    assert result["thumbnail"]["width"] <= 32 and result["thumbnail"]["height"] <= 16


def test_large_dimensions_rejected_before_preview_decode(tmp_path):
    path = tmp_path / "wide.png"
    Image.new("RGB", (8193, 1), "red").save(path)
    with pytest.raises(ValueError, match="dimensions"):
        image_snapshot(path.read_bytes(), "wide.png")

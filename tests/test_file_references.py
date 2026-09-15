import base64
import copy
import hashlib
import json

import pytest
from test_media_sets import attach
from test_navigation import bridge_for

from amplifier_tui.file_input import ImageDraft, reference_snapshot
from amplifier_tui.followups import Followups


def test_file_reference_locations_hashes_and_immutable_bytes(tmp_path):
    source = "first\r\nsecond\u2028still second\nthird\n".encode()
    path = tmp_path / "source.txt"
    path.write_bytes(source)
    value = reference_snapshot(tmp_path, "source.txt:2-3")
    assert value["source_sha256"] == hashlib.sha256(source).hexdigest()
    assert (value["start_line"], value["end_line"]) == (2, 3)
    assert base64.b64decode(value["data"]).decode() == "second\u2028still second\nthird\n"
    ImageDraft.validate({**value, "state": "attached"})
    path.unlink()
    blocks = ImageDraft.content(value)
    reference = json.loads(blocks[0]["text"].split("\n", 1)[1])
    assert reference["path"] == "source.txt" and reference["start_line"] == 2
    assert reference["source_sha256"] == value["source_sha256"]
    assert reference["text"] == "second\u2028still second\nthird\n"
    assert "data" not in ImageDraft.metadata(value)
    for field, replacement in (
        ("start_line", 1),
        ("source_sha256", "0" * 64),
        ("path", "other.txt"),
    ):
        with pytest.raises(ValueError, match="integrity"):
            ImageDraft.validate({**value, "state": "attached", field: replacement})


@pytest.mark.parametrize(
    "selector", ["source.txt:0", "source.txt:3-2", "source.txt:1-5", "../source.txt", "/source.txt"]
)
def test_reference_refuses_invalid_locations(tmp_path, selector):
    (tmp_path / "source.txt").write_text("first\nsecond\n")
    with pytest.raises(ValueError):
        reference_snapshot(tmp_path, selector)


def test_reference_refuses_symlink_and_accepts_empty_source(tmp_path):
    (tmp_path / "empty.txt").write_text("")
    value = reference_snapshot(tmp_path, "empty.txt")
    assert value["start_line"] == value["end_line"] == 1
    ImageDraft.validate({**value, "state": "attached"})
    (tmp_path / "link.txt").symlink_to(tmp_path / "empty.txt")
    with pytest.raises(OSError):
        reference_snapshot(tmp_path, "link.txt")


async def select_reference(bridge, events, selector):
    assert bridge.command(
        {"op": "reference_snapshot", "session_id": bridge.host.session_id, "path": selector}
    )[0]
    await bridge.lookup_task
    preview = events[-1]
    assert "data" not in preview and "preview_text" in preview
    assert bridge.command(
        {"op": "image_select", "session_id": bridge.host.session_id, "id": preview["id"]}
    )[0]
    return preview


async def test_text_only_reference_queue_reopen_and_source_deletion(prepared, tmp_path):
    bridge, events = await bridge_for(prepared, tmp_path / "state", tmp_path)
    try:
        provider = bridge.host.session.coordinator.get("providers")["fixture"]
        provider.config["capabilities"] = []
        path = tmp_path / "source.txt"
        path.write_text("excluded line\nretained evidence\nexcluded tail\n")
        preview = await select_reference(bridge, events, "source.txt:2")
        assert preview["preview_text"] == "retained evidence\n"
        assert not provider.calls
        path.unlink()
        value = copy.deepcopy(bridge.host.images.value)
        assert ImageDraft(bridge.host.store).value == value
        assert not bridge.command({"op": "submit", "text": "Missing attachment identity"})[0]
        assert bridge.host.images.value == value
        assert bridge.command(
            {"op": "queue", "text": "Inspect selected source", "image_id": value["id"]}
        )[0]
        reopened = Followups(bridge.host, events.append)
        assert reopened.paused and reopened.rows == bridge.followups.rows
        assert not provider.calls
        assert not bridge.command(
            {"op": "queue", "text": "No redelivery", "image_id": value["id"]}
        )[0]
        bridge.followups = reopened
        assert bridge.command({"op": "queue_run"})[0]
        await bridge.host.task
        messages = str(provider.calls[0].messages)
        assert "retained evidence" in messages and "source.txt" in messages
        assert "excluded line" not in messages and "excluded tail" not in messages
        assert not ImageDraft.needs_vision(value)
    finally:
        await bridge.close()


async def test_mixed_set_requires_vision_without_consuming_reference(prepared, tmp_path):
    bridge, events = await bridge_for(prepared, tmp_path / "state", tmp_path)
    try:
        provider = bridge.host.session.coordinator.get("providers")["fixture"]
        provider.config["capabilities"] = ["vision"]
        original = await attach(bridge, events, tmp_path, "sample.png", "red")
        (tmp_path / "source.txt").write_text("captured text")
        preview = await select_reference(bridge, events, "source.txt")
        value = copy.deepcopy(bridge.host.images.value)
        assert len(value["images"]) == 2
        assert not bridge.command(
            {"op": "image_select", "session_id": bridge.host.session_id, "id": preview["id"]}
        )[0]
        provider.config["capabilities"] = []
        assert not bridge.command({"op": "queue", "text": "Inspect both", "image_id": value["id"]})[
            0
        ]
        assert bridge.host.images.value == value
        provider.config["capabilities"] = ["vision"]
        assert bridge.command({"op": "submit", "text": "Inspect both", "image_id": value["id"]})[0]
        await bridge.host.task
        blocks = ImageDraft.content(value)
        assert base64.b64decode(blocks[1]["source"]["data"]) == original
        assert "captured text" in str(provider.calls[0].messages)
        assert bridge.host.images.value["state"] == "dispatched"
    finally:
        await bridge.close()

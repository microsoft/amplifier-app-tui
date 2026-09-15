"""Public historical child evidence and original-byte image transport."""

import asyncio
import base64
import io
import json

import pytest
from PIL import Image

from amplifier_tui.conversations import ConversationStore
from amplifier_tui.file_input import ImageDraft, image_snapshot
from amplifier_tui.host import SessionHost
from amplifier_tui.recovery import child_references, recover, recovery_catalog


async def test_interrupted_child_recovery_is_inspection_not_execution(prepared, tmp_path):
    store = ConversationStore(tmp_path / "state", {})
    host = SessionHost(store)
    await host.open(*prepared, tmp_path)
    host.children.prepared.bundle.providers[0].setdefault("config", {})["delay"] = 5
    task = asyncio.create_task(
        host.children.spawn("probe", "historical child instruction", host.session, {"probe": {}})
    )
    try:
        async with asyncio.timeout(5):
            while not any(
                s and s.coordinator.get("providers")["fixture"].calls
                for s in host.children.active.values()
            ):
                await asyncio.sleep(0.005)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        await host.close()
    original = {p.name: p.read_bytes() for p in (store.path / "children").iterdir()}
    identity = recover(tmp_path / "state", store.identity)
    restored = SessionHost(ConversationStore(tmp_path / "state", {}, identity))
    try:
        await restored.open(*prepared, tmp_path)
        result = recovery_catalog(restored.store)
        row = next(r for r in result["rows"] if r["label"].startswith("Historical child"))
        assert not row["live"] and "interrupted" in row["detail"]
        assert "historical child instruction" in row["detail"]
        assert not restored.children.records
        assert not restored.session.coordinator.get("providers")["fixture"].calls
        assert not (restored.store.path / "children").exists()
        assert original == {p.name: p.read_bytes() for p in (store.path / "children").iterdir()}
    finally:
        await restored.close()


def test_child_recovery_refuses_foreign_symlink_and_oversize(tmp_path):
    directory = tmp_path / "children"
    directory.mkdir()
    (directory / "foreign.json").write_text(json.dumps({"parent": "foreign-root", "messages": []}))
    (directory / "large.json").write_bytes(b"x" * (1024 * 1024 + 1))
    (tmp_path / "outside").write_text("private outside")
    (directory / "link.json").symlink_to(tmp_path / "outside")
    rows, partial = child_references(tmp_path, "root")
    assert partial and len(rows) == 3
    assert all(r["status"] == "historical child unavailable" for r in rows)
    assert "private outside" not in str(rows)


@pytest.mark.parametrize("format,media", [("GIF", "image/gif"), ("WEBP", "image/webp")])
def test_static_image_original_bytes_survive_store_and_content(tmp_path, format, media):
    output = io.BytesIO()
    Image.new("RGB", (8, 8), "blue").save(output, format=format)
    raw = output.getvalue()
    value = image_snapshot(raw, f"image.{format.lower()}")
    assert value["media_type"] == media
    store = ConversationStore(tmp_path, {})
    try:
        draft = ImageDraft(store)
        draft.save({**value, "state": "attached"})
        restored = ImageDraft(store)
        restored.validate(restored.value)
        image = next(
            block for block in restored.content(restored.value) if block["type"] == "image"
        )
        assert image["source"]["media_type"] == media
        assert base64.b64decode(image["source"]["data"]) == raw
    finally:
        store.close()


@pytest.mark.parametrize("format", ["GIF", "WEBP"])
def test_animation_requires_explicit_still_image(format):
    output = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(
        output,
        format=format,
        save_all=True,
        append_images=[Image.new("RGB", (8, 8), "blue")],
        duration=100,
    )
    with pytest.raises(ValueError, match="Animated"):
        image_snapshot(output.getvalue(), "animation")


async def test_macos_clipboard_parser_uses_explicit_png_without_conversion(monkeypatch):
    from amplifier_tui import file_input

    output = io.BytesIO()
    Image.new("RGB", (8, 8), "blue").save(output, format="PNG")
    raw = output.getvalue()
    commands = []

    class Process:
        pid = 999999999

        def __init__(self):
            self.stdout = asyncio.StreamReader()
            self.stdout.feed_data(("«data PNGf" + raw.hex() + "»\n").encode())
            self.stdout.feed_eof()

        async def wait(self):
            return 0

    async def create(*args, **kwargs):
        commands.append(args)
        assert kwargs["start_new_session"]
        return Process()

    monkeypatch.setattr(file_input.sys, "platform", "darwin")
    monkeypatch.setattr(
        file_input.shutil,
        "which",
        lambda name: "/usr/bin/osascript" if name == "osascript" else None,
    )
    monkeypatch.setattr(asyncio, "create_subprocess_exec", create)
    monkeypatch.setattr(file_input.os, "killpg", lambda *args: None)
    value = await file_input.clipboard_image()
    assert commands == [("/usr/bin/osascript", "-e", "the clipboard as «class PNGf»")]
    assert base64.b64decode(value["data"]) == raw

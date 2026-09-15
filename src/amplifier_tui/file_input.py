"""Explicit local text-file snapshots, never automatic reads from completion."""

import asyncio
import base64
import hashlib
import io
import json
import os
import re
import shutil
import signal
import stat
import sys
import uuid
import warnings
from pathlib import Path

MAX_FILE = 64 * 1024


def snapshot(cwd, name, *, image=False):
    limit = 2 * 1024 * 1024 if image else MAX_FILE
    if not isinstance(name, str) or not name or len(name) > 4096:
        raise ValueError("Choose a workspace-relative UTF-8 text file")
    path = Path(name)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("Only workspace-relative file paths are supported")
    if not name.isprintable():
        raise ValueError("File path must be printable")
    # Walk descriptor-relative without following symlinks, including intermediate dirs.
    directory = os.open(cwd, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
        fd = os.open(path.parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        with os.fdopen(fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
                raise ValueError(
                    "Select a regular image of at most 2 MiB"
                    if image
                    else "Select a regular text file of at most 64 KiB; images require Attach image"
                )
            raw = stream.read(limit + 1)
            after = os.fstat(stream.fileno())
            if len(raw) > limit or (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            ):
                raise ValueError("File changed while reading; refresh explicitly")
    finally:
        os.close(directory)
    digest = hashlib.sha256(raw).hexdigest()
    if image:
        return image_snapshot(raw, str(path))
    text = raw.decode("utf-8")
    if any(ord(c) < 32 and c not in "\n\r\t" for c in text) or "\x7f" in text:
        raise ValueError("Binary or terminal-control content is unsupported")
    return {"path": str(path), "sha256": digest, "bytes": len(raw), "text": text}


def image_snapshot(raw, source):
    from PIL import Image, ImageOps

    if not 0 < len(raw) <= 2 * 1024 * 1024:
        raise ValueError("Select an image of at most 2 MiB")
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        media_type = "image/png"
    elif raw.startswith(b"\xff\xd8\xff") and raw.endswith(b"\xff\xd9"):
        media_type = "image/jpeg"
    elif raw.startswith((b"GIF87a", b"GIF89a")):
        media_type = "image/gif"
    elif raw.startswith(b"RIFF") and raw[8:12] == b"WEBP":
        media_type = "image/webp"
    else:
        raise ValueError("Only PNG, JPEG, static GIF and static WebP snapshots are supported")
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        try:
            decoded = Image.open(io.BytesIO(raw))
        except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            raise ValueError("Image dimensions exceed the preview safety limit") from exc
    with decoded:
        if media_type in ("image/gif", "image/webp") and getattr(decoded, "n_frames", 1) != 1:
            raise ValueError("Animated GIF/WebP is unsupported; choose an explicit still image")
        if decoded.width * decoded.height > 16 * 1024 * 1024 or max(decoded.size) > 8192:
            raise ValueError(
                "Image dimensions exceed the preview limit (16 megapixels / 8192 per side)"
            )
        preview = ImageOps.exif_transpose(decoded).convert("RGB")
        preview.thumbnail((32, 16))
        thumbnail = {
            "width": preview.width,
            "height": preview.height,
            "pixels": [list(pixel) for pixel in preview.get_flattened_data()],
        }
    return {
        "path": source,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "media_type": media_type,
        "data": base64.b64encode(raw).decode("ascii"),
        "id": uuid.uuid4().hex,
        "thumbnail": thumbnail,
    }


def reference_snapshot(cwd, selector):
    """One captured source version, optional one-based inclusive line selection."""
    if not isinstance(selector, str):
        raise ValueError("Choose a workspace-relative file, optionally :line or :start-end")
    match = re.fullmatch(r"(.+):([0-9]{1,8})(?:-([0-9]{1,8}))?", selector)
    source = snapshot(cwd, match[1] if match else selector)
    # Split only at newline: Unicode separators are ordinary source characters.
    lines = source["text"].split("\n")
    lines = [line + "\n" for line in lines[:-1]] + ([lines[-1]] if lines[-1] else [])
    lines = lines or [""]
    start = int(match[2]) if match else 1
    end = int(match[3] or match[2]) if match else len(lines)
    if not 1 <= start <= end <= len(lines):
        raise ValueError(f"Choose an inclusive line range within 1–{len(lines)}")
    raw = "".join(lines[start - 1 : end]).encode("utf-8")
    value = {
        "id": uuid.uuid4().hex,
        "path": source["path"],
        "media_type": "text/plain",
        "source_sha256": source["sha256"],
        "start_line": start,
        "end_line": end,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "data": base64.b64encode(raw).decode("ascii"),
    }
    value["reference_digest"] = reference_digest(value)
    return value


def reference_digest(value):
    return hashlib.sha256(
        json.dumps(
            [value[k] for k in ("path", "source_sha256", "start_line", "end_line", "sha256")],
            ensure_ascii=True,
        ).encode()
    ).hexdigest()


async def clipboard_image():
    """Explicit host-desktop read, never OSC52 polling or remote-terminal inference."""
    apple = sys.platform == "darwin"
    if apple and shutil.which("osascript"):
        args = [shutil.which("osascript"), "-e", "the clipboard as «class PNGf»"]
    elif os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-paste"):
        apple = False
        args = [shutil.which("wl-paste"), "--no-newline", "--type", "image/png"]
    elif os.environ.get("DISPLAY") and shutil.which("xclip"):
        apple = False
        args = [shutil.which("xclip"), "-selection", "clipboard", "-target", "image/png", "-out"]
    else:
        raise ValueError(
            "Host clipboard image unavailable: requires macOS/osascript PNG data, Wayland/wl-paste or X11/xclip. Over SSH, save the image in the workspace and use Attach image."
        )
    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        async with asyncio.timeout(3):
            raw = bytearray()
            while chunk := await process.stdout.read(65536):
                raw.extend(chunk)
                if len(raw) > (4 * 1024 * 1024 + 128 if apple else 2 * 1024 * 1024):
                    raise ValueError("Clipboard image exceeds 2 MiB; nothing attached")
            if await process.wait():
                raise ValueError("Host clipboard does not provide a PNG image")
            if apple:
                match = re.fullmatch("«data PNGf([0-9a-fA-F]+)»\\s*".encode(), bytes(raw))
                if match is None:
                    raise ValueError(
                        "macOS clipboard returned no supported PNG data; nothing attached"
                    )
                raw = bytes.fromhex(match[1].decode("ascii"))
            return image_snapshot(bytes(raw), "host clipboard (PNG)")
    except TimeoutError as exc:
        raise ValueError("Host clipboard timed out; nothing attached") from exc
    finally:
        # Own the utility process group, including descendants keeping the pipe open.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        await process.wait()


class ImageDraft:
    """Four immutable attachments; legacy image keys keep old records readable."""

    def __init__(self, store):
        self.path = store.path / "image-draft.json" if store else None
        self.value, self.preview = None, None
        if self.path and self.path.exists():
            with self.path.open("rb") as stream:
                raw = stream.read(12 * 1024 * 1024 + 1)
            if len(raw) > 12 * 1024 * 1024:
                raise ValueError("Image draft exceeds storage limit; original retained")
            self.value = json.loads(raw)
            if self.value is not None:
                self.validate(self.value)

    @staticmethod
    def validate(value):
        if not isinstance(value, dict) or value.get("state") not in ("attached", "dispatched"):
            raise ValueError("Invalid image admission record; no retry")
        if "images" in value:
            images = value["images"]
            if not isinstance(images, list) or not 1 <= len(images) <= 4:
                raise ValueError("Choose at most four attachments")
            if any(not isinstance(i, dict) or "images" in i for i in images):
                raise ValueError("Invalid image set")
            for item in images:
                ImageDraft.validate({**item, "state": value["state"]})
            if (
                len({i["id"] for i in images}) != len(images)
                or value.get("bytes") != sum(i["bytes"] for i in images)
                or value.get("sha256") != ImageDraft.digest(images)
                or not isinstance(value.get("id"), str)
            ):
                raise ValueError("Image set failed integrity verification")
            return
        raw = base64.b64decode(value["data"], validate=True)
        reference = value.get("media_type") == "text/plain"
        if (
            not (0 if reference else 1) <= len(raw) <= (MAX_FILE if reference else 2 * 1024 * 1024)
            or hashlib.sha256(raw).hexdigest() != value["sha256"]
            or len(raw) != value["bytes"]
        ):
            raise ValueError("Image snapshot failed integrity verification")
        if reference:
            text = raw.decode("utf-8")
            path = value.get("path")
            if (
                not isinstance(path, str)
                or not path
                or not path.isprintable()
                or len(path) > 4096
                or Path(path).is_absolute()
                or ".." in Path(path).parts
                or type(value.get("start_line")) is not int
                or type(value.get("end_line")) is not int
                or not 1 <= value["start_line"] <= value["end_line"] <= MAX_FILE + 1
                or not re.fullmatch(r"[0-9a-f]{64}", str(value.get("source_sha256", "")))
                or value.get("reference_digest") != reference_digest(value)
                or any(ord(c) < 32 and c not in "\n\r\t" for c in text)
                or "\x7f" in text
            ):
                raise ValueError("File reference failed integrity verification")
        if value.get("media_type") not in (
            "image/png",
            "image/jpeg",
            "image/gif",
            "image/webp",
            "text/plain",
        ) or not isinstance(value.get("id"), str):
            raise ValueError("Invalid image identity/type")

    def save(self, value):
        from .conversations import atomic_json

        if self.path:
            atomic_json(self.path, value)
        self.value = value

    def public(self):
        return self.metadata(self.value)

    @staticmethod
    def metadata(value):
        if not value:
            return None
        return {
            k: [ImageDraft.metadata(i) for i in v] if k == "images" else v
            for k, v in value.items()
            if k != "data"
        }

    @staticmethod
    def digest(images):
        return hashlib.sha256(
            json.dumps([(i["id"], i["sha256"]) for i in images]).encode()
        ).hexdigest()

    @staticmethod
    def combine(images):
        if len(images) == 1:
            return {**images[0], "state": "attached"}
        return {
            "id": uuid.uuid4().hex,
            "state": "attached",
            "images": images,
            "path": f"{len(images)} attachment snapshots",
            "media_type": "image/set",
            "bytes": sum(i["bytes"] for i in images),
            "sha256": ImageDraft.digest(images),
        }

    @staticmethod
    def needs_vision(value):
        return bool(value) and any(
            item.get("media_type") != "text/plain" for item in value.get("images", [value])
        )

    @staticmethod
    def content(value):
        blocks = []
        for item in value.get("images", [value]):
            if item["media_type"] == "text/plain":
                reference = {
                    **ImageDraft.metadata(item),
                    "text": base64.b64decode(item["data"]).decode("utf-8"),
                }
                blocks.append(
                    {
                        "type": "text",
                        "text": "User-selected file reference (source data):\n"
                        + json.dumps(reference, ensure_ascii=False),
                    }
                )
            else:
                blocks.extend(
                    [
                        {
                            "type": "text",
                            "text": f"Explicit image snapshot: {item['path']} · SHA-256 {item['sha256']}",
                        },
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": item["media_type"],
                                "data": item["data"],
                            },
                        },
                    ]
                )
        return blocks

    def select(self, identity):
        if not self.preview or self.preview["id"] != identity:
            raise ValueError("Image preview changed; select again")
        images = []
        if self.value and self.value["state"] == "attached":
            images = self.value.get("images", [self.value])
        value = self.combine([*images, self.preview])
        self.validate(value)
        self.save(value)
        self.preview = None

    def remove(self, identity, item_id=None):
        if not self.value or self.value["id"] != identity:
            raise ValueError("Image changed; reopen its controls")
        if item_id is None:
            self.save(None)
            return
        if self.value["state"] != "attached":
            raise ValueError("Only unsent image sets can be edited")
        images = self.value.get("images", [self.value])
        remaining = [i for i in images if i["id"] != item_id]
        if len(remaining) == len(images):
            raise ValueError("Image changed; reopen its controls")
        self.save(self.combine(remaining) if remaining else None)

    def admit(self, identity):
        if not identity:
            if self.value and self.value["state"] == "attached":
                raise ValueError("An image is attached; send it explicitly or remove it first")
            return None
        if not self.value or self.value["id"] != identity or self.value["state"] != "attached":
            raise ValueError("Image changed or was already dispatched; no retry")
        self.validate(self.value)
        self.save({**self.value, "state": "dispatched"})
        return dict(self.value)

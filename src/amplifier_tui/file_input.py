"""Explicit local text-file snapshots, never automatic reads from completion."""

import base64
import hashlib
import json
import os
import stat
import uuid
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
        if raw.startswith(b"\x89PNG\r\n\x1a\n"):
            media_type = "image/png"
        elif raw.startswith(b"\xff\xd8\xff") and raw.endswith(b"\xff\xd9"):
            media_type = "image/jpeg"
        else:
            raise ValueError("Only PNG and JPEG image snapshots are supported")
        return {
            "path": str(path),
            "sha256": digest,
            "bytes": len(raw),
            "media_type": media_type,
            "data": base64.b64encode(raw).decode("ascii"),
            "id": uuid.uuid4().hex,
        }
    text = raw.decode("utf-8")
    if any(ord(c) < 32 and c not in "\n\r\t" for c in text) or "\x7f" in text:
        raise ValueError("Binary or terminal-control content is unsupported")
    return {"path": str(path), "sha256": digest, "bytes": len(raw), "text": text}


class ImageDraft:
    """One explicit immutable image. Dispatch is never restored as unsent intent."""

    def __init__(self, store):
        self.path = store.path / "image-draft.json" if store else None
        self.value, self.preview = None, None
        if self.path and self.path.exists():
            with self.path.open("rb") as stream:
                raw = stream.read(3 * 1024 * 1024 + 1)
            if len(raw) > 3 * 1024 * 1024:
                raise ValueError("Image draft exceeds storage limit; original retained")
            self.value = json.loads(raw)
            if self.value is not None:
                self.validate(self.value)

    @staticmethod
    def validate(value):
        if not isinstance(value, dict) or value.get("state") not in ("attached", "dispatched"):
            raise ValueError("Invalid image admission record; no retry")
        raw = base64.b64decode(value["data"], validate=True)
        if (
            not 0 < len(raw) <= 2 * 1024 * 1024
            or hashlib.sha256(raw).hexdigest() != value["sha256"]
            or len(raw) != value["bytes"]
        ):
            raise ValueError("Image snapshot failed integrity verification")
        if value.get("media_type") not in ("image/png", "image/jpeg") or not isinstance(
            value.get("id"), str
        ):
            raise ValueError("Invalid image identity/type")

    def save(self, value):
        from .conversations import atomic_json

        if self.path:
            atomic_json(self.path, value)
        self.value = value

    def public(self):
        return {k: v for k, v in self.value.items() if k != "data"} if self.value else None

    def select(self, identity):
        if not self.preview or self.preview["id"] != identity:
            raise ValueError("Image preview changed; select again")
        self.save({**self.preview, "state": "attached"})
        self.preview = None

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

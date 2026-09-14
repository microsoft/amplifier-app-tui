"""Explicit local text-file snapshots, never automatic reads from completion."""

import hashlib
import os
import stat
from pathlib import Path

MAX_FILE = 64 * 1024


def snapshot(cwd, name):
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
            if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_FILE:
                raise ValueError(
                    "Select a regular text file of at most 64 KiB; images are unsupported"
                )
            raw = stream.read(MAX_FILE + 1)
            after = os.fstat(stream.fileno())
            if len(raw) > MAX_FILE or (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            ):
                raise ValueError("File changed while reading; refresh explicitly")
    finally:
        os.close(directory)
    text = raw.decode("utf-8")
    if any(ord(c) < 32 and c not in "\n\r\t" for c in text) or "\x7f" in text:
        raise ValueError("Binary or terminal-control content is unsupported")
    digest = hashlib.sha256(raw).hexdigest()
    return {"path": str(path), "sha256": digest, "bytes": len(raw), "text": text}

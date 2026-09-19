"""Private UI intent, separate from admission and canonical model history."""

import json
import os
import stat

from .conversations import atomic_json

MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 32


def read(directory):
    try:
        parent = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return []
    try:
        try:
            descriptor = os.open(
                "editors.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
            )
        except FileNotFoundError:
            return []
        with os.fdopen(descriptor, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValueError("Local editor record must be a regular file")
            raw = stream.read(MAX_BYTES + 1)
    finally:
        os.close(parent)
    if len(raw) > MAX_BYTES:
        raise ValueError("Local editor record exceeds 2 MiB")
    value = json.loads(raw)
    if not isinstance(value, dict) or value.get("version") != 1:
        raise ValueError("Invalid local editor record; original retained")
    return validate(value.get("rows"))


def validate(rows):
    if not isinstance(rows, list) or len(rows) > MAX_ROWS:
        raise ValueError("Retain at most 32 local editor drafts; remove old drafts explicitly")
    ids = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"id", "kind", "source", "text"}:
            raise ValueError("Invalid local draft fields")
        if row["kind"] not in ("answer", "correction", "startup", "dialog"):
            raise ValueError("Unknown local editor kind")
        for key in ("id", "source"):
            if not isinstance(row[key], str) or not 0 < len(row[key]) <= 256:
                raise ValueError("Local draft requires a bounded source identity")
        if row["id"] in ids:
            raise ValueError("Duplicate local draft identity")
        ids.add(row["id"])
        if not isinstance(row["text"], str) or len(row["text"]) > 65536:
            raise ValueError("Local draft exceeds 65536 characters")
    if len(json.dumps({"version": 1, "rows": rows}, ensure_ascii=False).encode()) > MAX_BYTES:
        raise ValueError("Local editor record exceeds 2 MiB")
    return rows


def save(store, request):
    if not store or (not getattr(store, "shared_session", False) and store.journal is None):
        return False, "Local editor storage unavailable; copy text before exiting"
    if getattr(store, "shared_session", False):
        store.check_open()
    rows = read(store.path)
    if request.get("remove") is not None:
        rows = [row for row in rows if row["id"] != request["remove"]]
    else:
        row = request.get("row")
        validate([row])
        if row["source"] != store.identity:
            return False, "Editor draft belongs to another conversation"
        if row in rows:
            return True, "Local draft already saved; not submitted"
        rows = [old for old in rows if old["id"] != row["id"]]
        if row["text"]:
            rows.append(row)
    validate(rows)
    atomic_json(store.path / "editors.json", {"version": 1, "rows": rows})
    return True, "Local draft saved; not submitted"

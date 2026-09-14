"""Private, single-writer checkpoints. Canonical context is not rendered history.

An incomplete turn is deliberately not repaired or replayed. The journal retains
its observations; only a completed, matching checkpoint admits a resumed turn.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import tempfile
import uuid
from dataclasses import asdict
from pathlib import Path

from .events import Event, Transcript


def portable_history(messages):
    """Compare canonical content while allowing context-simple's documented re-sequencing.

    Only its internal metadata._seq is ignored, not role/content/tool IDs or other
    metadata. Recovery-created messages have no sequence until the module stamps them.
    """
    output = []
    for message in messages:
        value = dict(message)
        if isinstance(value.get("metadata"), dict):
            metadata = {k: v for k, v in value["metadata"].items() if k != "_seq"}
            if metadata:
                value["metadata"] = metadata
            else:
                value.pop("metadata")
        output.append(value)
    return output


def atomic_json(path, value):
    fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)


def catalog(state_dir):
    root = Path(state_dir) / "conversations"
    result = []
    for path in root.glob("*/metadata.json"):
        try:
            value = json.loads(path.read_text())
            if (
                isinstance(value, dict)
                and value.get("version") == 1
                and value.get("id") == path.parent.name
            ):
                result.append((path.stat().st_mtime_ns, value))
        except (OSError, ValueError):
            continue
    return [value for _, value in sorted(result, key=lambda row: row[0], reverse=True)]


def resolve_resume(state_dir, identity):
    entries = catalog(state_dir)
    if identity == "latest" and entries:
        return entries[0]
    for entry in entries:
        if entry["id"] == identity:
            return entry
    raise ValueError("Conversation not found; use --list-sessions with the same --state-dir")


class ConversationStore:
    def __init__(self, state_dir, launch, resume=None):
        self.identity = resume or uuid.uuid4().hex
        if not re.fullmatch(r"[0-9a-f]{32}", self.identity):
            raise ValueError("Invalid conversation identity")
        self.path = Path(state_dir) / "conversations" / self.identity
        if resume and not self.path.is_dir():
            raise ValueError("Conversation not found")
        self.path.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.lock = os.open(self.path / "lock", os.O_CREAT | os.O_RDWR, 0o600)
        self.journal = None
        try:
            try:
                fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise BlockingIOError(
                    "Conversation is already open; close its other client before resuming"
                ) from exc
            self.metadata = {"version": 1, "id": self.identity, "launch": launch}
            self.saved = None
            self.draft = ""
            self.restored_events = []
            if resume:
                self.metadata = json.loads((self.path / "metadata.json").read_text())
                if self.metadata.get("version") != 1 or self.metadata.get("id") != self.identity:
                    raise ValueError("Unsupported or corrupt conversation metadata")
                if self.metadata["launch"] != launch:
                    raise ValueError("Resume composition or working directory does not match")
                self.saved = json.loads((self.path / "checkpoint.json").read_text())
                if self.saved.get("version") != 1 or self.saved.get("status") != "ready":
                    raise ValueError(
                        "Conversation has uncertain/incomplete work; resume refused. No work replayed."
                    )
                self.draft = json.loads((self.path / "draft.json").read_text())["text"]
                self.restored_events = [
                    Event(**json.loads(line))
                    for line in (self.path / "events.jsonl").read_text().splitlines()
                ]
                if any(
                    event.session_id != self.identity or event.sequence != index
                    for index, event in enumerate(self.restored_events, 1)
                ):
                    raise ValueError(
                        "Conversation journal identity/order is corrupt; resume refused"
                    )
                if len(self.restored_events) != self.saved["sequence"]:
                    raise ValueError(
                        "Conversation journal differs from its checkpoint; outcome uncertain"
                    )
            else:
                atomic_json(self.path / "metadata.json", self.metadata)
                self.save_draft("")
            fd = os.open(self.path / "events.jsonl", os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
            self.journal = os.fdopen(fd, "a")
        except BaseException:
            os.close(self.lock)
            self.lock = None
            raise

    def record(self, event):
        # Admission is fsynced before execution starts. Other observations flush
        # incrementally; a checkpoint fsyncs the complete journal before committing.
        self.journal.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")
        self.journal.flush()
        if event.kind in ("steering.updated", "question.updated"):
            os.fsync(self.journal.fileno())
        if event.kind == "turn.accepted":
            os.fsync(self.journal.fileno())
            if not self.metadata.get("title"):
                self.metadata["title"] = " ".join(event.payload["text"].split())[:100]
                atomic_json(self.path / "metadata.json", self.metadata)

    def checkpoint(self, messages, sequence, fingerprint, ready):
        self.journal.flush()
        os.fsync(self.journal.fileno())
        atomic_json(
            self.path / "checkpoint.json",
            {
                "version": 1,
                "status": "ready" if ready else "uncertain",
                "messages": messages,
                "sequence": sequence,
                "fingerprint": fingerprint,
            },
        )
        # Latest means last checkpoint activity, not lexical UUID order.
        os.utime(self.path / "metadata.json", None)

    def save_draft(self, text):
        atomic_json(self.path / "draft.json", {"text": text})
        self.draft = text

    def projection(self):
        transcript = Transcript()
        for event in self.restored_events:
            transcript.apply(event)
        return [
            {**asdict(item), "detail": json.dumps(item.detail, ensure_ascii=False, indent=2)}
            for item in transcript.items.values()
        ]

    def close(self):
        if self.journal:
            self.journal.close()
            self.journal = None
        if self.lock is not None:
            os.close(self.lock)
            self.lock = None

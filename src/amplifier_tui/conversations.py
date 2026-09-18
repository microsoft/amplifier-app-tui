"""Private, single-writer checkpoints. Canonical context is not rendered history.

An incomplete context is deliberately not repaired or replayed. A validated,
matching checkpoint admits a resumed turn independently of earlier turn success.
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


def catalog(state_dir, *, cwd=None, archived=False, cli_home=None):
    root = Path(state_dir) / "conversations"
    directory = Path(cwd).resolve() if cwd is not None else None
    result = []
    for path in root.glob("*/metadata.json"):
        try:
            # Catalog discovery must not load an arbitrarily large/corrupt record.
            with path.open() as stream:
                raw = stream.read(65537)
            if len(raw) > 65536:
                continue
            value = json.loads(raw)
            if (
                isinstance(value, dict)
                and value.get("version") == 1
                and value.get("id") == path.parent.name
                and bool(value.get("archived", False)) == archived
                # Private journals without a CLI home are test-harness storage.
                # Product discovery never falls back to a retired live store.
                and (cli_home is None or value.get("launch", {}).get("fixture") is True)
            ):
                if directory is not None:
                    launch = value.get("launch")
                    recorded = launch.get("cwd") if isinstance(launch, dict) else None
                    if (
                        not isinstance(recorded, str)
                        or not Path(recorded).is_absolute()
                        or Path(recorded).resolve() != directory
                    ):
                        continue
                result.append((path.stat().st_mtime_ns, value))
        except (OSError, ValueError, RuntimeError):
            continue
    if cli_home is not None and directory is not None:
        from .cli_compat import shared_session_catalog

        shared = shared_session_catalog(cli_home, directory, archived=archived)
        identities = {entry["id"] for _, entry in shared}
        result = [row for row in result if row[1]["id"] not in identities] + shared
    return [value for _, value in sorted(result, key=lambda row: row[0], reverse=True)]


def entry_path(state_dir, entry):
    if entry.get("shared_session"):
        from .cli_compat import session_directory

        launch = entry["launch"]
        return session_directory(launch["cli_home"], launch["cwd"]) / entry["id"] / ".tui"
    return Path(state_dir) / "conversations" / entry["id"]


def open_conversation(state_dir, launch, resume=None):
    if launch.get("fixture"):
        return ConversationStore(state_dir, launch, resume)
    return SharedConversationStore(state_dir, launch, resume)


def archive_conversation(state_dir, identity, *, cwd, archived, cli_home=None):
    """Reversible metadata-only housekeeping under the same single-writer lock."""
    if (
        not isinstance(identity, str)
        or not re.fullmatch(r"[A-Za-z0-9-]{1,160}", identity)
        or identity == "latest"
    ):
        raise ValueError("Use an exact conversation ID from this directory, not latest")
    path = Path(state_dir) / "conversations" / identity
    shared = None
    if cli_home is not None:
        from .cli_compat import shared_session_entry

        shared = shared_session_entry(cli_home, cwd, identity)
        path = entry_path(state_dir, shared)
        path.mkdir(mode=0o700, exist_ok=True)
    metadata = path / "metadata.json"
    if path.is_symlink() or metadata.is_symlink() or not path.is_dir():
        raise ValueError("Conversation unavailable; no change made")
    lock = os.open(path / "lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError(
                "Close the conversation in every client before archiving/restoring"
            ) from exc
        if metadata.exists():
            with metadata.open() as stream:
                raw = stream.read(65537)
            if len(raw) > 65536:
                raise ValueError("Conversation metadata exceeds housekeeping limit")
            value = json.loads(raw)
        elif shared:
            value = shared
        else:
            raise ValueError("Conversation metadata missing")
        launch = value.get("launch") if isinstance(value, dict) else None
        recorded = launch.get("cwd") if isinstance(launch, dict) else None
        if (
            not isinstance(value, dict)
            or value.get("version") != 1
            or value.get("id") != identity
            or not isinstance(recorded, str)
            or not Path(recorded).is_absolute()
            or Path(recorded).resolve() != Path(cwd).resolve()
        ):
            raise ValueError("Conversation not found in this working directory; no change made")
        value["archived"] = bool(archived)
        atomic_json(metadata, value)
    finally:
        os.close(lock)


def resolve_resume(state_dir, identity, *, cwd=None, cli_home=None):
    entries = catalog(state_dir, cwd=cwd, cli_home=cli_home)
    if identity == "latest" and entries:
        return entries[0]
    for entry in entries:
        if entry["id"] == identity:
            return entry
    scope = " in this working directory" if cwd is not None else ""
    raise ValueError(
        f"Conversation not found{scope}; launch from its directory and use --list-sessions with the same --state-dir"
    )


def checkpoint_status(path):
    """Bounded discovery hint, never permission to execute an unchecked checkpoint.

    Our atomic writer emits version/status first. Large public contexts must not
    hide an uncertain status merely because the rest exceeds the menu read budget.
    Full schema, journal and context validation still happens on opening.
    """
    with Path(path).open() as stream:
        raw = stream.read(65537)
    if len(raw) <= 65536:
        return json.loads(raw).get("status")
    prefix = re.match(
        r'\s*\{\s*"version"\s*:\s*1\s*,\s*"status"\s*:\s*"(ready|uncertain)"\s*[,}]', raw
    )
    return prefix.group(1) if prefix else None


class ConversationStore:
    def __init__(self, state_dir, launch, resume=None, *, _path=None, _identity=None):
        self.identity = _identity or resume or uuid.uuid4().hex
        pattern = r"[A-Za-z0-9-]{1,160}" if _path is not None else r"[0-9a-f]{32}"
        if not re.fullmatch(pattern, self.identity):
            raise ValueError("Invalid conversation identity")
        self.path = _path or Path(state_dir) / "conversations" / self.identity
        if resume and not self.path.is_dir():
            raise ValueError("Conversation not found")
        self.path.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.path.is_symlink():
            raise ValueError("Conversation directory cannot be a symlink")
        if _path is not None:
            for name in ("metadata.json", "checkpoint.json", "events.jsonl", "draft.json"):
                if (self.path / name).is_symlink():
                    raise ValueError("Shared session sidecar files cannot be symlinks")
        self.lock = os.open(self.path / "lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
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
                if self.metadata.get("archived"):
                    raise ValueError("Conversation is archived; restore explicitly before resuming")
                if self.metadata["launch"] != launch and _path is None:
                    raise ValueError("Resume composition or working directory does not match")
                self.metadata["launch"] = launch
                self.saved = self.load_checkpoint()
                if self.saved.get("version") != 1 or self.saved.get("status") != "ready":
                    raise ValueError(
                        "Conversation has uncertain/incomplete work; resume refused. No work replayed. "
                        f"Use Resume's recovery choice, or amplifier-tui --recover {self.identity}, "
                        "to create a recovered conversation with the original preserved."
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
            fd = os.open(
                self.path / "events.jsonl",
                os.O_CREAT | os.O_APPEND | os.O_WRONLY | os.O_NOFOLLOW,
                0o600,
            )
            self.journal = os.fdopen(fd, "a")
        except BaseException:
            os.close(self.lock)
            self.lock = None
            raise

    def load_checkpoint(self):
        return json.loads((self.path / "checkpoint.json").read_text())

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
                self.metadata["title_source"] = "prompt"
                atomic_json(self.path / "metadata.json", self.metadata)

    def manual_title(self):
        source = self.metadata.get("title_source")
        if source:
            return source in ("user", "external")
        # Older releases did not track provenance. Preserve any title that
        # cannot be established as their exact first-prompt fallback.
        first = next((e for e in self.restored_events if e.kind == "turn.accepted"), None)
        fallback = " ".join(first.payload["text"].split())[:100] if first else None
        return bool(self.metadata.get("title") and self.metadata["title"] != fallback)

    def set_title(self, title, *, generated=False, description=None):
        if not isinstance(title, str) or not title.strip() or not title.isprintable():
            return False
        if generated and self.manual_title():
            return False
        metadata = {
            **self.metadata,
            "title": title.strip()[:100],
            "title_source": "generated" if generated else "user",
        }
        if generated and isinstance(description, str) and description.isprintable():
            metadata["description"] = description[:200]
        atomic_json(self.path / "metadata.json", metadata)
        self.metadata = metadata
        return True

    def naming_metadata(self, completed_turns):
        # The ecosystem naming hook owns this sidecar. It must never replace
        # our admission/composition metadata with a stale pre-request copy.
        path = self.path / "naming"
        path.mkdir(mode=0o700, exist_ok=True)
        value = {"turn_count": completed_turns}
        if self.manual_title() or self.metadata.get("title_source") == "generated":
            value["name"] = self.metadata.get("title")
            value["description"] = self.metadata.get("description", "")
        atomic_json(path / "metadata.json", value)
        return path

    def checkpoint_auxiliary(self, sequence):
        """An idle utility observation changes no canonical context or admission."""
        if self.saved:
            self.checkpoint(
                self.saved["messages"],
                sequence,
                self.saved["fingerprint"],
                self.saved["status"] == "ready",
            )

    def checkpoint(self, messages, sequence, fingerprint, ready):
        self.journal.flush()
        os.fsync(self.journal.fileno())
        saved = {
            "version": 1,
            "status": "ready" if ready else "uncertain",
            "messages": messages,
            "sequence": sequence,
            "fingerprint": fingerprint,
        }
        atomic_json(self.path / "checkpoint.json", saved)
        self.saved = saved
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


class SharedConversationStore(ConversationStore):
    """CLI owns transcript/metadata; this app owns only the .tui observation sidecar.

    The old CLI does not cooperate with our lock. Sequential client switching is
    supported; digest checks detect stale writers, not a distributed transaction.
    """

    def projection(self):
        from .inspection import CallUsage

        items = super().projection()
        if any(e.payload.get("accounting_snapshot") for e in self.restored_events):
            # Historical footers are receipts from that point in time. Show the
            # reconciled baseline separately; never rewrite history or journal a
            # duplicate summary each time someone opens the same conversation.
            text = "On resume · " + CallUsage(self.restored_events).costs(session_only=True)
            items.append(
                {
                    "id": "shared:resume-accounting",
                    "kind": "notice",
                    "text": text,
                    "status": "",
                    "detail": json.dumps({"source": "usage", "text": text}),
                }
            )
        return items

    def __init__(self, state_dir, launch, resume=None):
        from amplifier_app_cli.session_store import SessionStore

        from .cli_compat import session_directory, shared_session_entry

        launch = {**launch, "shared_session": True}
        identity = resume or str(uuid.uuid4())
        if not re.fullmatch(r"[A-Za-z0-9-]{1,160}", identity):
            raise ValueError("Invalid shared session identity")
        root = session_directory(launch["cli_home"], launch["cwd"])
        self.canonical_path = root / identity
        # Reject symlinked descendants before mounting modules or creating state.
        home = Path(launch["cli_home"])
        for path in (home, *reversed(root.parents[:2]), root, self.canonical_path):
            if path.is_symlink():
                raise ValueError("Shared session directories cannot be symlinks")
        self.cli_store = SessionStore(base_dir=root)
        self.shared_session = True
        self.canonical_launch = launch
        if resume:
            entry = shared_session_entry(home, launch["cwd"], identity)
            if entry["archived"]:
                raise ValueError("Conversation is archived")
        else:
            self.canonical_path.mkdir(mode=0o700)
            self.cli_store.save(identity, [], self._metadata(identity, []))
        self.canonical_messages, self.canonical_digest = self._read_canonical(identity)
        path = self.canonical_path / ".tui"
        existing = (path / "events.jsonl").exists()
        super().__init__(
            state_dir, launch, identity if existing else None, _path=path, _identity=identity
        )
        try:
            if not existing:
                self._seed_view()
            self._restore_accounting()
            if not resume:
                # Fresh forks/imports must reach the host's explicit transfer path.
                self.saved = None
            canonical = self.cli_store.get_metadata(identity)
            if canonical.get("name"):
                if canonical["name"] != self.metadata.get("title"):
                    self.metadata["title_source"] = "external"
                self.metadata["title"] = canonical["name"]
            atomic_json(self.path / "metadata.json", self.metadata)
        except BaseException:
            self.close()
            raise

    def _metadata(self, identity, messages):
        from datetime import UTC, datetime

        from .cli_compat import read_session_file

        existing = {}
        if (self.canonical_path / "metadata.json").exists():
            launch = self.canonical_launch
            existing = json.loads(
                read_session_file(
                    launch["cli_home"], launch["cwd"], identity, "metadata.json", 65536
                )
            )
            if not isinstance(existing, dict):
                raise ValueError("Invalid canonical metadata; nothing overwritten")
        bundle = self.canonical_launch.get("bundle") or existing.get("bundle", "unknown")
        if "://" not in bundle and Path(bundle).exists():
            bundle = Path(bundle).resolve().as_uri()
        return {
            **existing,
            "session_id": identity,
            "created": existing.get("created", datetime.now(UTC).isoformat()),
            "bundle": bundle,
            "working_dir": self.canonical_launch["cwd"],
            "turn_count": sum(m.get("role") == "user" for m in messages),
        }

    def _read_canonical(self, identity=None):
        import hashlib

        from .cli_compat import read_session_file
        from .recovery import public_history

        launch = self.canonical_launch
        raw = read_session_file(
            launch["cli_home"],
            launch["cwd"],
            identity or self.identity,
            "transcript.jsonl",
            8 * 1024 * 1024,
        )
        messages = [json.loads(line) for line in raw.splitlines() if line.strip()]
        public_history(messages)  # Validation only; never repair or execute old tools.
        return messages, hashlib.sha256(raw).hexdigest()

    def assert_current(self):
        from .cli_compat import shared_session_entry

        shared_session_entry(
            self.canonical_launch["cli_home"], self.canonical_launch["cwd"], self.identity
        )
        if self._read_canonical()[1] != self.canonical_digest:
            raise ValueError(
                "CLI transcript changed while this client was open; close and resume again. Nothing overwritten."
            )

    def load_checkpoint(self):
        saved = super().load_checkpoint()
        if saved.get("status") != "ready":
            raise ValueError(
                "Shared session has uncertain/incomplete work; inspect before resuming"
            )
        if saved.get("canonical_sha256") != self.canonical_digest:
            events = [
                json.loads(line) for line in (self.path / "events.jsonl").read_text().splitlines()
            ]
            if len(events) != saved.get("sequence") or any(
                e.get("sequence") != i or e.get("session_id") != self.identity
                for i, e in enumerate(events, 1)
            ):
                raise ValueError("TUI journal contains incomplete work; shared resume refused")
            # Preserve prior observations. Only the derived view is rebuilt; drafts
            # and child receipts are retained. No history becomes pending work.
            archive = self.path / "views" / uuid.uuid4().hex
            self._prior_usage = [
                Event(**e)
                for e in events
                if isinstance(e.get("payload", {}).get("usage_call"), dict)
            ]
            archive.mkdir(parents=True, mode=0o700)
            for name in ("events.jsonl", "checkpoint.json"):
                (self.path / name).rename(archive / name)
            self.journal = os.fdopen(
                os.open(self.path / "events.jsonl", os.O_CREAT | os.O_WRONLY | os.O_EXCL, 0o600),
                "w",
            )
            try:
                self._seed_view()
                saved = super().load_checkpoint()
            finally:
                self.journal.close()
                self.journal = None
        return {**saved, "messages": self.canonical_messages, "fingerprint": None}

    @staticmethod
    def observations(messages, identity):
        from .cli_compat import session_message_visible
        from .events import tool_status

        events = []
        turn = 0

        def emit(kind, item, **payload):
            event = Event(identity, len(events) + 1, f"history:{turn}", kind, item, payload)
            events.append(event)

        for index, message in enumerate(messages):
            if message.get("role") != "tool" and not session_message_visible(message):
                continue
            role, content = message["role"], message.get("content", "")
            if isinstance(content, list):
                content = "\n".join(
                    b.get("text", "")
                    for b in content
                    if isinstance(b, dict) and isinstance(b.get("text", ""), str)
                )
            if role == "user":
                turn += 1
                emit("turn.accepted", f"history:user:{index}", text=content)
            elif role == "assistant":
                if content:
                    emit("text.final", f"history:text:{index}", text=content)
                for call in message.get("tool_calls") or []:
                    function = call.get("function", call)
                    arguments = function.get("arguments", {})
                    if isinstance(arguments, str):
                        try:
                            arguments = json.loads(arguments)
                        except ValueError:
                            arguments = {"raw": arguments}
                    emit(
                        "tool.updated",
                        call["id"],
                        name=function.get("name") or function.get("tool", "tool"),
                        arguments=arguments,
                        status="unknown",
                    )
            elif role == "tool":
                emit(
                    "tool.ended",
                    message["tool_call_id"],
                    result=content,
                    status=tool_status("tool:post", content),
                )
        return events

    def _seed_view(self):
        self.metadata["shared_history_unaccounted"] = bool(self.canonical_messages)
        self.restored_events = self.observations(self.canonical_messages, self.identity)
        for event in self.restored_events:
            self.record(event)
        self._save_marker(self.canonical_messages, len(self.restored_events), None, True)

    def _restore_accounting(self):
        """Reconcile receipts into a sidecar-only historical session baseline.

        Canonical logs and conversation bytes are read-only here. Evidence rows
        live in Activity, not as hundreds of replayed conversation notices.
        """
        import hashlib
        from datetime import datetime

        from .cli_compat import historical_usage
        from .inspection import add_usage, call_usage_text, usage_totals, usage_values

        if not self.canonical_messages and not self.restored_events:
            return
        launch = self.canonical_launch
        logged, partial = historical_usage(launch["cli_home"], launch["cwd"], self.identity)
        if not logged and not self.metadata.get("shared_history_unaccounted"):
            # A TUI-owned history remains authoritative even without a logging
            # module. External CLI history without receipts is different.
            partial = False
        records = {row["usage_receipt_id"]: row for row in logged}
        logged_owners = {row["usage_session_id"] for row in logged}
        sources = [*getattr(self, "_prior_usage", ()), *self.restored_events]
        for event in sources:
            payload = event.payload
            if not isinstance(payload.get("usage_call"), dict):
                continue
            key = payload.get("usage_receipt_id")
            owner = payload.get("usage_session_id") or payload.get("child_id") or self.identity
            if key is None and owner in logged_owners:
                # The two observers cannot be joined without identity. Use the
                # canonical receipts and disclose the gap instead of guessing
                # equivalence from equal amounts or neighboring timestamps.
                partial = True
                continue
            key = (
                key or payload.get("accounting_key") or f"native:{event.session_id}:{event.item_id}"
            )
            if key in records:
                if usage_values(records[key]["usage_call"]) != usage_values(payload["usage_call"]):
                    partial = True
                continue
            records[key] = {
                "accounting_key": key,
                "usage_receipt_id": payload.get("usage_receipt_id"),
                "usage_session_id": owner,
                "usage_call": payload["usage_call"],
                "provider": payload.get("provider", {}),
                "timestamp": payload.get("timestamp"),
                "duration_ms": payload.get("duration_ms"),
                "purpose": payload.get("purpose"),
                "text": payload.get("text", "Usage details unavailable"),
            }
        if self.metadata.get("shared_history_unaccounted") and not logged:
            partial = True
        snapshot = usage_totals()
        for row in records.values():
            add_usage(snapshot, usage_values(row["usage_call"]))
        snapshot["totals"] = {
            k: str(v) if k == "cost_usd" else v for k, v in snapshot["totals"].items()
        }
        fingerprint = hashlib.sha256(
            json.dumps([records, partial], sort_keys=True).encode()
        ).hexdigest()
        previous = next(
            (e for e in reversed(self.restored_events) if e.payload.get("accounting_snapshot")),
            None,
        )
        self.metadata["shared_history_unaccounted"] = partial
        if previous and previous.payload.get("accounting_fingerprint") == fingerprint:
            return

        def retain(item, **payload):
            event = Event(
                self.identity,
                len(self.restored_events) + 1,
                None,
                "activity.observed",
                item,
                payload,
            )
            self.record(event)
            self.restored_events.append(event)

        retain(
            "shared:usage",
            name="Earlier session usage",
            status="partial" if partial else "observed",
            accounting_snapshot=snapshot,
            accounting_fingerprint=fingerprint,
            partial=partial,
            text=f"{snapshot['requests']} recorded calls. Historical session accounting, not next-turn usage. "
            + (
                "Some earlier receipts are unavailable or cannot be correlated."
                if partial
                else "Canonical and native receipts reconciled by observed identity."
            ),
        )
        for key, row in records.items():
            row = dict(row)
            if "text" not in row:
                try:
                    stamp = datetime.fromisoformat(
                        row["timestamp"].replace("Z", "+00:00")
                    ).astimezone()
                except (ValueError, TypeError, AttributeError):
                    stamp = None
                row["text"] = (
                    call_usage_text(
                        usage_values(row["usage_call"]),
                        row["provider"],
                        agent=row["purpose"]
                        or ("Child session" if row["usage_session_id"] != self.identity else ""),
                        timestamp=stamp,
                        duration_ms=row["duration_ms"],
                    )
                    if stamp
                    else "Recorded usage; timestamp unavailable. Inspect the exact fields."
                )
            retain(
                "shared:" + key,
                name="Recorded model call",
                source="usage",
                parent_item_id="shared:usage",
                status="observed",
                **row,
            )
        self._save_marker(self.canonical_messages, len(self.restored_events), None, True)

    def _save_marker(self, messages, sequence, fingerprint, ready):
        self.journal.flush()
        os.fsync(self.journal.fileno())
        marker = dict(
            version=1,
            status="ready" if ready else "uncertain",
            sequence=sequence,
            fingerprint=fingerprint,
            canonical_sha256=self.canonical_digest,
        )
        atomic_json(self.path / "checkpoint.json", marker)
        self.saved = {**marker, "messages": messages}

    def checkpoint(self, messages, sequence, fingerprint, ready):
        self.assert_current()
        # Mark pending before the CLI's two-file save. A crash is uncertainty,
        # never permission to reuse an older UI snapshot as canonical context.
        self._save_marker(messages, sequence, fingerprint, False)
        self.cli_store.save(self.identity, messages, self._metadata(self.identity, messages))
        self.canonical_messages, self.canonical_digest = self._read_canonical()
        self._save_marker(self.canonical_messages, sequence, fingerprint, ready)
        os.utime(self.path / "metadata.json", None)

    def set_title(self, title, *, generated=False, description=None):
        if not super().set_title(title, generated=generated, description=description):
            return False
        self.cli_store.update_metadata(
            self.identity,
            {
                "name": self.metadata["title"],
                **(
                    {"description": self.metadata["description"]}
                    if "description" in self.metadata
                    else {}
                ),
            },
        )
        return True

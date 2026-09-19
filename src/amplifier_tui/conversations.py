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


def _acquire_shared_owner(cwd, identity):
    from amplifier_foundation.session import SessionBusyError, SharedSessionStore

    try:
        # Use Foundation's shared default/environment root, never a TUI-specific
        # directory. The exact workspace/session key must match the other apps.
        return SharedSessionStore(cwd, identity).acquire(app="amplifier-tui", pid=os.getpid())
    except SessionBusyError as exc:
        # Owner metadata is untrusted advisory text. Do not forward arbitrary
        # client names, machine paths or terminal escapes into the startup error.
        raise BlockingIOError(
            "Conversation is open in another Amplifier client; close that session and retry. "
            "Nothing sent; your draft is retained."
        ) from exc


def archive_conversation(state_dir, identity, *, cwd, archived, cli_home=None):
    """Reversible metadata-only housekeeping under the same single-writer lock."""
    owner = None
    if cli_home is not None:
        try:
            owner = _acquire_shared_owner(cwd, identity)
        except BlockingIOError as exc:
            raise ValueError(
                "Close the conversation in every client before archiving/restoring"
            ) from exc
    try:
        return _archive_conversation(
            state_dir, identity, cwd=cwd, archived=archived, cli_home=cli_home
        )
    finally:
        if owner is not None:
            owner.release()


def _archive_conversation(state_dir, identity, *, cwd, archived, cli_home=None):
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
    """Foundation owns native history and writer coordination across clients.

    The .tui sidecar holds only local UI intent/admission receipts, not history.
    Ownership spans construction through runtime cleanup and close; revision checks
    additionally detect older, non-cooperating writers, not arbitrary races.
    Mutations and close run synchronously on the owning event loop, without an
    await between check and write. Cross-thread callers need synchronization;
    HeldSession.check alone is not atomic with release.
    """

    def history_page(self, offset=0):
        """Read-only pages of the resume snapshot, newest page first.

        Live events never shift offsets. Keep source identities, not rendered rows;
        the full canonical context is independent of this bounded IPC projection.
        """
        from .inspection import bounded_projection

        if type(offset) is not int or offset < 0:
            raise ValueError("Invalid history page")
        if getattr(self, "_history_sequence", None) != len(self.restored_events):
            transcript = Transcript()
            for event in self.restored_events:
                transcript.apply(event)
            self._history_items = list(transcript.items.values())
            self._history_sequence = len(self.restored_events)
            self._history_previous = {}
        count = len(self._history_items)
        if offset > count:
            raise ValueError("History page is outside this resume snapshot")
        end = count - offset
        retained, size = [], 0
        for item in reversed(self._history_items[max(0, end - 100) : end]):
            detail, limited = bounded_projection(item.detail, 65536)
            text = item.text[:65536].encode("utf-8")[:65536].decode("utf-8", errors="ignore")
            if len(item.text) > len(text):
                text += (
                    "\n[Historical preview shortened; the canonical transcript retains the source.]"
                )
                limited = True
            if limited and isinstance(detail, dict):
                detail = {
                    **detail,
                    "preview_limited": True,
                    "preview_note": "The canonical transcript retains the source.",
                }
            value = {
                "id": item.id,
                "kind": item.kind,
                "text": text,
                "status": item.status,
                "detail": json.dumps(detail, ensure_ascii=False, indent=2),
            }
            encoded_size = len(json.dumps(value, ensure_ascii=False).encode())
            # Leave room for separators, the snapshot envelope and bounded
            # accounting/recovery notices appended below.
            if size + encoded_size > 8 * 1024 * 1024 - 128 * 1024:
                break
            retained.append(value)
            size += encoded_size
        items = list(reversed(retained))
        next_offset = offset + len(items)
        if next_offset < count:
            self._history_previous[next_offset] = offset
        return {
            "items": items,
            "total": count,
            "offset": offset,
            "start": end - len(items) + 1 if items else 0,
            "end": end,
            "next_offset": next_offset if next_offset < count else None,
            "previous_offset": self._history_previous.get(offset, 0) if offset else None,
        }

    def projection(self):
        from .inspection import CallUsage

        page = self.history_page()
        items, count = page["items"], page["total"]
        if len(items) != count:
            notice = (
                f"Showing latest {len(items)} of {count} historical items. "
                "Actions → Earlier history to browse more. Full context retained."
            )
            items = [
                {
                    "id": "history:window",
                    "kind": "notice",
                    "text": notice,
                    "status": "",
                    "detail": json.dumps({"text": notice, "next_offset": page["next_offset"]}),
                },
                *items,
            ]
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
        recovered = sorted(
            {
                d.source
                for d in getattr(self, "history_diagnostics", ())
                if d.code == "recovered_backup" and d.source in ("transcript", "metadata")
            }
        )
        if recovered:
            text = (
                "Recovered "
                + " and ".join(recovered)
                + " from backup; the saved view may be older. Review before sending. "
                "No earlier work replayed."
            )
            items.append(
                {
                    "id": "shared:backup-recovery",
                    "kind": "notice",
                    "text": text,
                    "status": "warning",
                    "detail": json.dumps({"source": "history", "level": "warning", "text": text}),
                }
            )
        return items

    def __init__(self, state_dir, launch, resume=None):
        from amplifier_foundation.session import SessionHistoryStore

        from .cli_compat import session_directory

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
        self.shared_session = True
        self.canonical_launch = launch
        self.identity = identity
        self.journal = None
        self.lock = None
        self.history_store = SessionHistoryStore(self.canonical_path, session_id=identity)
        # Acquire before canonical reads/new-session writes or module mounting.
        # This object never replaces the handle: late callbacks retain their
        # original (released) capability rather than borrowing a new acquisition.
        self._owner = _acquire_shared_owner(launch["cwd"], identity)
        try:
            if not resume:
                root.mkdir(mode=0o700, parents=True, exist_ok=True)
                self.canonical_path.mkdir(mode=0o700)
                self._save_native([], self._metadata(identity, []))
            self.canonical_messages, self.canonical_digest = self._read_canonical()
            path = self.canonical_path / ".tui"
            prior_metadata = path / "metadata.json"
            if prior_metadata.exists():
                if path.is_symlink() or prior_metadata.is_symlink():
                    raise ValueError("Shared session sidecar files cannot be symlinks")
                with prior_metadata.open() as stream:
                    prior = stream.read(65537)
                if len(prior) > 65536:
                    raise ValueError("Shared session sidecar metadata exceeds limit")
                if json.loads(prior).get("archived"):
                    raise ValueError("Conversation is archived")
            self.path = path
            if path.is_symlink():
                raise ValueError("Shared session sidecar directory cannot be a symlink")
            path.mkdir(mode=0o700, exist_ok=True)
            for name in ("metadata.json", "checkpoint.json", "draft.json"):
                if (path / name).is_symlink():
                    raise ValueError("Shared session sidecar files cannot be symlinks")
            self.metadata = {"version": 1, "id": identity, "launch": launch}
            if prior_metadata.exists():
                self.metadata.update(json.loads(prior))
                self.metadata["launch"] = launch
            self.draft = ""
            if (path / "draft.json").exists():
                self.draft = json.loads((path / "draft.json").read_text())["text"]
            self.restored_events = self.observations(self.canonical_messages, identity)
            self._live_events = []
            self.saved = self.load_checkpoint() if resume else None
            self._restore_accounting()
            if self.saved:
                self.saved["sequence"] = len(self.restored_events)
            if not resume:
                # Fresh forks/imports must reach the host's explicit transfer path.
                self.saved = None
            canonical = self.canonical_metadata
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

        from .cli_compat import native_history

        self._owner.check()
        launch = self.canonical_launch
        existing = native_history(launch["cli_home"], launch["cwd"], identity, metadata_only=True)
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

    def _native_sources(self):
        """Check secure native revisions without reading history repeatedly."""
        from amplifier_foundation.session.history import file_stamp

        from .cli_compat import _NativeHistoryPath

        launch = self.canonical_launch
        sources = {}
        for key, filename in (
            ("transcript", "transcript.jsonl"),
            ("transcript_backup", "transcript.jsonl.backup"),
            ("metadata", "metadata.json"),
            ("metadata_backup", "metadata.json.backup"),
        ):
            sources[key] = file_stamp(
                _NativeHistoryPath(launch["cli_home"], launch["cwd"], self.identity, filename)
            )
        return sources

    @staticmethod
    def _revision_key(revision):
        import hashlib

        return hashlib.sha256(
            json.dumps(
                {k: asdict(v) if v is not None else None for k, v in revision.items()},
                sort_keys=True,
            ).encode()
        ).hexdigest()

    def _read_canonical(self):
        from .cli_compat import native_history
        from .recovery import native_resume_messages

        self._owner.check()
        launch = self.canonical_launch
        history = native_history(launch["cli_home"], launch["cwd"], self.identity)
        before = history.revision
        if not any(before[name] for name in ("transcript", "transcript_backup")):
            raise ValueError("Canonical transcript is missing; no empty history substituted")
        if not any(before[name] for name in ("metadata", "metadata_backup")):
            raise ValueError("Canonical metadata is missing; resume refused")
        if before != self._native_sources() or any(
            diagnostic.code == "changed_during_read" for diagnostic in history.diagnostics
        ):
            raise ValueError("Canonical history changed during capture; resume again")
        metadata = history.metadata
        if metadata.get("session_id", self.identity) != self.identity:
            raise ValueError("Invalid shared session metadata identity")
        if (
            metadata.get("working_dir")
            and Path(metadata["working_dir"]).resolve()
            != Path(self.canonical_launch["cwd"]).resolve()
        ):
            raise ValueError("Session belongs to another working directory")
        native_resume_messages(history.messages)  # No import limits, mutation or replay.
        self.canonical_metadata = metadata
        self.history_diagnostics = history.diagnostics
        return history.messages, self._revision_key(before)

    def _save_native(self, messages, metadata):
        from amplifier_core.utils.truncate import redact_secrets
        from amplifier_foundation import sanitize_message

        def native_message(message):
            # JSON provider continuation fields already are portable. The CLI's
            # older sanitizer drops content_blocks/thinking_block even when they
            # are plain JSON, so apply it only to non-serializable runtime values.
            try:
                json.dumps(message, allow_nan=False)
            except TypeError:
                return sanitize_message(message)
            return message

        self._owner.check()
        self._native_sources()
        self.history_store.save(messages, redact_secrets(metadata), sanitizer=native_message)

    def assert_current(self):
        self._owner.check()
        if self._revision_key(self._native_sources()) != self.canonical_digest:
            raise ValueError(
                "CLI transcript changed while this client was open; close and resume again. Nothing overwritten."
            )

    def load_checkpoint(self):
        # Only an explicit unfinished admission receipt gates execution. Missing
        # private UI files never gate an otherwise valid native conversation.
        path = self.path / "checkpoint.json"
        saved = json.loads(path.read_text()) if path.exists() else {}
        if saved and saved.get("status") != "ready":
            raise ValueError(
                "Shared session has uncertain/incomplete work; inspect before resuming"
            )
        return {
            "version": 1,
            "status": "ready",
            "sequence": len(self.restored_events),
            "messages": self.canonical_messages,
            "fingerprint": None,
        }

    @staticmethod
    def observations(messages, identity, *, limit_details=True):
        from .cli_compat import session_message_visible
        from .events import tool_status
        from .inspection import bounded_projection

        events = []
        turn = 0
        pending = {}

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
                for call_index, call in enumerate(message.get("tool_calls") or []):
                    function = call.get("function", call)
                    arguments = function.get("arguments", {})
                    if isinstance(arguments, str):
                        try:
                            arguments = json.loads(arguments)
                        except ValueError:
                            arguments = {"raw": arguments}
                    item_id = f"history:tool:{index}:{call_index}"
                    pending[call["id"]] = item_id
                    arguments, limited = (
                        bounded_projection(arguments) if limit_details else (arguments, False)
                    )
                    emit(
                        "tool.updated",
                        item_id,
                        tool_call_id=call["id"],
                        canonical_message_index=index,
                        name=function.get("name") or function.get("tool", "tool"),
                        arguments=arguments,
                        preview_limited=limited,
                        status="unknown",
                    )
            elif role == "tool":
                result, limited = bounded_projection(content) if limit_details else (content, False)
                emit(
                    "tool.ended",
                    pending.pop(message["tool_call_id"], f"history:result:{index}"),
                    tool_call_id=message["tool_call_id"],
                    canonical_result_index=index,
                    result=result,
                    preview_limited=limited,
                    status=tool_status("tool:post", content),
                )
        return events

    def _restore_accounting(self):
        """Derive an in-memory session baseline from shared recorded receipts.

        Canonical logs and conversation bytes are read-only here. Evidence rows
        live in Activity, not as hundreds of replayed conversation notices.
        """
        from datetime import datetime

        from .cli_compat import historical_usage
        from .inspection import add_usage, call_usage_text, usage_totals, usage_values

        if not self.canonical_messages and not self.restored_events:
            return
        launch = self.canonical_launch
        logged, partial = historical_usage(launch["cli_home"], launch["cwd"], self.identity)
        if not logged:
            partial = True
        records = {row["usage_receipt_id"]: row for row in logged}
        snapshot = usage_totals()
        for row in records.values():
            add_usage(snapshot, usage_values(row["usage_call"]))
        snapshot["totals"] = {
            k: str(v) if k == "cost_usd" else v for k, v in snapshot["totals"].items()
        }
        self.metadata["shared_history_unaccounted"] = partial

        def retain(item, **payload):
            event = Event(
                self.identity,
                len(self.restored_events) + 1,
                None,
                "activity.observed",
                item,
                payload,
            )
            self.restored_events.append(event)

        retain(
            "shared:usage",
            name="Earlier session usage",
            status="partial" if partial else "observed",
            accounting_snapshot=snapshot,
            partial=partial,
            text=f"{snapshot['requests']} recorded calls. Historical session accounting, not next-turn usage. "
            + (
                "Some earlier receipts are unavailable or cannot be correlated."
                if partial
                else "Shared recorded receipts reconciled by observed identity."
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

    def _save_marker(self, messages, sequence, fingerprint, ready):
        self._owner.check()
        marker = dict(
            version=1,
            status="ready" if ready else "uncertain",
            sequence=sequence,
            fingerprint=fingerprint,
        )
        atomic_json(self.path / "checkpoint.json", marker)
        self.saved = {**marker, "messages": messages}

    def checkpoint(self, messages, sequence, fingerprint, ready):
        self.assert_current()
        # Mark pending before Foundation's two-file save. A crash is uncertainty,
        # never permission to reuse an older UI snapshot as canonical context.
        self._save_marker(messages, sequence, fingerprint, False)
        self._save_native(messages, self._metadata(self.identity, messages))
        self.canonical_messages, self.canonical_digest = self._read_canonical()
        self._save_marker(self.canonical_messages, sequence, fingerprint, ready)
        os.utime(self.path / "metadata.json", None)

    def set_title(self, title, *, generated=False, description=None):
        from amplifier_core.utils.truncate import redact_secrets

        self.assert_current()
        if not super().set_title(title, generated=generated, description=description):
            return False
        self.history_store.save_metadata(
            redact_secrets(
                {
                    **self.canonical_metadata,
                    "name": self.metadata["title"],
                    **(
                        {"description": self.metadata["description"]}
                        if "description" in self.metadata
                        else {}
                    ),
                }
            )
        )
        self.canonical_metadata = {**self.canonical_metadata, "name": self.metadata["title"]}
        self.canonical_digest = self._revision_key(self._native_sources())
        return True

    def record(self, event):
        self._owner.check()
        self._live_events.append(event)
        if event.kind == "turn.accepted":
            # Admission uncertainty is durable before execution, but displayed
            # events themselves remain observations, never a second transcript.
            self._save_marker(self.canonical_messages, event.sequence, None, False)
            if not self.metadata.get("title"):
                self.metadata["title"] = " ".join(event.payload["text"].split())[:100]
                self.metadata["title_source"] = "prompt"
                atomic_json(self.path / "metadata.json", self.metadata)

    def activity_events(self):
        from itertools import chain

        return chain(self.restored_events, self._live_events)

    def check_open(self):
        self._owner.check()

    def checkpoint_auxiliary(self, sequence):
        self._owner.check()
        if self.saved:
            self.saved["sequence"] = sequence

    def save_draft(self, text):
        self._owner.check()
        super().save_draft(text)

    def naming_metadata(self, completed_turns):
        self._owner.check()
        return super().naming_metadata(completed_turns)

    def close(self):
        try:
            super().close()
        finally:
            # The host calls close only after child/runtime cleanup has settled.
            # Never write HeldSession's separate checkpoint: native files own history.
            self._owner.release()

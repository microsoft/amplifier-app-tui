"""Bounded local export and explicit, non-destructive historical-context forks."""

import copy
import fcntl
import hashlib
import json
import os
import re
import stat
import uuid
from pathlib import Path

from .conversations import ConversationStore, atomic_json, resolve_resume
from .events import Event, Transcript


def native_resume_messages(messages):
    """Validate captured tool pairing without imposing import/display budgets.

    IDs may repeat in later completed batches; module instructions may interleave.
    This neither repairs missing outcomes nor drops unknown provider JSON fields.
    A drained call/result pair needs no invented closing assistant response.
    """
    from amplifier_foundation.session import is_real_user_message

    if not isinstance(messages, list):
        raise ValueError("Canonical messages must be a list")
    pending = set()
    for message in messages:
        if (
            not isinstance(message, dict)
            or not isinstance(message.get("role"), str)
            or not message["role"]
        ):
            raise ValueError("Canonical messages require an object with a role")
        role = message.get("role")
        metadata = message.get("metadata")
        ephemeral = isinstance(metadata, dict) and metadata.get("ephemeral")
        if role in ("system", "developer") or (
            role == "user"
            and not message.get("tool_calls")
            and (ephemeral or not is_real_user_message(message))
        ):
            continue
        if role == "tool":
            identity = message.get("tool_call_id")
            if not isinstance(identity, str) or identity not in pending:
                raise ValueError(
                    "Unpaired tool result in canonical history; inspect before continuing"
                )
            pending.remove(identity)
            continue
        if pending:
            raise ValueError("Unfinished tool calls require explicit interrupted-work recovery")
        calls = message.get("tool_calls") or []
        if not isinstance(calls, list) or (calls and role != "assistant"):
            raise ValueError("Unsupported canonical tool-call representation")
        for call in calls:
            identity = call.get("id") if isinstance(call, dict) else None
            if not isinstance(identity, str) or not identity or identity in pending:
                raise ValueError("Missing or duplicate pending tool-call identity")
            pending.add(identity)
    if pending:
        raise ValueError("Unfinished tool calls require explicit interrupted-work recovery")
    return messages


def public_history(messages, *, repair=False):
    """Validate an explicit bounded public-context import/recovery operation.

    This is not a canonical-session admission validator: its import bounds and
    deliberately narrow public tool/role representation must not reject native
    CLI/Unified history. Native reads use Foundation SessionHistoryStore and
    execution safety uses the owning runtime's shared transcript diagnosis.
    Missing imported outcomes are explicit, never executed here.
    """
    if not isinstance(messages, list) or len(messages) > 10000:
        raise ValueError("Public context must contain at most 10000 messages")
    encoded = json.dumps(messages, allow_nan=False).encode()
    if len(encoded) > 8 * 1024 * 1024:
        raise ValueError("Public context exceeds 8 MiB")
    result, pending, seen, missing = [], {}, set(), []

    def finish_pending():
        if pending and not repair:
            raise ValueError("Unfinished tool calls require explicit interrupted-work recovery")
        for identity in pending:
            result.append(
                {
                    "role": "tool",
                    "tool_call_id": identity,
                    "content": "RECOVERY OBSERVATION: No terminal result was captured for this tool call. Its effects are UNKNOWN. This is not a tool execution or failure result. Do not repeat it without a new explicit user instruction.",
                }
            )
            missing.append(identity)
        pending.clear()

    for message in copy.deepcopy(messages):
        if not isinstance(message, dict) or message.get("role") not in (
            "system",
            "user",
            "assistant",
            "tool",
        ):
            raise ValueError("Unsupported public message role; no conversion performed")
        if message["role"] == "tool":
            identity = message.get("tool_call_id")
            if not isinstance(identity, str) or identity not in pending:
                raise ValueError("Unpaired or duplicate tool result; recovery refused")
            pending.pop(identity)
        else:
            finish_pending()
            calls = message.get("tool_calls") or []
            if not isinstance(calls, list) or (calls and message["role"] != "assistant"):
                raise ValueError("Unsupported public tool-call representation")
            for call in calls:
                identity = call.get("id") if isinstance(call, dict) else None
                if not isinstance(identity, str) or not identity or identity in seen:
                    raise ValueError("Missing or duplicate tool-call identity")
                seen.add(identity)
                pending[identity] = call
        result.append(message)
    finish_pending()
    return result, missing


def context_transfer(messages, source, *, turn=None):
    messages, _ = public_history(messages)
    if turn is not None and (type(turn) is not int or turn < 1):
        raise ValueError("Fork turn must be a positive integer")
    value = {
        "version": 1,
        "source_session": source,
        "messages": messages,
        "sha256": hashlib.sha256(json.dumps(messages, sort_keys=True).encode()).hexdigest(),
        "notice": "Explicit public-context fork into a NEW composition. Original conversation retained. No tools replayed. Provider pins, modes, queues and module-private state are not transferred; the selected overlay is executable configuration. Captured messages can reach the new provider only after your next explicit Send.",
    }
    if turn is not None:
        value["fork_turn"] = turn
        value["notice"] = (
            f"Public-context branch through turn {turn} of source {source}. New conversation under current launch configuration; original history retained. No tools replayed or effects undone. Pins, modes, goals, local controls, queues and private module state are not transferred. Captured context reaches providers only after explicit Send."
        )
    return value


def child_references(source, root_id):
    """Bounded public-context excerpts, never executable child reconstruction."""
    from .inspection import bounded

    rows, partial, budget = [], False, 8 * 1024 * 1024
    try:
        directory = os.open(source / "children", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return rows, partial
    try:
        with os.scandir(directory) as entries:
            names = []
            for entry in entries:
                if len(names) == 32:
                    partial = True
                    break
                if re.fullmatch(r"[A-Za-z0-9_-]{1,160}\.json", entry.name):
                    names.append(entry.name)
                else:
                    partial = True
        identities = {name[:-5] for name in names}
        for name in sorted(names):
            value = {"id": name[:-5], "source": root_id, "label": "Historical child", "live": False}
            try:
                fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
                with os.fdopen(fd, "rb") as stream:
                    if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                        raise ValueError("Not a regular child receipt")
                    raw = stream.read(min(budget, 1024 * 1024) + 1)
                budget -= len(raw)
                if budget < 0 or len(raw) > 1024 * 1024:
                    raise ValueError("Child receipt exceeds recovery read budget")
                row = json.loads(raw)
                if not isinstance(row, dict) or row.get("parent") not in identities | {root_id}:
                    raise ValueError("Child parent identity is outside the captured source")
                messages = row.get("messages")
                if not isinstance(messages, list) or any(not isinstance(m, dict) for m in messages):
                    raise ValueError("Public child messages unavailable")
                public = []
                for message in messages[-100:]:
                    content = message.get("content")
                    if isinstance(content, list):
                        content = [
                            block
                            if isinstance(block, dict) and block.get("type") == "text"
                            else {"notice": "Non-text block omitted from historical recovery"}
                            for block in content
                        ]
                    public.append(
                        {
                            "role": message.get("role"),
                            "content": content,
                            "tool_call_id": message.get("tool_call_id"),
                        }
                    )
                detail, clipped = bounded(
                    {
                        "agent": row.get("agent"),
                        "parent": row["parent"],
                        "instruction": row.get("instruction"),
                        "recorded_status": row.get("status"),
                        "messages": public,
                    }
                )
                value.update(
                    label=f"Historical child · {row.get('agent', 'unknown')}",
                    status="historical only; unfinished effects unknown",
                    source_sha256=hashlib.sha256(raw).hexdigest(),
                    detail=detail,
                    partial=clipped or len(messages) > 100,
                    recover_child=row.get("status") in ("interrupted", "failed", "running"),
                    reparented=row.get("parent") != root_id,
                )
            except (OSError, ValueError, TypeError) as exc:
                value.update(
                    status="historical child unavailable",
                    detail=f"{type(exc).__name__}: child receipt unavailable or outside recovery bounds; original retained",
                    partial=True,
                )
            rows.append(value)
            partial |= value["partial"]
            if budget <= 0:
                partial = True
                break
    finally:
        os.close(directory)
    return rows, partial


def recovery_catalog(store):
    """Inspect saved recovery evidence without importing it into model context."""
    from .inspection import bounded

    rows, partial = [], False
    if store and (store.path / "recovery.json").exists():
        with (store.path / "recovery.json").open("rb") as stream:
            raw = stream.read(16 * 1024 * 1024 + 1)
        if len(raw) > 16 * 1024 * 1024:
            raise ValueError("Recovery evidence exceeds inspection budget")
        value = json.loads(raw)
        rows.extend(value.get("children", []))
        partial = value.get("children_partial", False)
        for item in value.get("items", [])[: 100 - len(rows)]:
            detail, clipped = bounded(item)
            rows.append(
                {
                    "id": item["id"],
                    "label": f"Historical action · {item['id']}",
                    "source": value.get("source_session"),
                    "status": item.get("status", "unknown"),
                    "detail": detail,
                    "partial": clipped,
                    "live": False,
                }
            )
            partial |= clipped
        partial |= len(value.get("items", [])) + len(value.get("children", [])) > 100
    if store:
        current, limited = child_references(store.path, store.identity)
        rows = [r for r in current if r.get("recover_child")] + rows
        partial |= limited
    kept, remaining = [], 1024 * 1024
    for row in rows[:100]:
        remaining -= len(json.dumps(row, ensure_ascii=False).encode())
        if remaining < 0:
            partial = True
            break
        kept.append(row)
    rows = kept
    return {
        "rows": rows,
        "partial": partial,
        "scope": "Inspection never resumes work. Eligible interrupted direct children offer separately confirmed public-context adoption under a new identity and instruction; unsupported private state refuses. Child receipts: at most 32 / 8 MiB read per source, 1 MiB each; last 100 public messages and 16 KiB detail per child. Non-text blocks omitted in preview. Original files retained. Copying is not instruction delivery.",
    }


def import_reference(path):
    """Explicit text-only migration; never import another app's executable state."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > 1024 * 1024:
            raise ValueError("Transcript import requires a regular UTF-8 file of at most 1 MiB")
        raw = stream.read(1024 * 1024 + 1)
        after = os.fstat(stream.fileno())
        if len(raw) > 1024 * 1024 or (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ):
            raise ValueError("Transcript changed during capture; nothing imported")
    text = raw.decode("utf-8")
    if not text.strip() or any(ord(c) < 32 and c not in "\n\r\t" for c in text) or "\x7f" in text:
        raise ValueError("Transcript must contain readable text, not binary or terminal controls")
    return {
        "version": 1,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "text": text,
        "notice": "Imported historical text into a NEW conversation and composition. Original file unchanged. This is reference material, not canonical resume: no credentials, modes, provider pins, queued work, tool calls or private module state were imported. No prior instruction is being resumed. The selected provider can receive this text after your next explicit Send.",
    }


def reference_messages(value):
    text = value.get("text")
    if (
        value.get("version") != 1
        or not isinstance(text, str)
        or len(text.encode()) > 1024 * 1024
        or hashlib.sha256(text.encode()).hexdigest() != value.get("sha256")
    ):
        raise ValueError("Imported reference failed integrity verification")
    return [
        {"role": "user", "content": value["notice"] + "\n\nHistorical reference:\n" + text},
        {
            "role": "assistant",
            "content": "Historical reference retained. Waiting for a new explicit request; no previous work has been resumed.",
        },
    ]


def history(state_dir, identity, *, structured=False, cwd=None, cli_home=None):
    from dataclasses import asdict

    from .conversations import SharedConversationStore, entry_path

    entry = resolve_resume(state_dir, identity, cwd=cwd, cli_home=cli_home)
    identity = entry["id"]
    directory = entry_path(state_dir, entry)
    rows = None
    if entry.get("shared_session"):
        from .cli_compat import native_history

        native = native_history(cli_home, cwd, identity)
        if any(d.code == "changed_during_read" for d in native.diagnostics):
            raise ValueError("Native history changed during export; retry after work finishes")
        rows = [
            asdict(e)
            for e in SharedConversationStore.observations(
                native.messages, identity, limit_details=False
            )
        ]
    if rows is None:
        with (directory / "events.jsonl").open("rb") as stream:
            data = stream.read(16 * 1024 * 1024 + 1)
        if len(data) > 16 * 1024 * 1024:
            raise ValueError("History exceeds the 16 MiB recovery/export bound")
        rows = [json.loads(line) for line in data.splitlines()]
    if any(
        not isinstance(r, dict) or r.get("session_id") != identity or r.get("sequence") != i
        for i, r in enumerate(rows, 1)
    ):
        raise ValueError("History has invalid identity/order; recovery refused")
    parts = [f"# {entry.get('title', 'Conversation')}\n\nSource conversation: {identity}\n"]
    transcript = Transcript()
    finals = set()
    for row in rows:
        transcript.apply(Event(**row))
        if row["kind"] == "text.final":
            finals.add(row["item_id"])
    if structured:
        return entry, json.dumps(
            {
                "version": 1,
                "format": "amplifier-tui-observations",
                "source_session": identity,
                "title": entry.get("title", "Conversation"),
                "through_sequence": len(rows),
                "scope": "Private displayed observations, not canonical context or executable session state. No tools replayed. Review before sharing.",
                "items": [
                    {
                        **asdict(item),
                        "stream_complete": item.id in finals if item.kind == "assistant" else None,
                    }
                    for item in transcript.items.values()
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    for item in transcript.items.values():
        label = {"user": "You", "assistant": "Assistant"}.get(item.kind, item.kind)
        if item.kind == "assistant" and item.id not in finals:
            label += " (partial; interrupted stream)"
        parts.append(f"\n## {label}{' · ' + item.status if item.status else ''}\n\n{item.text}\n")
        if item.kind == "tool":
            parts.append(
                f"\nObserved result, not a claim of successful work:\n\n```json\n{json.dumps(item.detail, ensure_ascii=False, indent=2)}\n```\n"
            )
    return entry, "".join(parts)


def export(state_dir, identity, format="markdown", *, cwd=None, cli_home=None):
    if format not in ("markdown", "json"):
        raise ValueError("Choose markdown or json export")
    _, text = history(state_dir, identity, structured=format == "json", cwd=cwd, cli_home=cli_home)
    if len(text.encode()) > 32 * 1024 * 1024:
        raise ValueError("Rendered export exceeds the 32 MiB bound")
    directory = Path(state_dir) / "exports"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    suffix = "json" if format == "json" else "md"
    path = directory / f"conversation-{uuid.uuid4().hex}.{suffix}"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(text)
    return path


def recover(state_dir, identity):
    entry = resolve_resume(state_dir, identity)
    source = Path(state_dir) / "conversations" / entry["id"]
    fd = os.open(source / "lock", os.O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _, text = history(state_dir, entry["id"])
        # A typed evidence ledger accompanies the human-readable reference. It is
        # never passed as executable tool-call messages or module-private state.
        raw = (source / "events.jsonl").read_bytes()
        observations = {}
        for line in raw.splitlines():
            event = json.loads(line)
            if event["kind"] not in (
                "tool.updated",
                "tool.ended",
                "child.observed",
                "question.updated",
            ):
                continue
            item = observations.setdefault(
                event["item_id"],
                {
                    "id": event["item_id"],
                    "source_session": entry["id"],
                    "turn": event["turn_id"],
                    "first_sequence": event["sequence"],
                    "observations": [],
                },
            )
            # Preserve source identities and outcomes, not a guessed successful run.
            item["observations"].append(
                {"sequence": event["sequence"], "kind": event["kind"], "payload": event["payload"]}
            )
            item["status"] = event["payload"].get("status", item.get("status", "unknown"))
        for item in observations.values():
            if item["status"] in ("running", "pending", "waiting", "started", "observed"):
                item["status"] = "unknown; interrupted without a terminal observation"
        evidence = {
            "version": 1,
            "source_session": entry["id"],
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "policy": "Historical observations only. No pending execution, child continuation, private module state, or recipe effects are restored. Absent outcomes remain unknown.",
            "items": list(observations.values()),
        }
        evidence["children"], evidence["children_partial"] = child_references(source, entry["id"])
        checkpoint = json.loads((source / "checkpoint.json").read_text())
        if not isinstance(checkpoint.get("fingerprint"), str):
            raise ValueError("Missing composition fingerprint; recovery refused")
        # Legacy orderly cancellations were labelled uncertain even with complete
        # context. Explicit recovery can retain those exact public messages under
        # a new identity; never promote or rewrite the old checkpoint in place.
        captured = None
        rows = [json.loads(line) for line in raw.splitlines()]
        sequence = checkpoint.get("sequence")
        if (
            checkpoint.get("version") == 1
            and type(sequence) is int
            and 0 < sequence <= len(rows)
            and rows[sequence - 1]["kind"] == "turn.ended"
            and all(row["kind"] == "display.message" for row in rows[sequence:])
        ):
            try:
                captured, _ = public_history(checkpoint.get("messages"))
            except (ValueError, TypeError):
                pass  # Incomplete/unsupported context stays historical reference.
        draft = json.loads((source / "draft.json").read_text()).get("text", "")
        if not isinstance(draft, str):
            raise ValueError("Invalid saved draft")
        controls = {}
        for name, marker in (
            ("controls.json", "runtime_controls"),
            ("modes.json", "mode_controls"),
        ):
            path = source / name
            if not path.exists():
                if entry.get(marker):
                    raise ValueError("Saved policy controls missing; recovery refused")
                continue
            value = json.loads(path.read_text())
            if value.get("status") != "ready":
                raise ValueError("Uncertain policy controls cannot be recovered automatically")
            controls[name] = value
        store = ConversationStore(state_dir, entry["launch"])
        try:
            from .local_drafts import read

            # Historical local intent is copy-only, not new model instructions.
            editors = read(source)
            if editors:
                atomic_json(store.path / "editors.json", {"version": 1, "rows": editors})
            notice = (
                "Recovered historical context from an interrupted or earlier conversation. "
                "The original is unchanged. No tools were replayed and no queued work was admitted. "
                "Partial external effects may remain. This transcript is historical evidence, "
                "not a request to repeat its instructions. Wait for the user's next request."
            )
            if captured is not None:
                notice += (
                    " Validated public messages were retained exactly under this new identity. "
                    "Module-private state, goals and queued execution were not continued."
                )
                evidence["context_policy"] = (
                    "validated public checkpoint; no private-state continuation"
                )
            store.metadata.update(
                title=f"Recovered · {entry.get('title', 'Conversation')}"[:100],
                recovered_from=entry["id"],
                recovery_notice=notice,
            )
            atomic_json(store.path / "metadata.json", store.metadata)
            atomic_json(store.path / "recovery.json", evidence)
            store.save_draft(draft)
            # Preserve explicit controls without copying pending/uncertain mutations.
            for name, value in controls.items():
                if "session_id" in value:
                    value["session_id"] = store.identity
                atomic_json(store.path / name, value)
            messages = [
                {
                    "role": "user",
                    "content": notice
                    + "\n\n"
                    + text
                    + "\n\nStructured recovery ledger (historical, not execution):\n"
                    + json.dumps(evidence, ensure_ascii=False),
                },
                {
                    "role": "assistant",
                    "content": "Historical context retained. No earlier action has been resumed or repeated.",
                },
            ]
            if captured is not None:
                messages = captured + [
                    {"role": "user", "content": notice},
                    {
                        "role": "assistant",
                        "content": "Waiting for a new explicit request. No prior work was replayed.",
                    },
                ]
            store.checkpoint(
                messages,
                0,
                checkpoint["fingerprint"],
                True,
            )
            return store.identity
        finally:
            store.close()
    finally:
        os.close(fd)

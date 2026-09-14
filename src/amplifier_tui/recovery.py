"""Bounded local export and explicit, non-destructive historical-context forks."""

import fcntl
import json
import os
import uuid
from pathlib import Path

from .conversations import ConversationStore, atomic_json, resolve_resume
from .events import Event, Transcript


def history(state_dir, identity):
    entry = resolve_resume(state_dir, identity)
    identity = entry["id"]
    directory = Path(state_dir) / "conversations" / identity
    with (directory / "events.jsonl").open("rb") as stream:
        data = stream.read(16 * 1024 * 1024 + 1)
    if len(data) > 16 * 1024 * 1024:
        raise ValueError("History exceeds the 16 MiB recovery/export bound")
    rows = [json.loads(line) for line in data.splitlines()]
    if any(
        r.get("session_id") != identity or r.get("sequence") != i for i, r in enumerate(rows, 1)
    ):
        raise ValueError("History has invalid identity/order; recovery refused")
    parts = [f"# {entry.get('title', 'Conversation')}\n\nSource conversation: {identity}\n"]
    transcript = Transcript()
    finals = set()
    for row in rows:
        transcript.apply(Event(**row))
        if row["kind"] == "text.final":
            finals.add(row["item_id"])
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


def export(state_dir, identity):
    _, text = history(state_dir, identity)
    directory = Path(state_dir) / "exports"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = directory / f"conversation-{uuid.uuid4().hex}.md"
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
        checkpoint = json.loads((source / "checkpoint.json").read_text())
        if not isinstance(checkpoint.get("fingerprint"), str):
            raise ValueError("Missing composition fingerprint; recovery refused")
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
            store.metadata.update(
                title=f"Recovered · {entry.get('title', 'Conversation')}"[:100],
                recovered_from=entry["id"],
                recovery_notice=notice,
            )
            atomic_json(store.path / "metadata.json", store.metadata)
            store.save_draft(draft)
            # Preserve explicit controls without copying pending/uncertain mutations.
            for name, value in controls.items():
                if "session_id" in value:
                    value["session_id"] = store.identity
                atomic_json(store.path / name, value)
            store.checkpoint(
                [
                    {"role": "user", "content": notice + "\n\n" + text},
                    {
                        "role": "assistant",
                        "content": "Historical context retained. No earlier action has been resumed or repeated.",
                    },
                ],
                0,
                checkpoint["fingerprint"],
                True,
            )
            return store.identity
        finally:
            store.close()
    finally:
        os.close(fd)

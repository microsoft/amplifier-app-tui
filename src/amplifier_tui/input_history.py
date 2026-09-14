"""Read-only, directory-scoped recall; never restore another conversation's context."""

import json
from pathlib import Path

from .conversations import catalog


def recall(state_dir, cwd, current):
    root, cwd = Path(state_dir), Path(cwd).resolve()
    rows, budget, partial = [], 16 * 1024 * 1024, False
    entries = catalog(root)
    for entry in entries:
        try:
            matches = Path(entry["launch"]["cwd"]).resolve() == cwd
        except (KeyError, TypeError, ValueError, OSError):
            partial = True
            continue
        if entry["id"] == current or not matches:
            continue
        if budget <= 0 or len(rows) >= 1000:
            partial = True
            break
        try:
            path = root / "conversations" / entry["id"] / "events.jsonl"
            with path.open("rb") as stream:
                size = path.stat().st_size
                take = min(size, budget, 1024 * 1024)
                stream.seek(size - take)
                data = stream.read(take)
            budget -= take
            lines = data.splitlines()
            if size > take:
                lines = lines[1:]
                partial = True
            messages = []
            for line in lines:
                try:
                    event = json.loads(line)
                    if not isinstance(event, dict):
                        partial = True
                        continue
                    if (
                        event.get("session_id") == entry["id"]
                        and event.get("kind") == "turn.accepted"
                    ):
                        text = event["payload"]["text"]
                        if isinstance(text, str) and len(text) <= 65536:
                            messages.append(text)
                except (ValueError, KeyError, TypeError):
                    partial = True
            rows.extend(reversed(messages))
        except OSError:
            partial = True
    # Newest conversations first; within each, original submission order.
    selected, size = [], 0
    for text in rows[:1000]:
        size += len(text.encode())
        if size > 2 * 1024 * 1024:
            partial = True
            break
        selected.append(text)
    return {"entries": list(reversed(selected)), "partial": partial or len(rows) > 1000}

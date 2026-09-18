"""Read-only, directory-scoped recall; never restore another conversation's context."""

import json
from pathlib import Path

from .conversations import catalog, entry_path


def recall(state_dir, cwd, current, *, include_current=False, cli_home=None):
    root, cwd = Path(state_dir), Path(cwd).resolve()
    rows, budget, partial = [], 16 * 1024 * 1024, False
    entries = catalog(root, cwd=cwd, cli_home=cli_home)
    for entry in entries:
        try:
            matches = Path(entry["launch"]["cwd"]).resolve() == cwd
        except (KeyError, TypeError, ValueError, OSError):
            partial = True
            continue
        if (entry["id"] == current and not include_current) or not matches:
            continue
        if budget <= 0:
            partial = True
            break
        try:
            path = entry_path(root, entry) / "events.jsonl"
            if entry.get("shared_session"):
                path = path.parent.parent / "transcript.jsonl"
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
                    if entry.get("shared_session"):
                        from .cli_compat import session_message_visible

                        if not session_message_visible(event):
                            continue
                        if event.get("role") == "user" and isinstance(event.get("content"), str):
                            text = event["content"]
                            if len(text) <= 65536:
                                messages.append((0, text))
                        continue
                    if (
                        event.get("session_id") == entry["id"]
                        and event.get("kind") == "turn.accepted"
                    ):
                        text = event["payload"]["text"]
                        if isinstance(text, str) and len(text) <= 65536:
                            stamp = event.get("timestamp_ns", 0)
                            stamp = stamp if type(stamp) is int and stamp > 0 else 0
                            messages.append((stamp, text))
                except (ValueError, KeyError, TypeError):
                    partial = True
            rows.extend(reversed(messages))
        except OSError:
            partial = True
    # Known timestamps order interleaved conversations globally. Legacy rows keep
    # the former activity-based ordering and never acquire an invented timestamp.
    rows.sort(key=lambda row: row[0], reverse=True)
    selected, size = [], 0
    for _, text in rows[:1000]:
        size += len(text.encode())
        if size > 2 * 1024 * 1024:
            partial = True
            break
        selected.append(text)
    result = {"entries": list(reversed(selected)), "partial": partial or len(rows) > 1000}
    if include_current:
        result.update(replace=True, legacy=any(stamp == 0 for stamp, _ in rows[:1000]))
    return result

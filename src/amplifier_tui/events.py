"""Client-neutral source items. No provider, kernel or terminal dependencies."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_UNPARSED = object()


def tool_result(value):
    """Recognize bounded serialized envelopes, never execute returned text.

    The streaming loop serializes non-model results with str(); truncation hooks
    may serialize model results as JSON. Originals remain in event evidence.
    Malformed, oversized, deeply nested or non-envelope text stays unknown.
    """
    import ast
    import json

    if hasattr(value, "model_dump"):
        value = value.model_dump()
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or len(value) > 262144:
        return None
    try:
        parsed = json.loads(value)
    except (ValueError, RecursionError):
        try:
            tree = ast.parse(value, mode="eval")
            pending = [(tree, 0)]
            count = 0
            while pending:
                node, depth = pending.pop()
                count += 1
                if count > 8192 or depth > 20:
                    return None
                pending.extend((child, depth + 1) for child in ast.iter_child_nodes(node))
            parsed = ast.literal_eval(tree)
        except (ValueError, SyntaxError, RecursionError, MemoryError):
            return None
    pending, count = [(parsed, 0)], 0
    while pending:
        node, depth = pending.pop()
        count += 1
        if count > 8192 or depth > 20:
            return None
        if isinstance(node, dict):
            pending.extend((child, depth + 1) for child in node.values())
        elif isinstance(node, (list, tuple, set)):
            pending.extend((child, depth + 1) for child in node)
    if isinstance(parsed, dict) and type(parsed.get("success")) is bool:
        return parsed
    return None


def tool_status(event, result, *, parsed_result=_UNPARSED):
    if event == "tool:pre":
        return "running"
    if event == "tool:error":
        return "failed"
    value = tool_result(result) if parsed_result is _UNPARSED else parsed_result
    if value is not None:
        if value.get("success") is False or value.get("error"):
            return "failed"
        if value.get("success") is True:
            return "succeeded"
    return "unknown"


def message_text(data):
    source = data.get("source")
    level = data.get("level", "info")
    label = " / ".join(str(v) for v in (source, level if level != "info" else None) if v)
    return f"[{label}] {data['text']}" if label else data["text"]


def tool_text(data, *, parsed_result=_UNPARSED):
    """Bounded useful generic preview; the separate detail retains exact evidence."""
    import json
    from itertools import islice

    preview = data.get("preview")
    if isinstance(preview, str):
        return preview

    def excerpt(value, depth=0):
        if isinstance(value, str):
            return value[:1200] + ("…" if len(value) > 1200 else "")
        if depth >= 3:
            return "[inspect nested content]"
        if isinstance(value, dict):
            return {str(k)[:80]: excerpt(v, depth + 1) for k, v in islice(value.items(), 5)}
        if isinstance(value, list):
            return [excerpt(v, depth + 1) for v in value[:5]]
        return (
            value
            if value is None or isinstance(value, (bool, int, float))
            else str(type(value).__name__)
        )

    lines = [str(data.get("name", "Unknown tool"))]
    args = data.get("arguments")
    if isinstance(args, dict):
        for key in (
            "command",
            "file_path",
            "path",
            "pattern",
            "query",
            "skill_name",
            "agent",
            "instruction",
            "operation",
        ):
            if key in args:
                lines.extend(f"  {key}: {str(args[key])[:300]}".splitlines()[:2])
                break
    original = data.get("result")
    result = tool_result(original) if parsed_result is _UNPARSED else parsed_result
    if isinstance(result, dict):
        output = result.get("error") or result.get("output")
        if output is None:
            output = result.get("content", result.get("text"))
        if output is None and "output" not in result:
            output = {k: v for k, v in result.items() if k not in ("success", "error")}
        if isinstance(output, dict):
            # Common public result envelopes get readable content, not nested JSON.
            # Do not infer success here; the complete envelope remains in detail.
            for key in ("content", "stdout", "text", "message"):
                if isinstance(output.get(key), str) and output[key]:
                    output = output[key]
                    break
        if output is not None:
            clipped = excerpt(output)
            text = clipped if isinstance(clipped, str) else json.dumps(clipped, ensure_ascii=False)
            rows = text[:1400].splitlines()
            lines.extend("  " + row[:300] for row in rows[:5])
            if len(rows) > 5 or len(text) > 1400:
                lines.append("  … inspect tool for full result")
    elif isinstance(original, str) and original:
        lines.append("  " + original[:300] + ("…" if len(original) > 300 else ""))
    if data.get("error"):
        lines.append("  " + str(data["error"])[:300])
    return "\n".join(lines)


@dataclass(frozen=True)
class Event:
    session_id: str
    sequence: int
    turn_id: str | None
    kind: str
    item_id: str
    payload: dict[str, Any]
    timestamp_ns: int = 0  # Zero means legacy/unknown, not the time history was reopened.


@dataclass
class Item:
    id: str
    kind: str
    text: str = ""
    status: str = ""
    detail: dict = field(default_factory=dict)


class Transcript:
    """Idempotent projection; applying an event cannot execute anything."""

    def __init__(self):
        self.items: dict[str, Item] = {}
        self.seen: set[tuple[str, int]] = set()

    def apply(self, event: Event):
        key = (event.session_id, event.sequence)
        if key in self.seen:
            return
        self.seen.add(key)
        data = event.payload
        if event.kind == "turn.accepted":
            self.items[event.item_id] = Item(event.item_id, "user", data["text"])
        elif event.kind == "display.message":
            self.items[event.item_id] = Item(
                event.item_id, "notice", message_text(data), data.get("level", ""), data.copy()
            )
        elif event.kind == "question.updated":
            self.items[event.item_id] = Item(
                event.item_id, "question", data["text"], data["status"], data.copy()
            )
        elif event.kind == "steering.updated":
            self.items[event.item_id] = Item(
                event.item_id, "correction", data["text"], data["status"], data.copy()
            )
        elif event.kind in {"text.delta", "text.final"}:
            item = self.items.setdefault(event.item_id, Item(event.item_id, "assistant"))
            item.text = item.text + data["text"] if event.kind == "text.delta" else data["text"]
        elif event.kind.startswith("tool."):
            item = self.items.setdefault(event.item_id, Item(event.item_id, "tool"))
            item.status = data.get("status", item.status or "running")
            item.detail.update({k: v for k, v in data.items() if v is not None})
            item.text = tool_text(item.detail)
        elif event.kind == "turn.ended":
            self.items[event.item_id] = Item(
                event.item_id, "outcome", data.get("message", ""), data["status"]
            )

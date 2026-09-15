"""Client-neutral source items. No provider, kernel or terminal dependencies."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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
            self.items[event.item_id] = Item(event.item_id, "notice", data["text"])
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
            item.text = data.get("name", item.text)
            item.status = data.get("status", "running")
            item.detail.update(data)
        elif event.kind == "turn.ended":
            self.items[event.item_id] = Item(
                event.item_id, "outcome", data.get("message", ""), data["status"]
            )

"""Bounded read-only indexes of identified observations, never inferred authorship."""

import json
from collections import OrderedDict


def bounded(value, limit=16384):
    text = json.dumps(value, ensure_ascii=False, default=str, indent=2)
    if len(text.encode()) <= limit:
        return text, False
    return text.encode()[:limit].decode("utf-8", errors="ignore") + "\n[excerpt: size limit]", True


class Inspection:
    def __init__(self, events=()):
        self.rows = OrderedDict()
        self.partial = False
        for event in events:
            self.observe(event)

    def observe(self, event):
        if event.kind not in {
            "tool.updated",
            "tool.ended",
            "child.observed",
            "context.observed",
            "question.updated",
            "steering.updated",
            "approval.requested",
            "approval.resolved",
        }:
            return
        key = event.item_id
        old = self.rows.pop(key, {})
        previous = old.get("payload", {})
        if old and not old["partial"]:
            previous = json.loads(old["detail"])
        payload = {**previous, **{k: v for k, v in event.payload.items() if v is not None}}
        if event.kind == "approval.resolved":
            payload["status"] = "resolved"
        text, partial = bounded(payload)
        partial = partial or old.get("partial", False)
        recipe_ids = []
        result = payload.get("result")
        if payload.get("name") == "recipes" and isinstance(result, dict):
            output = result.get("output")
            if isinstance(output, dict):
                candidates = [output.get("session_id")]
                sessions = output.get("sessions")
                if isinstance(sessions, list):
                    candidates += [
                        r.get("session_id") for r in sessions[:20] if isinstance(r, dict)
                    ]
                recipe_ids = [
                    s
                    for s in candidates
                    if isinstance(s, str)
                    and 0 < len(s) <= 160
                    and all(c.isalnum() or c in "_-" for c in s)
                ]
        # Retain structured identity/status, not an unbounded second copy of tool output.
        self.rows[key] = {
            "id": key,
            "turn": event.turn_id,
            "sequence": event.sequence,
            "first_sequence": old.get("first_sequence", event.sequence),
            "kind": event.kind,
            "event": payload.get("event"),
            "source": event.session_id,
            "child": payload.get("child_id"),
            "label": payload.get("name", payload.get("event", event.kind)),
            "status": payload.get("status", "observed"),
            "detail": text,
            "partial": partial,
            "recipe_ids": list(dict.fromkeys(recipe_ids)),
            "payload": {k: payload[k] for k in ("name", "child_id", "status") if k in payload},
        }
        while len(self.rows) > 256:
            self.rows.popitem(last=False)
            self.partial = True

    def catalog(self, host, category, child=None):
        rows = list(reversed(self.rows.values()))
        if category == "children":
            rows = [r for r in rows if r["id"].startswith("child:") and r["kind"] == "tool.updated"]
        elif category == "context":
            rows = [r for r in rows if r["kind"] == "context.observed"]
        elif category == "instructions":
            rows = [
                r
                for r in rows
                if r["kind"] == "context.observed" and r.get("event") == "mentions:resolved"
            ]
        elif category == "recipes":
            rows = [r for r in rows if r["label"] == "recipes"]
        elif child:
            rows = [r for r in rows if r["child"] == child]
        else:
            rows = [r for r in rows if r["kind"] != "context.observed"]
        output, budget = [], 1024 * 1024
        partial = self.partial
        for row in rows[:100]:
            value = {k: v for k, v in row.items() if k != "payload"}
            value["live"] = bool(host.children and row["child"] in host.children.active)
            size = len(json.dumps(value, ensure_ascii=False).encode())
            if size > budget:
                partial = True
                break
            budget -= size
            output.append(value)
        return {
            "rows": output,
            "partial": partial or len(rows) > 100,
            "scope": "Observed source, not proof of task success, test coverage or Git authorship. "
            "Historical child rows are not active sessions. Refresh explicitly. "
            "Index: latest 256 identities, 100 results / 1 MiB, 16 KiB detail excerpts; full root results remain in tool evidence/export.",
            "storage_policy": host.report.get("storage_policy", {})
            if category == "context"
            else {},
            "context_note": "Resolved instruction sources are last-observed Foundation events, not the complete current provider request or proof a model used them. Inline instructions and other modules may add content. Empty means no observation, not no instructions. Inspection never rereads files or builds context."
            if category == "instructions"
            else "Usage/compaction are module observations, not a current exact context meter. "
            "No observation means unavailable, not zero. Inspection does not compact or call a model."
            if category == "context"
            else "",
        }

"""Bounded read-only indexes of identified observations, never inferred authorship."""

import json
import math
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
        self.capture_next = False
        self.request_preview = None
        for event in events:
            self.observe(event)

    def capture_request(self, data, host, identity):
        if not self.capture_next:
            return
        self.capture_next = False
        raw = data.get("raw")
        remaining, nodes = 65536, 2000
        partial = False

        def project(value, depth=0):
            nonlocal remaining, nodes, partial
            nodes -= 1
            if nodes < 0 or depth > 12 or remaining <= 0:
                partial = True
                return "[omitted: projection bound]"
            if isinstance(value, dict):
                if value.get("type") in ("image", "image_url", "input_image", "base64"):
                    partial = True
                    return "[omitted: media block]"
                result = {}
                for key, child in value.items():
                    if nodes <= 0 or remaining <= 0:
                        partial = True
                        break
                    if not isinstance(key, str) or key in (
                        "data",
                        "headers",
                        "authorization",
                        "api_key",
                        "url",
                    ):
                        partial = True
                        continue
                    result[key[:160]] = project(child, depth + 1)
                return result
            if isinstance(value, list):
                result = []
                for child in value:
                    if nodes <= 0 or remaining <= 0:
                        partial = True
                        break
                    result.append(project(child, depth + 1))
                return result
            if isinstance(value, str):
                encoded = value[:16384].encode("utf-8")
                excerpt = encoded[: min(16384, remaining)].decode("utf-8", errors="ignore")
                remaining -= len(excerpt.encode())
                partial |= len(excerpt) != len(value)
                return excerpt
            if (
                value is None
                or type(value) is bool
                or (type(value) is int and -(2**63) <= value < 2**63)
                or (type(value) is float and math.isfinite(value))
            ):
                return value
            partial = True
            return "[omitted: unsupported value]"

        fields = (
            "model",
            "messages",
            "system",
            "tools",
            "max_tokens",
            "max_output_tokens",
            "temperature",
            "tool_choice",
            "thinking",
        )
        if isinstance(raw, dict):
            selected = {key: raw[key] for key in fields if key in raw}
            projection = project(selected)
            partial |= len(selected) != len(raw)
            detail, limited = bounded(projection)
            status = "provider-reported projection; not exact wire"
        else:
            detail, limited = (
                "Provider did not expose llm:request.raw. No content was reconstructed or logging enabled.",
                False,
            )
            status = "request content unavailable"
        self.request_preview = {
            "id": identity,
            "source": host.session_id,
            "turn": host.turn_id,
            "sequence": host.sequence + 1,
            "first_sequence": host.sequence + 1,
            "label": "One-shot provider request observation",
            "status": status,
            "detail": detail,
            "partial": partial or limited,
            "live": False,
        }

    def request_catalog(self):
        return {
            "rows": [dict(self.request_preview)] if self.request_preview else [],
            "partial": bool(self.request_preview and self.request_preview["partial"]),
            "scope": "One-shot diagnostic, memory only; contains private context. Provider-reported/redacted fields, not exact wire bytes or delivery proof. Media/auth/unknown fields and content beyond projection limits are omitted. No model call, request construction or provider configuration change.",
            "context_note": "Waiting for the next root provider request; nothing submitted automatically."
            if self.capture_next
            else "Capture held for this launch only; clear, re-arm or reopening discards it. Module logging remains independent."
            if self.request_preview
            else "No capture retained or armed. Module logging remains independent.",
        }

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
        if category == "recovery":
            from .recovery import recovery_catalog

            return recovery_catalog(host.store)
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

    async def context_snapshot(self, host):
        """Read the public stored messages, never construct a provider request."""
        import asyncio

        async with asyncio.timeout(3):
            messages = await host.session.coordinator.get("context").get_messages()
        if not isinstance(messages, list):
            raise ValueError("Context module returned no supported message list")
        rows, remaining = [], 1024 * 1024
        partial = len(messages) > 100
        for index, message in enumerate(messages[-100:], max(0, len(messages) - 100)):
            if hasattr(message, "model_dump"):
                message = message.model_dump()
            if not isinstance(message, dict):
                partial = True
                continue
            value = dict(message)
            content = value.get("content")
            if isinstance(content, list):
                value["content"] = [
                    {"type": "image", "notice": "Image bytes omitted from inspection"}
                    if isinstance(block, dict) and block.get("type") == "image"
                    else block
                    for block in content
                ]
            detail, clipped = bounded(value)
            remaining -= len(detail.encode())
            if remaining < 0:
                partial = True
                break
            partial |= clipped
            rows.append(
                {
                    "id": f"context-message:{index}",
                    "label": f"Stored message {index + 1} · {value.get('role', 'unknown')}",
                    "status": "local context snapshot",
                    "source": host.session_id,
                    "detail": detail,
                    "partial": clipped,
                    "live": False,
                }
            )
        return {
            "rows": rows,
            "partial": partial,
            "scope": "Public context-module messages at inspection time; last 100 messages / 1 MiB, 16 KiB per message. Images omitted. No provider call or compaction.",
            "context_note": "This is stored context, NOT the exact next provider request. System prompts, routing, provider conversions and hooks may change what is sent. Inspect dispatch observations separately; absent observations mean unavailable, never zero.",
        }

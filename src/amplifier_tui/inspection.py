"""Bounded read-only indexes of identified observations, never inferred authorship."""

import json
import math
from collections import OrderedDict, deque
from datetime import datetime
from decimal import Decimal

from amplifier_foundation import sum_cost_usd

USAGE_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
    "cost_usd",
)


def usage_values(value):
    if not isinstance(value, dict):
        return {}
    result = {}
    for key in USAGE_FIELDS:
        aliases = {
            "cache_read_input_tokens": "cache_read_tokens",
            "cache_creation_input_tokens": "cache_write_tokens",
        }
        raw = value.get(key, value.get(aliases.get(key)))
        if key == "cost_usd":
            try:
                raw = Decimal(str(raw))
            except (ArithmeticError, ValueError):
                continue
            if raw.is_finite() and 0 <= raw < 2**53:
                result[key] = raw
        elif type(raw) is int and 0 <= raw < 2**53:
            result[key] = raw
        elif type(raw) is float and math.isfinite(raw) and 0 <= raw < 2**53:
            result[key] = raw
    return result


def usage_totals():
    """Constant-space summary; individual observations stay in the event journal."""
    return {"requests": 0, "reported": {}, "totals": {}}


def usage_receipt_id(data):
    """The kernel's emit identity shared by logging and host observation hooks.

    Do not use the observer's clock, a model iteration, or equal token counts as
    identity. Older observations without the kernel timestamp remain uncorrelated.
    """
    import hashlib

    stamp, session = data.get("timestamp"), data.get("session_id")
    if not isinstance(stamp, str) or not isinstance(session, str):
        return None
    try:
        if datetime.fromisoformat(stamp.replace("Z", "+00:00")).tzinfo is None:
            return None
    except ValueError:
        return None
    fields = (
        session,
        stamp,
        *(data.get(k) for k in ("request_id", "span_id", "provider", "model", "purpose")),
    )
    if any(v is not None and not isinstance(v, str) for v in fields):
        return None
    return "receipt:" + hashlib.sha256(json.dumps(fields).encode()).hexdigest()


def add_usage(total, values):
    """Add one provider response without retaining all prior usage dictionaries."""
    total["requests"] += 1
    for key, value in values.items():
        total["reported"][key] = total["reported"].get(key, 0) + 1
        if key == "cost_usd":
            total["totals"][key] = sum_cost_usd(
                [{"cost_usd": total["totals"].get(key)}, {"cost_usd": value}]
            )
        else:
            total["totals"][key] = total["totals"].get(key, 0) + value


def usage_summary(total, provider, elapsed):
    parts = [
        "Root request totals; last reported "
        + (
            " / ".join(str(provider[k])[:120] for k in ("provider", "model") if provider.get(k))
            or "provider/model unknown"
        )
    ]
    for key, label in (
        ("input_tokens", "input"),
        ("output_tokens", "output"),
        ("cache_read_input_tokens", "cache read"),
        ("cache_creation_input_tokens", "cache write"),
        ("cost_usd", "cost USD"),
    ):
        if key in total["totals"]:
            value = total["totals"][key]
            formatted = f"{value:.6f}" if key == "cost_usd" else f"{value:,}"
            parts.append(
                f"{label} {formatted}"
                + (" (partial)" if total["reported"][key] != total["requests"] else "")
            )
    if "cost_usd" not in total["totals"]:
        parts.append("cost not reported")
    parts.append(f"{elapsed:.1f}s")
    return " · ".join(parts)


class CallUsage:
    """App-owned accounting of identified responses, including children, never estimates.

    The journal owns individual calls. A bounded recent identity window deduplicates
    delivery/replay retries; totals remain constant-space.
    """

    MAX_SEEN = 1024

    def __init__(self, events=()):
        self.seen = OrderedDict()
        self.session = usage_totals()
        self.turn = usage_totals()
        self.turn_id = None
        self.legacy = False
        for event in events:
            if event.payload.get("accounting_snapshot"):
                snapshot = event.payload["accounting_snapshot"]
                self.session = {
                    **snapshot,
                    "totals": usage_values(snapshot["totals"]),
                    "reported": dict(snapshot["reported"]),
                }
                self.turn, self.turn_id = usage_totals(), None
                self.legacy = bool(event.payload.get("partial"))
                self.seen.clear()
            elif event.kind == "display.message" and isinstance(
                event.payload.get("usage_call"), dict
            ):
                self.add(
                    event.item_id,
                    event.turn_id,
                    event.payload["usage_call"],
                    session_only=event.payload.get("usage_scope") == "session",
                )
            elif event.kind == "context.observed" and event.payload.get("event") == "llm:response":
                identity = (
                    event.payload.get("usage_id")
                    or f"{event.turn_id}:usage:root:{event.payload.get('request_index', 0)}"
                )
                self.legacy |= identity not in self.seen

    def add(self, identity, turn_id, values, *, session_only=False):
        if identity in self.seen:
            return False
        self.seen[identity] = None
        if len(self.seen) > self.MAX_SEEN:
            self.seen.popitem(last=False)
        if not session_only and self.turn_id != turn_id:
            self.turn_id, self.turn = turn_id, usage_totals()
        normalized = usage_values(values)
        add_usage(self.session, normalized)
        if not session_only:
            add_usage(self.turn, normalized)
        return True

    def costs(self, *, session_only=False):
        def cost(total):
            value = total["totals"].get("cost_usd")
            if value is None:
                return "not reported"
            return f"${value:.2f}" + (
                " (partial)" if total["reported"]["cost_usd"] != total["requests"] else ""
            )

        return (
            ("" if session_only else f"Turn: {cost(self.turn)} · ")
            + f"Session: {cost(self.session)}"
            + (" (earlier usage unavailable)" if self.legacy else "")
        )

    def progress(self, turn_id):
        """Constant-size, JSON-safe view of reported calls, not in-flight estimates."""

        def scope(total):
            requests, values, reported = total["requests"], total["totals"], total["reported"]
            token_fields = ("input_tokens", "output_tokens")
            tokens = (
                sum(values.get(key, 0) for key in (*token_fields, "cache_creation_input_tokens"))
                if any(key in values for key in token_fields)
                else None
            )
            cost = values.get("cost_usd")
            return {
                "calls": requests,
                "tokens": tokens,
                "tokens_partial": any(reported.get(key, 0) != requests for key in token_fields),
                "cost": ("pending" if not requests else "not reported")
                if cost is None
                else (
                    ("<$0.01" if 0 < cost < Decimal("0.01") else f"${cost:.2f}")
                    + (" (partial)" if reported["cost_usd"] != requests else "")
                ),
            }

        return {
            "turn": scope(self.turn if self.turn_id == turn_id else usage_totals()),
            "session": scope(self.session),
            "earlier_usage_unavailable": self.legacy,
        }


def call_usage_text(values, provider, *, agent="", duration_ms=None, timestamp=None):
    """Match provider cache semantics: writes add input, reads are already in input."""
    model = (
        "/".join(str(provider[k])[:120] for k in ("provider", "model") if provider.get(k))
        or "model not reported"
    )
    basis = provider.get("basis")
    routing = f" · {'pinned' if basis == 'pinned' else basis}" if basis else ""
    duration = (
        f" · {duration_ms / 1000:.1f}s"
        if isinstance(duration_ms, (int, float)) and math.isfinite(duration_ms) and duration_ms >= 0
        else ""
    )
    stamp = (timestamp or datetime.now().astimezone()).strftime("%Y-%m-%d %H:%M:%S %Z")
    title = f"Usage · {agent + ' · ' if agent else ''}{model}{routing}{duration} · {stamp}"
    input_count = values.get("input_tokens")
    if input_count is not None:
        input_count += values.get("cache_creation_input_tokens", 0)
    output = values.get("output_tokens")

    def tokens(n):
        return f"{n:,}" if n is not None else "not reported"

    cached = values.get("cache_read_input_tokens")
    cache = f" ({cached / input_count:.0%} cached)" if cached is not None and input_count else ""
    if values.get("cache_creation_input_tokens") and not cached:
        cache = " (caching)"
    cost = f"${values['cost_usd']:.6f}" if "cost_usd" in values else "not reported"
    total = input_count + output if input_count is not None and output is not None else None
    return f"{title}\nInput: {tokens(input_count)}{cache} · Output: {tokens(output)} · Total: {tokens(total)} · Cost: {cost}"


def activity_task_title(payload):
    """Use observed display metadata, never guess a child's task from its role."""
    title = payload.get("task_title")
    children = payload.get("child_progress")
    if isinstance(children, list):
        if len(children) == 1 and isinstance(children[0], dict):
            title = children[0].get("task_title")
        elif len(children) > 1 and any(
            isinstance(row, dict) and row.get("task_title") for row in children
        ):
            count = payload.get("child_count", len(children))
            title = (
                f"{count if type(count) is int and count >= len(children) else len(children)} tasks"
            )
    return " ".join(title[:160].split()) if isinstance(title, str) and title.strip() else None


def bounded(value, limit=16384):
    text = json.dumps(value, ensure_ascii=False, default=str, indent=2)
    if len(text.encode()) <= limit:
        return text, False
    return text.encode()[:limit].decode("utf-8", errors="ignore") + "\n[excerpt: size limit]", True


def bounded_projection(value, limit=16384):
    """Make a bounded JSON-safe projection before Activity serializes hot-path data."""
    remaining, nodes, partial = max(limit - 1024, 0), 2000, False

    def project(item, depth=0):
        nonlocal remaining, nodes, partial
        if nodes <= 0 or depth > 12 or remaining <= 0:
            partial = True
            return "[omitted: projection bound]"
        nodes -= 1
        if isinstance(item, dict):
            result = {}
            for key, child in item.items():
                if not isinstance(key, str):
                    partial = True
                    continue
                key = key[:160]
                key_cost = len(key.encode("utf-8")) + 4
                if remaining <= key_cost:
                    partial = True
                    break
                remaining -= key_cost
                result[key] = project(child, depth + 1)
            return result
        if isinstance(item, list):
            result = []
            for child in item:
                if remaining <= 4:
                    partial = True
                    break
                remaining -= 2
                result.append(project(child, depth + 1))
            return result
        if isinstance(item, str):
            encoded = item.encode("utf-8")
            allowed = min(len(encoded), remaining, 4096)
            excerpt = encoded[:allowed].decode("utf-8", errors="ignore")
            remaining -= len(excerpt.encode("utf-8"))
            partial |= len(excerpt) != len(item)
            return excerpt
        if item is None or type(item) is bool:
            return item
        if type(item) is int and -(2**63) <= item < 2**63:
            encoded = str(item).encode("ascii")
            if len(encoded) > remaining:
                partial = True
                return "[omitted: oversized integer]"
            remaining -= len(encoded)
            return item
        if type(item) is float and math.isfinite(item):
            encoded = repr(item).encode("ascii")
            if len(encoded) > remaining:
                partial = True
                return "[omitted: projection bound]"
            remaining -= len(encoded)
            return item
        partial = True
        return f"[omitted: {type(item).__name__}]"

    result = project(value)
    if partial:
        if isinstance(result, dict):
            result["_excerpt"] = "[excerpt: projection limit]"
        else:
            result = {"value": result, "_excerpt": "[excerpt: projection limit]"}
    return result, partial


def recipe_files(host):
    """Names only in declared local recipe folders; never parse or execute a file."""
    import os
    import time
    from pathlib import Path

    roots = getattr(host, "recipe_roots", [])
    rows, seen, examined, partial = [], set(), 0, len(roots) > 32
    deadline = time.monotonic() + 0.1
    pending = deque((Path(root).absolute(), 0) for root in roots[:32])
    while pending:
        directory, depth = pending.popleft()
        if time.monotonic() >= deadline or examined >= 2000 or len(rows) >= 100:
            partial = True
            break
        try:
            descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                entries = os.scandir(descriptor)
            except BaseException:
                os.close(descriptor)
                raise
            try:
                with entries:
                    for entry in entries:
                        examined += 1
                        if examined > 2000 or time.monotonic() >= deadline or len(rows) >= 100:
                            partial = True
                            break
                        path = directory / entry.name
                        if entry.is_symlink() or not str(path).isprintable():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            if depth < 2:
                                pending.append((path, depth + 1))
                            else:
                                partial = True
                        elif entry.is_file(follow_symlinks=False) and path.suffix in (
                            ".yaml",
                            ".yml",
                        ):
                            identity = str(path.absolute())
                            if identity in seen:
                                continue
                            seen.add(identity)
                            rows.append(
                                {
                                    "id": identity,
                                    "label": f"{path.name} — {path.parent}",
                                    "status": "file candidate",
                                    "recipe_file": identity,
                                    "detail": f"Path: {identity}\nLocal filename only: contents and dependencies have not been validated. Select to append an unsent request to read/validate and explain effects; not permission to execute.",
                                }
                            )
            finally:
                os.close(descriptor)
        except FileNotFoundError:
            continue
        except OSError:
            partial = True
    return {
        "rows": sorted(rows, key=lambda r: r["label"]),
        "partial": partial,
        "scope": "Recipe FILE candidates, not active sessions or past activity. Names only; no contents read, no tool/model call. Selected working directory and composed bundle recipe folders only; remote/unresolved sources excluded. Limits: 32 roots, 2 subdirectory levels, 2000 entries, 100 files, 100 ms. Empty does not mean no recipes exist elsewhere. A file candidate does not establish that the recipes tool is mounted or its dependencies are available.",
    }


def safe_destination(value):
    """Forward only configured destination IDs, never a URL or arbitrary detail."""
    import re

    return (
        value
        if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,159}", value)
        else None
    )


def forwarding_observations(host):
    """Bounded, session-filtered public diagnostic files; never copy URLs/tokens."""
    import os
    import stat
    from datetime import datetime, timezone

    resolver = host.session.coordinator.get_capability("context_intelligence.hook_config_resolver")
    result = {
        "observations": [],
        "partial": False,
        "scope": "Today's bounded forwarding diagnostics for this root session only. No diagnostic is not proof of delivery. HTTP acceptance does not prove remote indexing; child sessions and previous days are not included. URLs, credentials and raw error details are omitted.",
    }
    if resolver is None:
        result["status"] = "No mounted intelligence diagnostic resolver"
        return result
    path = getattr(resolver, "forwarding_log_dir", None)
    if path is None:
        result["status"] = "Forwarding diagnostics disabled; remote delivery unknown"
        return result
    try:
        directory = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            name = "forwarding-" + datetime.now(timezone.utc).strftime("%Y-%m-%d") + ".jsonl"
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        finally:
            os.close(directory)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise ValueError("Not a regular diagnostic file")
            start = max(0, info.st_size - 65536)
            stream.seek(start)
            raw = stream.read(65536)
        result["partial"] = start > 0
        lines = raw.splitlines()[1:] if start else raw.splitlines()
        for line in lines:
            try:
                row = json.loads(line)
                if not isinstance(row, dict) or row.get("session_id") != host.session_id:
                    continue
                observation = {
                    key: row[key]
                    for key in ("kind", "ts")
                    if isinstance(row.get(key), str)
                    and row[key].isprintable()
                    and len(row[key]) <= 160
                }
                if destination := safe_destination(row.get("destination")):
                    observation["destination"] = destination
                if type(row.get("http_status")) is int and 100 <= row["http_status"] <= 599:
                    observation["http_status"] = row["http_status"]
                result["observations"].append(observation)
            except (ValueError, TypeError):
                result["partial"] = True
        if len(result["observations"]) > 20:
            result["partial"] = True
        result["observations"] = result["observations"][-20:]
        result["status"] = "Observed diagnostics; not a delivery certificate"
    except FileNotFoundError:
        result["status"] = "No diagnostic file observed today; delivery unknown"
    except (OSError, ValueError):
        result["status"] = "Diagnostics unavailable; delivery unknown"
        result["partial"] = True
    return result


class Inspection:
    def __init__(self, events=()):
        self.rows = OrderedDict()
        self.partial = False
        self.capture_next = False
        self.request_preview = None
        for event in events:
            self.observe(event)

    @staticmethod
    def context_budget(data):
        result = {}
        for key in (
            "effective_budget",
            "derived_budget",
            "max_tokens",
            "max_tokens_fallback",
            "context_window",
            "output_reservation",
        ):
            value = data.get(key)
            if type(value) is int and 0 <= value <= 2**53:
                result[key] = value
        for key in ("source", "capped"):
            value = data.get(key)
            if type(value) is bool or isinstance(value, str) and len(value) <= 120:
                result[key] = value
        return result

    @staticmethod
    def request_budget(data):
        """Numeric provider observations only; no request construction or private meter."""
        raw = data.get("raw")
        raw = raw if isinstance(raw, dict) else {}
        result = {}
        for key in ("context_window", "max_tokens", "max_output_tokens", "thinking_budget"):
            value = data.get(key, raw.get(key))
            if type(value) is int and 0 < value <= 2**31 - 1:
                result[key] = value
        thinking = raw.get("thinking")
        if isinstance(thinking, dict):
            value = thinking.get("budget_tokens")
            if type(value) is int and 0 < value <= 2**31 - 1:
                result["thinking_budget"] = value
        result["scope"] = (
            "Provider-reported declarations for this dispatch, not consumed tokens or current "
            "occupancy. Thinking may share the output reservation; do not add them. Missing "
            "limits are unknown. No catalog substitution, private meter or logging change."
        )
        return result

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
        if event.kind == "display.message" and event.payload.get("source") not in (
            "thinking",
            "usage",
        ):
            return
        if event.kind not in {
            "display.message",
            "tool.updated",
            "tool.progress",
            "activity.progress",
            "tool.ended",
            "child.observed",
            "activity.observed",
            "context.observed",
            "change.observed",
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
        title = activity_task_title(payload)
        if title:
            # Keep this small projection across output truncation and final status events.
            payload["task_title"] = title
        if event.kind == "approval.resolved":
            payload["status"] = "resolved"
        if payload.get("name") == "recipes" and isinstance(payload.get("result"), dict):
            result = payload["result"]
            output, error = result.get("output"), result.get("error")
            output = output if isinstance(output, dict) else {}
            error = error if isinstance(error, dict) else {}
            status = output.get("status")
            refusal = error.get("type") in (
                "V2RunNotRecorded",
                "V2EngineSessionMissing",
                "V2EngineSessionUnknown",
            )
            payload["recovery_guidance"] = (
                "Runner refused unsafe resume: checkpoint/outcome unavailable. No steps were replayed by this refusal. Inspect earlier effects; a fresh execution requires separate authorization."
                if refusal
                else "Runner reports all steps completed; no resume needed."
                if status in ("completed", "nothing_to_resume")
                else "Runner paused for approval. Inspect the exact stage; approval and resume remain separate explicit operations."
                if status == "paused_for_approval"
                else "Inspect the runner's recorded completed and unfinished steps before explicit resume. Unfinished steps may have partial effects; neither inspection nor reopening authorizes retry."
            )
        projection, limited = bounded_projection(payload)
        text, partial = bounded(projection)
        partial = partial or limited or old.get("partial", False)
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
        from .events import tool_text

        block = payload.get("block")
        block = block if isinstance(block, dict) else {}
        thinking = payload.get("source") == "thinking" or block.get("type") in (
            "thinking",
            "reasoning",
        )
        public_text = (
            payload.get("text")
            if (event.kind == "display.message" and payload.get("source") in ("thinking", "usage"))
            or (
                event.kind == "activity.observed"
                and (
                    isinstance(payload.get("usage_call"), dict)
                    or payload.get("accounting_snapshot")
                )
            )
            else block.get("text") or block.get("thinking")
        )
        public_text = public_text if isinstance(public_text, str) else None
        self.rows[key] = {
            "id": key,
            "turn": event.turn_id,
            "sequence": event.sequence,
            "first_sequence": old.get("first_sequence", event.sequence),
            "kind": old.get(
                "kind", "tool.updated" if event.kind == "tool.progress" else "child.observed"
            )
            if event.kind in ("tool.progress", "activity.progress")
            else event.kind,
            "event": payload.get("event", event.kind),
            "source": event.session_id,
            "child": payload.get("child_id"),
            "parent": payload.get("parent_item_id"),
            "public_text": public_text[:8192] if public_text is not None else None,
            "thinking": thinking,
            "preview_partial": public_text is not None and len(public_text) > 8192,
            "tool_preview": tool_text(payload),
            "label": (f"{title} · " if title else "")
            + payload.get("name", payload.get("event", event.kind)),
            "status": payload.get("status", "observed"),
            "detail": text,
            "partial": partial,
            "recipe_ids": list(dict.fromkeys(recipe_ids)),
            "payload": {
                k: payload[k]
                for k in ("name", "child_id", "status", "parent_item_id", "task_title")
                if k in payload
            },
        }
        while len(self.rows) > 256:
            self.rows.popitem(last=False)
            self.partial = True

    def activity_tree(self, node=None):
        """One bounded, stable sibling page. No context construction or execution."""
        rows = sorted(
            (
                r
                for r in self.rows.values()
                if r["kind"]
                in (
                    "tool.updated",
                    "tool.ended",
                    "child.observed",
                    "activity.observed",
                    "display.message",
                )
            ),
            key=lambda r: r["first_sequence"],
        )
        index = {r["id"]: r for r in rows}
        parent = index.get(node)
        selected = (
            [r for r in rows if r.get("parent") == node]
            if node
            else [r for r in rows if not r.get("parent") or r["parent"] not in index]
        )
        output = []
        for row in selected[:100] + ([parent] if parent else []):
            value = {
                k: v for k, v in row.items() if k not in ("payload", "public_text", "tool_preview")
            }
            try:
                payload = json.loads(row["detail"])
            except ValueError:
                payload = row["payload"]
            thinking = row["thinking"]
            text = row["public_text"]

            value["label"] = (
                row["label"]
                if payload.get("accounting_snapshot")
                else "Usage"
                if payload.get("source") == "usage"
                else "Thinking"
                if thinking
                else "Response"
                if text and row.get("event") != "display.message"
                else row["label"]
            )
            if payload.get("recipe_step"):
                value["label"] += f" · step {str(payload['recipe_step'])[:120]}"
            value["preview"] = text if isinstance(text, str) else row["tool_preview"]
            if row["preview_partial"]:
                value["preview"] += "\n\n[Public text excerpt: 8192 character limit]"
            value["markdown"] = isinstance(text, str)
            value["thinking"] = thinking
            children = [r for r in rows if r.get("parent") == row["id"]]
            descendants, seen = list(children), {row["id"]}
            counts = {}
            while descendants:
                child = descendants.pop()
                if child["id"] in seen:
                    continue
                seen.add(child["id"])
                state = "waiting" if child["status"].startswith("waiting") else child["status"]
                counts[state] = counts.get(state, 0) + 1
                descendants.extend(r for r in rows if r.get("parent") == child["id"])
            value["children"] = len(children)
            value["summary"] = " · ".join(
                f"{n} {state}"
                for state, n in counts.items()
                if state
                in ("running", "waiting", "failed", "interrupted", "unknown", "warning", "error")
            )
            if row.get("child") and row.get("parent") not in index:
                value["preview"] += "\nOriginating call unavailable; not inferred from timing."
            output.append(value)
        focus = output.pop() if parent else None
        budget = 1024 * 1024 - len(json.dumps(focus, ensure_ascii=False).encode())
        bounded_output = []
        for row in output:
            size = len(json.dumps(row, ensure_ascii=False).encode())
            if size > budget:
                break
            bounded_output.append(row)
            budget -= size
        trail, seen = [], set()
        cursor = parent
        while cursor and cursor["id"] not in seen:
            seen.add(cursor["id"])
            trail.append(cursor["label"])
            cursor = index.get(cursor.get("parent"))
        return {
            "rows": bounded_output,
            "node": node,
            "parent": parent.get("parent") if parent else None,
            "breadcrumb": " / ".join(reversed(trail)),
            "focus": focus,
            "partial": self.partial or len(selected) > len(bounded_output),
            "scope": "Read-only observations · Enter/click opens detail · no replay. Latest 256 identities, 100 siblings / 1 MiB, 16 KiB detail and 8192-character public text excerpts; full root evidence remains in Review/export. Unobserved child conversation and private reasoning are unavailable."
            + (" Selected node is unavailable or evicted." if node and not parent else ""),
        }

    @staticmethod
    def journal_version(path):
        """Identify a regular journal without following links or reading its contents."""
        import os
        import stat

        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise ValueError("Activity journal is not a regular file")
            return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns

    @staticmethod
    def _recorded_activity_row(event, association, identity, parent):
        """A bounded optional observation, never execution or an extra cost total."""

        def excerpt(value, limit=160):
            if not isinstance(value, str):
                return ""
            return value[:limit].encode("utf-8", errors="replace").decode("utf-8")

        data = event["data"]
        fields = (
            "tool_name",
            "name",
            "tool_call_id",
            "call_id",
            "message_id",
            "request_id",
            "span_id",
            "provider",
            "model",
            "purpose",
            "usage",
            "duration_ms",
            "status",
            "success",
            "error",
        )
        if event["event"].startswith("tool:"):
            fields += ("arguments", "input", "result")
        selected = {key: data[key] for key in fields if key in data}
        try:
            projection, limited = bounded_projection(selected)
        except (UnicodeError, OverflowError, ValueError, TypeError, RecursionError):
            projection, limited = {"unavailable": "Malformed observed fields omitted"}, True
        event_name = excerpt(event["event"])
        detail, clipped = bounded(
            {
                "event": event_name,
                "source_line": event["line"],
                "session_id": excerpt(event.get("session_id")),
                "timestamp": excerpt(event.get("timestamp")),
                "association": {
                    "method": association.method,
                    "message_indices": association.message_indices,
                    "turn_index": association.turn_index,
                    "auxiliary": association.auxiliary,
                },
                "observed_fields": projection,
            }
        )
        linked = (
            "Saved message "
            + ", ".join(str(index + 1) for index in association.message_indices)
            + f" · exact {association.method} association"
            if association.message_indices
            else "Auxiliary observation; not assigned to a conversation turn."
            if association.auxiliary
            else "Unassociated observation; no unique message/tool evidence."
        )
        name = excerpt(data.get("tool_name") or data.get("name") or data.get("model"), 120)
        preview = linked
        if event["event"] == "llm:response":
            try:
                stamp = datetime.fromisoformat(
                    excerpt(event.get("timestamp")).replace("Z", "+00:00")
                )
            except ValueError:
                preview += "\n\nCall timestamp unavailable; usage is retained in observed fields."
            else:
                duration = event.get("duration_ms", data.get("duration_ms"))
                if type(duration) not in (int, float) or not 0 <= duration < 2**53:
                    duration = None
                preview += "\n\n" + call_usage_text(
                    usage_values(data.get("usage")),
                    {key: excerpt(data.get(key)) for key in ("provider", "model", "basis")},
                    timestamp=stamp,
                    duration_ms=duration,
                )
        return {
            "id": identity,
            "parent": parent,
            "label": event_name + (f" · {name}" if name else ""),
            "status": "observed",
            "source": "shared session activity",
            "children": 0,
            "summary": f"source line {event['line']}",
            "preview": preview,
            "detail": detail,
            "partial": limited or clipped or event_name != event["event"],
            "markdown": False,
        }

    @staticmethod
    def native_activity(events, activity, messages, node=None, offset=0, *, active=False):
        """One ordinary Activity tree over canonical, live and CI observations.

        The store supplies in-memory canonical/live events. Foundation alone
        associates optional CI events to saved messages. No imported journal or
        origin-specific chooser is involved; display bounds never cap execution.
        """
        events = deque(events, maxlen=20001)
        partial = activity["partial"] or len(events) > 20000
        if len(events) > 20000:
            events.popleft()
        headers, by_message, by_call, receipts = {}, {}, {}, set()
        kinds = {
            "tool.updated",
            "tool.progress",
            "tool.ended",
            "child.observed",
            "activity.observed",
            "activity.progress",
            "display.message",
        }
        identities = dict.fromkeys(
            event.item_id
            for event in reversed(events)
            if event.kind in kinds
            and (
                event.kind != "display.message"
                or event.payload.get("source") in ("usage", "thinking")
            )
        )
        if len(identities) > 10000:
            partial = True
        retained = set(list(identities)[:10000])
        for event in events:
            payload, key = event.payload, event.item_id
            if event.kind not in kinds or (
                event.kind == "display.message"
                and payload.get("source") not in ("usage", "thinking")
            ):
                continue
            if key not in retained:
                continue
            if key not in headers:
                headers[key] = {
                    "parent": payload.get("parent_item_id"),
                    "label": str(payload.get("name", payload.get("source", event.kind)))[:256],
                    "status": payload.get("status", "observed"),
                }
            if payload.get("status") is not None:
                headers[key]["status"] = payload["status"]
            if payload.get("name") is not None:
                headers[key]["label"] = str(payload["name"])[:256]
            title = activity_task_title(payload)
            if title:
                headers[key]["label"] = title + " · " + headers[key]["label"]
            index = payload.get("canonical_message_index")
            if type(index) is int:
                by_message.setdefault(index, set()).add(key)
            call = payload.get("tool_call_id")
            if isinstance(call, str):
                by_call.setdefault(call, set()).add(key)
            receipt = payload.get("usage_receipt_id")
            if isinstance(receipt, str):
                receipts.add(receipt)

        extras = {}
        for association in activity["associations"]:
            event = activity["events"][association.event_index]
            data = event["data"]
            if event["event"] == "llm:response":
                observed = {
                    **data,
                    **{
                        key: event[key]
                        for key in ("session_id", "request_id", "span_id")
                        if key in event
                    },
                    "timestamp": event.get("timestamp"),
                }
                if usage_receipt_id(observed) in receipts:
                    continue
            matched = set()
            if association.message_indices and not association.auxiliary:
                call = data.get("tool_call_id") or data.get("call_id")
                if association.method == "tool_call_id" and isinstance(call, str):
                    matched.update(by_call.get(call, ()))
                else:
                    for index in association.message_indices:
                        matched.update(by_message.get(index, ()))
            parent = next(iter(matched)) if len(matched) == 1 else None
            if parent is None:
                anchor = association.turn_message_index
                if association.auxiliary:
                    parent, label = "observations:utility", "Utility calls"
                    preview = "Recorded auxiliary calls; not assigned to conversation turns."
                elif anchor is not None:
                    parent, label = (
                        f"observations:turn:{anchor}",
                        f"Turn {association.turn_index + 1} observations",
                    )
                    text = messages[anchor].get("content")
                    preview = " ".join(text[:400].split()) if isinstance(text, str) else ""
                else:
                    parent, label = "observations:unassociated", "Unassociated observations"
                    preview = "No unique message/tool association was recorded; timing is never used to guess one."
                if parent not in headers:
                    if len(headers) >= 10000:
                        partial = True
                        break
                    headers[parent] = {"parent": None, "label": label, "status": "observed"}
                    extras[parent] = {
                        "id": parent,
                        "parent": None,
                        "label": label,
                        "status": "observed",
                        "preview": preview.encode("utf-8", errors="replace").decode("utf-8"),
                        "detail": preview.encode("utf-8", errors="replace").decode("utf-8"),
                        "source": "saved activity",
                        "partial": False,
                        "markdown": False,
                    }
            key = f"observation:{event['line']}"
            if len(headers) >= 10000:
                partial = True
                break
            headers[key] = {
                "parent": parent,
                "label": str(event["event"])[:160]
                .encode("utf-8", errors="replace")
                .decode("utf-8"),
                "status": "observed",
            }
            extras[key] = (event, association)

        selected = [
            key
            for key, header in headers.items()
            if header["parent"] == node or (node is None and header["parent"] not in headers)
        ]
        wanted = set(selected[offset : offset + 100])
        if node in headers:
            wanted.add(node)
        index = Inspection()
        for event in events:
            if event.item_id in wanted:
                index.observe(event)
        base = index.activity_tree(node)
        projected = {
            row["id"]: row for row in base["rows"] + ([base["focus"]] if base["focus"] else [])
        }
        for key in wanted:
            if key in extras:
                extra = extras[key]
                projected[key] = (
                    dict(extra)
                    if isinstance(extra, dict)
                    else Inspection._recorded_activity_row(*extra, key, headers[key]["parent"])
                )

        adjacency = {}
        for key, header in headers.items():
            adjacency.setdefault(header["parent"], []).append(key)
        for key, row in projected.items():
            row["label"] = str(row["label"])[:282]
            row["children"] = len(adjacency.get(key, ()))
            row["parent"] = headers[key]["parent"]
            pending, seen, counts = list(adjacency.get(key, ())), set(), {}
            while pending:
                child = pending.pop()
                if child in seen:
                    continue
                seen.add(child)
                status = headers[child]["status"]
                if isinstance(status, str):
                    counts[status] = counts.get(status, 0) + 1
                pending.extend(adjacency.get(child, ()))
            row["summary"] = " · ".join(
                f"{count} {status}"
                for status, count in counts.items()
                if status
                in ("running", "waiting", "failed", "unknown", "interrupted", "warning", "error")
            )
        focus = projected.get(node)
        rows, budget = [], 1024 * 1024 - 4096 - len(json.dumps(focus).encode())
        for key in selected[offset : offset + 100]:
            row = projected.get(key)
            if row is None:
                partial = True
                continue
            size = len(json.dumps(row, ensure_ascii=False).encode())
            if size > budget:
                partial = True
                break
            rows.append(row)
            budget -= size
        trail, seen, cursor = [], set(), node
        while cursor in headers and cursor not in seen:
            seen.add(cursor)
            trail.append(str(headers[cursor]["label"])[:282])
            cursor = headers[cursor]["parent"]
        # Bounded breadcrumbs also protect a pathological nested activity tree.
        breadcrumb = " / ".join(reversed(trail[-12:]))[:2048]
        return {
            "rows": rows,
            "focus": focus,
            "node": node,
            "parent": headers[node]["parent"] if node in headers else None,
            "breadcrumb": breadcrumb,
            "offset": offset,
            "next_offset": offset + len(rows)
            if rows and offset + len(rows) < len(selected)
            else None,
            "partial": partial or (node is not None and node not in headers),
            "snapshot": not active,
            "scope": "Conversation and observed work · canonical history plus current activity. "
            "Saved observations attach only by Foundation's exact message/tool associations; "
            "unassociated and utility observations remain explicit. No replay or extra accounting contribution. "
            "CI is read on explicit open, never polled; live updates use memory. "
            "Display limits: latest 20,000 events / latest 10,000 identities, CI 16 MiB / 5000 lines, "
            "100 rows / 1 MiB per page, 16 KiB detail excerpts. "
            "Only operational metadata and bounded tool fields are shown; raw provider bodies are omitted."
            + (
                " Some saved activity is unavailable or outside display bounds; canonical history is unchanged."
                if partial
                else ""
            ),
        }

    @staticmethod
    def journal_activity(path, node=None, offset=0):
        """One read-only sibling page from retained events, not the hot cache.

        Run off the input/event loop. Snapshot the file size; append-only arrivals
        belong to the next refresh. Bound reads, identities, time and page memory.
        Never read child private context or recover pre-policy tool output.
        """
        import os
        import stat
        import time

        from .events import Event

        index, headers, selected = Inspection(), {}, set()
        count, read, partial = 0, 0, False
        deadline = time.monotonic() + 2
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise ValueError("Activity journal is not a regular file")
            journal_version = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
            limit = min(info.st_size, 64 * 1024 * 1024)
            while read < limit:
                raw = stream.readline(min(limit - read, 8 * 1024 * 1024) + 1)
                read += len(raw)
                if not raw.endswith(b"\n") or read > limit or time.monotonic() > deadline:
                    partial = True
                    break
                event = Event(**json.loads(raw))
                payload, key = event.payload, event.item_id
                if event.kind not in {
                    "tool.updated",
                    "tool.progress",
                    "tool.ended",
                    "child.observed",
                    "activity.observed",
                    "activity.progress",
                    "display.message",
                }:
                    continue
                if event.kind == "display.message" and payload.get("source") not in (
                    "usage",
                    "thinking",
                ):
                    continue
                if key not in headers:
                    if len(headers) >= 10000:
                        partial = True
                        break
                    headers[key] = {
                        "parent": payload.get("parent_item_id"),
                        "label": payload.get("name", payload.get("source", event.kind)),
                        "name": payload.get("name", payload.get("source", event.kind)),
                        "task_title": None,
                        "status": payload.get("status", "observed"),
                    }
                    if headers[key]["parent"] == node:
                        if offset <= count < offset + 100:
                            selected.add(key)
                        count += 1
                header = headers[key]
                if payload.get("status") is not None:
                    header["status"] = payload["status"]
                if payload.get("name") is not None:
                    header["name"] = payload["name"]
                title = activity_task_title(payload)
                if title:
                    header["task_title"] = title
                header["label"] = (
                    f"{header['task_title']} · " if header["task_title"] else ""
                ) + header["name"]
                if key in selected or key == node:
                    index.observe(event)
            partial |= read < info.st_size
        result = index.activity_tree(node)
        # The page is deliberately not a complete in-memory descendant index.
        # Derive counts/breadcrumbs from bounded lightweight observed identities.
        adjacency = {}
        for key, header in headers.items():
            adjacency.setdefault(header["parent"], []).append(key)
        for row in result["rows"] + ([result["focus"]] if result["focus"] else []):
            children = adjacency.get(row["id"], [])
            row["children"] = len(children)
            pending, seen, counts = list(children), set(), {}
            while pending:
                key = pending.pop()
                if key in seen:
                    continue
                seen.add(key)
                status = headers[key]["status"]
                counts[status] = counts.get(status, 0) + 1
                pending.extend(adjacency.get(key, []))
            row["summary"] = " · ".join(
                f"{n} {status}"
                for status, n in counts.items()
                if status
                in ("running", "waiting", "failed", "unknown", "interrupted", "warning", "error")
            )
            row["preview"] = row["preview"].removesuffix(
                "\nOriginating call unavailable; not inferred from timing."
            )
            if row.get("child") and row.get("parent") not in headers:
                row["preview"] += "\nOriginating call unavailable; not inferred from timing."
        trail, seen, cursor = [], set(), node
        while cursor in headers and cursor not in seen:
            seen.add(cursor)
            trail.append(headers[cursor]["label"])
            cursor = headers[cursor]["parent"]
        returned = len(result["rows"])
        result.update(
            breadcrumb=" / ".join(reversed(trail)),
            partial=partial,
            offset=offset,
            next_offset=offset + returned if offset + returned < count and returned else None,
            _journal_version=journal_version,
            scope="Read-only saved activity · 100 siblings per page / 1 MiB; detail excerpts up to 16 KiB. "
            "No model request or tool replay. Scan limits: 64 MiB, 10,000 identities, 2 seconds; "
            "limits are disclosed. Full events remain in the private journal; Export includes usage.",
        )
        return result

    def catalog(self, host, category, child=None):
        if category == "activity_tree":
            return self.activity_tree(child)
        if category == "recipe_files":
            return recipe_files(host)
        if category == "cli_sessions":
            from .cli_compat import session_catalog

            launch = host.store.metadata["launch"] if host.store else {}
            if launch.get("settings_policy") != "cli":
                return {
                    "rows": [],
                    "partial": False,
                    "scope": "Launch with --settings-policy cli to browse that configured home's CLI sessions. Isolated mode does not inspect shared history.",
                }
            try:
                return session_catalog(launch["cli_home"], launch["cwd"])
            except (OSError, ValueError):
                return {
                    "rows": [],
                    "partial": True,
                    "scope": "CLI history unavailable or unsafe to read; check the selected home's permissions. No transcript imported.",
                }
        if category == "recovery":
            from .recovery import recovery_catalog

            return recovery_catalog(host.store)
        rows = list(reversed(self.rows.values()))
        if category == "children":
            rows = [r for r in rows if r["id"].startswith("child:") and r["kind"] == "tool.updated"]
        elif category == "context":
            rows = [r for r in rows if r["kind"] == "context.observed"]
            delivery = forwarding_observations(host)
            rows.append(
                {
                    "id": "intelligence-forwarding",
                    "label": "Intelligence forwarding · observed diagnostics",
                    "kind": "context.observed",
                    "child": None,
                    "source": host.session_id,
                    "status": delivery["status"],
                    "detail": json.dumps(delivery, indent=2),
                    "partial": delivery["partial"],
                }
            )
            # Public configuration is not runtime occupancy. Never invoke context
            # preparation/compaction or read a module's private meter to paint this.
            section = (host.session.config or {}).get("session", {}).get("context", {})
            config = section.get("config", {})
            policy = {"module": section.get("module"), "configured": {}}
            for key in ("max_tokens", "compact_threshold", "target_usage", "token_meter"):
                value = config.get(key)
                if key == "token_meter":
                    if value in ("actual", "estimate"):
                        policy["configured"][key] = value
                elif type(value) in (int, float) and 0 <= value <= 2**63 - 1:
                    policy["configured"][key] = value
            policy["notice"] = (
                "Explicit configuration only; omitted values use module-owned defaults. "
                "max_tokens is a configured fallback, not the selected model's effective "
                "request budget. Completed-request usage below is historical, not current "
                "occupancy or remaining capacity. No request built or private state read."
            )
            rows.insert(
                0,
                {
                    "id": "context-policy",
                    "label": "Context budget policy · configured limits",
                    "kind": "context.observed",
                    "child": None,
                    "source": host.session_id,
                    "status": "configuration, not occupancy",
                    "detail": json.dumps(policy, indent=2),
                    "partial": False,
                },
            )
        elif category == "changes":
            rows = [r for r in rows if r["kind"] == "change.observed"]
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

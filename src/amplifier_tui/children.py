"""App-owned child sessions over public Foundation composition/session APIs."""

import asyncio
import copy
import fcntl
import hashlib
import json
import os
import re
import stat
import time
import unicodedata
import uuid
from collections import defaultdict, deque
from contextvars import ContextVar
from dataclasses import replace
from pathlib import Path

from amplifier_core import HookResult, ToolResult
from amplifier_foundation import Bundle, ProviderPreference

from .composition import TERMINAL_HOOKS, expand_environment, provider_instances
from .conversations import atomic_json, portable_history

# Observation scope travels with the actual async tool task (including recipe
# tasks it creates). Never use a process-global "last tool" for parallel work.
_activity_call = ContextVar("tui_activity_call", default=None)


def parent_call(session):
    current = _activity_call.get()
    return current[1] if current and current[0] == session else None


def task_title(instruction):
    """Extract a bounded display label; never rewrite or summarize execution intent.

    Explicit heading wins. Otherwise peel only conventional *leading* boilerplate
    from an opening clause. Negation and task content stay intact. This is not a
    semantic model summary, a policy claim, or a reason to inspect child context.
    """
    # Foundation's delegate prepends inherited history, then the explicit task.
    # Locate the outer/final delimiter before clipping: the history can be much
    # longer than the title excerpt and contain old task headings/wrappers itself.
    # Scan only a bounded suffix, once per run; never relabel history as a task
    # when the boundary is unavailable. This never changes the execution string.
    if instruction[:128].lstrip().startswith("[PARENT CONVERSATION CONTEXT]"):
        boundary = "\n[END PARENT CONTEXT]\n\n[YOUR TASK]\n"
        offset = instruction.rfind(boundary, max(0, len(instruction) - 262144))
        text = (
            instruction[offset + len(boundary) : offset + len(boundary) + 4096]
            if offset >= 0
            else ""
        )
    else:
        text = instruction[:4096]
    text = re.sub(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)", "", text)
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
    text = "".join(c for c in text if c in "\n\t" or unicodedata.category(c) not in ("Cc", "Cf"))
    lines = [line.strip().strip("#* ") for line in text.splitlines()[:16] if line.strip()]
    source, title = "instruction excerpt", ""
    for index, line in enumerate(lines):
        heading = re.match(
            r"(?i)^(?:task(?: title)?|title|objective|goal)(?:\s*[*:—-]+\s*(.*)|\s*)$", line
        )
        if heading:
            title = (heading[1] or "").strip("* ") or (
                lines[index + 1] if index + 1 < len(lines) else ""
            )
            source = "instruction heading"
            break
    if not title:
        candidates = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
        # Skip only standalone role/location framing when another clause exists.
        while len(candidates) > 1 and re.match(
            r"(?i)^\s*(?:you are\b|(?:working directory|cwd|role)\s*:)", candidates[0]
        ):
            candidates.pop(0)
        title = candidates[0] if candidates else ""
        prefix = r"(?i)^(?:please\b|(?:perform|conduct|carry out)\b|do (?=an?\b|one\b)|(?:a|an|one)\b|(?:read[- ]only|bounded|targeted|independent|brief|small|careful)\b)[\s,:-]*"
        title = " ".join(title.split()).strip("#* ")
        for _ in range(12):
            shortened = re.sub(prefix, "", title, count=1)
            if shortened == title:
                break
            title = shortened
    title = " ".join(title.replace("`", "").replace("**", "").split()).strip(" .:;#*")
    words = title.split()
    clipped = " ".join(words[:8])
    if len(clipped) > 64:
        clipped = clipped[:64].rsplit(" ", 1)[0] if " " in clipped[:64] else clipped[:64]
    if not clipped:
        return {"task_title": "Delegated task", "task_title_source": "unavailable"}
    return {
        "task_title": (
            clipped if re.match(r"\S*[/\\.]", clipped) else clipped[0].upper() + clipped[1:]
        )
        + ("…" if clipped != title else ""),
        "task_title_source": source,
    }


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def parent_orchestrator(session):
    section = (session.config or {}).get("session", {}).get("orchestrator", {})
    return section.get("config", {}) if isinstance(section, dict) else {}


def recovery_fingerprint(plan):
    """Only the app-owned persistent transcript location may move on adoption."""
    value = copy.deepcopy(plan)
    context = value.get("session", {}).get("context", {})
    if context.get("module") == "context-persistent":
        context.setdefault("config", {})["transcript_path"] = "<new isolated child store>"
    return fingerprint(value)


async def child_routing(plan, preferences, roles, coordinator):
    """Reuse pinned CLI promotion/diagnostics without copying its session lifecycle."""
    from amplifier_app_cli.session_spawner import (
        _apply_provider_preferences,
        _coerce_provider_preferences,
        _normalize_model_role,
        _preference_failure,
    )

    plan = copy.deepcopy(plan)
    if roles and not (
        isinstance(roles, str)
        or isinstance(roles, list)
        and all(isinstance(role, str) for role in roles)
    ):
        raise ValueError("Child model_role must be a string or list of strings")
    roles = _normalize_model_role(roles)
    requested = bool(preferences)
    preferences = _coerce_provider_preferences(preferences)
    plan.pop("model_role", None)
    plan.pop("provider_preferences", None)
    if roles:
        plan["model_role"] = roles
    fallback = "invalid_provider_preferences" if requested and not preferences else None
    if preferences:
        plan["provider_preferences"] = [p.to_dict() for p in preferences]
        plan, diagnostics = await _apply_provider_preferences(plan, preferences, coordinator)
        failure = _preference_failure(diagnostics, plan.get("providers", []), preferences)
        if failure:
            fallback = failure["reason"]
    return plan, [p.to_dict() for p in preferences], roles, fallback


def child_resumable(row):
    return (row.get("status") == "completed" and not row.get("execution_uncertain")) or (
        row.get("status") == "interrupted"
        and row.get("resumable") is True
        and not row.get("execution_uncertain")
    )


def routing_checkpoint(row):
    """Detect inconsistent saved continuation fields; not local-file authentication."""
    keys = ("policy_fingerprint", "mount_fingerprint", "routing", "model_role")
    # Early routing receipts predate independent parent/child mode tracking.
    if "parent_mode" in row:
        keys += ("mode", "parent_mode")
    if "use_subprocess" in row:
        keys += ("use_subprocess",)
    return fingerprint({key: row.get(key) for key in keys})


class ChildDisplay:
    def __init__(self, owner, identity):
        self.owner, self.identity = owner, identity
        self.store = None
        self.session = None
        self.local_commands = None  # Root-local controls are not child mode policy.

    @property
    def _stop_requested(self):
        return self.owner.host._stop_requested

    @property
    def ready(self):
        return self.owner.host.ready

    @ready.setter
    def ready(self, value):
        if not value:
            self.owner.host.ready = False

    def emit(self, kind, identity, **payload):
        self.owner.host.emit(kind, f"child:{self.identity}:{identity}", **payload)

    async def request_approval(self, prompt, options, timeout, default):
        self.owner.publish(self.identity, "waiting_permission")
        try:
            return await self.owner.host.request_approval(
                f"{prompt}\nAgent: {self.owner.label(self.identity)} ({self.identity})",
                options,
                timeout,
                default,
            )
        finally:
            self.owner.publish(self.identity, "running")

    def show_message(self, message, level="info", source="hook", **kwargs):
        row = self.owner.records[self.identity]
        level = level if level in ("info", "warning", "error") else "info"
        source = str(source)[:160]
        # The display proxy knows its owner even during mounting, when there is
        # no child session/dispatch yet. Never infer ownership from a short ID.
        self.owner.host.emit(
            "activity.observed",
            f"activity:{self.identity}:{row['activity_run']}:notice:{uuid.uuid4().hex}",
            child_id=self.identity,
            parent_item_id=parent_call(self.identity) or f"child:{self.identity}",
            name=f"{source} · {level}",
            agent=self.owner.label(self.identity),
            event="display.message",
            source=source,
            level=level,
            status=level if level != "info" else "observed",
            block={"type": "text", "text": str(message)},
        )
        if level in ("warning", "error"):
            row["notices"][level] = row["notices"].get(level, 0) + 1
        self.owner.progress(self.identity, f"{source} · {message}")


class Children:
    """Owned child work with per-parent admission and bounded hot context payloads.

    Completed children can resume explicitly when their active parent, composition
    and mode reconstruct exactly. Receipts never authorize automatic execution.
    """

    def __init__(self, host, prepared, cwd):
        self.host, self.prepared, self.cwd = host, prepared, cwd
        self.records, self.active, self.parents = {}, {}, {host.session_id: (prepared, 0)}
        self.initializing = asyncio.Lock()
        self.tasks = {}
        self.restoring = {}
        self.recovering = {}
        self.tool_outcomes = {}
        self.running_tools = {}
        self.branches = defaultdict(dict)
        self.calls = defaultdict(dict)
        self.completed = deque()
        try:
            self.capacity = int(os.environ.get("AMPLIFIER_TUI_CHILD_CONCURRENCY", "8"))
        except ValueError as exc:
            raise ValueError("AMPLIFIER_TUI_CHILD_CONCURRENCY must be between 1 and 64") from exc
        if not 1 <= self.capacity <= 64:
            raise ValueError("AMPLIFIER_TUI_CHILD_CONCURRENCY must be between 1 and 64")
        self.slots = {}
        self.waiting = set()

    def register(self, session):
        session.coordinator.register_capability("session.spawn", self.spawn)
        session.coordinator.register_capability("session.resume", self.resume)
        session.coordinator.register_capability(
            "session.spawn_limits",
            {
                "concurrent_per_parent": self.capacity,
                "hot_completed_contexts": 32,
                "depth": "delegate module policy",
            },
        )
        # Rust hook callbacks can run in a different Python task: a ContextVar
        # set in tool:pre does NOT propagate back to execute. Establish scope at
        # the actual invocation, using the loop's task-keyed dispatch observation.
        # Keep the original tool instance/schema/config and all execution policy.
        for tool in (session.coordinator.get("tools") or {}).values():
            original = tool.execute
            if getattr(original, "_tui_activity_owner", None) is self:
                continue
            owner = getattr(original, "__self__", None)
            class_bound = owner is not None and getattr(original, "__func__", None) is getattr(
                type(owner), "execute", None
            )

            async def execute(*args, _original=original, _class_bound=class_bound, **kwargs):
                contexts = getattr(session.coordinator, "_tool_dispatch_contexts", {})
                dispatch = (
                    contexts.get(asyncio.current_task(), {}) if isinstance(contexts, dict) else {}
                )
                dispatch = dispatch if isinstance(dispatch, dict) else {}
                call = dispatch.get("tool_call_id")
                scope = None
                if isinstance(call, str) and call:
                    identity = session.session_id
                    item = (
                        f"{self.host.turn_id}:tool:{call}"
                        if identity == self.host.session_id
                        else self.activity_id(identity, call)
                    )
                    scope = (identity, item)
                token = _activity_call.set(scope)
                try:
                    # Preserve a module's replacement of its class method too;
                    # observing dispatch must not freeze a stale implementation.
                    owner = getattr(_original, "__self__", None)
                    # An instance-bound guard is not the class method: never
                    # bypass it when resolving a later class implementation.
                    implementation = getattr(type(owner), "execute", None) if _class_bound else None
                    call = implementation.__get__(owner) if implementation else _original
                    # A model request already in flight may return new tool
                    # calls after Stop. Pair those calls with explicit skipped
                    # results, but never begin their effects. Calls already
                    # entered keep running until they return (or force Stop).
                    if session.coordinator.cancellation.is_cancelled:
                        result = ToolResult(
                            success=False,
                            error={"message": "Stopped before execution", "cancelled": True},
                        )
                    else:
                        result = await call(*args, **kwargs)
                    if scope:
                        from .events import tool_status

                        # Retain only the outcome, never pre-policy output. Hooks
                        # may redact/truncate the returned envelope afterwards.
                        self.tool_outcomes[scope[1]] = tool_status("tool:post", result)
                        while len(self.tool_outcomes) > 1024:
                            self.tool_outcomes.pop(next(iter(self.tool_outcomes)))
                    return result
                finally:
                    _activity_call.reset(token)

            execute._tui_activity_owner = self
            try:
                tool.execute = execute
            except (AttributeError, TypeError):
                # A foreign immutable tool remains usable, but uncorrelated.
                pass

    def observed_outcome(self, call_id, event, status):
        if event == "tool:pre":
            self.tool_outcomes.pop(call_id, None)
        if event not in ("tool:post", "tool:error"):
            return status, "event"
        invoked = self.tool_outcomes.pop(call_id, "unknown")
        if status == "unknown" and invoked in ("succeeded", "failed"):
            return invoked, "invocation; processed result envelope unavailable"
        return status, "event"

    def publish(self, identity, status, output=""):
        row = self.records[identity]
        row["activity_status"] = status
        self.host.emit(
            "tool.updated",
            f"child:{identity}",
            name=self.label(identity)
            if row.get("metadata", {}).get("is_forked_skill_session")
            else f"Agent · {self.label(identity)}",
            child_id=identity,
            parent_item_id=row.get("parent_item_id"),
            recipe_step=row.get("metadata", {}).get("recipe_step"),
            task_title=row.get("task_title"),
            task_title_source=row.get("task_title_source"),
            status=status,
            arguments={"instruction": row["instruction"]},
            result={
                "output": output,
                "session_id": identity,
                "parent_id": row["parent"],
                "tools": row.get("tools", []),
                "hooks": row.get("hooks", []),
                "continuation": "Explicit continuation validates canonical state, parent and non-routing policy. Uncertain work refuses. Restored rows are not live sessions.",
            },
        )
        activity = output if status == "running" else status
        self.progress(identity, activity or "Starting agent")

    def label(self, identity):
        row = self.records[identity]
        if row.get("label"):
            return row["label"]
        metadata = row.get("metadata", {})
        name = row["agent"]
        if metadata.get("is_forked_skill_session") and isinstance(metadata.get("skill_name"), str):
            name = f"Skill · {' '.join(metadata['skill_name'].split())[:120]}"
        row["label"] = f"{name} #{list(self.records).index(identity) + 1}"
        return row["label"]

    def activity_id(self, identity, call):
        row = self.records[identity]
        # Provider call IDs and optional request counters can restart on resume.
        return f"activity:{identity}:{row['activity_run']}:{row['request_index']}:{call}"

    def summary(self, identity):
        from amplifier_foundation import sum_cost_usd

        row = self.records[identity]
        subtree, pending = [], [identity]
        while pending:
            key = pending.pop()
            subtree.append(self.records[key])
            pending.extend(
                k
                for k in self.branches[key]
                if self.records[k].get("parent_activity_run")
                == self.records[key].get("activity_run")
            )
        usages = [r.get("usage", {}) for r in subtree]
        costs = [u["totals"] for u in usages if "cost_usd" in u.get("totals", {})]
        calls = sum(u.get("requests", 0) for u in usages)
        cost = sum_cost_usd(costs) if costs else None
        return {
            "child_id": identity,
            "agent": self.label(identity),
            "task_title": row.get("task_title"),
            "task_title_source": row.get("task_title_source"),
            "status": row.get("activity_status", "running"),
            "activity": row.get("activity", "Starting"),
            "calls": calls,
            "cost_usd": str(cost) if cost is not None else None,
            "cost_display": f"${cost:.2f}" if cost is not None else None,
            "cost_partial": sum(u.get("reported", {}).get("cost_usd", 0) for u in usages) != calls,
            "tools_completed": sum(r.get("tools_completed", 0) for r in subtree),
            "warnings": {
                status: sum(r.get("warnings", {}).get(status, 0) for r in subtree)
                for status in ("failed", "unknown", "interrupted")
            },
            "notices": {
                level: sum(r.get("notices", {}).get(level, 0) for r in subtree)
                for level in ("warning", "error")
            },
            "last_warning": row.get("last_warning"),
            "elapsed_seconds": row.get("elapsed_seconds"),
        }

    @staticmethod
    def progress_payload(summaries):
        """Keep compact delegate cost display exact and owned by the host."""
        from amplifier_foundation import sum_cost_usd

        costs = [
            {"cost_usd": summary["cost_usd"]}
            for summary in summaries
            if summary.get("cost_usd") is not None
        ]
        total = sum_cost_usd(costs) if costs else None
        terminal = ("succeeded", "completed", "failed", "interrupted")
        live = [s for s in summaries if s.get("status") not in terminal]
        finished = [s for s in summaries if s.get("status") in terminal]
        # Keep live work visible even when an older long-running child is
        # followed by many short completions. Accounting still covers all rows.
        keep = live[:64] + finished[-(32 - len(live)) :] if len(live) < 32 else live[:64]
        selected_ids = {id(s) for s in keep}
        selected = [s for s in summaries if id(s) in selected_ids]
        return {
            "child_progress": selected,
            "child_progress_omitted": len(summaries) - len(selected),
            "child_count": len(summaries),
            "child_calls": sum(s.get("calls", 0) for s in summaries),
            "child_totals": {
                key: {
                    status: sum(s.get(key, {}).get(status, 0) for s in summaries)
                    for status in states
                }
                for key, states in (
                    ("warnings", ("failed", "unknown", "interrupted")),
                    ("notices", ("warning", "error")),
                )
            },
            "child_cost_usd": str(total) if total is not None else None,
            "child_cost_display": f"${total:.2f}" if total is not None else None,
            "child_cost_partial": bool(summaries)
            and (
                len(costs) != len(summaries)
                or any(summary.get("cost_partial") for summary in summaries)
            ),
        }

    def progress(self, identity, activity):
        row = self.records[identity]
        row["activity"] = " ".join(str(activity).split())[:240]
        if row.get("activity_started") is not None:
            row["elapsed_seconds"] = round(time.monotonic() - row["activity_started"], 1)
        self.host.emit(
            "tool.progress",
            f"child:{identity}",
            **self.progress_payload([self.summary(identity)]),
        )
        parent = row.get("parent_item_id")
        if not parent:
            return
        owner = self.records.get(row.get("parent"))
        if owner and row.get("parent_activity_run") != owner.get("activity_run"):
            return  # A late old child cannot repaint its parent's new execution.
        # Update the exact calling tool without replacing its args, result or outcome.
        siblings = [
            self.summary(key)
            for key in self.calls[(row["parent"], parent)]
            if self.records[key].get("parent_activity_run") == row.get("parent_activity_run")
        ]
        self.host.emit(
            "tool.progress" if row["parent"] == self.host.session_id else "activity.progress",
            parent,
            **self.progress_payload(siblings),
        )
        if owner and row["parent"] != identity:
            self.progress(row["parent"], f"{row['agent']} · {row['activity']}")

    async def spawn(
        self,
        agent_name,
        instruction,
        parent_session,
        agent_configs,
        sub_session_id=None,
        tool_inheritance=None,
        hook_inheritance=None,
        orchestrator_config=None,
        parent_messages=None,
        provider_preferences=None,
        self_delegation_depth=0,
        session_metadata=None,
        use_subprocess=False,
        model_role=None,
    ):
        if type(use_subprocess) is not bool:
            raise ValueError("use_subprocess must be a boolean")
        if orchestrator_config is not None:
            if not isinstance(orchestrator_config, dict):
                raise ValueError("Child orchestrator configuration must be a JSON object")
            try:
                encoded = json.dumps(orchestrator_config, allow_nan=False)
            except (ValueError, TypeError) as exc:
                raise ValueError(
                    "Child orchestrator configuration must be JSON-compatible"
                ) from exc
            if len(encoded.encode()) > 65536:
                raise ValueError("Child orchestrator configuration exceeds 64 KiB")
            orchestrator_config = json.loads(encoded)
        parent_id = parent_session.session_id
        if parent_id not in self.parents or self.host._stop_requested or not self.host.ready:
            raise ValueError("Child request has no active parent in this conversation")
        base, depth = self.parents[parent_id]
        controls = getattr(self.host, "local_commands", None)
        if (
            controls
            and parent_id == self.host.session_id
            and agent_name in controls.configuration.snapshot()["disabled"]["agents"]
        ):
            raise ValueError("Agent definition disabled in the parent session")
        if type(self_delegation_depth) is not int or self_delegation_depth < 0:
            raise ValueError("Self-delegation depth must be a nonnegative integer")
        if not isinstance(instruction, str) or not 0 < len(instruction) <= 262144:
            raise ValueError("Child instruction must contain 1–262144 characters")
        config = agent_configs.get(agent_name) if agent_name != "self" else {}
        if not isinstance(config, dict):
            raise ValueError(f"Unknown or unresolved agent: {agent_name}")
        config = copy.deepcopy(config)
        use_subprocess = use_subprocess or config.get("spawn_mode") == "subprocess"
        overlay = Bundle(
            name=agent_name,
            version="1.0.0",
            session=config.get("session", {}),
            providers=config.get("providers", []),
            tools=config.get("tools", []),
            hooks=config.get("hooks", []),
            context=config.get("context", {}),
            instruction=config.get("instruction")
            or (config.get("system") or {}).get("instruction"),
        )
        effective = provider_instances(base.bundle.compose(overlay))
        # Exclusions apply to the effective child, including explicitly declared tools.
        for section, policy in (("tools", tool_inheritance), ("hooks", hook_inheritance)):
            policy = policy or {}
            if set(policy) - {f"inherit_{section}", f"exclude_{section}"}:
                raise ValueError(f"Unknown {section} inheritance policy")
            allowed = policy.get(f"inherit_{section}")
            excluded = set(policy.get(f"exclude_{section}", []))
            entries = getattr(effective, section)
            setattr(
                effective,
                section,
                [
                    e
                    for e in entries
                    if e["module"] not in excluded and (allowed is None or e["module"] in allowed)
                ],
            )
        effective.hooks = [h for h in effective.hooks if h["module"] not in TERMINAL_HOOKS]
        # Agent overlays cannot redirect the app's local capture/recipe storage.
        guarded = {
            "hooks-logging": ("session_log_template", "strip_raw"),
            "hook-context-intelligence": (
                "base_path",
                "context_intelligence_server_url",
                "context_intelligence_api_key",
                "destinations",
            ),
            "tool-recipes": ("session_dir",),
        }
        if self.host.report.get("settings_policy") == "cli":
            guarded = {}  # Declared root/agent storage policy belongs to the configured modules.
        originals = {
            e["module"]: e for e in self.prepared.bundle.hooks + self.prepared.bundle.tools
        }
        for entry in effective.hooks + effective.tools:
            if entry["module"] in guarded:
                original = originals.get(entry["module"], {}).get("config", {})
                for key in guarded[entry["module"]]:
                    if key not in original:
                        raise ValueError("Child storage module lacks an app-local policy")
                    entry.setdefault("config", {})[key] = copy.deepcopy(original[key])
        plan = effective.to_mount_plan()
        for section in ("providers", "tools", "hooks"):
            for entry in plan.get(section, []):
                entry["config"] = expand_environment(
                    entry.get("config", {}), required=section == "providers"
                )
        if orchestrator_config:
            plan.setdefault("session", {}).setdefault("orchestrator", {}).setdefault(
                "config", {}
            ).update(orchestrator_config)
        identity = sub_session_id or uuid.uuid4().hex
        if (
            not isinstance(identity, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", identity)
            or (identity in self.records and identity not in self.restoring)
        ):
            raise ValueError("Invalid or already used child identity")
        context_plan = plan.get("session", {}).get("context", {})
        if context_plan.get("module") == "context-persistent":
            if not self.host.store:
                raise ValueError("Persistent child context requires isolated conversation storage")
            directory = self.host.store.path / "child-context" / identity
            context_plan.setdefault("config", {})["transcript_path"] = str(
                directory / "messages.jsonl"
            )
        routing_base = copy.deepcopy(plan)
        plan, routing, roles, fallback = await child_routing(
            plan,
            provider_preferences or config.get("provider_preferences"),
            model_role or config.get("model_role"),
            parent_session.coordinator,
        )
        prepared = replace(base, bundle=effective, mount_plan=plan)
        recovery = self.recovering.get(identity)
        if recovery:
            section = plan.get("session", {})
            legacy_plan = copy.deepcopy(plan)
            if context_plan.get("module") == "context-persistent":
                # Older receipts hashed the original app-owned storage path. Verify
                # that exact policy at its original location, never ignore the hash.
                legacy_plan["session"]["context"]["config"]["transcript_path"] = recovery[
                    "legacy_transcript_path"
                ]
            if (
                section.get("context", {}).get("module")
                not in ("context-simple", "context-persistent")
                or section.get("orchestrator", {}).get("module")
                not in ("loop-streaming", "loop-basic")
                or (
                    recovery_fingerprint(plan) != recovery["recovery_fingerprint"]
                    if recovery.get("recovery_fingerprint")
                    else fingerprint(legacy_plan) != recovery["mount_fingerprint"]
                )
            ):
                raise ValueError(
                    "Child public-context recovery requires unchanged supported context and stateless loop policy; private-state reconstruction refused"
                )
            if context_plan.get("module") == "context-persistent" and directory.exists():
                raise ValueError("Recovery requires a fresh persistent child store")
        restored = self.restoring.get(identity)
        if restored:
            if restored.get("policy_fingerprint") and restored.get("routing_checkpoint"):
                compatible = fingerprint(routing_base) == restored["policy_fingerprint"]
            else:
                # Legacy receipts prove their original routed plan first. Never
                # strip provider fields out of an old fingerprint to accept a change.
                old_plan, _, _, _ = await child_routing(
                    routing_base,
                    restored.get("routing"),
                    restored.get("model_role"),
                    parent_session.coordinator,
                )
                compatible = fingerprint(old_plan) == restored.get("mount_fingerprint")
            if not compatible:
                raise ValueError("Child effective composition changed; continuation refused")
        if (
            self.host.store
            and (self.host.store.path / "children" / f"{identity}.json").exists()
            and not restored
        ):
            raise ValueError("Child identity already exists on disk; use explicit continuation")
        if context_plan.get("module") == "context-persistent":
            directory.mkdir(mode=0o700, parents=True, exist_ok=not bool(recovery))
        rollback = (
            dict(self.records.get(identity) or {**(restored or {}), "archived": True})
            if restored
            else None
        )
        self.records[identity] = {
            **(restored or {}),
            "agent": agent_name,
            "parent": parent_id,
            "parent_item_id": parent_call(parent_id),
            "parent_activity_run": self.records.get(parent_id, {}).get("activity_run"),
            "instruction": instruction,
            "prepared": prepared,
            "depth": depth + 1,
            "self_depth": self_delegation_depth,
            "label": restored.get("label") if restored else None,
            "messages": parent_messages or [],
            "status": restored["status"] if restored else "new",
            "metadata": session_metadata or {},
            "use_subprocess": use_subprocess,
            "mode": restored.get("mode")
            if restored
            else parent_session.coordinator.session_state.get("active_mode"),
            "parent_mode": restored.get("parent_mode", restored.get("mode"))
            if restored
            else parent_session.coordinator.session_state.get("active_mode"),
            "routing": routing,
            "model_role": roles,
            "routing_fallback": fallback,
            "_routing_base": routing_base,
            "policy_fingerprint": fingerprint(routing_base),
            "request_index": 0,
            "mount_fingerprint": fingerprint(plan),
            "recovery_fingerprint": recovery_fingerprint(plan),
            "root_fingerprint": self.host.fingerprint,
            "restart_policy": {
                "tools": tool_inheritance,
                "hooks": hook_inheritance,
                "orchestrator": (
                    "parent"
                    if orchestrator_config == parent_orchestrator(parent_session)
                    else copy.deepcopy(orchestrator_config)
                )
                if orchestrator_config
                else None,
            },
        }
        self.branches[parent_id][identity] = None
        self.calls[(parent_id, self.records[identity]["parent_item_id"])][identity] = None
        return await self.execute(identity, instruction, parent_session, rollback=rollback)

    def recovery_operation(self, source, identity, digest, instruction):
        """Validate immutable capture before returning a new, explicitly owned turn."""
        from .recovery import public_history

        store = self.host.store
        allowed = {self.host.session_id, store.metadata.get("recovered_from")} if store else set()
        if (
            source not in allowed
            or not isinstance(source, str)
            or not re.fullmatch(r"[a-f0-9]{32}", source)
        ):
            raise ValueError("Child source is outside this conversation's recovery lineage")
        if not isinstance(identity, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", identity):
            raise ValueError("Invalid child identity")
        if not isinstance(instruction, str) or not 0 < len(instruction.strip()) <= 262144:
            raise ValueError("A new explicit child instruction is required")
        directory = store.path.parent / source
        lock = None
        try:
            if source != self.host.session_id:
                lock = os.open(directory / "lock", os.O_RDONLY | os.O_NOFOLLOW)
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            parent_fd = os.open(
                directory / "children", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
            )
            try:

                def read_receipt(child):
                    if not isinstance(child, str) or not re.fullmatch(
                        r"[A-Za-z0-9_-]{1,160}", child
                    ):
                        raise ValueError("Invalid child ancestry identity")
                    fd = os.open(
                        f"{child}.json",
                        os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                        dir_fd=parent_fd,
                    )
                    with os.fdopen(fd, "rb") as stream:
                        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                            raise ValueError("Child receipt is not a regular file")
                        data = stream.read(1024 * 1024 + 1)
                    if len(data) > 1024 * 1024:
                        raise ValueError("Child ancestry receipt exceeds 1 MiB")
                    value = json.loads(data)
                    if (
                        not isinstance(value, dict)
                        or value.get("root_fingerprint") != self.host.fingerprint
                    ):
                        raise ValueError("Child ancestry composition changed")
                    return data, value

                raw, row = read_receipt(identity)
                ancestor, seen, ancestry = row.get("parent"), {identity}, []
                while ancestor != source:
                    if ancestor in seen or len(ancestry) >= 2 or self.active:
                        raise ValueError("Child ancestry is cyclic, too deep or still active")
                    seen.add(ancestor)
                    ancestor_raw, ancestor_row = read_receipt(ancestor)
                    ancestry.append(
                        {"id": ancestor, "sha256": hashlib.sha256(ancestor_raw).hexdigest()}
                    )
                    ancestor = ancestor_row.get("parent")
            finally:
                os.close(parent_fd)
        finally:
            if lock is not None:
                os.close(lock)
        if len(raw) > 1024 * 1024 or hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("Child evidence changed or exceeds 1 MiB; inspect again")
        row = json.loads(raw)
        if not isinstance(row, dict):
            raise ValueError("Invalid child receipt")
        if (
            row.get("status") not in ("interrupted", "failed", "running")
            or identity in self.active
            or row.get("root_fingerprint") != self.host.fingerprint
        ):
            raise ValueError(
                "Only an inactive captured child with unchanged composition can be adopted"
            )
        parent = self.host.session
        if row.get("mode") != parent.coordinator.session_state.get("active_mode"):
            raise ValueError("Child mode differs; restore the original mode first")
        policy = row.get("restart_policy")
        if not isinstance(policy, dict) or set(policy) != {"tools", "hooks", "orchestrator"}:
            raise ValueError("Unsupported child restart policy")
        messages, unknown = public_history(row.get("messages"), repair=True)
        preferences = [ProviderPreference.from_dict(p) for p in row.get("routing", [])]
        new_id = uuid.uuid4().hex

        async def run():
            self.recovering[new_id] = {
                **row,
                "legacy_transcript_path": str(
                    directory / "child-context" / identity / "messages.jsonl"
                ),
            }
            try:
                result = await self.spawn(
                    row["agent"],
                    instruction,
                    parent,
                    self.prepared.bundle.agents,
                    sub_session_id=new_id,
                    parent_messages=messages,
                    tool_inheritance=policy["tools"],
                    hook_inheritance=policy["hooks"],
                    orchestrator_config=parent_orchestrator(parent)
                    if policy["orchestrator"] == "parent"
                    else policy["orchestrator"],
                    provider_preferences=preferences or None,
                    model_role=row.get("model_role"),
                    session_metadata={
                        "recovery": {
                            "source_session": source,
                            "child": identity,
                            "sha256": digest,
                            "unknown_tool_calls": unknown,
                            "original_parent": row["parent"],
                            "ancestry": ancestry,
                            "reparented": row["parent"] != source,
                            "notice": "New identity and instruction; public messages only, no tool replay or private-state reconstruction",
                        }
                    },
                )
                return f"Recovered child {identity} continued as {result['session_id']}.\n{result['output']}"
            finally:
                self.recovering.pop(new_id, None)

        return run

    async def resume(self, sub_session_id, instruction, provider_preferences=None, model_role=None):
        if not isinstance(instruction, str) or not 0 < len(instruction) <= 262144:
            raise ValueError("Child instruction must contain 1–262144 characters")
        row = self.records.get(sub_session_id)
        if row and row.get("archived"):
            return await self.restore(sub_session_id, instruction, provider_preferences, model_role)
        if row is None and self.host.store:
            return await self.restore(sub_session_id, instruction, provider_preferences, model_role)
        if not row or not child_resumable(row) or sub_session_id in self.active:
            raise ValueError("Child is unavailable, active or incomplete; no work replayed")
        parent = (
            self.host.session
            if row["parent"] == self.host.session_id
            else self.active.get(row["parent"])
        )
        if parent is None or self.host._stop_requested or not self.host.ready:
            raise ValueError("Child parent no longer active")
        if row.get("parent_mode", row.get("mode")) != parent.coordinator.session_state.get(
            "active_mode"
        ):
            raise ValueError("Inherited child mode changed; create a new delegation")
        if row["status"] == "interrupted":
            from .recovery import public_history

            public_history(row["messages"])  # Validate again; never synthesize outcomes.
        updates = None
        if provider_preferences or model_role or row.get("routing") or row.get("model_role"):
            base = row.get("_routing_base")
            if base is None:
                raise ValueError("Child routing baseline unavailable; restore its saved receipt")
            if fingerprint(base) != row.get("policy_fingerprint"):
                raise ValueError("Child effective composition changed; continuation refused")
            plan, routing, roles, fallback = await child_routing(
                base,
                provider_preferences or row.get("routing"),
                model_role or row.get("model_role"),
                parent.coordinator,
            )
            updates = {
                "prepared": replace(row["prepared"], mount_plan=plan),
                "routing": routing,
                "model_role": roles,
                "routing_fallback": fallback,
                "mount_fingerprint": fingerprint(plan),
                "recovery_fingerprint": recovery_fingerprint(plan),
            }
        return await self.execute(sub_session_id, instruction, parent, updates=updates)

    async def restore(self, identity, instruction, provider_preferences, model_role):
        if not isinstance(identity, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", identity):
            raise ValueError("Invalid child identity")
        if (
            not self.host.ready
            or self.host._stop_requested
            or identity in self.restoring
            or identity in self.active
        ):
            raise ValueError("Child continuation unavailable while stopping or restoring")
        path = self.host.store.path / "children" / f"{identity}.json"
        try:
            with path.open("rb") as stream:
                raw = stream.read(16 * 1024 * 1024 + 1)
            if len(raw) > 16 * 1024 * 1024:
                raise ValueError("Child receipt exceeds 16 MiB")
            row = json.loads(raw)
        except OSError as exc:
            raise ValueError("Child receipt unavailable; no work replayed") from exc
        if not isinstance(row, dict) or not child_resumable(row):
            raise ValueError("Child is incomplete; no work replayed")
        if row.get("routing_checkpoint") and row["routing_checkpoint"] != routing_checkpoint(row):
            raise ValueError(
                "Child saved continuation metadata is inconsistent; continuation refused"
            )
        parent_id = row.get("parent")
        parent = (
            self.host.session if parent_id == self.host.session_id else self.active.get(parent_id)
        )
        if (
            parent is None
            or parent_id not in self.parents
            or row.get("root_fingerprint") != self.host.fingerprint
        ):
            raise ValueError("Child parent/composition changed; continuation refused")
        policy = row.get("restart_policy")
        if (
            not isinstance(policy, dict)
            or set(policy) != {"tools", "hooks", "orchestrator"}
            or (
                policy["orchestrator"] not in (None, "parent")
                and not isinstance(policy["orchestrator"], dict)
            )
        ):
            raise ValueError("Child restart policy is unsupported; create a new delegation")
        routing = row.get("routing", [])
        if not isinstance(routing, list) or not all(isinstance(p, dict) for p in routing):
            raise ValueError("Invalid child provider routing")
        preferences = provider_preferences or [ProviderPreference.from_dict(p) for p in routing]
        if row.get("parent_mode", row.get("mode")) != parent.coordinator.session_state.get(
            "active_mode"
        ):
            raise ValueError("Inherited child mode changed; create a new delegation")
        if not isinstance(row.get("messages"), list) or not all(
            isinstance(m, dict) for m in row["messages"]
        ):
            raise ValueError("Invalid child canonical context")
        if row["status"] == "interrupted":
            from .recovery import public_history

            public_history(row["messages"])
        self.restoring[identity] = row
        try:
            return await self.spawn(
                row["agent"],
                instruction,
                parent,
                self.parents[parent_id][0].bundle.agents,
                sub_session_id=identity,
                tool_inheritance=policy["tools"],
                hook_inheritance=policy["hooks"],
                orchestrator_config=parent_orchestrator(parent)
                if policy["orchestrator"] == "parent"
                else policy["orchestrator"],
                parent_messages=row["messages"],
                provider_preferences=preferences or None,
                session_metadata=row.get("metadata", {}),
                self_delegation_depth=row.get(
                    "self_depth", row.get("depth", 0) if row["agent"] == "self" else 0
                ),
                model_role=model_role or row.get("model_role"),
                use_subprocess=row.get("use_subprocess", False),
            )
        finally:
            self.restoring.pop(identity, None)

    def save(self, identity):
        if self.host.store:
            self.records[identity]["routing_checkpoint"] = routing_checkpoint(
                self.records[identity]
            )
            directory = self.host.store.path / "children"
            directory.mkdir(mode=0o700, exist_ok=True)
            atomic_json(
                directory / f"{identity}.json",
                {
                    k: v
                    for k, v in self.records[identity].items()
                    if k not in ("prepared", "_routing_base")
                },
            )

    def archive_completed(self):
        """Receipts retain canonical state; resident rows retain only observations."""
        if not self.host.store:
            return  # A deliberately non-durable host cannot promise disk restoration.
        while len(self.completed) > 32:
            identity = self.completed.popleft()
            row = self.records[identity]
            if identity in self.active:
                continue
            # Only after final receipt persistence. Keep ancestry/accounting and
            # exact stable labels; no UI retention policy can reject a new spawn.
            self.label(identity)
            for key in (
                "prepared",
                "_routing_base",
                "messages",
                "instruction",
                "metadata",
                "restart_policy",
                "tools",
                "hooks",
            ):
                row.pop(key, None)
            row["archived"] = True
            self.running_tools.pop(identity, None)

    async def execute(self, identity, instruction, parent, *, updates=None, rollback=None):
        if identity in self.active:
            raise ValueError("Child is already active; no concurrent continuation")
        row = self.records[identity]
        previous_row = rollback or dict(row)
        was_resumable = child_resumable(previous_row)
        row["instruction"] = instruction
        row.update(task_title(instruction))
        previous = (row["parent"], row.get("parent_item_id"))
        self.calls[previous].pop(identity, None)
        row["parent_item_id"] = parent_call(parent.session_id)
        row["parent_activity_run"] = self.records.get(parent.session_id, {}).get("activity_run")
        self.calls[(row["parent"], row["parent_item_id"])][identity] = None
        self.active[identity] = None
        self.tasks[identity] = asyncio.current_task()
        slot = self.slots.setdefault(parent.session_id, asyncio.Semaphore(self.capacity))
        acquired, started = False, False
        try:
            if slot.locked():
                row["status"] = "waiting_capacity"
                self.waiting.add(identity)
                self.publish(identity, "waiting_capacity", "Waiting for agent capacity")
            if self.host._stop_requested or parent.coordinator.cancellation.is_cancelled:
                raise asyncio.CancelledError("Stopped before child admission")
            await slot.acquire()
            acquired = True
            self.waiting.discard(identity)
            if self.host._stop_requested or parent.coordinator.cancellation.is_cancelled:
                raise asyncio.CancelledError("Stopped before child admission")
            if updates:
                row.update(updates)
            started = True
            return await self._execute(identity, instruction, parent)
        except asyncio.CancelledError:
            if not started:
                row["status"] = "interrupted"
                self.publish(
                    identity, "interrupted", "Stopped before child admission; nothing executed"
                )
                try:
                    if not was_resumable:
                        self.save(identity)
                except Exception:
                    self.host.ready = False
                    raise
                if (
                    self.host._stop_requested or parent.coordinator.cancellation.is_graceful
                ) and not (
                    self.host._force_requested or parent.coordinator.cancellation.is_immediate
                ):
                    # Match admitted children: returning a cancelled result lets
                    # gather/delegate join current calls, not abort their parent.
                    return {
                        "session_id": identity,
                        "output": "Stopped before child admission; nothing executed",
                        "metadata": {"status": "cancelled"},
                    }
            raise
        finally:
            if not started and was_resumable:
                row.clear()
                row.update(previous_row)
            self.waiting.discard(identity)
            self.active.pop(identity, None)
            self.tasks.pop(identity, None)
            if acquired:
                slot.release()
            if row.get("status") in ("completed", "interrupted", "failed"):
                if identity in self.completed:
                    self.completed.remove(identity)
                self.completed.append(identity)
                self.archive_completed()

    async def configure_child(self, session, row, proxy):
        """Same app-owned policy in a local session or a fresh worker interpreter."""
        coordinator = session.coordinator
        proxy.session = session
        for point in ("context", "orchestrator", "providers"):
            if not coordinator.get(point):
                raise RuntimeError(f"Child missing {point}")
        self.register(session)
        from .modes import Modes

        modes = Modes(proxy)
        await modes.open()
        self.register(session)
        if row.get("mode"):
            if not modes.supported:
                raise ValueError("Child cannot enforce the inherited active mode")
            result = await modes.apply({"operation": "set", "name": row["mode"]})
            if not result.success or modes.current() != row["mode"]:
                raise ValueError("Child failed to restore inherited mode policy")
        coordinator.register_capability("self_delegation_depth", row["self_depth"])
        if self.host.interactive_questions:

            async def ask(questions, **kwargs):
                self.publish(session.session_id, "waiting_answer")
                try:
                    return await self.host.questions.ask(questions, **kwargs)
                finally:
                    self.publish(session.session_id, "running")

            coordinator.register_capability("user.questions", ask)
        context = coordinator.get("context")
        if row["messages"]:
            await context.set_messages(copy.deepcopy(row["messages"]))
            if portable_history(await context.get_messages()) != portable_history(row["messages"]):
                raise RuntimeError(
                    "Context module did not restore child history; continuation refused"
                )
        row["tools"] = sorted(coordinator.get("tools") or {})
        row["hooks"] = coordinator.hooks.list_handlers()

    async def _execute(self, identity, instruction, parent):
        row = self.records[identity]
        from .inspection import usage_totals

        row.update(
            resumable=False,
            execution_uncertain=False,
            usage=usage_totals(),
            tools_completed=0,
            warnings={},
            notices={},
            last_warning=None,
            activity_started=time.monotonic(),
            activity_run=uuid.uuid4().hex,
            parent_activity_run=self.records.get(parent.session_id, {}).get("activity_run"),
        )
        self.running_tools[identity] = {}
        self.active[identity] = None
        self.tasks[identity] = asyncio.current_task()
        self.publish(identity, "running")
        session, outcome, output = None, {}, ""
        parent_cancellation = parent.coordinator.cancellation
        child_cancellation = None
        try:
            row["status"] = "running"
            # Mark dispatch before effects so an old completed receipt cannot be reused.
            self.save(identity)
            proxy = ChildDisplay(self, identity)
            async with self.initializing:
                from .composition import ProcessSession, create_owned_session

                if row.get("use_subprocess"):
                    session = await ProcessSession.open(self, identity, proxy, parent)
                else:
                    session = await create_owned_session(
                        row["prepared"],
                        session_id=identity,
                        parent_id=row["parent"],
                        session_cwd=Path(self.cwd),
                        approval_system=proxy,
                        display_system=proxy,
                        interactive_approval=self.host.interactive_questions,
                    )
            self.active[identity] = session
            proxy.session = session
            if row.get("routing_fallback"):
                proxy.show_message(
                    f"Requested child routing unresolved ({row['routing_fallback']}); using configured provider priority.",
                    level="warning",
                    source="routing",
                )
            self.parents[identity] = (row["prepared"], row["depth"])
            coordinator = session.coordinator
            child_cancellation = coordinator.cancellation
            # Public kernel tokens propagate both stages recursively, including
            # a child whose initialization finishes after its parent's Stop.
            parent_cancellation.register_child(child_cancellation)
            if not row.get("use_subprocess"):
                await self.configure_child(session, row, proxy)
            context = coordinator.get("context")

            async def observe(event, data):
                if data.get("session_id") in (None, "", identity):
                    call_id = self.activity_id(identity, data.get("tool_call_id", "unknown"))
                    if event.startswith("tool:") and self.host.tool_evidence:
                        evidence = await self.host.tool_evidence.observe(
                            event,
                            data,
                            session=identity,
                            turn=self.host.turn_id,
                            agent=row["agent"],
                        )
                        if evidence:
                            self.host.emit(
                                "change.observed",
                                f"{self.host.turn_id}:change:{identity}:{evidence['tool_call_id']}",
                                child_id=identity,
                                **evidence,
                            )
                    if event == "orchestrator:complete":
                        outcome.update(data)
                    else:
                        from .inspection import bounded, bounded_projection

                        if event == "provider:request":
                            row["request_index"] += 1
                            row["provider"] = {}
                            self.publish(identity, "running", f"Model call {row['request_index']}")
                            return HookResult()
                        if event == "provider:resolve":
                            if data.get("scope") == "conversation":
                                row["provider"] = {
                                    k: data[k]
                                    for k in ("provider", "model", "basis")
                                    if isinstance(data.get(k), str)
                                }
                            return HookResult()
                        if event == "llm:request":
                            self.progress(identity, f"Thinking · {data.get('model', 'model call')}")
                            return HookResult()
                        if event == "llm:response":
                            values = self.host.observe_usage(
                                f"{self.host.turn_id}:usage:{identity}:{self.host.sequence + 1}",
                                data,
                                row.get("provider", {}),
                                agent=self.label(identity),
                                child_id=identity,
                            )
                            if values is not None:
                                from .inspection import add_usage

                                add_usage(row["usage"], values)
                                totals = row["usage"]["totals"]
                                if "cost_usd" in totals:
                                    totals["cost_usd"] = str(totals["cost_usd"])
                                self.progress(identity, row.get("activity", "Working"))
                            return HookResult()
                        observed = {
                            k: data[k]
                            for k in (
                                "tool_name",
                                "tool_call_id",
                                "tool_input",
                                "result",
                                "error",
                                "block",
                            )
                            if k in data
                        }
                        block = observed.get("block")
                        if hasattr(block, "model_dump"):
                            block = block.model_dump()
                        if isinstance(block, dict):
                            # Publicly emitted text only; no signatures, opaque
                            # reasoning state or reconstructed private content.
                            observed["block"] = {
                                k: block[k] for k in ("type", "text", "thinking") if k in block
                            }
                        if event == "content_block:end" and (
                            not isinstance(block, dict)
                            or block.get("type") not in ("text", "thinking", "reasoning")
                            or not (block.get("text") or block.get("thinking"))
                        ):
                            return HookResult()  # Tool-use/opaque blocks are not conversation text.
                        projection, partial = bounded_projection(observed)
                        text, serialized_partial = bounded(projection)
                        partial |= serialized_partial
                        result = data.get("result")
                        if hasattr(result, "model_dump"):
                            result = result.model_dump()
                        from .events import tool_result, tool_status

                        parsed_result = tool_result(result)
                        status = (
                            tool_status(event, result, parsed_result=parsed_result)
                            if event.startswith("tool:")
                            else "observed"
                        )
                        status, outcome_source = self.observed_outcome(call_id, event, status)
                        if event in ("tool:post", "tool:error") and status in (
                            "failed",
                            "unknown",
                            "interrupted",
                        ):
                            row["warnings"][status] = row["warnings"].get(status, 0) + 1
                            row["last_warning"] = f"{data.get('tool_name', 'tool')} · {status}"
                        if event.startswith("tool:"):
                            running = self.running_tools[identity]
                            if event == "tool:pre":
                                running[call_id] = data.get("tool_name", "tool")
                            else:
                                running.pop(call_id, None)
                                row["tools_completed"] += 1
                            activity = (
                                f"{next(iter(running.values()))} · running"
                                + (f" · {len(running)} tools" if len(running) > 1 else "")
                                if running
                                else f"{data.get('tool_name', 'tool')} · {status}"
                            )
                            self.progress(identity, activity)
                        source_id = str(data.get("tool_call_id", data.get("block_index", "text")))
                        self.host.emit(
                            "child.observed",
                            call_id
                            if event.startswith("tool:")
                            else self.activity_id(identity, f"{source_id}:{event}"),
                            child_id=identity,
                            parent_item_id=f"child:{identity}",
                            name=f"{self.label(identity)} · {data.get('tool_name', event)}",
                            event=event,
                            arguments=data.get("tool_input"),
                            result=result,
                            block=observed.get("block"),
                            source=text,
                            partial=partial,
                            status=status,
                            outcome_source=outcome_source,
                        )
                return HookResult()

            coordinator.hooks.register(
                "orchestrator:complete", observe, priority=999, name="tui-child-outcome"
            )
            for name in (
                "provider:request",
                "provider:resolve",
                "llm:request",
                "llm:response",
                "content_block:end",
                "tool:pre",
                "tool:post",
                "tool:error",
            ):
                coordinator.hooks.register(
                    name, observe, priority=999, name="tui-child-observation"
                )
            self.publish(identity, "running")
            from .composition import execute_owned

            if coordinator.cancellation.is_immediate:
                raise asyncio.CancelledError
            if coordinator.cancellation.is_graceful:
                output = "Stopped before agent execution"
                outcome["status"] = "cancelled"
            else:
                output = await execute_owned(
                    session,
                    instruction,
                    on_forced=lambda: row.update(execution_uncertain=True),
                )
            row["messages"] = await context.get_messages()
            row["mode"] = coordinator.session_state.get("active_mode")
            if coordinator.cancellation.is_immediate:
                raise asyncio.CancelledError
            if outcome.get("status") == "cancelled" or (
                coordinator.cancellation.is_graceful and outcome.get("status") == "success"
            ):
                # Returning partial results lets the delegate tool finish its
                # current call and join siblings. CancelledError here would
                # implicitly turn a graceful tree stop into an immediate one.
                row["status"] = "interrupted"
                outcome["status"] = "cancelled"
            elif outcome.get("status") != "success":
                raise RuntimeError(f"Child did not complete: {outcome.get('status', 'unknown')}")
            else:
                row["status"] = "completed"
        except BaseException as exc:
            row["status"] = "interrupted" if isinstance(exc, asyncio.CancelledError) else "failed"
            self.publish(identity, row["status"], str(exc) or "Stopped; partial effects may remain")
            raise
        finally:
            # Delegate callers can cancel more than once. They own their wait,
            # not the acquired session's cleanup or final durable receipt.
            finalizer = asyncio.create_task(self.finalize(identity, session))
            cancelled = None
            while not finalizer.done():
                try:
                    await asyncio.shield(finalizer)
                except asyncio.CancelledError as exc:
                    cancelled = exc
                    if row["status"] != "failed":
                        row["status"] = "interrupted"
            try:
                finalizer.result()
                if cancelled is not None:
                    # Cancellation can race the finalizer's last synchronous save.
                    self.save(identity)
                    self.publish(
                        identity, "interrupted", "Stopped during finalization; effects remain"
                    )
                    raise cancelled
            finally:
                if child_cancellation is not None:
                    parent_cancellation.unregister_child(child_cancellation)
                self.active.pop(identity, None)
                self.parents.pop(identity, None)
                self.tasks.pop(identity, None)
        if row.get("execution_uncertain"):
            raise RuntimeError("Child execution or final state uncertain; continuation refused")
        self.publish(
            identity, "interrupted" if row["status"] == "interrupted" else "succeeded", output
        )
        return {"session_id": identity, "output": output, "metadata": outcome}

    async def finalize(self, identity, session):
        row = self.records[identity]
        try:
            if session:
                try:
                    context = session.coordinator.get("context")
                    if context:
                        row["messages"] = await context.get_messages()
                finally:
                    await session.cleanup()
        except BaseException:
            row["status"] = "failed"
            self.host.ready = False
            self.publish(identity, "failed", "Child cleanup failed; partial effects may remain")
            raise
        finally:
            # Retain task ownership until both cleanup and receipt persistence end.
            try:
                if row.get("execution_uncertain") and row["status"] == "completed":
                    row["status"] = "failed"
                row["resumable"] = row["status"] == "completed" and not row.get(
                    "execution_uncertain"
                )
                if row["status"] == "interrupted" and not row.get("execution_uncertain"):
                    from .recovery import public_history

                    try:
                        public_history(row["messages"])
                        row["resumable"] = True
                    except (TypeError, ValueError):
                        pass
                self.save(identity)
            except BaseException:
                row["status"] = "failed"
                self.host.ready = False
                self.publish(identity, "failed", "Child record could not be saved")
                raise

    def stop(self, *, immediate=True):
        # Capacity waiters have not started a model/tool operation. Cancelling
        # them is graceful and wakes them promptly without polling or replay.
        for identity in self.waiting:
            task = self.tasks.get(identity)
            if task and not task.done() and not task.cancelling():
                task.cancel()
        for session in self.active.values():
            if session:
                cancellation = session.coordinator.cancellation
                if immediate:
                    cancellation.request_immediate()
                else:
                    cancellation.request_graceful()
        if immediate:
            for task in set(self.tasks.values()):
                if task is not asyncio.current_task() and not task.done() and not task.cancelling():
                    task.cancel()

    async def drain(self, *, cancel=True):
        # Some delegation tools detach cancelled children instead of awaiting
        # cleanup. The app still owns those sessions and their journal lifetime.
        pending = {
            t for t in self.tasks.values() if t is not asyncio.current_task() and not t.done()
        }
        for task in pending:
            if cancel and not task.cancelling():
                task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

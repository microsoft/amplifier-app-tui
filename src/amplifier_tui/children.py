"""App-owned child sessions over public Foundation composition/session APIs."""

import asyncio
import copy
import hashlib
import json
import re
import uuid
from dataclasses import replace
from pathlib import Path

from amplifier_core import HookResult
from amplifier_foundation import (
    Bundle,
    ProviderPreference,
    apply_provider_preferences_with_resolution,
)

from .composition import TERMINAL_HOOKS, expand_environment, provider_instances
from .conversations import atomic_json, portable_history


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def parent_orchestrator(session):
    section = (session.config or {}).get("session", {}).get("orchestrator", {})
    return section.get("config", {}) if isinstance(section, dict) else {}


class ChildDisplay:
    def __init__(self, owner, identity):
        self.owner, self.identity = owner, identity
        self.store = None
        self.session = None

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
                f"Child {self.identity}: {prompt}", options, timeout, default
            )
        finally:
            self.owner.publish(self.identity, "running")

    def show_message(self, message, **kwargs):
        self.owner.host.show_message(f"Child {self.identity}: {message}")


class Children:
    """At most 4 running / 32 retained children and 3 nested levels per root host.

    Completed children can resume explicitly when their active parent, composition
    and mode reconstruct exactly. Receipts never authorize automatic execution.
    """

    def __init__(self, host, prepared, cwd):
        self.host, self.prepared, self.cwd = host, prepared, cwd
        self.records, self.active, self.parents = {}, {}, {host.session_id: (prepared, 0)}
        self.initializing = asyncio.Lock()
        self.tasks = {}
        self.restoring = {}

    def register(self, session):
        session.coordinator.register_capability("session.spawn", self.spawn)
        session.coordinator.register_capability("session.resume", self.resume)

    def publish(self, identity, status, output=""):
        row = self.records[identity]
        self.host.emit(
            "tool.updated",
            f"child:{identity}",
            name=f"Agent · {row['agent']}",
            child_id=identity,
            status=status,
            arguments={"instruction": row["instruction"]},
            result={
                "output": output,
                "session_id": identity,
                "parent_id": row["parent"],
                "tools": row.get("tools", []),
                "hooks": row.get("hooks", []),
                "continuation": "Explicit completed-child continuation checks composition and mode; interrupted/unsupported children refuse. Restored rows are not live sessions.",
            },
        )

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
    ):
        if use_subprocess:
            raise ValueError(
                "Subprocess-isolated recipe steps are not supported; use in-process spawn"
            )
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
        if depth >= 3 or len(self.active) >= 4 or len(self.records) >= 32:
            raise ValueError(
                "Child limit reached: 3 levels, 4 active, 32 retained per open conversation"
            )
        if not isinstance(instruction, str) or not 0 < len(instruction) <= 262144:
            raise ValueError("Child instruction must contain 1–262144 characters")
        config = agent_configs.get(agent_name) if agent_name != "self" else {}
        if not isinstance(config, dict):
            raise ValueError(f"Unknown or unresolved agent: {agent_name}")
        config = copy.deepcopy(config)
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
        if provider_preferences:
            plan["provider_preferences"] = [p.to_dict() for p in provider_preferences]
            plan = await apply_provider_preferences_with_resolution(
                plan, provider_preferences, parent_session.coordinator
            )
        if len(self.active) >= 4 or len(self.records) >= 32:
            raise ValueError("Child concurrency/retention limit reached")
        identity = sub_session_id or uuid.uuid4().hex
        if (
            not isinstance(identity, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", identity)
            or identity in self.records
        ):
            raise ValueError("Invalid or already used child identity")
        context_plan = plan.get("session", {}).get("context", {})
        if context_plan.get("module") == "context-persistent":
            if not self.host.store:
                raise ValueError("Persistent child context requires isolated conversation storage")
            directory = self.host.store.path / "child-context" / identity
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            context_plan.setdefault("config", {})["transcript_path"] = str(
                directory / "messages.jsonl"
            )
        prepared = replace(base, bundle=effective, mount_plan=plan)
        restored = self.restoring.get(identity)
        if restored and fingerprint(plan) != restored.get("mount_fingerprint"):
            raise ValueError("Child effective composition changed; continuation refused")
        if (
            self.host.store
            and (self.host.store.path / "children" / f"{identity}.json").exists()
            and not restored
        ):
            raise ValueError("Child identity already exists on disk; use explicit continuation")
        self.records[identity] = {
            "agent": agent_name,
            "parent": parent_id,
            "instruction": instruction,
            "prepared": prepared,
            "depth": depth + 1,
            "messages": parent_messages or [],
            "status": "new",
            "metadata": session_metadata or {},
            "mode": parent_session.coordinator.session_state.get("active_mode"),
            "routing": [p.to_dict() for p in provider_preferences or []],
            "request_index": 0,
            "mount_fingerprint": fingerprint(plan),
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
        return await self.execute(identity, instruction, parent_session)

    async def resume(self, sub_session_id, instruction, provider_preferences=None, model_role=None):
        row = self.records.get(sub_session_id)
        if row is None and self.host.store:
            return await self.restore(sub_session_id, instruction, provider_preferences, model_role)
        if not row or row["status"] != "completed" or sub_session_id in self.active:
            raise ValueError("Child is unavailable, active or incomplete; no work replayed")
        if model_role or (
            provider_preferences and [p.to_dict() for p in provider_preferences] != row["routing"]
        ):
            raise ValueError("Changing child routing on resume requires a new delegation")
        parent = (
            self.host.session
            if row["parent"] == self.host.session_id
            else self.active.get(row["parent"])
        )
        if parent is None or self.host._stop_requested:
            raise ValueError("Child parent no longer active")
        return await self.execute(sub_session_id, instruction, parent)

    async def restore(self, identity, instruction, provider_preferences, model_role):
        if not isinstance(identity, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", identity):
            raise ValueError("Invalid child identity")
        if not self.host.ready or self.host._stop_requested or identity in self.restoring:
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
        if not isinstance(row, dict) or row.get("status") != "completed":
            raise ValueError("Child is incomplete; no work replayed")
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
            or model_role
        ):
            raise ValueError("Child restart policy is unsupported; create a new delegation")
        routing = row.get("routing", [])
        if not isinstance(routing, list) or not all(isinstance(p, dict) for p in routing):
            raise ValueError("Invalid child provider routing")
        if provider_preferences and [p.to_dict() for p in provider_preferences] != routing:
            raise ValueError("Changing child routing requires a new delegation")
        preferences = [ProviderPreference.from_dict(p) for p in routing]
        if row.get("mode") != parent.coordinator.session_state.get("active_mode"):
            raise ValueError("Inherited child mode changed; create a new delegation")
        if not isinstance(row.get("messages"), list) or not all(
            isinstance(m, dict) for m in row["messages"]
        ):
            raise ValueError("Invalid child canonical context")
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
            )
        finally:
            self.restoring.pop(identity, None)

    def save(self, identity):
        if self.host.store:
            directory = self.host.store.path / "children"
            directory.mkdir(mode=0o700, exist_ok=True)
            atomic_json(
                directory / f"{identity}.json",
                {k: v for k, v in self.records[identity].items() if k != "prepared"},
            )

    async def execute(self, identity, instruction, parent):
        row = self.records[identity]
        self.active[identity] = None
        self.tasks[identity] = asyncio.current_task()
        self.publish(identity, "running")
        session, outcome, output = None, {}, ""
        try:
            row["status"] = "running"
            # Mark dispatch before effects so an old completed receipt cannot be reused.
            self.save(identity)
            proxy = ChildDisplay(self, identity)
            async with self.initializing:
                from .composition import create_owned_session

                session = await create_owned_session(
                    row["prepared"],
                    session_id=identity,
                    parent_id=row["parent"],
                    session_cwd=Path(self.cwd),
                    approval_system=proxy,
                    display_system=proxy,
                )
            self.active[identity] = session
            proxy.session = session
            self.parents[identity] = (row["prepared"], row["depth"])
            coordinator = session.coordinator
            for point in ("context", "orchestrator", "providers"):
                if not coordinator.get(point):
                    raise RuntimeError(f"Child missing {point}")
            self.register(session)
            from .modes import Modes

            modes = Modes(proxy)
            await modes.open()
            if row.get("mode"):
                if not modes.supported:
                    raise ValueError("Child cannot enforce the inherited active mode")
                result = await modes.apply({"operation": "set", "name": row["mode"]})
                if not result.success or modes.current() != row["mode"]:
                    raise ValueError("Child failed to restore inherited mode policy")
            coordinator.register_capability("self_delegation_depth", row["depth"])
            if self.host.interactive_questions:

                async def ask(questions, **kwargs):
                    self.publish(identity, "waiting_answer")
                    try:
                        return await self.host.questions.ask(questions, **kwargs)
                    finally:
                        self.publish(identity, "running")

                coordinator.register_capability("user.questions", ask)
            context = coordinator.get("context")
            if row["messages"]:
                await context.set_messages(copy.deepcopy(row["messages"]))
                if portable_history(await context.get_messages()) != portable_history(
                    row["messages"]
                ):
                    raise RuntimeError(
                        "Context module did not restore child history; continuation refused"
                    )
            row["tools"] = sorted(coordinator.get("tools") or {})
            row["hooks"] = coordinator.hooks.list_handlers()

            async def observe(event, data):
                if data.get("session_id") in (None, "", identity):
                    if event == "orchestrator:complete":
                        outcome.update(data)
                    else:
                        from .inspection import bounded

                        if event == "provider:request":
                            row["request_index"] += 1
                            self.publish(
                                identity, "running", f"Provider request {row['request_index']}"
                            )
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
                        text, partial = bounded(observed)
                        result = data.get("result")
                        if hasattr(result, "model_dump"):
                            result = result.model_dump()
                        status = "running" if event == "tool:pre" else "observed"
                        if event == "tool:error":
                            status = "failed"
                        elif event == "tool:post":
                            status = "unknown"
                            if isinstance(result, dict):
                                if result.get("success") is True:
                                    status = "succeeded"
                                elif result.get("success") is False or result.get("error"):
                                    status = "failed"
                        source_id = str(data.get("tool_call_id", data.get("block_index", "text")))
                        self.host.emit(
                            "child.observed",
                            f"activity:{identity}:{row['request_index']}:{source_id}:{event}",
                            child_id=identity,
                            name=f"{row['agent']} · {data.get('tool_name', event)}",
                            event=event,
                            source=text,
                            partial=partial,
                            status=status,
                        )
                return HookResult()

            coordinator.hooks.register(
                "orchestrator:complete", observe, priority=999, name="tui-child-outcome"
            )
            for name in (
                "provider:request",
                "content_block:end",
                "tool:pre",
                "tool:post",
                "tool:error",
            ):
                coordinator.hooks.register(
                    name, observe, priority=999, name="tui-child-observation"
                )
            self.publish(identity, "running")
            output = await session.execute(instruction)
            row["messages"] = await context.get_messages()
            row["mode"] = coordinator.session_state.get("active_mode")
            if outcome.get("status") != "success":
                raise RuntimeError(f"Child did not complete: {outcome.get('status', 'unknown')}")
            row["status"] = "completed"
        except BaseException as exc:
            row["status"] = "interrupted" if isinstance(exc, asyncio.CancelledError) else "failed"
            self.publish(identity, row["status"], str(exc) or "Stopped; partial effects may remain")
            raise
        finally:
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
                self.active.pop(identity, None)
                self.parents.pop(identity, None)
                self.tasks.pop(identity, None)
            if self.host.store:
                try:
                    self.save(identity)
                except BaseException:
                    row["status"] = "failed"
                    self.host.ready = False
                    self.publish(identity, "failed", "Child record could not be saved")
                    raise
        self.publish(identity, "succeeded", output)
        return {"session_id": identity, "output": output, "metadata": outcome}

    def stop(self):
        for session in self.active.values():
            if session:
                session.coordinator.cancellation.request_immediate()

    async def drain(self):
        # Some delegation tools detach cancelled children instead of awaiting
        # cleanup. The app still owns those sessions and their journal lifetime.
        pending = {
            t for t in self.tasks.values() if t is not asyncio.current_task() and not t.done()
        }
        for task in pending:
            if not task.cancelling():
                task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

"""One conversation, one active kernel execution, explicit admission and outcomes."""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import logging
import time
import uuid
from importlib.metadata import version
from pathlib import Path

from amplifier_core import HookResult

from .conversations import portable_history
from .delivery import EventDelivery
from .events import Event, message_text, tool_result, tool_status, tool_text
from .inspection import (
    CallUsage,
    Inspection,
    add_usage,
    call_usage_text,
    usage_totals,
    usage_values,
)
from .questions import Questions
from .runtime_controls import RuntimeControls


class InitializationDiagnostics(logging.Handler):
    """Pinned core's initializer logs optional mount failures before continuing.

    PreparedBundle has no pre-initialize observer seam. This narrowly scoped
    fallback refuses readiness on initializer warnings; it is not a mount ledger.
    """

    def __init__(self):
        super().__init__(logging.WARNING)
        self.failed = False

    def emit(self, record):
        self.failed = True


class SessionHost:
    def __init__(self, store=None):
        self.store = store
        self.fingerprint = None
        self.session_id = store.identity if store else uuid.uuid4().hex
        self.events = EventDelivery()
        self.delivery_failed = asyncio.Event()
        self.inspection = Inspection(store.restored_events if store else ())
        self.sequence = store.saved["sequence"] if store and store.saved else 0
        self.turn_id = None
        self.session = None
        self.task = None
        self.local_commands = None
        self.ready = False
        self.report = {}
        self.outcome = None
        self.observed_tools = {"root": {}, "children": {}}
        self.blocks = set()
        self._execution_started = False
        self._closed = False
        self._opening = None
        self._close_task = None
        self.validation_active = False
        self._finalizing = False
        self.auto_deny_approvals = False
        self._pending = {}
        self._tool_ids = set()
        self._stop_requested = False
        self._force_requested = False
        self._request_index = 0
        self.turn_usage = usage_totals()
        self.call_usage = CallUsage(store.restored_events if store else ())
        self.background_callback = None
        self.activity_callback = None
        self.model_activity = ""
        self.title_callback = None
        self.naming_calls = 0
        self.naming_turns = 0
        self.naming_turn = None
        self.last_provider = {}
        self._turn_started = None
        self.command_processor = None
        self.thinking_blocks = {}
        self.thinking_emitted = {}
        self.thinking_ids = set()
        self.thinking_limited = False
        self.controls = None
        self.children = None
        self.modes = None
        self.images = None
        self.tool_evidence = None
        self.questions = Questions(self)
        self.interactive_questions = False
        self.capabilities = {
            "submit": True,
            "stop": True,
            "approval": True,
            "queue": False,
            "steer": False,
            "resume": store is not None,
            "delegation": False,
        }

    @property
    def ready(self):
        return self._ready and not self._closed

    @ready.setter
    def ready(self, value):
        self._ready = value

    def emit(self, kind, item_id, **payload):
        self.sequence += 1
        event = Event(
            self.session_id,
            self.sequence,
            self.turn_id,
            kind,
            item_id,
            copy.deepcopy(payload),
            timestamp_ns=time.time_ns(),
        )
        if self.store:
            self.store.record(event)
            if (
                kind == "display.message"
                and (self.task is None or self.task.done())
                and self.store.saved
                and self.store.saved["sequence"] == self.sequence - 1
            ):
                # A late public notice changes no canonical messages. Preserve the
                # checkpoint's safety status while keeping journal order exact.
                self.store.checkpoint_auxiliary(self.sequence)
        self.inspection.observe(event)
        if kind in ("tool.updated", "tool.ended") and not item_id.startswith("child:"):
            self.observed_tools["root"][item_id] = payload.get("status", "unknown")
        elif kind == "child.observed" and payload.get("event", "").startswith("tool:"):
            # Legacy journals used phase IDs; newer observers keep one call ID.
            key = item_id.rsplit(":tool:", 1)[0]
            self.observed_tools["children"][key] = payload.get("status", "unknown")
        if not self.delivery_failed.is_set():
            try:
                self.events.put_nowait(event)
            except asyncio.QueueFull:
                # The journal was written first. Do not block execution/control on
                # paint, or silently discard delivery while claiming a healthy view.
                self.delivery_failed.set()
                self.ready = False
                self.stop()
                logging.getLogger(__name__).error(
                    "Source event delivery exceeded 4096 pending records or 8 MiB; connection failed. "
                    "Retained journal is authoritative; no work will retry automatically."
                )

    def background(self, phase):
        # Preparation is transient UI state, not a mutation of the conversation.
        # A refused reopen must not append phases past its last good checkpoint.
        if self.background_callback:
            self.background_callback(phase)

    def activity(self, phase):
        """Transient observed foreground phase; never a journal row or inference."""
        if phase != self.model_activity:
            self.model_activity = phase
            if self.activity_callback:
                self.activity_callback(phase)

    def observe_usage(
        self, identity, data, provider, *, agent="", child_id=None, session_only=False
    ):
        value = data.get("usage", {})
        if hasattr(value, "model_dump"):
            value = value.model_dump()
        values = usage_values(value)
        if not self.call_usage.add(identity, self.turn_id, values, session_only=session_only):
            return
        actual = {
            **provider,
            **{k: data[k] for k in ("provider", "model") if isinstance(data.get(k), str)},
        }
        duration = data.get("duration_ms")
        self.emit(
            "display.message",
            identity,
            source="usage",
            level="info",
            text=call_usage_text(values, actual, agent=agent, duration_ms=duration),
            usage_call={k: str(v) if k == "cost_usd" else v for k, v in values.items()},
            usage_scope="session" if session_only else "turn",
            provider=actual,
            duration_ms=duration,
            child_id=child_id,
            parent_item_id=f"child:{child_id}" if child_id else None,
        )
        return values

    async def next_event(self):
        if self.delivery_failed.is_set():
            raise RuntimeError(
                "Source event backlog exceeded; inspect retained history before recovery"
            )
        return await self.events.get()

    async def open(self, prepared, report, cwd: Path):
        from dataclasses import replace

        if self._closed:
            raise RuntimeError("Session is closed")
        if self._opening is not None or self.session is not None:
            raise RuntimeError("Session is already opening or open")
        prepared = replace(
            prepared,
            mount_plan=copy.deepcopy(prepared.mount_plan),
            bundle=copy.deepcopy(prepared.bundle),
        )
        self.report = report
        bases = [
            cwd,
            prepared.bundle.base_path,
            *(prepared.bundle.source_base_paths or {}).values(),
        ]
        self.recipe_roots = list(
            dict.fromkeys(str(Path(base) / "recipes") for base in bases if base)
        )
        self.fingerprint = hashlib.sha256(
            json.dumps(prepared.mount_plan, sort_keys=True, default=str).encode()
        ).hexdigest()
        if (
            self.store
            and self.store.saved
            and self.store.saved["fingerprint"] is not None
            and self.store.saved["fingerprint"] != self.fingerprint
        ):
            raise ValueError("Effective module configuration changed; resume refused")
        diagnostics = InitializationDiagnostics()
        initializer = logging.getLogger("amplifier_core._session_init")
        initializer.addHandler(diagnostics)
        self._opening = asyncio.current_task()
        try:
            from .composition import create_owned_session

            self.background("Initializing modules")
            self.session = await create_owned_session(
                prepared,
                session_id=self.session_id,
                session_cwd=cwd,
                approval_system=self,
                display_system=self,
                interactive_approval=self.interactive_questions,
                observer=self._observe,
            )
            if self._closed:
                raise RuntimeError("Session was closed during startup")
            if diagnostics.failed:
                raise RuntimeError("Module initialization reported a failure; inspect diagnostics")
            coordinator = self.session.coordinator
            if self.store and any(
                h.get("module") == "hooks-session-naming"
                for h in prepared.mount_plan.get("hooks", [])
            ):
                self.naming_turns = sum(
                    e.kind == "turn.ended" and e.payload.get("status") == "completed"
                    for e in self.store.restored_events
                )
                coordinator.session_dir = str(self.store.naming_metadata(self.naming_turns))
                coordinator.hooks.register(
                    "prompt:complete", self._prepare_naming, priority=90, name="tui-naming-metadata"
                )
                for naming_event in (
                    "session-naming:set",
                    "session-naming:error",
                    "session-naming:timeout",
                ):
                    coordinator.hooks.register(
                        naming_event, self._observe, priority=999, name="tui-naming"
                    )
            from .workspace_review import ToolEvidence

            self.tool_evidence = ToolEvidence(cwd, self.store.restored_events if self.store else ())
            self.background("Restoring conversation and controls")
            from .file_input import ImageDraft

            self.images = ImageDraft(self.store)
            for point in ("orchestrator", "context", "providers"):
                if not coordinator.get(point):
                    raise RuntimeError(f"Required mount missing: {point}")
            if self.store:
                context = coordinator.get("context")
                shared = getattr(self.store, "shared_session", False)
                if shared:
                    self.call_usage.legacy |= self.store.metadata.get(
                        "shared_history_unaccounted", False
                    )
                    self.store.canonical_launch["bundle"] = report.get(
                        "selected_bundle"
                    ) or self.store.canonical_launch.get("bundle")
                if not all(
                    callable(getattr(context, name, None))
                    for name in ("get_messages", "set_messages")
                ):
                    raise RuntimeError("Context module does not support canonical history resume")
                if self.store.saved:

                    def comparable(messages):
                        if shared:
                            from amplifier_foundation import sanitize_message

                            messages = [
                                sanitize_message(m)
                                for m in messages
                                if m.get("role") not in ("system", "developer")
                            ]
                        return portable_history(messages)

                    restored = comparable(self.store.saved["messages"])
                    if comparable(await context.get_messages()) != restored:
                        await context.set_messages(copy.deepcopy(self.store.saved["messages"]))
                    if comparable(await context.get_messages()) != restored:
                        raise RuntimeError(
                            "Context module did not restore canonical history; resume refused"
                        )
                elif (self.store.path / "imported-reference.json").exists():
                    from .recovery import reference_messages

                    with (self.store.path / "imported-reference.json").open("rb") as stream:
                        raw = stream.read(7 * 1024 * 1024 + 1)
                    if len(raw) > 7 * 1024 * 1024:
                        raise ValueError("Imported reference exceeds storage limit")
                    imported = json.loads(raw)
                    messages = reference_messages(imported)
                    await context.set_messages(messages)
                    if portable_history(await context.get_messages()) != portable_history(messages):
                        raise RuntimeError("Context module did not preserve imported reference")
                    self.emit(
                        "display.message",
                        "imported-reference",
                        text=imported["notice"] + "\nSource SHA-256: " + imported["sha256"],
                    )
                elif (self.store.path / "imported-context.json").exists():
                    from .recovery import context_transfer

                    with (self.store.path / "imported-context.json").open("rb") as stream:
                        raw = stream.read(9 * 1024 * 1024 + 1)
                    if len(raw) > 9 * 1024 * 1024:
                        raise ValueError("Transferred context exceeds limit")
                    imported = json.loads(raw)
                    validated = context_transfer(
                        imported.get("messages"),
                        imported.get("source_session"),
                        turn=imported.get("fork_turn"),
                    )
                    if imported.get("version") != 1 or validated["sha256"] != imported.get(
                        "sha256"
                    ):
                        raise ValueError("Transferred context failed integrity verification")
                    if (
                        any(
                            isinstance(m.get("content"), list)
                            and any(
                                isinstance(b, dict) and b.get("type") in ("image", "image_url")
                                for b in m["content"]
                            )
                            for m in validated["messages"]
                        )
                        and not self.supports_images()
                    ):
                        raise ValueError("New composition cannot accept the captured images")
                    await context.set_messages(copy.deepcopy(validated["messages"]))
                    if portable_history(await context.get_messages()) != portable_history(
                        validated["messages"]
                    ):
                        raise ValueError(
                            "New context module did not retain transferred public history"
                        )
                    self.emit("display.message", "context-transfer", text=validated["notice"])
            mounted = coordinator.get("tools") or {}
            required = set(report.get("required_tools", []))
            if prepared.mount_plan.get("tools") and not mounted:
                raise RuntimeError("No declared tools mounted")
            missing = required - set(mounted)
            if missing:
                raise RuntimeError(f"Required tool mount missing: {', '.join(sorted(missing))}")
            for name in (
                "provider:request",
                "provider:resolve",
                "llm:stream_block_delta",
                "llm:stream_block_start",
                "llm:stream_block_end",
                "content_block:end",
                "tool:pre",
                "tool:post",
                "tool:error",
                "orchestrator:complete",
                "orchestrator:steering_injected",
                "llm:response",
                "llm:request",
                "context:compaction",
                "context:tool_result_ingress_truncated",
                "context:budget",
                "provider:retry",
                "provider:throttle",
                "orchestrator:goal_progress",
            ):
                coordinator.hooks.register(name, self._observe, priority=999, name="tui-observer")
            self.controls = RuntimeControls(self)
            from .children import Children

            self.children = Children(self, prepared, cwd)
            self.children.register(self.session)
            self.capabilities["delegation"] = True
            from .modes import Modes

            self.modes = Modes(self)
            await self.modes.open()
            from .runtime_controls import LocalCommands

            self.local_commands = LocalCommands(self, prepared, cwd)
            await self.local_commands.open()
            self.children.register(self.session)  # Observe app-installed mode/control adapters too.
            self.capabilities["modes"] = self.modes.supported
            if self.interactive_questions:
                coordinator.register_capability("user.questions", self.questions.ask)
            self.capabilities["questions"] = self.interactive_questions
            mounted = coordinator.get("tools") or {}
            if self.delivery_failed.is_set():
                raise RuntimeError("Source event delivery failed during startup")
            self.ready = True
            # Optional module discovery, not a frontend import or private dict.
            self.background("Discovering skills and capabilities")
            skills = []
            skills_note = "No skills discovery capability mounted"
            discovery = coordinator.get_capability("skills_discovery")
            if discovery is not None and callable(getattr(discovery, "list_skills", None)):
                try:
                    skills = [
                        {"name": name, "description": description}
                        for name, description in discovery.list_skills()
                    ]
                    skills_note = "Discovered at startup; loading/execution remains module policy"
                except Exception:
                    skills_note = "Skill discovery failed; inspect the mounted tool"
            from .cli_compat import skill_commands

            self.report = {
                **report,
                "app_version": version("amplifier-app-tui"),
                "frontend_policy": "Native Ratatui product; historical events may predate this runtime",
                "stage": "mounted",
                "tools": sorted(mounted),
                "providers": sorted(coordinator.get("providers")),
                "verified_required_tools": sorted(required),
                "module_export_attribution": "unverified; tool names are observed mounts",
                "hook_handlers": coordinator.hooks.list_handlers(),
                "capabilities": self.capabilities,
                "skills": skills,
                "commands": skill_commands(self.session),
                "skills_note": skills_note,
                "conversation_provider": self.controls.catalog(),
                "mode_control": self.modes.catalog(),
                "goal_control": self.local_commands.goal_status(),
            }
            self.background("")
            self.emit("session.ready", "session", **self.report)
            if self.store and self.store.metadata.get("recovery_notice"):
                self.emit(
                    "display.message", "recovery", text=self.store.metadata["recovery_notice"]
                )
            if self.store:
                self.store.checkpoint(
                    await context.get_messages(), self.sequence, self.fingerprint, True
                )
        except BaseException:
            # An external close owns this opening task and waits for it. Do not
            # recursively join that close; on local failure detach before joining.
            self._opening = None
            if not self._closed:
                await self.close()
            raise
        finally:
            self._opening = None
            initializer.removeHandler(diagnostics)

    def submit(
        self,
        text: str,
        input_id=None,
        image_id=None,
        queued_image=None,
        *,
        operation=None,
        preflight=None,
    ) -> tuple[bool, str]:
        if not text.strip():
            return False, "Write a message first."
        if self._closed or not self.ready:
            return False, "The session is not ready. Your draft is retained."
        if self.task is not None and not self.task.done():
            return (
                False,
                "A turn is running. Your draft is retained; use distinct queue or correction controls.",
            )
        if getattr(self.store, "shared_session", False):
            try:
                self.store.assert_current()
            except (OSError, ValueError) as exc:
                return False, str(exc)
        if text.lstrip().startswith("/") and operation is None and preflight is None:
            if (
                input_id is not None
                and self.local_commands
                and self.local_commands.recognizes(text)
            ):
                return False, "Local controls require an explicit idle Send, not queued execution"
            if self.local_commands:
                local = self.local_commands.submit(text, bool(image_id or queued_image))
                if local is not None:
                    return local
            if self.command_processor is None:
                from amplifier_app_cli.main import CommandProcessor

                self.command_processor = CommandProcessor(
                    self.session, self.report.get("bundle", "unknown")
                )
            action, data = (
                self.command_processor.process_input(text.lstrip())
                if self.command_processor
                else ("unknown", {})
            )
            if action != "load_skill":
                return (
                    False,
                    "Unsupported local command here; use Actions or /help. Nothing sent; draft retained.",
                )
            discovery = self.session.coordinator.get_capability("skills_discovery")
            if not discovery or not discovery.find(data.get("skill_name", "")):
                return False, "Unknown skill; inspect Skills. Nothing sent; draft retained."
        image = None
        try:
            value = queued_image or (self.images.value if self.images and image_id else None)
            if (image_id or queued_image) and not self.supports_attachments(value):
                return (
                    False,
                    "Mounted provider/context does not support these attachments; draft retained",
                )
            if queued_image:
                from .file_input import ImageDraft

                ImageDraft.validate(queued_image)
                image = queued_image
            elif self.images:
                image = self.images.admit(image_id)
            elif image_id:
                return False, "Image input unavailable"
        except (ValueError, OSError) as exc:
            return False, str(exc)
        self.turn_id = uuid.uuid4().hex
        if self.local_commands and self.session.coordinator.session_state.get("goal"):
            try:
                self.local_commands.save("pending")
            except Exception:
                self.ready = False
                return False, "Control checkpoint failed; no turn started, draft retained"
        self.questions.count = 0
        self.outcome = None
        self.observed_tools = {"root": {}, "children": {}}
        self.blocks = set()
        self._execution_started = False
        self._finalizing = False
        self._tool_ids = set()
        self._stop_requested = False
        self._force_requested = False
        self._execution_uncertain = False
        self._request_index = 0
        self.turn_usage = usage_totals()
        self.last_provider = {}
        self.thinking_blocks = {}
        self.thinking_emitted = {}
        self.thinking_ids = set()
        self.thinking_limited = False
        self._turn_started = time.monotonic()
        self.session.coordinator.cancellation.reset()
        self.current_input_id = input_id
        self.emit(
            "turn.accepted",
            f"{self.turn_id}:user",
            text=text,
            input_id=input_id,
            image=self.images.metadata(image) if image else None,
        )
        if self.store and self.store.draft == text:
            self.store.save_draft("")
        if image:
            self.emit(
                "display.message",
                f"{self.turn_id}:image",
                text=f"Attachment snapshot: {image['path']} · {image['bytes']} bytes · SHA-256 {image['sha256']}",
            )
        self.task = asyncio.create_task(self._execute(text, image, operation, preflight))
        return True, self.turn_id

    def supports_attachments(self, value):
        from .file_input import ImageDraft

        if not self.session or not callable(
            getattr(self.session.coordinator.get("context"), "add_message", None)
        ):
            return False
        return not ImageDraft.needs_vision(value) or self.supports_images()

    def supports_images(self):
        if not self.session:
            return False
        providers = self.session.coordinator.get("providers") or {}
        # Conservative across routing: every mounted provider must advertise vision.
        try:
            return (
                bool(providers)
                and all(
                    "vision" in provider.get_info().capabilities for provider in providers.values()
                )
                and callable(getattr(self.session.coordinator.get("context"), "add_message", None))
            )
        except Exception:
            return False

    async def _execute(self, text, image=None, operation=None, preflight=None):
        self._execution_started = True
        status, message = "unknown", "No completion evidence was received."
        try:
            if self._stop_requested:
                raise asyncio.CancelledError
            if preflight is not None:
                text = await preflight()
                if self._stop_requested:
                    raise asyncio.CancelledError
            if image:
                from .file_input import ImageDraft

                await self.session.coordinator.get("context").add_message(
                    {
                        "role": "user",
                        "content": ImageDraft.content(image),
                    }
                )
            from .composition import execute_owned

            if operation is None:
                if text.lstrip().startswith("/") and preflight is None:
                    action, data = self.command_processor.process_input(text.lstrip())
                    valid, prompt = await self.command_processor._load_skill(
                        data.get("skill_name", ""), data.get("arguments", "")
                    )
                    if action != "load_skill" or not valid:
                        raise ValueError("Skill became unavailable before execution")
                    text = prompt
                reply = await execute_owned(
                    self.session,
                    text,
                    on_forced=self.execution_uncertain,
                )
            else:
                context = self.session.coordinator.get("context")
                await context.add_message({"role": "user", "content": text})
                reply = await execute_owned(
                    self.session, text, operation=operation, on_forced=self.execution_uncertain
                )
                await context.add_message({"role": "assistant", "content": reply})
                self.outcome = self.outcome or "success"
            status = {
                "success": "completed",
                "error": "failed",
                "cancelled": "interrupted",
                "budget_exhausted": "incomplete",
                "incomplete": "incomplete",
            }.get(self.outcome, "unknown")
            message = {
                "completed": "Turn complete.",
                "failed": "Turn failed.",
                "interrupted": "Stopped; partial effects may remain.",
                "incomplete": "Turn incomplete.",
                "unknown": "No completion evidence was received.",
            }[status]
            # Streaming blocks already own text. A non-streaming replacement can
            # still provide a useful response without pretending it emitted deltas.
            if reply and not self.blocks:
                self.emit("text.final", f"{self.turn_id}:reply", text=reply)
            if self._stop_requested and status != "failed":
                status = "interrupted"
            if status == "completed" and not getattr(operation, "manual_tool", False):
                # Like app-cli, the host owns this lifecycle boundary. The kernel
                # and orchestrator do not emit it; ecosystem naming and other
                # post-prompt hooks depend on it. Interrupted turns are not complete.
                from amplifier_core.events import PROMPT_COMPLETE

                await self.session.coordinator.hooks.emit(
                    PROMPT_COMPLETE,
                    {"prompt": text, "response": reply, "session_id": self.session_id},
                )
        except asyncio.CancelledError:
            status, message = (
                "interrupted",
                "Stopped. Partial effects may remain; nothing was undone.",
            )
        except Exception as exc:
            status, message = "failed", f"{type(exc).__name__}: {exc}"
        finally:
            self._finalizing = True
            self.activity("")
            if self.children and self.children.active:
                if status == "completed":
                    status, message = (
                        "incomplete",
                        "Child work remained active; stopped and drained before checkpoint",
                    )
                await self.children.drain(cancel=not self._stop_requested or self._force_requested)
            if self.tool_evidence:
                for evidence in self.tool_evidence.interrupted():
                    self.emit(
                        "change.observed",
                        f"{self.turn_id}:change:{evidence['source_session']}:{evidence['tool_call_id']}",
                        **evidence,
                    )
            if self._stop_requested and status != "failed":
                status = "interrupted"
                message = "Stopped. Partial effects may remain; nothing was undone."
            for item_id in self._tool_ids:
                self.emit("tool.ended", item_id, status="unknown")
            for request_id, (future, _options) in list(self._pending.items()):
                if not future.done():
                    future.set_result("deny")
            if self.controls:
                self.controls.ended()
            self.questions.cancel_all()
            tools = {
                scope: {
                    state: sum(value == state for value in values.values())
                    for state in ("succeeded", "failed", "unknown", "running")
                }
                for scope, values in self.observed_tools.items()
            }
            total = sum(len(v) for v in self.observed_tools.values())
            if total:
                failed = sum(v["failed"] for v in tools.values())
                unknown = sum(v["unknown"] + v["running"] for v in tools.values())
                if failed or unknown:
                    message += (
                        f" Tools: {failed} failed, {unknown} unresolved. See Activity evidence."
                    )
            if self.call_usage.turn_id == self.turn_id and self.call_usage.turn["requests"]:
                self.show_message(self.call_usage.costs(), source="usage")
            if self.local_commands and (
                self.local_commands.state["status"] == "pending"
                or self.local_commands.state["goal"]
                != self.session.coordinator.session_state.get("goal")
            ):
                try:
                    self.local_commands.save()
                except Exception:
                    self.ready = False
            messages = None
            resumable = status == "completed"
            if self.store:
                try:
                    messages = await self.session.coordinator.get("context").get_messages()
                    if status == "interrupted" and not self._execution_uncertain:
                        from .recovery import public_history

                        try:
                            public_history(messages)  # Validate; never repair implicitly.
                            resumable = True
                        except (ValueError, TypeError):
                            pass
                    if status == "interrupted" and not resumable:
                        self.ready = False
                        message += f" Context requires explicit recovery; quit and use amplifier-tui --recover {self.session_id}."
                except Exception:
                    self.ready = False
                    message += " Canonical context capture failed; resume is unavailable."
            # No await between final observation and its checkpoint: clients must
            # not advertise an idle/reusable session while persistence is pending.
            if self.local_commands:
                self.local_commands.refresh_completion()
            self.emit(
                "turn.ended", f"{self.turn_id}:outcome", status=status, message=message, tools=tools
            )
            if self.store and messages is not None:
                try:
                    self.store.checkpoint(
                        messages,
                        self.sequence,
                        self.fingerprint,
                        resumable and self._ready and not self.delivery_failed.is_set(),
                    )
                except Exception:
                    self.ready = False
                    self.emit(
                        "display.message",
                        uuid.uuid4().hex,
                        text="Checkpoint failed; resume is unavailable. No work will be replayed.",
                    )
            self.blocks.clear()
            self.turn_usage = usage_totals()
            self.last_provider.clear()
            self.thinking_blocks.clear()
            self.thinking_emitted.clear()
            self.thinking_ids.clear()
        return status

    async def _prepare_naming(self, event, data):
        if data.get("session_id") == self.session_id and self.naming_turn != self.turn_id:
            self.store.naming_metadata(self.naming_turns)
            self.naming_turns += 1
            self.naming_turn = self.turn_id
        return HookResult()

    def _checkpoint_auxiliary(self):
        if self.store and (not self.task or self.task.done()):
            try:
                self.store.checkpoint_auxiliary(self.sequence)
            except Exception:
                self.ready = False
                raise

    async def _observe(self, event, data):
        if self.validation_active:
            # Standalone access probes cannot masquerade as conversation activity.
            return HookResult()
        # Child activity must never impersonate the root conversation.
        if data.get("session_id") not in (None, "", self.session_id):
            return HookResult()
        if event.startswith("session-naming:"):
            if event == "session-naming:set" and self.store:
                if (
                    self.store.set_title(
                        data.get("name"), generated=True, description=data.get("description")
                    )
                    and self.title_callback
                ):
                    self.title_callback(self.store.metadata["title"])
            elif event in ("session-naming:error", "session-naming:timeout"):
                self.naming_calls = 0
                self.background("")
                self.show_message(
                    "Automatic naming unavailable; Rename is still available.",
                    source="naming",
                    level="warning",
                )
                self._checkpoint_auxiliary()
            return HookResult()
        if data.get("purpose") == "session-naming":
            # Utility callbacks can finish after a turn's checkpoint or during
            # another turn. Never treat them as root requests/streamed answers.
            if event == "llm:request":
                self.naming_calls += 1
                self.background("Naming conversation")
            elif event == "llm:response":
                self.naming_calls = max(0, self.naming_calls - 1)
                self.observe_usage(
                    f"naming:usage:{self.sequence + 1}",
                    data,
                    {},
                    agent="Session naming · session-only",
                    session_only=True,
                )
                self.show_message(self.call_usage.costs(session_only=True), source="usage")
                self._checkpoint_auxiliary()
                if not self.naming_calls:
                    self.background("")
            return HookResult()
        if event.startswith("tool:") and self.tool_evidence:
            evidence = await self.tool_evidence.observe(
                event, data, session=self.session_id, turn=self.turn_id, agent="root"
            )
            if evidence:
                self.emit(
                    "change.observed",
                    f"{self.turn_id}:change:{evidence['tool_call_id']}",
                    **evidence,
                )
        block_id = str(data.get("block_index", data.get("block_id", "0")))
        if event == "llm:request":
            self.activity("Waiting for model")
        elif event in ("llm:response", "tool:pre"):
            self.activity("")
        elif event == "llm:stream_block_start":
            self.activity(
                {"thinking": "Thinking", "reasoning": "Thinking", "text": "Responding"}.get(
                    data.get("block_type"), ""
                )
            )
        elif event in ("llm:stream_block_end", "content_block:end"):
            self.activity("")
        if event in ("provider:retry", "provider:throttle"):
            fields = {
                k: v
                for k in ("attempt", "delay", "retry_after")
                if type(v := data.get(k)) in (int, float) and 0 <= v < 86400
            }
            label = "Provider retry" if event == "provider:retry" else "Provider throttling"
            self.activity(label)
            self.show_message(
                label
                + (
                    " · " + ", ".join(f"{k} {v}" for k, v in fields.items())
                    if fields
                    else " · waiting"
                ),
                level="warning",
                source="provider",
            )
            return HookResult()
        if event == "context:budget":
            observation = self.inspection.context_budget(data)
            self.emit(
                "context.observed",
                f"{self.turn_id}:budget:{self.sequence + 1}",
                event=event,
                name="Effective context budget",
                status="reported, not occupancy",
                observation=observation,
            )
            if "effective_budget" in observation:
                self.show_message(
                    f"Context budget: {observation['effective_budget']:,} tokens",
                    source="context",
                )
            return HookResult()
        if event == "orchestrator:goal_progress":
            if self.local_commands:
                self.emit("goal.status", "goal-status", **self.local_commands.goal_status())
            if self.session.coordinator.session_state.get("goal_circuit_breaker"):
                # The safety hook already published the terminal reason. Do
                # not follow it with the triggering event's stale "continuing".
                return HookResult()
            state = str(data.get("state", "unknown"))[:80]
            turn = data.get("turn", "unknown")
            cap = data.get("cap") or "unlimited"
            reason = str(data.get("reason") or "No evaluator reason reported")[:2000]
            self.show_message(f"Goal {state} · evaluated {turn}/{cap}\n{reason}", source="goal")
            return HookResult()
        if event == "llm:request":
            self.inspection.capture_request(data, self, f"{self.turn_id}:wire:{self.sequence + 1}")
            # Observe the provider's actual dispatch event, not orchestrator intent.
            # Raw wire payloads can contain secrets/images and are never copied here.
            fields = (
                "provider",
                "model",
                "message_count",
                "has_system",
                "thinking_enabled",
                "thinking_budget",
                "request_id",
            )
            self.emit(
                "context.observed",
                f"{self.turn_id}:wire:{self.sequence + 1}",
                event=event,
                name="Provider dispatch observation",
                status="dispatch observed; delivery not proven",
                observation={
                    k: data[k]
                    for k in fields
                    if k in data and isinstance(data[k], (str, int, bool, type(None)))
                },
                request_budget=self.inspection.request_budget(data),
            )
            return HookResult()
        if event == "mentions:resolved":
            for row in data.get("resolutions", [])[:256]:
                if not isinstance(row, dict):
                    continue
                observation = {
                    k: row.get(k)
                    for k in ("mention", "resolved_path", "source_type", "content_hash", "is_new")
                }
                identity = hashlib.sha256(
                    json.dumps(observation, sort_keys=True).encode()
                ).hexdigest()
                self.emit(
                    "context.observed",
                    f"instruction:{identity}",
                    event=event,
                    name=row.get("mention")
                    or row.get("resolved_path")
                    or "Resolved instruction source",
                    status="observed resolved",
                    observation=observation,
                )
            if data.get("failed") or len(data.get("resolutions", [])) > 256:
                self.emit(
                    "context.observed",
                    f"{self.turn_id}:instructions:{self.sequence + 1}",
                    event=event,
                    name="Instruction resolution limits/failures",
                    status="partial",
                    observation={"failed": data.get("failed", [])[:256], "partial": True},
                )
            return HookResult()
        if event in ("llm:response", "context:compaction", "context:tool_result_ingress_truncated"):
            # A response observation, not an orchestrator iteration: retries and
            # parallel provider calls can share that iteration. Replay keeps this
            # journal identity; opening views never creates another observation.
            usage_id = f"{self.turn_id}:usage:root:{self.sequence + 1}"
            if event == "llm:response":
                self.observe_usage(
                    usage_id,
                    data,
                    self.last_provider,
                )
            value = data.get("usage") if event == "llm:response" else data
            if value is not None:
                if hasattr(value, "model_dump"):
                    value = value.model_dump()
                if event == "llm:response":
                    add_usage(self.turn_usage, usage_values(value))
                    self.last_provider.update(
                        {k: data[k] for k in ("provider", "model") if isinstance(data.get(k), str)}
                    )
                self.emit(
                    "context.observed",
                    f"{self.turn_id}:context:{self.sequence + 1}",
                    event=event,
                    observation=value,
                    name=f"Request {self._request_index} usage"
                    if event == "llm:response"
                    else event,
                    status="Provider-reported completed-request usage; not current context occupancy"
                    if event == "llm:response"
                    else "observed",
                    request_index=self._request_index,
                    usage_id=usage_id if event == "llm:response" else None,
                    provider=data.get("provider"),
                    model=data.get("model"),
                )
            return HookResult()
        item_id = f"{self.turn_id}:request:{self._request_index}:block:{block_id}"
        if event == "provider:request":
            self._request_index += 1
            if self._request_index == 1 and self.capabilities["steer"]:
                self.emit("steering.ready", f"{self.turn_id}:steering")
        elif event == "provider:resolve" and data.get("scope") == "conversation":
            self.last_provider.update(
                {k: data[k] for k in ("provider", "model", "basis") if isinstance(data.get(k), str)}
            )
            self.emit(
                "provider.selected",
                f"{self.turn_id}:provider",
                **{key: data.get(key) for key in ("provider", "model", "basis", "scope")},
            )
        elif event == "orchestrator:steering_injected" and self.controls:
            self.controls.applied(data)
        elif event.startswith("llm:stream_block_") and data.get("block_type") in (
            "thinking",
            "reasoning",
        ):
            if event == "llm:stream_block_start":
                if self.retain_thinking(item_id):
                    self.thinking_blocks[item_id] = ""
                    self.thinking_emitted.pop(item_id, None)
            elif event == "llm:stream_block_delta" and isinstance(data.get("text"), str):
                value = self.thinking_blocks.get(item_id)
                if value is not None and len(value) < 32769:
                    self.thinking_blocks[item_id] = value + data["text"][: 32769 - len(value)]
            elif event == "llm:stream_block_end":
                if item_id in self.thinking_ids:
                    self.publish_thinking(item_id, self.thinking_blocks.pop(item_id, ""))
        elif event == "llm:stream_block_delta" and data.get("block_type", "text") == "text":
            text = data.get("text", "")
            self.blocks.add(item_id)
            self.emit("text.delta", item_id, text=text)
        elif event == "content_block:end":
            block = data.get("block", {})
            if not isinstance(block, dict) and hasattr(block, "model_dump"):
                block = block.model_dump()
            if block.get("type") == "text":
                self.blocks.add(item_id)
                self.emit("text.final", item_id, text=block.get("text", ""))
            elif block.get("type") in ("thinking", "reasoning"):
                text = block.get("thinking") or block.get("text")
                if isinstance(text, str) and text and self.retain_thinking(item_id):
                    self.publish_thinking(item_id, text)
        elif event.startswith("tool:"):
            item_id = f"{self.turn_id}:tool:{data.get('tool_call_id', 'unknown')}"
            result = data.get("result", {})
            if hasattr(result, "model_dump"):
                result = result.model_dump()
            parsed_result = tool_result(result)
            status = tool_status(event, result, parsed_result=parsed_result)
            outcome_source = "event"
            if self.children:
                status, outcome_source = self.children.observed_outcome(item_id, event, status)
            preview = tool_text(
                {
                    "name": data.get("tool_name", "unknown tool"),
                    "arguments": data.get("tool_input"),
                    "result": result,
                    "error": data.get("error"),
                },
                parsed_result=parsed_result,
            )
            if event == "tool:pre":
                self._tool_ids.add(item_id)
            else:
                self._tool_ids.discard(item_id)
            self.emit(
                "tool.updated",
                item_id,
                name=data.get("tool_name", "unknown tool"),
                status=status,
                arguments=data.get("tool_input"),
                result=result,
                error=data.get("error"),
                preview=preview,
                outcome_source=outcome_source,
            )
        elif event == "orchestrator:complete" and data.get("goal_final", True):
            self.outcome = data.get("status")
        return HookResult()

    async def request_approval(self, prompt, options, timeout, default):
        if self._stop_requested:
            return "deny"
        request_id = uuid.uuid4().hex
        if self.auto_deny_approvals:
            self.emit("approval.requested", request_id, prompt=prompt, options=options)
            self.emit("approval.resolved", request_id, reason="non-interactive denial")
            return "deny"
        future = asyncio.get_running_loop().create_future()
        self._pending[request_id] = (future, options)
        self.emit("approval.requested", request_id, prompt=prompt, options=options)
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            return "deny"
        finally:
            self._pending.pop(request_id, None)
            self.emit("approval.resolved", request_id)

    def answer(self, request_id, option):
        pending = self._pending.get(request_id)
        if not pending or pending[0].done() or option not in pending[1]:
            return False
        pending[0].set_result(option)
        return True

    def execution_uncertain(self):
        self._execution_uncertain = True
        self.ready = False
        self.emit(
            "display.message",
            f"{self.turn_id}:forced-cancel",
            text="Execution wait stopped without confirmed module completion. Effects remain uncertain; quit and use explicit recovery before new work.",
        )

    @property
    def stop_stage(self):
        if not self.task or self.task.done() or not self._stop_requested:
            return ""
        return "immediate" if self._force_requested else "graceful"

    def stop(self, *, immediate=True):
        """Signal the tree synchronously; only explicit escalation cancels awaits.

        Internal shutdown keeps its immediate default. Interactive Stop chooses
        the next stage; graceful calls have no deadline that secretly forces them.
        """
        if self.task is None or self.task.done():
            return False
        if self._force_requested or (self._stop_requested and not immediate):
            return True
        if (
            self._finalizing
            and not self._stop_requested
            and not (self.children and self.children.active)
        ):
            return False
        self._stop_requested = True
        self._force_requested = immediate
        cancellation = self.session.coordinator.cancellation
        if immediate:
            cancellation.request_immediate()
        else:
            cancellation.request_graceful()
        if self.children:
            self.children.stop(immediate=immediate)
        self.questions.cancel_all()
        for future, _ in self._pending.values():
            if not future.done():
                future.set_result("deny")
        # Cancelling a task before its first step skips its finally block. Let
        # an unstarted task enter _execute and publish its interrupted outcome.
        if immediate and self._execution_started and not self._finalizing:
            self.task.cancel()
        return True

    def publish_thinking(self, identity, text):
        excerpt = text[:32768] + ("\n[thinking excerpt]" if len(text) > 32768 else "")
        if excerpt and self.thinking_emitted.get(identity) != excerpt:
            self.thinking_emitted[identity] = excerpt
            self.emit(
                "display.message",
                f"thinking:{identity}",
                text=excerpt,
                level="info",
                source="thinking",
            )

    def retain_thinking(self, identity):
        if identity in self.thinking_ids:
            return True
        if len(self.thinking_ids) < 16:
            self.thinking_ids.add(identity)
            return True
        if not self.thinking_limited:
            self.thinking_limited = True
            self.show_message(
                "Thinking observations limited to 16 blocks for this turn; inspect provider evidence for other activity.",
                source="thinking",
            )
        return False

    def show_message(self, message, level="info", source="hook", **kwargs):
        from .children import parent_call

        origin = parent_call(self.session_id)
        if origin and level not in ("warning", "error"):
            self.emit(
                "activity.observed",
                f"{origin}:progress:{str(source)[:160]}",
                parent_item_id=origin,
                name=f"{str(source)[:160]} progress",
                event="display.message",
                status="observed",
                block={"type": "text", "text": str(message)},
            )
            return
        self.emit(
            "display.message",
            uuid.uuid4().hex,
            text=str(message),
            level=level if level in ("info", "warning", "error") else "info",
            source=str(source)[:160],
        )

    async def close(self):
        self._closed = True
        if self._close_task is None:
            # Apply intent before yielding to the cleanup owner. Otherwise a
            # freshly admitted turn can enter the runtime before Stop takes effect.
            self.stop()
            self._close_task = asyncio.create_task(self._close())
        cancelled = None
        while not self._close_task.done():
            try:
                await asyncio.shield(self._close_task)
            except asyncio.CancelledError as exc:
                # Keep the handle and lock until cleanup finishes. Cancellation of
                # a caller is reported afterwards, never forwarded into cleanup.
                cancelled = exc
        self._close_task.result()
        if cancelled is not None:
            raise cancelled

    async def _close(self):
        opening = self._opening
        if opening is not None and not opening.done():
            if not opening.cancelling():
                opening.cancel()
            result = (await asyncio.gather(opening, return_exceptions=True))[0]
            if isinstance(result, BaseException) and not isinstance(result, asyncio.CancelledError):
                raise result
        if self.task and not self.task.done():
            self.stop()
            await asyncio.gather(self.task, return_exceptions=True)
        if self.children:
            await self.children.drain()
        if self.session:
            await self.session.cleanup()
            self.session = None
        self.ready = False
        if self.store:
            self.store.close()


class RuntimeBridge:
    """Experimental presentation adapter over the existing execution authority.

    It is not a second orchestrator. Later host selection still owes full module
    swap, slow-reader durability and partial-initialization ownership evidence.
    """

    def __init__(self, host, opener, emit, fixture, cwd, store_factory=None):
        self.host, self.opener, self.emit = host, opener, emit
        self.fixture, self.cwd = fixture, cwd
        self.pump = None
        self.pending = None
        self.decisions = {}
        self.tools = {}
        self.store_factory = store_factory
        self.runtime_output = None
        self.failure = host.delivery_failed
        self.navigation_enabled = False
        self.bind_host_observations()

    def bind_host_observations(self):
        host = self.host

        def observed(kind, **payload):
            if self.host is host:
                self.emit({"type": kind, "session_id": host.session_id, **payload})

        host.background_callback = lambda phase: observed("background", phase=phase)
        host.activity_callback = lambda phase: observed(
            "model_activity", turn_id=host.turn_id, phase=phase
        )
        host.title_callback = lambda title: observed("title", text=title)

    async def open(self):
        self.host.interactive_questions = True
        if self.store_factory:
            store = self.store_factory()
            self.host.store = store
            self.host.session_id = store.identity
            self.host.sequence = store.saved["sequence"] if store.saved else 0
            self.host.inspection = Inspection(store.restored_events)
            self.host.call_usage = CallUsage(store.restored_events)
            self.host.capabilities["resume"] = True
        self.snapshot()
        self.pump = asyncio.create_task(self.events())
        await self.opener(self.host)

    def snapshot(self, reset=False):
        from .local_drafts import read

        drafts, draft_error = [], ""
        if self.host.store:
            try:
                drafts = read(self.host.store.path)
            except (ValueError, OSError) as exc:
                draft_error = f"Local editor recovery unavailable: {exc}. Original retained."
        self.emit(
            {
                "type": "snapshot",
                "ready": self.host.ready,
                "session_id": self.host.session_id,
                "reset": reset,
                "navigation": self.navigation_enabled,
                "mode": "FIXTURE RUNTIME" if self.fixture else "LIVE RUNTIME",
                "title": f"Amplifier / {self.host.session_id[:12]}",
                "context": self.cwd.name,
                "draft": self.host.store.draft if self.host.store else "",
                "items": self.host.store.projection() if self.host.store else [],
                "durable": self.host.store is not None,
                "local_drafts": drafts,
                "local_drafts_error": draft_error,
                "system": ["Preparing real bundle and module mounts…"],
            }
        )

    def turn_metrics(self):
        # Transient projection: no timer journal entries, token-history scans,
        # or money arithmetic in the renderer. Child and utility calls already
        # enter the identified ledger through observe_usage.
        self.emit(
            {
                "type": "turn_metrics",
                "session_id": self.host.session_id,
                "turn_id": self.host.turn_id,
                "elapsed_seconds": (
                    max(0, time.monotonic() - self.host._turn_started)
                    if self.host._turn_started is not None
                    else None
                ),
                **self.host.call_usage.progress(self.host.turn_id),
            }
        )

    def preserve_startup_draft(self, request):
        """Back up late-arriving restored text before replacing or submitting a draft."""
        from .local_drafts import save

        row = request.get("startup_backup")
        if row is None:
            return True, "No startup conflict"
        if request.get("session_id") != self.host.session_id:
            return False, "Startup draft belongs to another conversation"
        if not isinstance(row, dict) or row.get("kind") != "startup":
            return False, "Invalid startup draft backup"
        try:
            return save(self.host.store, {"row": row})
        except (ValueError, OSError) as exc:
            return (
                False,
                f"Startup draft backup failed: {exc}; original retained, copy new text before exiting",
            )

    def command(self, request):
        preserved, reason = self.preserve_startup_draft(request)
        if not preserved:
            return False, reason
        if request.get("op") in ("modes", "mode_select"):
            if not self.host.ready or self.host.modes is None:
                return False, "Mode controls require a ready session"
            if request.get("session_id") != self.host.session_id:
                return False, "Mode control belongs to another conversation"
        if request.get("op") == "modes":
            self.emit(
                {
                    "type": "modes",
                    "session_id": self.host.session_id,
                    "request_id": request.get("request_id"),
                    **self.host.modes.catalog(),
                    "select": request.get("select"),
                }
            )
            return True, "Discovered mode policy"
        if request.get("op") == "mode_select":
            return self.host.modes.select(request)
        op = request.get("op")
        if op == "inspect":
            if request.get("session_id") != self.host.session_id:
                return False, "Inspection belongs to another conversation"
            if request.get("category") == "runtime_output":
                self.emit(
                    {
                        "type": "inspection",
                        "session_id": self.host.session_id,
                        "request_id": request.get("request_id"),
                        "category": "runtime_output",
                        **(
                            self.runtime_output.catalog()
                            if self.runtime_output is not None
                            else {
                                "rows": [],
                                "partial": True,
                                "scope": "Runtime output capture unavailable in this host.",
                            }
                        ),
                    }
                )
                return True, "Private process diagnostics; no execution or journal writes"
            if request.get("category") not in (
                "changes",
                "recovery",
                "children",
                "context",
                "instructions",
                "activity",
                "activity_tree",
                "recipes",
                "recipe_files",
                "cli_sessions",
            ):
                return False, "Unknown inspection category"
            self.emit(
                {
                    "type": "inspection",
                    "session_id": self.host.session_id,
                    "request_id": request.get("request_id"),
                    "category": request["category"],
                    "child": request.get("child"),
                    **self.host.inspection.catalog(
                        self.host, request["category"], request.get("child")
                    ),
                }
            )
            return True, "Local observations only; no execution"
        if op == "editor_draft":
            from .local_drafts import save

            if request.get("session_id") != self.host.session_id:
                return False, "Local draft belongs to another conversation"
            try:
                return save(self.host.store, request)
            except (ValueError, OSError) as exc:
                return False, f"Local draft not saved: {exc}; copy text before exiting"
        if op in ("question_answer", "question_cancel"):
            if request.get("session_id") != self.host.session_id:
                return False, "Question belongs to a different conversation"
            return self.host.questions.answer(request)
        if op in ("steer", "provider_select", "providers"):
            if not self.host.controls:
                return False, "Runtime controls are not ready"
            if request.get("session_id") != self.host.session_id:
                return False, "Conversation identity required for runtime controls"
            if op == "steer":
                return self.host.controls.steer(request)
            result = (
                self.host.controls.select(request)
                if op == "provider_select"
                else (True, "Mounted provider choices")
            )
            self.emit(
                {
                    "type": "providers",
                    "request_id": request.get("request_id"),
                    "session_id": self.host.session_id,
                    **self.host.controls.catalog(),
                }
            )
            return result
        if op == "draft":
            if self.host.store and not self.host._closed and isinstance(request.get("text"), str):
                self.host.store.save_draft(request["text"])
                return True, "Draft saved"
            return False, "Draft storage unavailable"
        if op == "submit":
            text = request.get("text")
            if self.host.local_commands:
                self.host.local_commands.wire = self.emit
            return (
                self.host.submit(text, image_id=request.get("image_id"))
                if isinstance(text, str)
                else (False, "Text must be a string")
            )
        if op == "stop":
            accepted = self.host.stop(immediate=self.host._stop_requested)
            status = (
                "Stopping now; partial effects may remain"
                if self.host.stop_stage == "immediate"
                else "Finishing current calls; Ctrl-C again to force stop"
            )
            if accepted:
                self.emit(
                    {
                        "type": "state",
                        "session_id": self.host.session_id,
                        "turn_id": self.host.turn_id,
                        "ready": self.host.ready,
                        "busy": True,
                        "status": status,
                        "approval": self.pending,
                        "cancellation": self.host.stop_stage,
                    }
                )
            return accepted, status if accepted else "No active turn"
        if op == "decision":
            accepted = self.host.answer(request.get("approval_id"), request.get("option"))
            return accepted, "Decision accepted" if accepted else "Stale or invalid decision"
        return False, "Unsupported operation; inspect the host's advertised capabilities"

    async def events(self):
        while True:
            event = await self.host.next_event()
            data = event.payload
            metadata = {
                "session_id": event.session_id,
                "sequence": event.sequence,
                "turn_id": event.turn_id,
            }

            def emit(value):
                self.emit({**metadata, **value})

            def state(status):
                emit(
                    {
                        "type": "state",
                        "ready": self.host.ready,
                        "status": status,
                        "approval": self.pending,
                        "busy": event.kind not in ("session.ready", "turn.ended"),
                        "cancellation": self.host.stop_stage,
                    }
                )

            if event.kind == "session.ready":
                emit({"type": "mode_status", **data.get("mode_control", {})})
                emit({"type": "goal_status", **data.get("goal_control", {})})
                system = [
                    "Effective composition · observed mounts",
                    f"Running app: {data.get('app_version', 'unknown historical version')} · native product",
                    f"Bundle: {data.get('bundle')}",
                    f"Providers: {', '.join(data.get('providers', []))}",
                    "Tools (mounted; use them by asking in the conversation):",
                    *[f"  • {name}" for name in data.get("tools", [])],
                    "",
                    f"Agents (host-owned delegation; {self.host.children.capacity} active per parent, cancellable capacity waits; depth follows module policy):"
                    if self.host.children
                    else "Agents (delegation unavailable):",
                    *[f"  • {name}" for name in data.get("agents", [])],
                    "",
                    "Skills (discovered, not automatically loaded):",
                    data.get("skills_note", "Discovery unavailable"),
                    *[
                        f"  • {skill['name']} — {skill['description']}"
                        for skill in data.get("skills", [])
                    ],
                    "",
                    "Modes: Actions → Modes; model-initiated gated changes request a scoped decision.",
                    *[
                        f"{name}: {policy}"
                        for name, policy in data.get("storage_policy", {}).items()
                    ],
                    f"Excluded terminal hooks: {data.get('excluded_terminal_hooks', [])}",
                    "Queue: Actions → Queue draft / Pending follow-ups; delegation enabled"
                    if self.navigation_enabled
                    else "Queue / delegated execution: unavailable",
                    "Steering: Actions → Correct active turn after the first provider request"
                    if data.get("capabilities", {}).get("steer")
                    else "Steering: unavailable; no public capability mounted",
                    "Resume: Actions → Resume / New conversation; workspace paths: ./ then Tab (names only)"
                    if self.navigation_enabled
                    else f"Resume: scripts/run.py --resume {self.host.session_id} (same --state-dir)"
                    if self.host.store
                    else "Resume: unavailable in this launch",
                    f"Settings policy: {data.get('settings_policy', 'isolated')}; configuration changes require a new launch. Existing conversations retain their recorded policy.",
                    "",
                    "Actions → Composition details shows origins, overrides and registered hooks.",
                ]
                emit(
                    {
                        "type": "system",
                        "lines": system,
                        "skills": [skill["name"] for skill in data.get("skills", [])],
                        "commands": data.get("commands", []),
                        "mode_names": [
                            m["name"] for m in data.get("mode_control", {}).get("choices", [])
                        ],
                        "steer": data.get("capabilities", {}).get("steer", False),
                        "conversation_provider": data.get("conversation_provider", {}),
                        "diagnostics": json.dumps(
                            data, ensure_ascii=False, indent=2, default=str
                        ).splitlines(),
                    }
                )
                state("Ready · real modules mounted")
            elif event.kind == "turn.accepted":
                if self.navigation_enabled and self.host.store:
                    emit(
                        {
                            "type": "title",
                            "text": self.host.store.metadata.get("title", "Untitled conversation"),
                        }
                    )
                emit(
                    {
                        "type": "item",
                        "id": event.item_id,
                        "kind": "user",
                        "text": data["text"],
                        "input_id": data.get("input_id"),
                        "status": "",
                        "detail": "",
                    }
                )
                state("Working · draft stays editable")
            elif event.kind == "text.delta":
                emit({"type": "delta", "id": event.item_id, "text": data["text"]})
            elif event.kind == "provider.selected":
                emit({"type": "provider_observed", **data})
            elif event.kind == "steering.ready":
                emit({"type": "steering_ready"})
            elif event.kind == "steering.updated":
                emit(
                    {
                        "type": "item",
                        "id": event.item_id,
                        "kind": "correction",
                        "text": data["text"],
                        "status": data["status"],
                        "detail": json.dumps(data, ensure_ascii=False),
                    }
                )
            elif event.kind == "question.updated":
                emit(
                    {
                        "type": "item",
                        "id": event.item_id,
                        "kind": "question",
                        "text": data["text"],
                        "status": data["status"],
                        "detail": json.dumps(data, ensure_ascii=False),
                    }
                )
                emit({"type": "question", "id": event.item_id, **data})
            elif event.kind == "modes.updated":
                # A typed command has no menu request to complete. Its ordinary
                # mode.status event updates the badge without stealing focus.
                if data.get("request_id") is not None:
                    emit({"type": "modes", **data})
            elif event.kind == "mode.status" and event.item_id == "mode-status":
                emit({"type": "mode_status", **data})
            elif event.kind == "goal.status":
                emit({"type": "goal_status", **data})
            elif event.kind in ("control.started", "control.finished"):
                emit(
                    {
                        "type": "state",
                        "ready": self.host.ready,
                        "busy": event.kind == "control.started",
                        "status": data["message"],
                        "approval": self.pending,
                    }
                )
            elif event.kind == "text.final":
                emit(
                    {
                        "type": "item",
                        "id": event.item_id,
                        "kind": "assistant",
                        "text": data["text"],
                        "status": "",
                        "detail": "",
                    }
                )
            elif event.kind.startswith("tool."):
                detail = self.tools.setdefault(event.item_id, {})
                detail.update({key: value for key, value in data.items() if value is not None})
                emit(
                    {
                        "type": "item",
                        "id": event.item_id,
                        "kind": "tool",
                        "text": tool_text(detail),
                        "status": detail.get("status", "unknown"),
                        "detail": json.dumps(detail, ensure_ascii=False, indent=2, default=str),
                    }
                )
            elif event.kind == "approval.requested":
                self.decisions[event.item_id] = {
                    "id": event.item_id,
                    "prompt": "Approval requested by runtime policy",
                    "command": str(data["prompt"]),
                    "options": data["options"],
                }
                self.pending = next(iter(self.decisions.values()), None)
                state("Waiting for your decision")
            elif event.kind == "approval.resolved":
                self.decisions.pop(event.item_id, None)
                self.pending = next(iter(self.decisions.values()), None)
                state(
                    "Waiting for your decision" if self.pending else "Working · decision resolved"
                )
            elif event.kind == "turn.ended":
                from .cli_compat import skill_commands

                emit({"type": "commands", "commands": skill_commands(self.host.session)})
                emit(
                    {
                        "type": "item",
                        "id": event.item_id,
                        "kind": "outcome",
                        "text": data["message"],
                        "status": data["status"],
                        "detail": "",
                    }
                )
                state(f"{data['status'].capitalize()} · {data['message']}")
            elif event.kind == "display.message":
                emit(
                    {
                        "type": "item",
                        "id": event.item_id,
                        "kind": "notice",
                        "text": message_text(data),
                        "status": data.get("level", ""),
                        "detail": json.dumps(data, ensure_ascii=False, default=str),
                    }
                )
            if event.turn_id == self.host.turn_id and (
                event.kind in ("turn.accepted", "turn.ended", "session.ready")
                or (event.kind == "display.message" and "usage_call" in data)
            ):
                self.turn_metrics()

    async def close(self):
        await self.host.close()
        if self.pump:
            # Drain already emitted terminal outcomes before stopping the adapter.
            await asyncio.sleep(0)
            self.pump.cancel()
            await asyncio.gather(self.pump, return_exceptions=True)

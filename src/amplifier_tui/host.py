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
from .events import Event
from .inspection import Inspection
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
        self.ready = False
        self.report = {}
        self.outcome = None
        self.observed_tools = {"root": {}, "children": {}}
        self.blocks: dict[str, str] = {}
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
        self._request_index = 0
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
        self.inspection.observe(event)
        if kind in ("tool.updated", "tool.ended") and not item_id.startswith("child:"):
            self.observed_tools["root"][item_id] = payload.get("status", "unknown")
        elif kind == "child.observed" and payload.get("event", "").startswith("tool:"):
            # Child observers use separate pre/post/error event IDs. Count calls,
            # not event occurrences or the parent's aggregate delegation card.
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
        self.fingerprint = hashlib.sha256(
            json.dumps(prepared.mount_plan, sort_keys=True, default=str).encode()
        ).hexdigest()
        if self.store and self.store.saved and self.store.saved["fingerprint"] != self.fingerprint:
            raise ValueError("Effective module configuration changed; resume refused")
        diagnostics = InitializationDiagnostics()
        initializer = logging.getLogger("amplifier_core._session_init")
        initializer.addHandler(diagnostics)
        self._opening = asyncio.current_task()
        try:
            from .composition import create_owned_session

            self.session = await create_owned_session(
                prepared,
                session_id=self.session_id,
                session_cwd=cwd,
                approval_system=self,
                display_system=self,
                observer=self._observe,
            )
            if self._closed:
                raise RuntimeError("Session was closed during startup")
            if diagnostics.failed:
                raise RuntimeError("Module initialization reported a failure; inspect diagnostics")
            coordinator = self.session.coordinator
            from .workspace_review import ToolEvidence

            self.tool_evidence = ToolEvidence(cwd, self.store.restored_events if self.store else ())
            from .file_input import ImageDraft

            self.images = ImageDraft(self.store)
            for point in ("orchestrator", "context", "providers"):
                if not coordinator.get(point):
                    raise RuntimeError(f"Required mount missing: {point}")
            if self.store:
                context = coordinator.get("context")
                if not all(
                    callable(getattr(context, name, None))
                    for name in ("get_messages", "set_messages")
                ):
                    raise RuntimeError("Context module does not support canonical history resume")
                if self.store.saved:
                    await context.set_messages(copy.deepcopy(self.store.saved["messages"]))
                    if portable_history(await context.get_messages()) != portable_history(
                        self.store.saved["messages"]
                    ):
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
                        imported.get("messages"), imported.get("source_session")
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
            self.capabilities["modes"] = self.modes.supported
            if self.interactive_questions:
                coordinator.register_capability("user.questions", self.questions.ask)
            self.capabilities["questions"] = self.interactive_questions
            if self.delivery_failed.is_set():
                raise RuntimeError("Source event delivery failed during startup")
            self.ready = True
            # Optional module discovery, not a frontend import or private dict.
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
                "skills_note": skills_note,
                "conversation_provider": self.controls.catalog(),
                "mode_control": self.modes.catalog(),
            }
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
        self, text: str, input_id=None, image_id=None, queued_image=None, *, operation=None
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
        self.questions.count = 0
        self.outcome = None
        self.observed_tools = {"root": {}, "children": {}}
        self.blocks = {}
        self._execution_started = False
        self._finalizing = False
        self._tool_ids = set()
        self._stop_requested = False
        self._request_index = 0
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
        self.task = asyncio.create_task(self._execute(text, image, operation))
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

    async def _execute(self, text, image=None, operation=None):
        self._execution_started = True
        status, message = "unknown", "No completion evidence was received."
        try:
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
                reply = await execute_owned(
                    self.session,
                    text,
                    on_forced=lambda: self.emit(
                        "display.message",
                        f"{self.turn_id}:forced-cancel",
                        text="Cooperative Stop grace expired; execution wait cancelled. Tool effects may remain.",
                    ),
                )
            else:
                context = self.session.coordinator.get("context")
                await context.add_message({"role": "user", "content": text})
                reply = await operation()
                await context.add_message({"role": "assistant", "content": reply})
                self.outcome = "success"
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
        except asyncio.CancelledError:
            status, message = (
                "interrupted",
                "Stopped. Partial effects may remain; nothing was undone.",
            )
        except Exception as exc:
            status, message = "failed", f"{type(exc).__name__}: {exc}"
        finally:
            self._finalizing = True
            if self.children and self.children.active:
                if status == "completed":
                    status, message = (
                        "incomplete",
                        "Child work remained active; stopped and drained before checkpoint",
                    )
                await self.children.drain()
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
            self.emit(
                "turn.ended", f"{self.turn_id}:outcome", status=status, message=message, tools=tools
            )
            if self.store:
                try:
                    messages = await self.session.coordinator.get("context").get_messages()
                    self.store.checkpoint(
                        messages,
                        self.sequence,
                        self.fingerprint,
                        status == "completed" and self.ready,
                    )
                except Exception:
                    self.ready = False
                    self.emit(
                        "display.message",
                        uuid.uuid4().hex,
                        text="Checkpoint failed; resume is unavailable. No work will be replayed.",
                    )
        return status

    async def _observe(self, event, data):
        if self.validation_active:
            # Standalone access probes cannot masquerade as conversation activity.
            return HookResult()
        # Child activity must never impersonate the root conversation.
        if data.get("session_id") not in (None, "", self.session_id):
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
            value = data.get("usage") if event == "llm:response" else data
            if value is not None:
                if hasattr(value, "model_dump"):
                    value = value.model_dump()
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
            self.emit(
                "provider.selected",
                f"{self.turn_id}:provider",
                **{key: data.get(key) for key in ("provider", "model", "basis", "scope")},
            )
        elif event == "orchestrator:steering_injected" and self.controls:
            self.controls.applied(data)
        elif event == "llm:stream_block_delta" and data.get("block_type", "text") == "text":
            text = data.get("text", "")
            self.blocks[item_id] = self.blocks.get(item_id, "") + text
            self.emit("text.delta", item_id, text=text)
        elif event == "content_block:end":
            block = data.get("block", {})
            if not isinstance(block, dict) and hasattr(block, "model_dump"):
                block = block.model_dump()
            if block.get("type") == "text":
                self.blocks[item_id] = block.get("text", "")
                self.emit("text.final", item_id, text=self.blocks[item_id])
        elif event.startswith("tool:"):
            item_id = f"{self.turn_id}:tool:{data.get('tool_call_id', 'unknown')}"
            result = data.get("result", {})
            if hasattr(result, "model_dump"):
                result = result.model_dump()
            status = "running"
            if event == "tool:pre":
                self._tool_ids.add(item_id)
            else:
                self._tool_ids.discard(item_id)
                status = "failed" if event == "tool:error" else "unknown"
                if isinstance(result, dict) and event == "tool:post":
                    if result.get("success") is True:
                        status = "succeeded"
                    elif result.get("success") is False or result.get("error"):
                        status = "failed"
            self.emit(
                "tool.updated",
                item_id,
                name=data.get("tool_name", "unknown tool"),
                status=status,
                arguments=data.get("tool_input"),
                result=result,
                error=data.get("error"),
            )
        elif event == "orchestrator:complete" and data.get("goal_final", True):
            self.outcome = data.get("status")
        return HookResult()

    async def request_approval(self, prompt, options, timeout, default):
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

    def stop(self):
        if self.task is None or self.task.done():
            return False
        if self._stop_requested:
            # Repeated controls must not inject cancellation into the first
            # Stop's checkpoint, child draining or other finalization awaits.
            return True
        if self._finalizing:
            # A completed execution is no longer cancellable work. Its checkpoint
            # and child accounting must finish even if Stop arrives at this await.
            return False
        self._stop_requested = True
        if self.children:
            self.children.stop()
        self.questions.cancel_all()
        self.session.coordinator.cancellation.request_immediate()
        for future, _ in self._pending.values():
            if not future.done():
                future.set_result("deny")
        # Cancelling a task before its first step skips its finally block. Let
        # an unstarted task enter _execute and publish its interrupted outcome.
        if self._execution_started:
            self.task.cancel()
        return True

    def show_message(self, message, level="info", source="hook", **kwargs):
        self.emit("display.message", uuid.uuid4().hex, text=str(message))

    async def close(self):
        self._closed = True
        self.ready = False
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
        self.failure = host.delivery_failed
        self.navigation_enabled = False

    async def open(self):
        self.host.interactive_questions = True
        if self.store_factory:
            store = self.store_factory()
            self.host.store = store
            self.host.session_id = store.identity
            self.host.sequence = store.saved["sequence"] if store.saved else 0
            self.host.inspection = Inspection(store.restored_events)
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
            if request.get("category") not in (
                "changes",
                "recovery",
                "children",
                "context",
                "instructions",
                "activity",
                "recipes",
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
            return (
                self.host.submit(text, image_id=request.get("image_id"))
                if isinstance(text, str)
                else (False, "Text must be a string")
            )
        if op == "stop":
            accepted = self.host.stop()
            return accepted, "Stop requested; nothing was undone" if accepted else "No active turn"
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
                    }
                )

            if event.kind == "session.ready":
                emit({"type": "mode_status", **data.get("mode_control", {})})
                system = [
                    "Effective composition · observed mounts",
                    f"Running app: {data.get('app_version', 'unknown historical version')} · native product",
                    f"Bundle: {data.get('bundle')}",
                    f"Providers: {', '.join(data.get('providers', []))}",
                    "Tools (mounted; use them by asking in the conversation):",
                    *[f"  • {name}" for name in data.get("tools", [])],
                    "",
                    "Agents (host-owned delegation; 4 active / 32 retained / depth 3):",
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
                    "Conversation provider: Actions → Conversation provider (when supported). Other configuration needs a new launch; no implicit CLI settings import.",
                    "",
                    "Actions → Composition details shows origins, overrides and registered hooks.",
                ]
                emit(
                    {
                        "type": "system",
                        "lines": system,
                        "skills": [skill["name"] for skill in data.get("skills", [])],
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
                emit({"type": "modes", **data})
            elif event.kind == "mode.status" and event.item_id == "mode-status":
                emit({"type": "mode_status", **data})
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
                        "text": detail.get("name", "Unknown tool"),
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
                        "text": data["text"],
                        "status": "",
                        "detail": "",
                    }
                )

    async def close(self):
        await self.host.close()
        if self.pump:
            # Drain already emitted terminal outcomes before stopping the adapter.
            await asyncio.sleep(0)
            self.pump.cancel()
            await asyncio.gather(self.pump, return_exceptions=True)

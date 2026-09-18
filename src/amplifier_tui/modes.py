"""Explicit mode decisions over the composed mode tool; never write active_mode directly."""

import asyncio
import copy
import hashlib
import json
import uuid
from dataclasses import asdict

from amplifier_core import HookResult, ToolResult

from .conversations import atomic_json


class ModeToolAdapter:
    def __init__(self, owner, tool):
        self.owner, self.tool = owner, tool
        self.name, self.description, self.input_schema = (
            tool.name,
            tool.description,
            tool.input_schema,
        )

    async def execute(self, input):
        return await self.owner.execute(input)


class Modes:
    def __init__(self, host):
        self.host = host
        self.coordinator = host.session.coordinator
        self.tool = (self.coordinator.get("tools") or {}).get("mode")
        self.discovery = self.coordinator.session_state.get("mode_discovery")
        self.supported = (
            self.tool is not None
            and self.discovery is not None
            and self.tool.__class__.__module__ == "amplifier_module_tool_mode"
        )
        self.path = host.store.path / "modes.json" if host.store else None
        self.failed = False
        self.lock = asyncio.Lock()
        self.observation_revision = uuid.uuid4().hex

    def current(self):
        return self.coordinator.session_state.get("active_mode")

    def digest(self, name):
        mode = self.discovery.find(name) if name else None
        if name and not mode:
            raise ValueError("Saved mode definition unavailable")
        return hashlib.sha256(
            json.dumps(asdict(mode) if mode else None, sort_keys=True, default=str).encode()
        ).hexdigest()

    def save(self, status):
        if self.path:
            atomic_json(
                self.path,
                {
                    "version": 1,
                    "status": status,
                    "mode": self.current(),
                    "definition": self.digest(self.current()),
                },
            )

    async def open(self):
        async def failed(event, data):
            self.failed = True
            self.host.ready = False
            self.coordinator.cancellation.request_immediate()
            return HookResult()

        self.coordinator.hooks.register(
            "mode:activation_failed", failed, priority=999, name="tui-mode-failure"
        )
        if self.path and self.path.exists():
            value = json.loads(self.path.read_text())
            if (
                not self.supported
                or value.get("version") != 1
                or value.get("status") != "ready"
                or value.get("definition") != self.digest(value.get("mode"))
            ):
                raise ValueError("Saved mode state is incompatible or uncertain; recovery required")
            if value["mode"]:
                result = await self.apply({"operation": "set", "name": value["mode"]})
                if not result.success or self.current() != value["mode"]:
                    raise ValueError("Saved mode could not be restored")
        elif self.host.store and self.host.store.metadata.get("mode_controls"):
            raise ValueError("Saved mode state missing; recovery required")
        if self.supported:

            async def current_observation(_event, _data):
                # Local controls are not model turns. Older tool results can still
                # describe an earlier mode, so expose current module state at the
                # request boundary without rewriting history or granting authority.
                return HookResult(
                    action="inject_context",
                    context_injection=(
                        "TUI current mode observation: "
                        + (self.current() or "default (no named mode active)")
                        + ". This is the current module state; earlier conversation mode "
                        "statements may be historical. This observation grants no permissions "
                        "and does not replace the module's tool/transition policy."
                        f" Observation revision: {self.observation_revision}."
                    ),
                    context_injection_role="system",
                    ephemeral=True,
                )

            self.coordinator.hooks.register(
                "provider:request", current_observation, priority=99, name="tui-mode-observation"
            )
            await self.coordinator.mount("tools", ModeToolAdapter(self, self.tool), name="mode")
            if self.host.store:
                self.save("ready")
                self.host.store.metadata["mode_controls"] = True
                atomic_json(self.host.store.path / "metadata.json", self.host.store.metadata)

    def authorized_tool(self):
        # One explicitly authorized transition. Its original transition/allow_clear
        # checks and hooks still execute; the mounted gate policy is never changed.
        return type(self.tool)(
            {**copy.deepcopy(self.tool.config), "gate_policy": "auto"}, self.coordinator
        )

    async def apply(self, input):
        result = await self.authorized_tool().execute(input)
        if self.failed:
            raise ValueError("Mode activation failed; stop and recover before further work")
        return result

    def catalog(self):
        return {
            "supported": self.supported,
            "current": self.current(),
            "choices": [
                {"name": m.name, "description": m.description} for m in self.discovery.list_modes()
            ]
            if self.supported
            else [],
        }

    async def execute(self, input, *, explicit=False):
        if input.get("operation") not in ("set", "clear"):
            return await self.tool.execute(input)
        controls = self.host.local_commands
        if controls and controls.state["disabled"]:
            return ToolResult(
                success=False,
                error={
                    "message": "Re-enable locally disabled tools before changing mode; mode transitions can restore their own tool policy"
                },
            )
        async with self.lock:
            if self.failed or self.host._stop_requested:
                return ToolResult(
                    success=False,
                    error={"message": "Mode control unavailable after stop/storage failure"},
                )
            gate = self.tool.config.get("gate_policy", "warn")
            if not explicit and gate != "auto":
                answer = await self.host.request_approval(
                    f"Change mode from {self.current() or 'default'} to {input.get('name') or 'default'}? This changes tool policy for this session.",
                    ["Change mode", "Keep current mode"],
                    600,
                    "Keep current mode",
                )
                if answer != "Change mode" or self.host._stop_requested:
                    return ToolResult(
                        success=False,
                        output={
                            "status": "denied",
                            "message": "Mode unchanged; user did not authorize this transition",
                        },
                    )
            try:
                self.save("pending")
                result = await self.apply(input)
                self.save("ready")
                self.host.emit("mode.status", "mode-status", current=self.current(), supported=True)
                self.host.emit(
                    "display.message", uuid.uuid4().hex, text=f"Mode: {self.current() or 'default'}"
                )
                # Returning to a previous mode is a NEW observation. Content-only
                # deduplication must not leave an older mode reminder last in context.
                if result.success:
                    self.observation_revision = uuid.uuid4().hex
                return result
            except BaseException:
                self.failed = True
                self.host.ready = False
                raise

    def select(self, request):
        host = self.host
        if not self.supported or not host.ready or (host.task and not host.task.done()):
            return False, "Finish the active turn before changing mode"
        if request.get("current") != self.current():
            return False, "Mode changed; reopen Modes"
        name = request.get("mode")
        if name is not None and name not in {m.name for m in self.discovery.list_modes()}:
            return False, "Choose a discovered mode"
        host._stop_requested = False
        host._force_requested = False
        self.coordinator.cancellation.reset()
        host._execution_started = False
        host._finalizing = False
        host.task = asyncio.create_task(self.change(name, request.get("request_id")))
        return True, "Applying your mode choice through module policy"

    async def change(self, name, request_id):
        try:
            self.host._execution_started = True
            self.host.emit("control.started", "mode-control", message="Applying mode policy")
            if self.host._stop_requested:
                raise asyncio.CancelledError
            # Native user intent is explicit authorization, not an assistant retry.
            result = await self.execute(
                {"operation": "set" if name else "clear", "name": name}, explicit=True
            )
            self.host.emit(
                "display.message",
                uuid.uuid4().hex,
                text=(
                    f"Mode: {self.current() or 'default'} · policy applied"
                    if result.success
                    else f"Mode change failed: {result.error or result.output}"
                ),
                source="mode",
                level="info" if result.success else "error",
                observation=result.output if result.success else result.error or result.output,
            )
        except Exception as exc:
            self.host.show_message(f"Mode change failed: {exc}")
        finally:
            self.host._finalizing = True
            self.host.emit("modes.updated", "modes", **self.catalog(), request_id=request_id)
            try:
                messages = (
                    await self.coordinator.get("context").get_messages()
                    if self.host.store
                    else None
                )
                self.host.emit(
                    "control.finished",
                    "mode-control",
                    message=f"Mode command finished · {self.current() or 'default'}",
                )
                # No await between the terminal observation and synchronous
                # checkpoint: delivery cannot advertise completion early, and
                # the final journal event must be included in the saved sequence.
                if self.host.store:
                    self.host.store.checkpoint(
                        messages, self.host.sequence, self.host.fingerprint, self.host.ready
                    )
            except Exception:
                self.host.ready = False
                self.host.show_message(
                    "Mode checkpoint failed; resume unavailable, no automatic retry"
                )
                raise

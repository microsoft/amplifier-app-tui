"""Explicit host composition policy over Foundation's public bundle API."""

from __future__ import annotations

import asyncio
import copy
import json
import os
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from amplifier_foundation import BundleRegistry, load_bundle

# These modules write directly to Rich/stdout. Other policy hooks are retained.
TERMINAL_HOOKS = {"hooks-streaming-ui", "hooks-todo-display"}


class ExecutionOwner:
    """Own the actual module coroutine across a native session-await boundary.

    The kernel still dispatches and emits lifecycle events; the module still owns
    execution policy. Cancelling only the native awaiter does not join its Python
    callback. Track and join that callback's work through the public mount seam.
    """

    def __init__(self, module):
        self.module = module
        self.tasks = set()

    def __getattr__(self, name):
        return getattr(self.module, name)

    async def execute(self, *args, **kwargs):
        task = asyncio.ensure_future(self.module.execute(*args, **kwargs))
        self.tasks.add(task)
        try:
            return await task
        finally:
            self.tasks.discard(task)

    def stop(self):
        for task in self.tasks:
            task.cancel()


async def execute_owned(session, prompt, *, grace=0.25, on_forced=None, operation=None):
    """Retain execution ownership while cooperative cancellation records its outcome.

    Cancelling the Rust-backed wait can return before Python callbacks have drained.
    Give the public cancellation token a bounded grace, then cancel and join the
    owned module task. If that ownership is unavailable, cancel the native wait
    and disclose uncertainty. Repeated caller cancellation neither abandons work
    nor extends that grace. An
    uncooperative module still requires the client's separately owned process deadline.
    """
    execution = asyncio.ensure_future(
        operation() if operation is not None else session.execute(prompt)
    )
    try:
        return await asyncio.shield(execution)
    except asyncio.CancelledError:
        session.coordinator.cancellation.request_immediate()
        deadline = asyncio.get_running_loop().time() + grace
        forced = False
        while not execution.done():
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0 and not forced:
                forced = True
                get = getattr(session.coordinator, "get", None)
                owner = get("orchestrator") if get else None
                if isinstance(owner, ExecutionOwner) and owner.tasks:
                    owner.stop()
                else:
                    if on_forced:
                        on_forced()
                    execution.cancel()
            try:
                if forced:
                    await asyncio.shield(execution)
                else:
                    await asyncio.wait({execution}, timeout=remaining)
            except asyncio.CancelledError:
                continue
            except Exception:
                break
        # Retrieve the outcome even when the caller was cancelled. Cancellation is
        # never converted to a successful turn by a late cooperative return.
        if not execution.cancelled():
            execution.exception()
        raise


async def create_owned_session(
    prepared, *, session_cwd=None, observer=None, interactive_approval=False, **kwargs
):
    """Own cleanup before the first await, using public kernel/Foundation APIs.

    Foundation's convenience factory returns only after initialization. This
    app-side assembly keeps its resolver, namespace, prompt and logging policy,
    but owns the handle on mount failure/cancellation. No global monkeypatch.
    """
    from dataclasses import replace

    from amplifier_core import AmplifierSession
    from amplifier_foundation import inject_additional_events
    from amplifier_foundation.mentions import BaseMentionResolver, ContentDeduplicator

    plan = copy.deepcopy(prepared.mount_plan)
    inject_additional_events(plan, ("session:config", "mentions:resolved"))
    session = AmplifierSession(plan, **kwargs)
    try:
        await session.coordinator.mount("module-source-resolver", prepared.resolver)
        coordinator = session.coordinator
        # Application transport capability, not permission to execute. Modules
        # still return ask_user and the kernel waits for the actual decision.
        coordinator.register_capability("approval.interactive", interactive_approval is True)
        if prepared.bundle_package_paths:
            coordinator.register_capability(
                "bundle_package_paths", list(prepared.bundle_package_paths)
            )
        bundle = prepared.bundle
        cwd = session_cwd or bundle.base_path or Path.cwd()
        coordinator.register_capability("session.working_dir", str(cwd.resolve()))
        namespaces = dict(bundle.source_base_paths or {})
        if bundle.name:
            namespaces.setdefault(bundle.name, bundle.base_path)
        resolver = BaseMentionResolver(
            bundles={
                name: replace(bundle, base_path=path or bundle.base_path)
                for name, path in namespaces.items()
                if name
            },
            base_path=cwd,
        )
        coordinator.register_capability("mention_resolver", resolver)
        coordinator.register_capability("mention_deduplicator", ContentDeduplicator())
        if observer:
            coordinator.hooks.register(
                "mentions:resolved", observer, priority=999, name="tui-instruction-source"
            )
        await session.initialize()
        from amplifier_core import HookResult

        async def stopped_tool(_event, _data):
            if coordinator.cancellation.is_cancelled:
                return HookResult(action="deny", reason="Stopped before execution")
            return HookResult()

        # Public hook covers immutable foreign tools too. The invocation adapter
        # also checks immediately before execute, after any asynchronous policy.
        coordinator.hooks.register("tool:pre", stopped_tool, priority=-1000, name="tui-stop-gate")
        orchestrator = coordinator.get("orchestrator")
        if orchestrator is not None:
            await coordinator.mount("orchestrator", ExecutionOwner(orchestrator))
        if "recipes" in (coordinator.get("tools") or {}):

            async def recipe_guidance(_event, _data):
                if "recipes" not in (coordinator.get("tools") or {}):
                    return HookResult()
                return HookResult(
                    action="inject_context",
                    context_injection=(
                        "Recipe discovery: recipes(operation='list') lists active recipe sessions, "
                        "NOT available recipe files. An empty sessions list does not mean no recipes "
                        "exist. Use the bundle's documented recipe namespace or inspect local recipe "
                        "folders with glob/read_file, then validate the selected recipe and required "
                        "inputs. Distinguish finding, validating and executing. Never claim a recipe "
                        "ran from a list/validate result. Honor the user's execution scope and approvals."
                    ),
                    context_injection_role="system",
                    ephemeral=True,
                )

            coordinator.hooks.register(
                "provider:request", recipe_guidance, priority=40, name="tui-recipe-discovery"
            )
        bundle.resolve_pending_context()
        coordinator.register_capability(
            "hook_metadata",
            {
                name: {"event": event}
                for event, names in coordinator.hooks.list_handlers().items()
                for name in names
            },
        )
        # Unconditionally bind the public factory. Empty bundles produce an empty
        # prompt; pending context was resolved above without accessing private fields.
        coordinator.register_contributor(
            "observability.events", "foundation:mention-resolver", lambda: ["mentions:resolved"]
        )
        factory = prepared.create_system_prompt_factory(session, session_cwd=session_cwd)
        context = coordinator.get("context")
        if context and callable(getattr(context, "set_system_prompt_factory", None)):
            await context.set_system_prompt_factory(factory)
        elif context:
            prompt = await factory()
            if prompt:
                await context.add_message({"role": "system", "content": prompt})
        return session
    except BaseException:
        # A second cancellation cannot abandon a partially initialized session.
        cleanup = asyncio.ensure_future(session.cleanup())
        while not cleanup.done():
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                continue
        cleanup.result()
        raise


def expand_environment(value, *, required=False):
    """Expand module config only, not prompts or deferred child configuration."""
    if isinstance(value, dict):
        return {key: expand_environment(item, required=required) for key, item in value.items()}
    if isinstance(value, list):
        return [expand_environment(item, required=required) for item in value]
    if not isinstance(value, str):
        return value

    def replace(match):
        name, default = match.groups()
        if name in os.environ:
            return os.environ[name]
        if default is not None:
            return default
        if required:
            raise ValueError(f"Required environment variable is unset: {name}")
        return ""

    return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::([^}]*))?\}", replace, value)


class SourceMap:
    """Explicit local overrides; namespace resolution remains Foundation's job."""

    def __init__(self, paths: dict[str, str] | None = None):
        self.paths = paths or {}

    @classmethod
    def read(cls, path: Path | None):
        if path is None:
            return cls()
        values = json.loads(path.read_text())
        return cls({key: str((path.parent / value).resolve()) for key, value in values.items()})

    def resolve(self, source: str) -> str | None:
        if source in self.paths:
            return self.paths[source]
        if not source.startswith("git+https://"):
            return None
        parsed = urlparse(source[4:])
        repo, _, _ref = parsed.path.partition("@")
        key = f"https://{parsed.netloc}{repo.removesuffix('.git')}"
        if key not in self.paths:
            return None
        subpath = parse_qs(parsed.fragment).get("subdirectory", [""])[0]
        return str(Path(self.paths[key]) / subpath)


def provider_instances(bundle):
    """Bridge Foundation's composition `id` and core's mount `instance_id`.

    Runs on loaded roots/explicit overlays before app composition. Recursive
    includes have already been composed by Foundation, so those authors must
    supply `id` at their source; this cannot recover entries already merged away.
    """
    bundle = copy.deepcopy(bundle)
    for entry in bundle.providers:
        identity = entry.get("id", entry.get("instance_id"))
        if identity is None:
            continue
        if not isinstance(identity, str) or not identity.strip():
            raise ValueError("Provider instance identity must be a nonempty string")
        if entry.get("instance_id", identity) != identity:
            raise ValueError("Provider id and instance_id disagree")
        entry.update(id=identity, instance_id=identity)
    return bundle


async def compose(
    source: str,
    overlays: list[str],
    state_dir: Path,
    sources: SourceMap,
    *,
    cli_policy=None,
    native_home=None,
):
    registry = BundleRegistry(
        home=state_dir / "registry", strict=True, include_source_resolver=sources.resolve
    )

    def location(value):
        resolved = sources.resolve(value) or value
        return str(Path(resolved).resolve()) if Path(resolved).exists() else resolved

    policy_report = {"settings_policy": "isolated"}
    if cli_policy:
        from .cli_compat import compose_cli

        bundle, resolver, policy_report = await compose_cli(source, overlays, sources, **cli_policy)
        policy_report["_module_resolver"] = resolver
    else:
        bundle = provider_instances(await load_bundle(location(source), registry=registry))
        for overlay in overlays:
            bundle = bundle.compose(
                provider_instances(await load_bundle(location(overlay), registry=registry))
            )
    # Registry caches its values. Never change those values in place.
    bundle = copy.deepcopy(bundle)
    bundle.load_agent_metadata()
    removed = [entry["module"] for entry in bundle.hooks if entry["module"] in TERMINAL_HOOKS]
    bundle.hooks = [entry for entry in bundle.hooks if entry["module"] not in TERMINAL_HOOKS]
    state_dir = state_dir.resolve()
    storage_overrides = {}
    for hook in bundle.hooks:
        if cli_policy:
            continue  # Preserve declared remote/logging policy, not a local-only replacement.
        config = hook.setdefault("config", {})
        if hook["module"] == "hooks-logging":
            config["session_log_template"] = str(
                Path(native_home) / "projects/{project}/sessions/{session_id}/events.jsonl"
                if native_home is not None
                else state_dir / "events" / "{session_id}.jsonl"
            )
            config["strip_raw"] = True
            storage_overrides[hook["module"]] = "local event log; raw payloads excluded"
        elif hook["module"] == "hook-context-intelligence":
            config.update(
                base_path=str(
                    Path(native_home) / "projects"
                    if native_home is not None
                    else state_dir / "context-intelligence"
                ),
                context_intelligence_server_url="",
                context_intelligence_api_key="",
                destinations={},
            )
            storage_overrides[hook["module"]] = "local capture; external dispatch disabled"
    for tool in bundle.tools:
        if cli_policy and tool["module"] != "tool-skills":
            continue
        config = tool.setdefault("config", {})
        if tool["module"] == "tool-recipes" and not cli_policy:
            config["session_dir"] = str(state_dir / "recipes" / "{project}")
            storage_overrides[tool["module"]] = "local recipe sessions"
        if tool["module"] == "tool-skills":
            config["skills"] = [sources.resolve(s) or s for s in config.get("skills", [])]
    return bundle, {
        **policy_report,
        "root": source,
        "overlays": overlays,
        "excluded_terminal_hooks": removed,
        "storage_policy": storage_overrides,
        "provider_instance_policy": policy_report.get(
            "provider_instance_policy",
            "Root/explicit-overlay id and instance_id normalized before app composition. Recursive includes must author Foundation id to preserve separate instances; already-collapsed entries cannot be recovered.",
        ),
    }


async def prepare(
    source,
    overlays,
    state_dir,
    sources,
    *,
    install_deps=True,
    cli_policy=None,
    progress=None,
    native_home=None,
):
    if progress:
        progress("Loading bundle and settings")
    bundle, report = await compose(
        source, overlays, state_dir, sources, cli_policy=cli_policy, native_home=native_home
    )
    if progress:
        progress("Preparing module dependencies")
    resolver = report.pop("_module_resolver", lambda _module, uri: sources.resolve(uri) or uri)
    prepared = await bundle.prepare(
        strict=True,
        install_deps=install_deps,
        source_resolver=resolver,
    )
    for section in ("providers", "tools", "hooks"):
        for entry in prepared.mount_plan.get(section, []):
            if cli_policy:
                continue  # Already expanded by the pinned CLI policy; preserve absent config.
            config = entry.get("config", {})
            if section == "providers":
                for key in ("api_key", "token", "api_token"):
                    if key in config:
                        expand_environment(config[key], required=True)
            entry["config"] = expand_environment(config)
    for point in ("orchestrator", "context"):
        entry = prepared.mount_plan.get("session", {}).get(point)
        if isinstance(entry, dict) and not cli_policy:
            entry["config"] = expand_environment(entry.get("config", {}))
    report["stage"] = "prepared"
    report["bundle"] = bundle.name
    # Origins and names are safe to inspect; provider configuration can contain credentials.
    report["modules"] = {
        section: [
            {
                "module": entry["module"],
                "source": entry.get("source"),
                **({"instance_id": entry["instance_id"]} if entry.get("instance_id") else {}),
            }
            for entry in prepared.mount_plan.get(section, [])
        ]
        for section in ("providers", "tools", "hooks")
    }
    report["agents"] = sorted(prepared.mount_plan.get("agents", {}))
    report["environment_policy"] = (
        "Root module configs: ${VAR:default}, unset ${VAR} empty; explicit missing provider credentials reject startup"
    )
    report["source_overrides"] = dict(sources.paths)
    return prepared, report


class ProcessSession:
    """App-owned session proxy, not a replacement runtime or permission policy."""

    @classmethod
    async def open(cls, owner, identity, display, parent):
        import socket
        import sys
        from types import SimpleNamespace

        from amplifier_core import CancellationToken
        from amplifier_foundation.subprocess_runner import _build_child_env

        from .frontend_bridge import ChildChannel

        self = cls()
        self.owner, self.row, self.display = owner, owner.records[identity], display
        self.session_id, self.config = identity, self.row["prepared"].mount_plan
        self.callbacks, self.mounts = {}, {}
        self.process = self.peer = self.watcher = None
        self.finished = False
        self.coordinator = SimpleNamespace(
            cancellation=CancellationToken(),
            config=self.config,
            session_state={},
            get=self.mounts.get,
            hooks=SimpleNamespace(register=self.register),
        )
        parent.coordinator.cancellation.register_child(self.coordinator.cancellation)
        local, remote = socket.socketpair()
        try:
            env = _build_child_env()
            # Find this installed app even when cwd is the user's workspace.
            env["PYTHONPATH"] = os.pathsep.join(str(Path(p).resolve()) for p in sys.path if p)
            self.process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "amplifier_tui.composition",
                str(remote.fileno()),
                str(os.getpid()),
                pass_fds=(remote.fileno(),),
                start_new_session=True,
                stdin=asyncio.subprocess.DEVNULL,
                cwd=owner.cwd,
                env=env,
            )
            remote.close()
            self.peer = await ChildChannel.connect(local, self.handle)
            self.watcher = asyncio.create_task(self.watch())
            prepared = self.row["prepared"]
            bundle = prepared.bundle
            bundle.resolve_pending_context()
            fields = (
                "name",
                "version",
                "description",
                "session",
                "providers",
                "tools",
                "hooks",
                "spawn",
                "agents",
                "instruction",
            )
            value = {key: getattr(bundle, key) for key in fields}
            for key in ("context", "source_base_paths"):
                value[key] = {k: str(v) if v else None for k, v in getattr(bundle, key).items()}
            value["base_path"] = str(bundle.base_path) if bundle.base_path else None
            initialized = await self.peer.call(
                "initialize",
                identity=identity,
                parent=self.row["parent"],
                cwd=str(owner.cwd),
                bundle=value,
                mount_plan=self.config,
                package_paths=prepared.bundle_package_paths,
                row={
                    key: self.row.get(key)
                    for key in ("messages", "mode", "self_depth", "depth", "activity_run", "agent")
                },
                turn=owner.host.turn_id,
                interactive=owner.host.interactive_questions,
            )
            self.row.update({k: initialized[k] for k in ("tools", "hooks")})
            self.coordinator.session_state["active_mode"] = initialized["mode"]
            self.mounts["context"] = self
            self.mounts["providers"] = {
                name: ProcessProvider(self.peer, name) for name in initialized["providers"]
            }
            return self
        except BaseException:
            cleanup = asyncio.create_task(self.cleanup())
            while not cleanup.done():
                try:
                    await asyncio.shield(cleanup)
                except asyncio.CancelledError:
                    continue
            cleanup.result()
            raise
        finally:
            parent.coordinator.cancellation.unregister_child(self.coordinator.cancellation)
            remote.close()
            if self.peer is None:
                local.close()

    def register(self, event, callback, **_kwargs):
        self.callbacks.setdefault(event, []).append(callback)

    async def handle(self, operation, payload):
        from .children import _activity_call

        if operation == "resolve":
            resolver = self.row["prepared"].resolver
            source = await resolver.async_resolve(payload["module_id"], payload.get("source_hint"))
            return str(source.resolve())
        if operation == "observe":
            event, data = payload["event"], payload["data"]
            status = payload.get("invoked")
            if status:
                self.owner.tool_outcomes[
                    self.owner.activity_id(self.session_id, data.get("tool_call_id", "unknown"))
                ] = status
            for callback in self.callbacks.get(event, []):
                await callback(event, data)
            return None
        if operation == "display":
            self.display.show_message(**payload)
            return None
        if operation == "emit":
            self.display.emit(payload["kind"], payload["identity"], **payload["payload"])
            return None
        if operation == "phase":
            self.owner.publish(self.session_id, payload["status"])
            return None
        if operation == "unready":
            self.display.ready = False
            return None
        if operation == "approval":
            return await self.display.request_approval(**payload)
        if operation == "question":
            return await self.owner.host.questions.ask(**payload)
        if operation in ("spawn", "resume"):
            self.coordinator.session_state["active_mode"] = payload.pop("mode")
            item = payload.pop("parent_item")
            token = _activity_call.set((self.session_id, item) if item else None)
            try:
                if operation == "spawn":
                    return await self.owner.spawn(parent_session=self, **payload)
                return await self.owner.resume(**payload)
            finally:
                _activity_call.reset(token)
        raise ValueError("Unknown child host operation")

    async def watch(self):
        stage = None
        while not self.finished:
            cancellation = self.coordinator.cancellation
            requested = (
                "immediate"
                if cancellation.is_immediate
                else ("graceful" if cancellation.is_graceful else None)
            )
            if requested and requested != stage:
                stage = requested
                try:
                    await asyncio.wait_for(
                        self.peer.call("stop", immediate=stage == "immediate"), 0.2
                    )
                except (TimeoutError, RuntimeError, ConnectionError):
                    if stage != "immediate":
                        self.row["execution_uncertain"] = True
                if stage == "immediate":
                    await asyncio.sleep(0.5)
                    if not self.finished:
                        self.kill()
                    return
            await asyncio.sleep(0.025)

    def kill(self):
        from amplifier_foundation.subprocess_runner import _kill_subprocess_tree

        if self.process and self.process.returncode is None:
            self.row["execution_uncertain"] = True
            _kill_subprocess_tree(self.process.pid)

    async def execute(self, prompt):
        try:
            result = await self.peer.call("execute", prompt=prompt)
            self.row["messages"] = result["messages"]
            self.coordinator.session_state["active_mode"] = result["mode"]
            return result["output"]
        except (RuntimeError, ConnectionError):
            if self.peer.closed:
                self.row["execution_uncertain"] = True
                self.coordinator.cancellation.request_immediate()
            raise

    async def get_messages(self):
        if not self.peer.closed:
            try:
                result = await asyncio.wait_for(self.peer.call("context"), 2)
                self.row["messages"] = result
            except (TimeoutError, RuntimeError, ConnectionError):
                self.row["execution_uncertain"] = True
        else:
            self.row["execution_uncertain"] = True
        return copy.deepcopy(self.row["messages"])

    async def cleanup(self):
        if self.finished:
            return
        try:
            if self.peer and not self.peer.closed:
                try:
                    await asyncio.wait_for(self.peer.call("cleanup"), 2)
                except (RuntimeError, TimeoutError, ConnectionError):
                    self.row["execution_uncertain"] = True
            if self.peer:
                await self.peer.close()
            if self.process:
                try:
                    await asyncio.wait_for(self.process.wait(), 1)
                except TimeoutError:
                    self.kill()
                    await self.process.wait()
        finally:
            self.finished = True
            if self.watcher:
                self.watcher.cancel()
                await asyncio.gather(self.watcher, return_exceptions=True)


class ProcessProvider:
    def __init__(self, peer, name):
        self.peer, self.name = peer, name

    async def list_models(self):
        from types import SimpleNamespace

        models = await self.peer.call("models", name=self.name)
        return [SimpleNamespace(**model) if isinstance(model, dict) else model for model in models]


async def run_child_process(fd, parent_pid):
    """Fresh interpreter with the same public session/module assembly as local work."""
    import inspect
    import signal
    import socket
    import sys
    import threading
    from types import SimpleNamespace

    from amplifier_core import CancellationToken, HookResult
    from amplifier_foundation import Bundle
    from amplifier_foundation.bundle import PreparedBundle
    from amplifier_foundation.bundle._prepared import BundleModuleSource

    from .children import Children, parent_call
    from .frontend_bridge import ChildChannel

    # Tools must not inherit the control descriptor. A separate watchdog can
    # reap this app-created group even when a module blocks the asyncio thread
    # after the host disappears; this is ownership, not a sandbox guarantee.
    os.set_inheritable(fd, False)
    finished = threading.Event()

    def parent_watch():
        while not finished.wait(0.25):
            if os.getppid() != parent_pid:
                if os.getpgrp() == os.getpid():
                    os.killpg(os.getpid(), signal.SIGKILL)
                os._exit(125)

    watchdog = threading.Thread(target=parent_watch, daemon=True)
    watchdog.start()
    session = owner = row = None
    cancellation = CancellationToken()
    pending = []
    transport_failed = False

    def enqueue(operation, **payload):
        if len(pending) >= 128:
            raise RuntimeError("Child display capacity exceeded")
        pending.append((operation, payload))

    async def flush():
        while pending:
            operation, payload = pending.pop(0)
            await peer.call(operation, **payload)

    class Resolver:
        async def async_resolve(self, module_id, source_hint=None, **_kwargs):
            path = await peer.call("resolve", module_id=module_id, source_hint=source_hint)
            return BundleModuleSource(Path(path))

    class Display:
        store = local_commands = session = None

        @property
        def _stop_requested(self):
            return cancellation.is_cancelled

        @property
        def ready(self):
            return not cancellation.is_cancelled

        @ready.setter
        def ready(self, value):
            if not value:
                enqueue("unready")

        def show_message(self, message, level="info", source="hook", **_kwargs):
            enqueue("display", message=str(message), level=level, source=str(source))

        def emit(self, kind, identity, **payload):
            enqueue("emit", kind=kind, identity=identity, payload=payload)

        async def request_approval(self, prompt, options, timeout, default):
            await flush()
            return await peer.call(
                "approval", prompt=prompt, options=options, timeout=timeout, default=default
            )

    class RemoteChildren(Children):
        async def forward(self, operation, function, *args, **kwargs):
            bound = inspect.signature(function).bind(self, *args, **kwargs)
            values = dict(bound.arguments)
            values.pop("self")
            values.pop("parent_session", None)
            await flush()
            return await peer.call(
                operation,
                **values,
                mode=session.coordinator.session_state.get("active_mode"),
                parent_item=parent_call(session.session_id),
            )

        async def spawn(self, *args, **kwargs):
            return await self.forward("spawn", Children.spawn, *args, **kwargs)

        async def resume(self, *args, **kwargs):
            return await self.forward("resume", Children.resume, *args, **kwargs)

        def publish(self, identity, status, detail=None):
            enqueue("phase", status=status)

    async def handle(operation, payload):
        nonlocal session, owner, row
        if operation == "stop":
            if payload["immediate"]:
                cancellation.request_immediate()
            else:
                cancellation.request_graceful()
            return None
        if operation == "initialize":
            if session is not None:
                raise ValueError("Child already initialized")
            value = payload["bundle"]
            for key in ("context", "source_base_paths"):
                value[key] = {k: Path(v) if v else None for k, v in value[key].items()}
            value["base_path"] = Path(value["base_path"]) if value["base_path"] else None
            sys.path.extend(p for p in payload["package_paths"] if p not in sys.path)
            prepared = PreparedBundle(
                payload["mount_plan"], Resolver(), Bundle(**value), payload["package_paths"]
            )
            display = Display()

            async def ask(questions, **kwargs):
                await flush()
                return await peer.call("question", questions=questions, **kwargs)

            host = SimpleNamespace(
                session_id=payload["parent"],
                turn_id=payload["turn"],
                interactive_questions=payload["interactive"],
                questions=SimpleNamespace(ask=ask),
            )
            owner = RemoteChildren(host, prepared, payload["cwd"])
            row = payload["row"]
            row["request_index"] = 0
            owner.records[payload["identity"]] = row
            session = await create_owned_session(
                prepared,
                session_id=payload["identity"],
                parent_id=payload["parent"],
                session_cwd=Path(payload["cwd"]),
                approval_system=display,
                display_system=display,
                interactive_approval=payload["interactive"],
            )
            cancellation.register_child(session.coordinator.cancellation)
            await owner.configure_child(session, row, display)

            async def observe(event, data):
                nonlocal transport_failed
                await flush()
                if event == "provider:request":
                    row["request_index"] += 1
                call = owner.activity_id(session.session_id, data.get("tool_call_id", "unknown"))
                invoked = (
                    owner.tool_outcomes.pop(call, None)
                    if event in ("tool:post", "tool:error")
                    else None
                )
                # Never transfer an entire model request merely to display a wait.
                keys = {
                    "provider:request": ("session_id",),
                    "provider:resolve": ("session_id", "scope", "provider", "model", "basis"),
                    "llm:request": ("session_id", "model"),
                    "llm:response": ("session_id", "provider", "model", "usage", "duration_ms"),
                }.get(event)
                if keys is not None:
                    data = {key: data[key] for key in keys if key in data}
                try:
                    await peer.call("observe", event=event, data=data, invoked=invoked)
                except Exception:
                    # Hook failures may be swallowed by the kernel; never claim
                    # successful owned execution after losing its observations.
                    transport_failed = True
                    cancellation.request_immediate()
                    raise
                return HookResult()

            for event in (
                "orchestrator:complete",
                "provider:request",
                "provider:resolve",
                "llm:request",
                "llm:response",
                "content_block:end",
                "tool:pre",
                "tool:post",
                "tool:error",
            ):
                session.coordinator.hooks.register(
                    event, observe, priority=999, name="tui-child-process"
                )
            await flush()
            return {
                "tools": row["tools"],
                "hooks": row["hooks"],
                "mode": session.coordinator.session_state.get("active_mode"),
                "providers": list(session.coordinator.get("providers") or {}),
            }
        if session is None:
            raise ValueError("Child session not initialized")
        if operation == "execute":
            output = await execute_owned(session, payload["prompt"])
            await flush()
            if transport_failed:
                raise RuntimeError("Child observation transport failed")
            return {
                "output": output,
                "messages": await session.coordinator.get("context").get_messages(),
                "mode": session.coordinator.session_state.get("active_mode"),
            }
        if operation == "models":
            return await session.coordinator.get("providers")[payload["name"]].list_models()
        if operation == "context":
            return await session.coordinator.get("context").get_messages()
        if operation == "cleanup":
            await session.cleanup()
            await flush()
            return None
        raise ValueError("Unknown child worker operation")

    peer = await ChildChannel.connect(socket.socket(fileno=fd), handle)
    try:
        await peer.reader_task
    finally:
        cancellation.request_immediate()
        try:
            await peer.close()
            if session:
                await session.cleanup()
        finally:
            finished.set()
            watchdog.join(timeout=1)


if __name__ == "__main__":
    import sys

    asyncio.run(run_child_process(int(sys.argv[1]), int(sys.argv[2])))

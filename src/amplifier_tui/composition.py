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


async def execute_owned(session, prompt, *, grace=0.25, on_forced=None):
    """Retain execution ownership while cooperative cancellation records its outcome.

    Cancelling the Rust-backed wait can return before Python callbacks have drained.
    Give the public cancellation token a bounded grace, then cancel the owned wait.
    Repeated caller cancellation neither abandons it nor extends that grace. An
    uncooperative module still requires the client's separately owned process deadline.
    """
    execution = asyncio.ensure_future(session.execute(prompt))
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


async def create_owned_session(prepared, *, session_cwd=None, observer=None, **kwargs):
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


async def compose(source: str, overlays: list[str], state_dir: Path, sources: SourceMap):
    registry = BundleRegistry(
        home=state_dir / "registry", strict=True, include_source_resolver=sources.resolve
    )

    def location(value):
        resolved = sources.resolve(value) or value
        return str(Path(resolved).resolve()) if Path(resolved).exists() else resolved

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
        config = hook.setdefault("config", {})
        if hook["module"] == "hooks-logging":
            config["session_log_template"] = str(state_dir / "events" / "{session_id}.jsonl")
            config["strip_raw"] = True
            storage_overrides[hook["module"]] = "local event log; raw payloads excluded"
        elif hook["module"] == "hook-context-intelligence":
            config.update(
                base_path=str(state_dir / "context-intelligence"),
                context_intelligence_server_url="",
                context_intelligence_api_key="",
                destinations={},
            )
            storage_overrides[hook["module"]] = "local capture; external dispatch disabled"
    for tool in bundle.tools:
        config = tool.setdefault("config", {})
        if tool["module"] == "tool-recipes":
            config["session_dir"] = str(state_dir / "recipes" / "{project}")
            storage_overrides[tool["module"]] = "local recipe sessions"
        if tool["module"] == "tool-skills":
            config["skills"] = [sources.resolve(s) or s for s in config.get("skills", [])]
    return bundle, {
        "root": source,
        "overlays": overlays,
        "excluded_terminal_hooks": removed,
        "storage_policy": storage_overrides,
        "provider_instance_policy": "Root/explicit-overlay id and instance_id normalized before app composition. Recursive includes must author Foundation id to preserve separate instances; already-collapsed entries cannot be recovered.",
    }


async def prepare(source, overlays, state_dir, sources, *, install_deps=True):
    bundle, report = await compose(source, overlays, state_dir, sources)
    prepared = await bundle.prepare(
        strict=True,
        install_deps=install_deps,
        source_resolver=lambda _module, uri: sources.resolve(uri) or uri,
    )
    for section in ("providers", "tools", "hooks"):
        for entry in prepared.mount_plan.get(section, []):
            config = entry.get("config", {})
            if section == "providers":
                for key in ("api_key", "token", "api_token"):
                    if key in config:
                        expand_environment(config[key], required=True)
            entry["config"] = expand_environment(config)
    for point in ("orchestrator", "context"):
        entry = prepared.mount_plan.get("session", {}).get(point)
        if isinstance(entry, dict):
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

"""Explicit host composition policy over Foundation's public bundle API."""

from __future__ import annotations

import copy
import json
import os
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from amplifier_foundation import BundleRegistry, load_bundle

# These modules write directly to Rich/stdout. Other policy hooks are retained.
TERMINAL_HOOKS = {"hooks-streaming-ui", "hooks-todo-display"}


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

"""App-layer CLI compatibility; pinned policy helpers, never terminal or kernel policy.

Private CLI helper usage is deliberately version-pinned in pyproject.toml and
compared against the actual CLI resolver in tests. No settings/credential copying.
"""

from __future__ import annotations

import copy
import os
from pathlib import Path


def skill_commands(session):
    """Read cached module metadata only; never resolve sources on a keypress."""
    import re

    try:
        discovery = session.coordinator.get_capability("skills_discovery") if session else None
        values = discovery.get_shortcuts() if discovery else {}
        return sorted(
            name
            for name in values
            if isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", name)
        )[:500]
    except Exception:
        return []


def settings_for(cwd, home):
    import yaml
    from amplifier_app_cli.lib.settings import AppSettings, SettingsPaths

    paths = SettingsPaths(
        Path(home) / "settings.yaml",
        Path(cwd) / ".amplifier/settings.yaml",
        Path(cwd) / ".amplifier/settings.local.yaml",
    )
    # Unlike the CLI's permissive reader, never silently discard malformed policy.
    merged = {}
    for path in (paths.global_settings, paths.project_settings, paths.local_settings):
        if path.exists():
            try:
                with path.open() as stream:
                    raw = stream.read(2 * 1024 * 1024 + 1)
                if len(raw) > 2 * 1024 * 1024:
                    raise ValueError("size limit")
                value = yaml.safe_load(raw) or {}
                if not isinstance(value, dict):
                    raise ValueError("mapping required")
                merged = AppSettings(paths)._deep_merge(merged, value)
            except Exception:
                raise ValueError(
                    "CLI settings invalid or unreadable; launch refused (values withheld)"
                ) from None

    class Snapshot(AppSettings):
        def get_merged_settings(self):
            return copy.deepcopy(merged)

    return Snapshot(paths)


def apply_settings(bundle, settings):
    """The pinned CLI merge order, before activation so added sources also prepare."""
    from amplifier_app_cli.lib.settings import get_custom_routing_dir
    from amplifier_app_cli.runtime import config as policy

    plan = bundle.to_mount_plan()
    overrides = settings.get_config_overrides()
    for container in [plan, *plan.get("agents", {}).values()]:
        if not isinstance(container, dict):
            continue
        for section in ("providers", "tools", "hooks"):
            if container.get(section):
                container[section] = policy._apply_config_overrides_to_section(
                    container[section], overrides
                )
    for key in ("context", "orchestrator"):
        entry = plan.get("session", {}).get(key)
        if entry:
            plan["session"][key] = policy._apply_config_overrides_to_entry(entry, overrides)
    providers = settings.get_provider_overrides()
    if providers:
        plan["providers"] = (
            policy._apply_provider_overrides(plan["providers"], providers)
            if plan.get("providers")
            else policy._ensure_raw_defaults(providers)
        )
    if plan.get("providers"):
        plan["providers"] = policy._map_id_to_instance_id(plan["providers"])
        policy._validate_provider_credentials(plan["providers"])
    tools = settings.get_tool_overrides()
    plan["tools"] = (
        policy._apply_tool_overrides(plan.get("tools", []), tools)
        if tools
        else policy._ensure_cli_tool_policies(plan.get("tools", []))
    )
    hooks = settings.get_notification_hook_overrides()
    routing = settings.get_routing_config()
    if routing:
        config = {
            k: v
            for k, v in overrides.get("hooks-routing", {}).items()
            if k not in ("default_matrix", "overrides")
        }
        if "matrix" in routing:
            config["default_matrix"] = routing["matrix"]
        if "overrides" in routing:
            config["overrides"] = routing["overrides"]
        directory = get_custom_routing_dir()
        if directory.is_dir():
            config["custom_routing_dirs"] = [str(directory)]
        entry = {"module": "hooks-routing", "config": config}
        if not policy._bundle_declares_hook(plan.get("hooks"), "hooks-routing"):
            entry["source"] = policy._routing_hook_source()
        if config:
            hooks.append(entry)
    if hooks:
        plan["hooks"] = policy._apply_hook_overrides(plan.get("hooks", []), hooks)
    plan = policy.expand_env_vars(plan)
    for section in ("providers", "tools", "hooks", "session", "agents"):
        if section in plan:
            setattr(bundle, section, plan[section])
    return bundle


async def compose_cli(source, overlays, sources, *, cwd, home):
    from amplifier_app_cli.lib.bundle_loader.discovery import AppBundleDiscovery
    from amplifier_app_cli.lib.bundle_loader.prepare import (
        _append_agents_instruction_tail,
        _build_include_source_resolver,
        _preserve_root_instruction,
    )
    from amplifier_app_cli.runtime import config as policy
    from amplifier_foundation import load_bundle

    from .composition import provider_instances

    settings = settings_for(cwd, home)
    discovery = AppBundleDiscovery(
        search_paths=[Path(cwd) / ".amplifier/bundles", Path(home) / "bundles"]
    )
    configured_resolver = _build_include_source_resolver(settings.get_bundle_sources())

    def resolve(value):
        value = configured_resolver(value) or value
        return sources.resolve(value) or value

    discovery.registry.set_include_source_resolver(resolve)
    selected = source or settings.get_active_bundle() or "anchors"
    aliases = settings.get_merged_settings().get("bundle", {}).get("added", {})
    uri = aliases.get(selected, selected)
    if not Path(uri).exists() and "://" not in uri:
        uri = discovery.find(uri)
    if not uri:
        raise ValueError("Selected CLI bundle could not be resolved")
    bundle = provider_instances(await load_bundle(resolve(uri), registry=discovery.registry))
    behaviors = (
        policy._build_modes_behaviors()
        + policy._build_app_cli_behaviors()
        + policy._build_skills_behaviors()
        + policy._build_routing_behaviors(settings)
        + policy._build_wayfinder_behaviors()
        + policy._build_notification_behaviors(settings.get_notification_flags())
        + settings.get_app_bundles()
    )
    instruction = bundle.instruction
    for uri in behaviors:
        behavior = provider_instances(await load_bundle(resolve(uri), registry=discovery.registry))
        composed = bundle.compose(behavior)
        _preserve_root_instruction(
            composed, root_instruction=instruction, composed_bundle=behavior, behavior_uri=uri
        )
        bundle = composed
    # Explicit TUI overlays have the usual later-wins semantics; app behaviors do not.
    for uri in overlays:
        bundle = bundle.compose(
            provider_instances(await load_bundle(resolve(uri), registry=discovery.registry))
        )
    bundle.instruction = _append_agents_instruction_tail(bundle.instruction)
    bundle.load_agent_metadata()
    bundle = apply_settings(bundle, settings)
    module_sources = {
        **settings.get_module_sources(),
        **settings.get_source_overrides(),
        **{p["module"]: p["source"] for p in settings.get_provider_overrides() if p.get("source")},
    }

    def module_source(module, uri):
        value = module_sources.get(module, uri)
        return sources.resolve(value) or value

    # Module sources from agent frontmatter and settings are activated normally.
    return (
        bundle,
        module_source,
        {
            "settings_policy": "cli",
            "selected_bundle": selected,
            "app_behavior_count": len(settings.get_app_bundles()),
            "settings_scopes": [
                name
                for name, path in (
                    ("global", settings.paths.global_settings),
                    ("project", settings.paths.project_settings),
                    ("local", settings.paths.local_settings),
                )
                if path.exists()
            ],
            "policy_differences": [
                "Terminal printing hooks replaced by structured TUI projection",
                "Declared behavior failures refuse startup; no optional silent omission",
                "TUI conversation checkpoints remain separate; CLI import is explicit",
                "Mounted recipes tool receives app-owned ephemeral file-discovery guidance",
            ],
            "provider_instance_policy": "Pinned CLI id-to-instance_id and provider merge semantics",
        },
    )


def session_directory(home, cwd):
    # Same deterministic path policy as the pinned CLI; no cwd mutation for lookup.
    slug = str(Path(cwd).resolve()).replace("/", "-").replace("\\", "-").replace(":", "")
    return Path(home) / "projects" / (slug if slug.startswith("-") else "-" + slug) / "sessions"


def read_session_file(home, cwd, identity, filename, limit):
    """Descriptor-relative, bounded regular-file reads; no mutable path authority."""
    import re
    import stat

    if not isinstance(identity, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", identity):
        raise ValueError("Invalid CLI session identity")
    root = session_directory(home, cwd)
    # Open each descendant relative to its already-open parent, closing the
    # symlink-swap gap between path validation and the final directory open.
    directory = os.open(home, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    child = None
    try:
        for part in root.relative_to(home).parts:
            next_directory = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory
            )
            os.close(directory)
            directory = next_directory
        child = os.open(identity, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
        fd = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=child)
        with os.fdopen(fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
                raise ValueError("CLI source exceeds import bound or is not a regular file")
            raw = stream.read(limit + 1)
            after = os.fstat(stream.fileno())
            if len(raw) > limit or (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            ):
                raise ValueError("CLI source changed during capture; try again after work finishes")
            return raw
    finally:
        if child is not None:
            os.close(child)
        os.close(directory)


def session_catalog(home, cwd):
    import json
    import time

    root = session_directory(home, cwd)
    rows, partial = [], False
    deadline = time.monotonic() + 0.2
    candidates = []
    if not root.exists():
        return {
            "rows": [],
            "partial": False,
            "scope": "No CLI sessions for this exact working directory",
        }
    with os.scandir(root) as entries:
        for index, entry in enumerate(entries):
            if index >= 5000 or time.monotonic() >= deadline - 0.1:
                partial = True
                break
            if not entry.is_dir(follow_symlinks=False):
                continue
            try:
                candidates.append((entry.stat(follow_symlinks=False).st_mtime_ns, entry.name))
            except OSError:
                partial = True
    partial = partial or len(candidates) > 100
    for _, identity in sorted(candidates, reverse=True)[:100]:
        if time.monotonic() >= deadline:
            partial = True
            break
        try:
            metadata = json.loads(read_session_file(home, cwd, identity, "metadata.json", 65536))
            if not isinstance(metadata, dict):
                raise ValueError("Invalid metadata")
            title = str(metadata.get("name") or metadata.get("title") or identity)[:160]
            rows.append(
                {
                    "id": identity,
                    "cli_import": identity,
                    "label": title,
                    "status": "CLI historical reference",
                    "source": identity,
                    "detail": "Import captures the current text of this CLI transcript into a NEW TUI conversation. Original files are unchanged. Tools, credentials, modes, provider pins and private state are NOT resumed. Review the imported reference before Send; the selected provider can receive it on that next explicit request.",
                }
            )
        except (OSError, ValueError, TypeError):
            partial = True
    return {
        "rows": rows,
        "partial": partial,
        "scope": "CLI sessions in this exact working directory; newest observed directories first. Metadata only: up to 5000 entries scanned / 100 rows / 200 ms. Partial means other sessions may be absent. Explicit historical import, not canonical resume.",
    }


def import_session(home, cwd, identity, *, structured=False):
    import hashlib
    import json

    raw = read_session_file(home, cwd, identity, "transcript.jsonl", 1024 * 1024)
    if structured:
        from .recovery import context_transfer

        public = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
        if not public:
            raise ValueError("CLI transcript is empty")
        # Missing tool outcomes refuse; do not manufacture success or repair
        # private provider messages under the guise of canonical CLI resume.
        value = context_transfer(public, identity)
        value["source_sha256"] = hashlib.sha256(raw).hexdigest()
        value["source_kind"] = "cli-public-context"
        return value
    messages = []
    for line in raw.decode("utf-8").splitlines():
        if not line.strip():
            continue
        message = json.loads(line)
        if not isinstance(message, dict):
            raise ValueError("CLI transcript contains an invalid message")
        role = message.get("role", "unknown")
        content = message.get("content", "")
        if isinstance(content, list):
            content = "\n".join(
                str(b.get("text", "[non-text block omitted]"))
                for b in content
                if isinstance(b, dict)
            )
        if not isinstance(content, str):
            content = "[non-text content omitted]"
        messages.append(f"{role}: {content}")
        if message.get("tool_calls"):
            messages.append("[historical tool calls omitted; no calls will be replayed]")
    text = "\n\n".join(messages)
    if not text.strip() or len(text.encode()) > 1024 * 1024:
        raise ValueError("CLI transcript empty or exceeds text-import bound")
    return {
        "version": 1,
        "text": text,
        "sha256": hashlib.sha256(text.encode()).hexdigest(),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "source_session": identity,
        "bytes": len(raw),
        "notice": "Imported CLI history as a reference into a NEW conversation. Original unchanged; no canonical resume, credentials, mode/pin, queued work or module-private state imported. No historical tools replayed. The selected provider can receive this reference after your next explicit Send.",
    }

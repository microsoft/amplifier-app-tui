"""App-layer CLI compatibility; pinned policy helpers, never terminal or kernel policy.

Private CLI helper usage is deliberately version-pinned in pyproject.toml and
compared against the actual CLI resolver in tests. No settings/credential copying.
"""

from __future__ import annotations

import copy
import os
from contextlib import contextmanager
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


def settings_for(cwd, home, session_id=None):
    import yaml
    from amplifier_app_cli.lib.settings import AppSettings, SettingsPaths

    paths = SettingsPaths(
        Path(home) / "settings.yaml",
        Path(cwd) / ".amplifier/settings.yaml",
        Path(cwd) / ".amplifier/settings.local.yaml",
        session_directory(home, cwd) / session_id / "settings.yaml" if session_id else None,
    )
    # Unlike the CLI's permissive reader, never silently discard malformed policy.
    merged = {}
    for path in (
        paths.global_settings,
        paths.project_settings,
        paths.local_settings,
        paths.session_settings,
    ):
        if path is None:
            continue
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


async def compose_cli(source, overlays, sources, *, cwd, home, session_id=None):
    from amplifier_app_cli.lib.bundle_loader.discovery import AppBundleDiscovery
    from amplifier_app_cli.lib.bundle_loader.prepare import (
        _append_agents_instruction_tail,
        _build_include_source_resolver,
        _preserve_root_instruction,
    )
    from amplifier_app_cli.runtime import config as policy
    from amplifier_foundation import load_bundle

    from .composition import provider_instances

    settings = settings_for(cwd, home, session_id)
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
    # App-private policy travels with the deep-copied bundle, never the public
    # report or kernel mount plan. Local controls own application/restoration.
    bundle._tui_configurator = copy.deepcopy(settings.get_merged_settings().get("configurator", {}))
    bundle._tui_settings_paths = settings.paths
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
                    ("session", settings.paths.session_settings),
                )
                if path is not None and path.exists()
            ],
            "policy_differences": [
                "Terminal printing hooks replaced by structured TUI projection",
                "Declared behavior failures refuse startup; no optional silent omission",
                "Canonical sessions are shared; TUI display state is a separate sidecar",
                "Mounted recipes tool receives app-owned ephemeral file-discovery guidance",
            ],
            "provider_instance_policy": "Pinned CLI id-to-instance_id and provider merge semantics",
        },
    )


def session_directory(home, cwd):
    # Same deterministic path policy as the pinned CLI; no cwd mutation for lookup.
    slug = str(Path(cwd).resolve()).replace("/", "-").replace("\\", "-").replace(":", "")
    return Path(home) / "projects" / (slug if slug.startswith("-") else "-" + slug) / "sessions"


def shared_session_entry(home, cwd, identity):
    """Read-only native discovery. CLI metadata, not a stale UI title, wins."""
    import json

    # Mirror the pinned CLI's two pure metadata rules without importing its
    # eager __init__/main bootstrap in a read-only launcher or custom-home picker.
    if "_" in identity:
        raise ValueError("Choose a root conversation, not a delegated session")
    metadata = native_history(home, cwd, identity, metadata_only=True)
    root = session_directory(home, cwd) / identity
    if not any((root / name).is_file() for name in ("transcript.jsonl", "transcript.jsonl.backup")):
        raise FileNotFoundError("No saved conversation transcript")
    if not isinstance(metadata, dict) or metadata.get("session_id", identity) != identity:
        raise ValueError("Invalid shared session metadata")
    if (
        metadata.get("working_dir")
        and Path(metadata["working_dir"]).resolve() != Path(cwd).resolve()
    ):
        raise ValueError("Session belongs to another working directory")
    bundle = metadata.get("bundle")
    bundle = bundle.removeprefix("bundle:") if bundle and bundle != "unknown" else None
    launch = dict(
        fixture=False,
        bundle=bundle,
        overlays=[],
        sources=None,
        cwd=str(Path(cwd).resolve()),
        settings_policy="cli",
        cli_home=str(Path(home).resolve()),
        shared_session=True,
    )
    sidecar = session_directory(home, cwd) / identity / ".tui"
    prior = {}
    if sidecar.exists():
        if sidecar.is_symlink():
            raise ValueError("Shared session sidecar cannot be a symlink")
        path = sidecar / "metadata.json"
        if path.exists():
            if path.is_symlink() or path.stat().st_size > 65536:
                raise ValueError("Invalid shared session sidecar")
            prior = json.loads(path.read_text())
            if prior.get("version") != 1 or prior.get("id") != identity:
                raise ValueError("Invalid shared session sidecar identity")
            for key in ("overlays", "sources", "required_tools", "settings_policy"):
                if key in prior.get("launch", {}):
                    launch[key] = prior["launch"][key]
    return {
        "version": 1,
        "id": identity,
        "launch": launch,
        "title": metadata.get("name")
        or metadata.get("title")
        or prior.get("title", "Untitled conversation"),
        "archived": bool(prior.get("archived")),
        "shared_session": True,
    }


def shared_session_catalog(home, cwd, *, archived=False):
    root = session_directory(home, cwd)
    if not root.is_dir() or root.is_symlink():
        return []
    rows = []
    for path in root.iterdir():
        if not path.is_dir() or path.is_symlink() or path.name.startswith("."):
            continue
        try:
            entry = shared_session_entry(home, cwd, path.name)
            if entry["archived"] == archived:
                stamps = [
                    source.stat().st_mtime_ns
                    for source in (path / "metadata.json", path / "metadata.json.backup")
                    if source.is_file()
                ]
                rows.append((max(stamps, default=0), entry))
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            continue
    return sorted(rows, key=lambda row: row[0], reverse=True)


def session_message_visible(message):
    """Pinned CLI display-only rule, also usable before its eager key bootstrap.

    Differential tests compare its reminder grammar with the real CLI predicate.
    Never use this filter on canonical messages sent to a context module.
    """
    import re

    if not isinstance(message, dict):
        return False
    if message.get("role") == "assistant":
        return True
    if message.get("role") != "user":
        return False
    metadata = message.get("metadata")
    if (
        not isinstance(metadata, dict)
        or metadata.get("ephemeral") is not True
        or metadata.get("persisted") is not True
    ):
        return True
    content = message.get("content")
    if isinstance(content, str):
        texts = [content.strip()]
    elif isinstance(content, list) and content:
        if any(
            not isinstance(b, dict) or b.get("type") != "text" or not isinstance(b.get("text"), str)
            for b in content
        ):
            return True
        texts = [b["text"].strip() for b in content if b["text"].strip()]
    else:
        return True
    if not texts:
        return True
    for text in texts:
        match = re.fullmatch(r"<system-reminders>(.*?)</system-reminders>", text, re.S)
        tag = "system-reminders"
        if match is None:
            match = re.fullmatch(
                r'<system-reminder(?: source="[^"]*")?>(.*?)</system-reminder>', text, re.S
            )
            tag = "system-reminder"
        if match is None or re.search(r"</?" + tag + r"[> \t\r\n]", match[1]):
            return True
    return False


@contextmanager
def _open_session_file(home, cwd, identity, filename):
    """Open only a regular native file through no-follow directory descriptors."""
    import re
    import stat

    if not isinstance(identity, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", identity):
        raise ValueError("Invalid CLI session identity")
    if Path(filename).name != filename:
        raise ValueError("Expected a native session filename")
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
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValueError("CLI source is not a regular file")
            yield stream
    finally:
        if child is not None:
            os.close(child)
        os.close(directory)


def read_session_file(home, cwd, identity, filename, limit):
    """Descriptor-relative, bounded regular-file reads; no mutable path authority."""
    with _open_session_file(home, cwd, identity, filename) as stream:
        before = os.fstat(stream.fileno())
        if before.st_size > limit:
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


class _NativeHistoryPath:
    """Read-only Path facade; Foundation owns parsing and backup semantics.

    Foundation currently accepts Paths, not an opened-stream factory. Constrain
    its read-only path operations here so adoption does not weaken no-follow and
    byte-limit policy. Never use this facade with the Foundation write methods.
    """

    def __init__(self, home, cwd, identity, filename):
        self.home, self.cwd, self.identity, self.name = home, cwd, identity, filename

    def with_suffix(self, suffix):
        return type(self)(
            self.home, self.cwd, self.identity, str(Path(self.name).with_suffix(suffix))
        )

    @property
    def suffix(self):
        return Path(self.name).suffix

    def stat(self):
        with _open_session_file(self.home, self.cwd, self.identity, self.name) as stream:
            return os.fstat(stream.fileno())

    def read_bytes(self):
        limit = 8 * 1024 * 1024 if self.name.startswith("transcript.") else 65536
        return read_session_file(self.home, self.cwd, self.identity, self.name, limit)

    def open(self, mode):
        import io

        if mode != "rb":
            raise ValueError("Native history adapter is read-only")
        return io.BytesIO(self.read_bytes())


def native_history(home, cwd, identity, *, metadata_only=False):
    """Shared native parser/recovery with bounded, no-follow host read policy.

    No runtime, CLI bootstrap, event log or provider is loaded for discovery.
    Unknown JSON fields survive. Recovery is read-only; callers surface the
    returned history diagnostics and retry changed reads under shared ownership.
    """
    from amplifier_foundation.session import SessionHistoryStore

    store = SessionHistoryStore(session_directory(home, cwd) / identity, session_id=identity)
    store.transcript_path = _NativeHistoryPath(home, cwd, identity, "transcript.jsonl")
    store.metadata_path = _NativeHistoryPath(home, cwd, identity, "metadata.json")
    return store.load_metadata() if metadata_only else store.load(include_events=False)


def session_events_path(session_dir):
    """Pure mirror of pinned CLI cost-history policy; discovery cannot bootstrap CLI.

    An explicit CI relocation is a projects root. Select exactly one capture:
    existing CI first, then the old CLI logger only when CI is absent. Invalid
    or unreadable CI must not be silently replaced by a different observer.
    """
    from amplifier_foundation.session import SessionHistoryStore

    session_dir = Path(session_dir)
    raw = os.environ.get("AMPLIFIER_CONTEXT_INTELLIGENCE_BASE_PATH", "").strip()
    root = Path(raw).expanduser() if raw and "${" not in raw else None
    capture = session_dir
    if root is not None and root.is_absolute():
        capture = root / session_dir.parent.parent.name / "sessions" / session_dir.name
    path = SessionHistoryStore(capture).events_path
    # lexists also keeps a broken CI symlink from authorizing another capture.
    return path if os.path.lexists(path) else session_dir / "events.jsonl"


class _OpenedEventSource:
    """Read-only bridge to Foundation's Path.open seam using an owned descriptor.

    Foundation owns decoding/normalization. Its current public reader accepts a
    Path, not an opened stream; substituting only that open seam preserves our
    descriptor-relative no-follow policy without a parser fork or disk copy.
    Retire this adapter when the shared API accepts host-owned input streams.
    """

    def __init__(self, descriptor):
        import stat

        self.descriptor = descriptor
        self.before = os.fstat(descriptor)
        if not stat.S_ISREG(self.before.st_mode):
            raise ValueError("Activity source is not a regular file")
        self.bytes_read = self.lines_read = 0
        self.stream = None

    def open(self, mode):
        if mode != "rb" or self.stream is not None:
            raise ValueError("Activity source is read-only and single-use")
        self.stream = os.fdopen(os.dup(self.descriptor), mode)
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.stream.close()

    def readline(self, size=-1):
        # Bound an individual provider payload as well as the aggregate scan.
        bound = 4 * 1024 * 1024 + 1
        raw = self.stream.readline(min(size, bound) if size >= 0 else bound)
        self.bytes_read += len(raw)
        self.lines_read += bool(raw)
        if len(raw) >= bound:
            raise OSError("Activity row exceeds capture bound")
        return raw

    def peek(self, size):
        return self.stream.peek(size)

    @property
    def changed(self):
        after = os.fstat(self.descriptor)
        return (self.before.st_size, self.before.st_mtime_ns, self.before.st_ctime_ns) != (
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )


def _session_event_reader(home, cwd, identity):
    """Open the selected capture without following any descendant symlinks."""
    import re
    from contextlib import contextmanager

    from amplifier_foundation.session import SessionHistoryStore

    @contextmanager
    def reader():
        if not isinstance(identity, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", identity):
            raise ValueError("Invalid CLI session identity")
        session_dir = session_directory(home, cwd) / identity
        path = session_events_path(session_dir)
        # The selected path is either native under home or exactly CI's resolved
        # projects root/project/sessions/identity/context-intelligence/events.
        anchor = Path(home)
        try:
            relative = path.relative_to(anchor)
        except ValueError:
            anchor = path.parents[4]
            relative = path.relative_to(anchor)
        directory = os.open(anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptor = None
        try:
            for part in relative.parts[:-1]:
                child = os.open(
                    part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory
                )
                os.close(directory)
                directory = child
            descriptor = os.open(
                relative.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
            )
            source = _OpenedEventSource(descriptor)
            history = SessionHistoryStore(session_dir, session_id=identity)
            history.events_path = source
            yield history, source
        finally:
            if descriptor is not None:
                os.close(descriptor)
            os.close(directory)

    return reader()


def read_session_activity(
    home, cwd, identity, messages, *, byte_limit=16 * 1024 * 1024, line_limit=5000
):
    """Bounded in-memory observations and exact Foundation associations, no writes.

    Missing or limited activity is not a canonical-history error. The returned
    events never grant approval, complete a job or replace transcript messages.
    """
    from amplifier_foundation.session import associate_events

    events, diagnostics, partial = [], [], False
    try:
        with _session_event_reader(home, cwd, identity) as (history, source):
            events.extend(history.iter_events(max_bytes=byte_limit, max_lines=line_limit))
            diagnostics = [diagnostic.code for diagnostic in history.diagnostics]
            partial = bool(diagnostics) or source.changed
            partial |= bool(source.lines_read and not events)
    except (OSError, ValueError, RecursionError):
        partial = True
    return {
        "events": events,
        "associations": associate_events(messages, events),
        "partial": partial,
        "diagnostics": diagnostics,
    }


def historical_usage(
    home, cwd, identity, *, byte_limit=64 * 1024 * 1024, file_limit=128, line_limit=100000
):
    """Read canonical logging receipts, never transcript prose or estimated prices.

    Descendants require recorded parent metadata or fork events, not ID prefixes.
    Limits and missing/corrupt sources are accounting gaps, not resume failures.
    """
    import json
    import re
    from itertools import islice

    from .inspection import usage_receipt_id, usage_values

    root = session_directory(home, cwd)
    parents, partial = {}, False
    try:
        paths = list(islice(root.iterdir(), 513))
        partial = len(paths) > 512
        for path in paths[:512]:
            if path.name == identity or path.is_symlink() or not path.is_dir():
                continue
            try:
                meta = json.loads(read_session_file(home, cwd, path.name, "metadata.json", 65536))
                if isinstance(meta, dict) and isinstance(meta.get("parent_id"), str):
                    parents[path.name] = meta["parent_id"]
            except (OSError, ValueError, RecursionError):
                continue
    except OSError:
        return [], True
    descendants = {identity}
    for _ in range(len(parents)):
        added = {child for child, parent in parents.items() if parent in descendants}
        if added <= descendants:
            break
        descendants.update(added)
    owners = [identity, *sorted(descendants - {identity})]
    partial |= len(owners) > file_limit
    records = {}

    def add_record(rec, owner):
        nonlocal partial
        if rec.get("event") == "session:fork":
            data = rec.get("data", {})
            child = data.get("child_session_id") if isinstance(data, dict) else None
            if (
                not isinstance(data, dict)
                or rec.get("session_id") != owner
                or data.get("parent_session_id") != owner
                or not isinstance(child, str)
                or not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", child)
                or parents.get(child, owner) != owner
            ):
                raise ValueError("Unattributed fork")
            if child not in descendants:
                if len(owners) >= file_limit:
                    partial = True
                    return
                descendants.add(child)
                owners.append(child)
            return
        if rec.get("event") != "llm:response":
            return
        data = rec.get("data", {})
        if not isinstance(data, dict) or rec.get("session_id") != owner:
            raise ValueError("Unattributed response")
        if any(
            rec.get(key) is not None and data.get(key) is not None and rec[key] != data[key]
            for key in ("request_id", "span_id", "timestamp")
        ):
            raise ValueError("Conflicting response identity")
        observed = {
            **data,
            **{k: rec[k] for k in ("session_id", "request_id", "span_id") if k in rec},
            "timestamp": rec.get("timestamp"),
        }
        key = usage_receipt_id(observed)
        if key is None:
            # A physical row remains evidence, but cannot be joined with another
            # observer. Equal token counts or nearby observer clocks are not IDs.
            key = f"log:{owner}:{rec['line'] - 1}"
            partial = True
        values = usage_values(data.get("usage"))
        row = {
            "usage_receipt_id": key,
            "usage_session_id": owner,
            "usage_call": {k: str(v) if k == "cost_usd" else v for k, v in values.items()},
            "provider": {k: data[k] for k in ("provider", "model") if isinstance(data.get(k), str)},
            "timestamp": rec.get("timestamp"),
            "duration_ms": rec.get("duration_ms", data.get("duration_ms")),
            "purpose": data.get("purpose") if isinstance(data.get("purpose"), str) else None,
        }
        if key in records and records[key] != row:
            partial = True  # Conflicting observations are never summed.
        else:
            records[key] = row

    for position, owner in enumerate(owners):
        if position >= file_limit:
            partial = True
            break
        for child, parent in parents.items():
            if parent == owner and child not in descendants:
                if len(owners) >= file_limit:
                    partial = True
                    continue
                descendants.add(child)
                owners.append(child)
        if byte_limit <= 0 or line_limit <= 0:
            return list(records.values()), True
        try:
            with _session_event_reader(home, cwd, owner) as (history, source):
                seen = False
                events = history.iter_events(max_bytes=byte_limit, max_lines=line_limit)
                try:
                    for rec in events:
                        seen = True
                        try:
                            add_record(rec, owner)
                        except (ValueError, TypeError, RecursionError):
                            partial = True
                        if len(records) >= 10000:
                            return list(records.values()), True
                finally:
                    events.close()
                    byte_limit -= source.bytes_read
                    line_limit -= source.lines_read
                partial |= bool(history.diagnostics) or source.changed
                partial |= bool(source.lines_read and not seen)
        except (OSError, ValueError, RecursionError):
            partial = True
    return list(records.values()), partial


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

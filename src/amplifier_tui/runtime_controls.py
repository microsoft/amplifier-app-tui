"""App-side adapters over public coordinator capabilities; no kernel policy.

Steering uses an identified envelope because the module's queue accepts strings.
Provider selection is a separate, fail-closed control record, not model context.
"""

import asyncio
import copy
import inspect
import json
import math
import os
import shlex
import uuid
from pathlib import Path

from .conversations import atomic_json


class Configuration:
    """Pinned Foundation configuration policy; persistence stays in the app."""

    categories = {
        "tools": "tool",
        "providers": "provider",
        "context": "context",
        "agents": "agent",
        "behaviors": "behavior",
    }

    def __init__(self, owner, prepared):
        self.owner, self.adapter = owner, owner.configurator
        self.paths = getattr(prepared.bundle, "_tui_settings_paths", None)
        self.initial = self.validate(getattr(prepared.bundle, "_tui_configurator", {}))
        self.overrides = {}

    @classmethod
    def validate(cls, value):
        if not isinstance(value, dict) or set(value) - {"disabled", "config_overrides"}:
            raise ValueError("Unsupported saved configurator policy; values withheld")
        disabled, overrides = value.get("disabled", {}), value.get("config_overrides", {})
        if (
            not isinstance(disabled, dict)
            or set(disabled) - {*cls.categories, "hooks"}
            or not isinstance(overrides, dict)
        ):
            raise ValueError("Invalid saved configurator policy; values withheld")
        if disabled.get("hooks"):
            raise ValueError("Hook toggles are unsupported by the CLI/Foundation adapter")
        for names in disabled.values():
            if (
                not isinstance(names, list)
                or len(names) > 128
                or any(not isinstance(n, str) or not n or len(n) > 512 for n in names)
                or len(set(names)) != len(names)
            ):
                raise ValueError("Invalid disabled-component list; values withheld")
        if len(overrides) > 128:
            raise ValueError("Too many staged configuration values")
        for path, item in overrides.items():
            cls.setting(path, item)
        return {
            "disabled": {c: sorted(disabled.get(c, [])) for c in cls.categories},
            "config_overrides": copy.deepcopy(overrides),
        }

    @staticmethod
    def setting(path, value):
        if (
            not isinstance(path, str)
            or len(path) > 512
            or not path
            or any(not p for p in path.split("."))
        ):
            raise ValueError("Configuration path must contain nonempty dot-separated keys")
        if not path.isprintable() or ".config." not in path:
            raise ValueError(
                "Set module configuration metadata beneath a .config. path, not component identities"
            )
        if any(
            p.lower()
            in ("api_key", "key", "token", "secret", "password", "credentials", "authorization")
            for p in path.split(".")
        ):
            raise ValueError(
                "Use provider-owned credential setup; secret values are not configuration commands"
            )
        if (
            type(value) not in (str, bool, int, float)
            or isinstance(value, str)
            and len(value) > 4096
            or type(value) is float
            and not math.isfinite(value)
            or type(value) is int
            and not -(2**63) <= value < 2**63
        ):
            raise ValueError("Configuration values must be bounded scalar values")

    def snapshot(self):
        # Pinned facade exposes its stashes as read-only compatibility properties.
        # Only names and explicit scalar overrides are serialized, not instances.
        return {
            "disabled": {
                c: sorted(
                    self.adapter._disabled_behaviors if c == "behaviors" else self.adapter._stash[c]
                )
                for c in self.categories
            },
            "config_overrides": copy.deepcopy(self.overrides),
        }

    def parse_setting(self, tokens):
        if len(tokens) != 3:
            raise ValueError("Usage: /config set PATH VALUE (quote a value containing spaces)")
        path, value = tokens[1:]
        if value.lower() in ("true", "false"):
            value = value.lower() == "true"
        else:
            try:
                value = int(value)
            except ValueError:
                try:
                    value = float(value)
                except ValueError:
                    pass
        self.setting(path, value)
        if path not in self.overrides and len(self.overrides) >= 128:
            raise ValueError("Configuration override limit reached")
        self.setting_target(path)
        return path, value

    def setting_target(self, path):
        node = self.owner.coordinator.config
        for key in path.split(".")[:-1]:
            if not isinstance(node, dict) or key not in node:
                raise ValueError(
                    "Choose an existing configuration dictionary; use CLI setup for new components"
                )
            node = node[key]
        if not isinstance(node, dict):
            raise ValueError("Configuration path cannot replace a mounted component list")

    async def apply(self, value):
        value = self.validate(value)
        for category in ("behaviors", "context", "tools", "providers", "agents"):
            for name in value["disabled"][category]:
                result = getattr(self.adapter, self.categories[category] + "_disable")(name)
                if inspect.isawaitable(result):
                    result = await result
                if isinstance(result, dict) and result.get("warnings"):
                    raise ValueError("Saved behavior policy applied incompletely; startup refused")
        for path, item in value["config_overrides"].items():
            self.setting_target(path)
            self.adapter.config_set(path, item)
        self.overrides = value["config_overrides"]
        if "mode" in self.adapter._stash["tools"] or not self.owner.coordinator.get("providers"):
            raise ValueError("Configuration removed a required control/provider; startup refused")
        pin = self.owner.host.controls.pin
        if pin and pin.current() and pin.current() not in self.owner.coordinator.get("providers"):
            raise ValueError("Configuration removed the selected provider; startup refused")
        actual = self.validate(self.snapshot())
        for category, names in value["disabled"].items():
            if not set(names).issubset(actual["disabled"][category]):
                raise ValueError("Saved configuration did not take effect; startup refused")

    def check_toggle(self, category, action, name):
        if category not in self.categories or action not in ("enable", "disable"):
            raise ValueError(
                "Choose tools, providers, context, agents or behaviors; hooks are inspection-only"
            )
        if action == "disable" and len(self.snapshot()["disabled"][category]) >= 128:
            raise ValueError("Disabled-component limit reached")
        if self.owner.host.modes.current():
            raise ValueError("Leave the active mode before changing root configuration")
        records = getattr(self.adapter, category + "_list")()
        item = next((r for r in records if r.name == name), None)
        if item is None:
            raise ValueError("Choose a loaded configuration item")
        if item.enabled == (action == "enable"):
            raise ValueError("Item is already " + ("enabled" if item.enabled else "disabled"))
        if category == "tools" and name == "mode":
            raise ValueError("Mode control cannot be disabled here")
        if category == "providers" and action == "disable":
            if len(self.owner.coordinator.get("providers") or {}) <= 1:
                raise ValueError("Keep at least one mounted provider")
            if self.owner.host.controls.pin and self.owner.host.controls.pin.current() == name:
                raise ValueError(
                    "Return the conversation provider to auto before disabling its pin"
                )
        if category == "behaviors" and action == "disable":
            # A broad group operation must not strand the control plane or a
            # pinned/last provider. Conservative inspection is preferable to
            # calling a partly mutating helper then discovering it was unsafe.
            for group in ("tools", "providers"):
                for record in getattr(self.adapter, group + "_list")():
                    if any(o.bundle == name for o in record.origins):
                        if group == "tools" and record.name == "mode" or group == "providers":
                            raise ValueError(
                                "This behavior owns a protected control/provider; change individual components or use a new composition"
                            )

    async def toggle(self, category, action, name):
        self.check_toggle(category, action, name)
        self.owner.save("pending")
        result = getattr(self.adapter, self.categories[category] + "_" + action)(name)
        if inspect.isawaitable(result):
            result = await result
        if isinstance(result, dict) and result.get("warnings"):
            raise ValueError("Behavior transition incomplete; no successful completion recorded")
        records = getattr(self.adapter, category + "_list")()
        item = next((r for r in records if r.name == name), None)
        if item is None or item.enabled != (action == "enable"):
            raise ValueError("Configuration transition did not take effect")
        self.owner.state["configuration"] = self.validate(self.snapshot())
        self.owner.state["disabled"] = self.owner.state["configuration"]["disabled"]["tools"]
        self.owner.save()
        return "Hooks are unchanged by behavior toggles. " if category == "behaviors" else ""

    def persist(self, scope):
        if self.paths is None:
            raise ValueError(
                "Shared save requires a CLI-configured launch; isolated sessions never write shared settings"
            )
        from amplifier_app_cli.lib.settings import AppSettings

        from .cli_compat import settings_for

        settings = AppSettings(self.paths)
        # The pinned writer uses its per-scope lock, secret normalization and
        # atomic YAML replacement. Validate before its permissive read, while
        # holding the same lock, so malformed policy cannot be overwritten.
        with settings._scope_lock(scope):
            settings_for(self.owner.cwd, self.paths.global_settings.parent)
            current = settings._read_scope(scope)
            current["configurator"] = self.snapshot()
            settings._write_scope(scope, current)


class LocalCommands:
    """Explicit app controls, separate from model turns and module-private state.

    The filesystem adapter is intentionally specific to the inspected module;
    it is not an OS sandbox and does not constrain bash or delegated sessions.
    """

    scope = "This root session only; children, bash and other tools are unchanged. Not an OS sandbox. Shared settings are unchanged."
    config_scope = "Saved for this conversation; shared settings unchanged."
    config_categories = ("providers", "tools", "hooks", "context", "agents", "behaviors")

    def __init__(self, host, prepared, cwd):
        from amplifier_foundation.configurator import SessionConfigurator

        self.host, self.cwd = host, Path(cwd)
        self.coordinator = host.session.coordinator
        self.configurator = SessionConfigurator(host.session, prepared)
        self.configuration = Configuration(self, prepared)
        self.session_modules = {
            key: entry.get("module")
            for key, entry in prepared.mount_plan.get("session", {}).items()
            if key in ("orchestrator", "context") and isinstance(entry, dict)
        }
        self.path = host.store.path / "local-controls.json" if host.store else None
        self.state = {
            "version": 2,
            "fingerprint": host.fingerprint,
            "status": "ready",
            "disabled": [],
            "directories": {},
            "goal": None,
            "configuration": copy.deepcopy(self.configuration.initial),
        }
        self.wire = None
        self.goal_detector = None
        self.completion = None

    async def open(self):
        if self.path and self.path.exists():
            with self.path.open("rb") as stream:
                raw = stream.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise ValueError("Local controls exceed restore limit")
            value = json.loads(raw)
            if (
                isinstance(value, dict)
                and value.get("version") == 1
                and "configuration" not in value
            ):
                value["version"] = 2
                value["configuration"] = Configuration.validate(
                    {"disabled": {"tools": value.get("disabled", [])}}
                )
            if (
                not isinstance(value, dict)
                or set(value) != set(self.state)
                or value["version"] != 2
                or value["fingerprint"] != self.host.fingerprint
                or value["status"] != "ready"
                or not isinstance(value["disabled"], list)
                or len(value["disabled"]) > 128
                or any(not isinstance(n, str) for n in value["disabled"])
                or not isinstance(value["directories"], dict)
                or any(
                    k not in ("allowed_write_paths", "denied_write_paths")
                    or not isinstance(v, list)
                    or len(v) > 128
                    or any(not isinstance(p, str) or not Path(p).is_absolute() for p in v)
                    for k, v in value["directories"].items()
                )
                or (value["goal"] is not None and not isinstance(value["goal"], dict))
            ):
                raise ValueError("Local control state incompatible or uncertain; resume refused")
            self.state = value
            self.state["configuration"] = Configuration.validate(value["configuration"])
            if value["disabled"] != value["configuration"]["disabled"]["tools"]:
                raise ValueError("Saved tool configuration is inconsistent; resume refused")
            if value["goal"] is not None and not self.goal_supported():
                raise ValueError("Saved goal requires its original orchestrator")
            goal = value["goal"]
            if goal is not None and (
                not isinstance(goal.get("condition"), str)
                or not goal["condition"].strip()
                or type(goal.get("turns_used")) is not int
                or goal["turns_used"] < 0
                or not isinstance(goal.get("reasons"), list)
                or any(not isinstance(r, str) for r in goal["reasons"])
                or (
                    goal.get("cap") is not None
                    and (type(goal["cap"]) is not int or goal["cap"] <= 0)
                )
            ):
                raise ValueError("Saved goal state is invalid; resume refused")
            self.apply_directories(value["directories"])
            self.coordinator.session_state["goal"] = copy.deepcopy(value["goal"])
        elif self.host.store and self.host.store.metadata.get("local_controls"):
            raise ValueError("Saved local controls missing; resume refused")
        elif self.host.store and self.host.store.saved:
            # Old conversations with no control record used the prepared defaults.
            # A shared save is for new sessions, never a silent policy migration.
            self.state["configuration"] = Configuration.validate({})
        await self.configuration.apply(self.state["configuration"])
        self.state["configuration"] = self.configuration.snapshot()
        self.state["disabled"] = self.state["configuration"]["disabled"]["tools"]
        if self.state["configuration"] != Configuration.validate({}):
            self.save()  # Retain initial shared policy independently of future saves.

        # App controls are not tools or implicit grants. Explain recovery only
        # for the module whose policy this adapter can actually manage.
        from amplifier_core import HookResult

        async def filesystem_guidance(_event, _data):
            try:
                self.filesystem()
            except ValueError:
                return HookResult(action="continue")
            return HookResult(
                action="inject_context",
                context_injection=(
                    "TUI filesystem permission controls: if write_file/edit_file reports "
                    "a path outside allowed write paths or inside denied paths, mkdir does "
                    "not grant permission. Do not bypass that refusal with bash or another "
                    "tool. Ask the user to review /allowed-dirs and /denied-dirs in the TUI; "
                    "they can explicitly use /allowed-dirs add <narrow directory> if appropriate. "
                    "Denied paths still take precedence. These are user-entered local commands, "
                    "not model tools. Changes persist in this root session only, not children, "
                    "bash, or shared settings; this is not an OS sandbox."
                ),
                context_injection_role="system",
                ephemeral=True,
            )

        self.coordinator.hooks.register(
            "provider:request", filesystem_guidance, priority=99, name="tui-filesystem-controls"
        )
        # The CLI's mechanical backstop is host policy, independent of the
        # orchestrator's model-based stall judge. Only its rendering is replaced.
        from amplifier_app_cli.goal_circuit_breaker import (
            ENV_REPEAT_LIMIT,
            RepeatedReasonDetector,
            repeat_limit_from_env,
        )

        raw = os.environ.get(ENV_REPEAT_LIMIT, "").strip()
        try:
            limit = int(raw) if raw else repeat_limit_from_env({})
        except ValueError:
            limit = repeat_limit_from_env({})
            self.host.show_message(
                f"{ENV_REPEAT_LIMIT} is not an integer; using {limit} repeated reasons.",
                level="warning",
                source="goal",
            )
        self.goal_detector = RepeatedReasonDetector(limit)
        self.coordinator.hooks.register(
            "orchestrator:goal_progress",
            self.goal_progress,
            priority=0,
            name="tui-goal-circuit-breaker",
        )
        self.refresh_completion()

    def refresh_completion(self):
        """Discovery runs between turns/controls, never in a completion request."""
        from amplifier_app_cli.main import CommandProcessor
        from amplifier_app_cli.ui.completion import SlashCompletionEngine, build_completion_snapshot

        try:
            processor = CommandProcessor(self.host.session, "runtime")
            processor.configurator = self.configurator
            self.completion = SlashCompletionEngine(build_completion_snapshot(processor))
        except Exception:
            # Optional discovery cannot prevent finalization/checkpointing, nor
            # can we keep advertising a stale catalog after a failed refresh.
            self.completion = None
            self.host.show_message(
                "Command argument discovery unavailable", source="completion", level="warning"
            )

    def complete(self, text, cursor):
        from amplifier_app_cli.ui.completion import Candidate

        if (
            not isinstance(text, str)
            or len(text) > 32768
            or type(cursor) is not int
            or not 0 <= cursor <= len(text)
        ):
            raise ValueError("Invalid completion request")
        candidates = self.completion.complete(text, cursor) if self.completion else []
        before, after = text[:cursor], text[cursor:]
        words = before.split()
        prefix = "" if before[-1:].isspace() else words[-1] if words else ""
        complete_words = words if not prefix else words[:-1]
        # Reuse the CLI's cached names, but never advertise its unsupported
        # mutations, arbitrary value queries, save flags or renderer flags.
        if complete_words[:1] == ["/config"]:
            args = complete_words[1:]
            allowed = {"show", "diff", "set", "save", *self.config_categories} if not args else None
            if args == ["show"]:
                allowed = set(self.config_categories)
            mutable = bool(args and args[0] in Configuration.categories and len(args) <= 2)
            candidates = [
                c
                for c in candidates
                if (allowed is None or c.value in allowed)
                and (not c.value.startswith("--") or args[:1] == ["save"])
                and (mutable or c.value not in ("enable", "disable"))
                and not (
                    len(args) == 2
                    and args[0] == "tools"
                    and args[1] in ("enable", "disable")
                    and c.value == "mode"
                )
            ]
            if (
                len(args) >= 2
                and args[0] not in Configuration.categories
                and args[1] in ("enable", "disable")
            ):
                candidates = []
            if args == ["save", "--scope"] and "local".startswith(prefix):
                candidates.append(Candidate("local", "Project-local settings"))
            if (
                args[:1] == ["save"]
                and len(args) == 3
                and args[1] == "--scope"
                and args[2] in ("project", "global", "local")
            ):
                candidates = (
                    [Candidate("--confirm", "Explicitly save policy; YAML formatting may change")]
                    if "--confirm".startswith(prefix)
                    else []
                )
        if self.completion and "\n" not in before and (not after or after[0].isspace()):
            if complete_words == ["/provider"]:
                candidates.extend(Candidate(n) for n in ("status", "login") if n.startswith(prefix))
            elif complete_words == ["/provider", "login"]:
                candidates = [
                    Candidate(n) for n in self.completion.snapshot.providers if n.startswith(prefix)
                ]
        return {
            "candidates": [
                {
                    "value": c.value if after[:1].isspace() else c.insertion,
                    "description": c.description,
                }
                for c in candidates[:80]
                if len(c.value) <= 512 and c.value.isprintable()
            ],
            "truncated": len(candidates) > 80,
            "command_arguments": True,
        }

    async def goal_progress(self, _event, data):
        from amplifier_core import HookResult

        if not isinstance(data, dict) or data.get("state") != "continuing":
            return HookResult()
        goal = self.coordinator.session_state.get("goal")
        reason = data.get("reason")
        if not goal or not isinstance(reason, (str, type(None))):
            return HookResult()
        trip = self.goal_detector.observe(reason, turn=data.get("turn"))
        if trip:
            state = self.coordinator.session_state
            state["goal"] = None
            state["goal_circuit_breaker"] = {
                "state": "needs_manager",
                "repeated_message": trip.message,
                "repeats": trip.count,
                "turn": trip.turn,
            }
            # Remain pending until execution drains and its context checkpoint
            # commits. Never mark in-flight work safe merely because goal cleared.
            self.save("pending")
            self.host.emit("goal.status", "goal-status", **self.goal_status())
            self.host.show_message(
                f"Goal stopped · needs manager · same reason {trip.count} times\n"
                f"{trip.message}\nThe goal was not achieved. Review it before explicitly restarting.",
                level="error",
                source="goal",
            )
        return HookResult()

    def save(self, status="ready"):
        self.state["status"] = status
        self.state["goal"] = copy.deepcopy(self.coordinator.session_state.get("goal"))
        if self.path:
            atomic_json(self.path, self.state)
            if self.host.store and not self.host.store.metadata.get("local_controls"):
                self.host.store.metadata["local_controls"] = True
                atomic_json(self.host.store.path / "metadata.json", self.host.store.metadata)

    def goal_supported(self):
        loop = self.coordinator.get("orchestrator")
        from .composition import ExecutionOwner

        if isinstance(loop, ExecutionOwner):
            loop = loop.module
        return type(loop).__module__ == "amplifier_module_loop_streaming"

    def goal_status(self):
        goal = self.coordinator.session_state.get("goal")
        return {"active": bool(goal), "cap": goal.get("cap") if goal else None}

    @staticmethod
    def auth_status(provider):
        if not callable(getattr(provider, "auth_status", None)):
            return "module has no auth-status method"
        try:
            reported = provider.auth_status()
        except Exception:
            return "status unavailable"
        return (
            reported
            if reported in ("authenticated", "expired", "unauthenticated")
            else "status unknown"
        )

    def filesystem(self):
        tools = self.coordinator.get("tools") or {}
        selected = [tools.get(name) for name in ("write_file", "edit_file")]
        if any(
            type(t).__module__
            not in (
                "amplifier_module_tool_filesystem.write",
                "amplifier_module_tool_filesystem.edit",
            )
            for t in selected
        ):
            raise ValueError(
                "Directory changes require the supported write_file and edit_file mounts; re-enable both first"
            )
        return selected

    def apply_directories(self, values):
        if values:
            for tool in self.filesystem():
                for key, value in values.items():
                    setattr(tool, key, list(value))
                    tool.config[key] = list(value)

    def directory_change(self, command, tokens):
        key = "allowed_write_paths" if command == "/allowed-dirs" else "denied_write_paths"
        mounts = self.filesystem()
        if not tokens or tokens == ["list"]:
            return key, mounts, None
        if len(tokens) != 2 or tokens[0] not in ("add", "remove"):
            raise ValueError("Usage: " + command + " add|remove PATH")
        path = str((self.cwd / Path(tokens[1]).expanduser()).resolve())
        before = [list(getattr(tool, key)) for tool in mounts]
        if before[0] != before[1]:
            raise ValueError("Filesystem tools have different policies; use a new composition")
        paths = [str((self.cwd / Path(value).expanduser()).resolve()) for value in before[0]]
        if tokens[0] == "add":
            if path in paths:
                raise ValueError("Path already present; nothing changed")
            paths.append(path)
        elif path not in paths:
            raise ValueError("Path not present; nothing changed")
        else:
            paths.remove(path)
        if len(paths) > 128:
            raise ValueError("Directory control limit reached")
        return key, mounts, paths

    def config_query(self, tokens):
        """Validate inspection grammar without querying modules on admission."""
        args = tokens[1:] if tokens[:1] == ["show"] else tokens
        if not args:
            return self.config_categories, None
        if len(args) <= 2 and args[0] in self.config_categories:
            return (args[0],), args[1] if len(args) == 2 else None
        raise ValueError(
            "Usage: /config [show] [providers|tools|hooks|context|agents|behaviors] [NAME]. "
            "/config CATEGORY disable|enable NAME changes this session (hooks are read-only). "
            "/config diff | set PATH VALUE | save --scope project|local|global --confirm."
        )

    def config_report(self, tokens):
        """Loaded Foundation metadata only, not arbitrary config or source contents."""
        categories, selected = self.config_query(tokens)

        def field(item, key):
            return item.get(key) if isinstance(item, dict) else getattr(item, key, None)

        def label(value):
            if not isinstance(value, str):
                return "unavailable"
            value = " ".join("".join(c for c in value if c.isprintable()).split())
            return value[:159] + "…" if len(value) > 160 else value or "unnamed"

        lines = ["Loaded configuration · metadata only"]
        if len(categories) > 1:
            lines.extend(
                f"{key.capitalize()}: {label(value)}" for key, value in self.session_modules.items()
            )
        for category in categories:
            # Same public inspector as the CLI; it reflects runtime toggles and
            # mode contributions, without resolving bundles or reading files.
            try:
                records = getattr(self.configurator, category + "_list")()
            except Exception:
                lines.append(f"\n{category.capitalize()}: inspection unavailable")
                continue  # Third-party errors may contain secrets; omit values.
            if selected is not None:
                records = [r for r in records if field(r, "name") == selected]
                if not records:
                    lines.append("No matching configuration item; use the category list")
                    continue
            heading = {"agents": "Available agent definitions", "context": "Context entries"}.get(
                category, category.capitalize()
            )
            lines.append(f"\n{heading} · {len(records)}")
            for record in records[:32]:
                enabled = field(record, "enabled")
                status = (
                    "enabled" if enabled is True else "disabled" if enabled is False else "unknown"
                )
                module = field(record, "module_id")
                lines.append(
                    f"{label(field(record, 'name'))} · {status}"
                    + (f" · {label(module)}" if module else "")
                )
                if selected is not None:
                    origins = field(record, "origins") or []
                    for origin in origins[:8]:
                        lines.append("From: " + label(field(origin, "bundle")))
                    if len(origins) > 8:
                        lines.append(f"{len(origins) - 8} more origins omitted")
                    injection = field(record, "runtime_injection")
                    if injection:
                        lines.append("Introduced by: " + label(injection))
            if len(records) > 32:
                lines.append(
                    f"{len(records) - 32} more items omitted; /config show {category} NAME inspects an exact item"
                )
        lines.extend(
            [
                "\nRead-only. Shared settings unchanged.",
                "Values, source URLs and instruction contents omitted.",
            ]
        )
        if selected is None:
            lines.append("/config show CATEGORY NAME")
            if "tools" in categories:
                lines.append("/config tools disable|enable NAME")
        return "\n".join(lines)

    def recognizes(self, text):
        command = text.strip().split(maxsplit=1)[0].lower() if text.strip() else ""
        return (
            command
            in (
                "/goal",
                "/config",
                "/agents",
                "/tools",
                "/allowed-dirs",
                "/denied-dirs",
                "/provider",
                "/mode",
            )
            or command.startswith("/")
            and command[1:] in {m["name"] for m in self.host.modes.catalog()["choices"]}
        )

    def submit(self, text, image=False):
        parts = text.strip().split(maxsplit=1)
        command, args = parts[0].lower(), parts[1] if len(parts) > 1 else ""
        if command in ("/agents", "/tools"):
            args = command[1:] + (" " + args if args else "")
            command = "/config"
        names = {m["name"] for m in self.host.modes.catalog()["choices"]}
        if command[1:] in names:
            args = command[1:] + (" " + args if args else "")
            command = "/mode"
        if command not in (
            "/goal",
            "/config",
            "/allowed-dirs",
            "/denied-dirs",
            "/provider",
            "/mode",
        ):
            return None
        if image:
            return False, "Local controls cannot consume attachments; detach them first"
        try:
            tokens = shlex.split(args) if command not in ("/goal", "/mode") else []
            if command == "/goal" and not self.goal_supported():
                raise ValueError("This orchestrator has no supported goal protocol")
            if command == "/goal" and args:
                from amplifier_app_cli.main import _parse_goal_max_turns

                _, condition = _parse_goal_max_turns(args)
                if not condition:
                    raise ValueError("Goal requires condition text after its turn limit")
            if command == "/config":
                if len(tokens) == 3 and tokens[1] in ("disable", "enable"):
                    self.configuration.check_toggle(*tokens)
                elif tokens[:1] == ["set"]:
                    self.configuration.parse_setting(tokens)
                    if self.host.modes.current():
                        raise ValueError(
                            "Leave the active mode before editing configuration metadata"
                        )
                elif tokens[:1] == ["save"]:
                    if (
                        len(tokens) != 4
                        or tokens[1] != "--scope"
                        or tokens[2] not in ("project", "global", "local")
                        or tokens[3] != "--confirm"
                    ):
                        raise ValueError(
                            "Shared save rewrites selected settings (including YAML formatting). Explicitly use /config save --scope project|local|global --confirm; current modules are not reloaded"
                        )
                    if self.configuration.paths is None:
                        raise ValueError("Shared save requires a CLI-configured launch")
                    if self.host.modes.current():
                        raise ValueError("Leave the active mode before saving base configuration")
                elif tokens != ["diff"]:
                    self.config_query(tokens)
            if command in ("/allowed-dirs", "/denied-dirs"):
                self.directory_change(command, tokens)
            if command == "/provider" and tokens and tokens[0] in ("use", "auto"):
                if not (tokens == ["auto"] or len(tokens) == 2 and tokens[0] == "use"):
                    raise ValueError("Usage: /provider use NAME | /provider auto")
                result = self.host.controls.select(
                    {
                        **self.host.controls.catalog(),
                        "provider": tokens[1] if len(tokens) == 2 else None,
                    }
                )
                if result[0]:
                    self.host.show_message(result[1], source="provider")
                    if self.wire:
                        self.wire(
                            {
                                "type": "providers",
                                "session_id": self.host.session_id,
                                **self.host.controls.catalog(),
                            }
                        )
                return result
            if command == "/provider" and tokens[:1] == ["login"]:
                if len(tokens) != 2 or not self.wire:
                    raise ValueError("Usage: /provider login NAME in the native client")
                provider = (self.coordinator.get("providers") or {}).get(tokens[1])
                if not inspect.iscoroutinefunction(
                    getattr(provider, "login", None)
                ) or not callable(getattr(provider, "auth_status", None)):
                    raise ValueError(
                        "Provider has no supported asynchronous login; use its external setup"
                    )
            elif (
                command == "/provider" and tokens and tokens[0] not in ("status", "models", "test")
            ):
                raise ValueError(
                    "Usage: /provider status | use NAME | auto | models | test NAME | login NAME"
                )
            if command == "/mode":
                if not self.host.modes.supported:
                    raise ValueError("No supported mode module mounted")
                if not args.strip():
                    self.host.show_message(f"Mode: {self.host.modes.current() or 'default'}")
                    return True, "Mode status; nothing changed"
                if args.strip().split()[0] == "info":
                    from dataclasses import asdict

                    words = args.strip().split()
                    name = words[1] if len(words) == 2 else self.host.modes.current()
                    mode = (
                        self.host.modes.discovery.find(name) if name and len(words) <= 2 else None
                    )
                    if mode is None:
                        raise ValueError("Usage: /mode info NAME for a discovered mode")
                    self.host.show_message(json.dumps(asdict(mode), ensure_ascii=False, indent=2))
                    return True, "Authored mode definition; nothing changed"
                from amplifier_app_cli.main import CommandProcessor

                mode_args, trailing = CommandProcessor(
                    self.host.session, "runtime"
                )._split_mode_trailing(args)
                tokens = mode_args.split()
                name = tokens[0] if tokens else None
                if name == "off" or len(tokens) == 2 and tokens[1] == "off":
                    if len(tokens) == 2 and self.host.modes.current() != name:
                        raise ValueError("That mode is not active; nothing changed")
                    name = None
                elif name not in {m["name"] for m in self.host.modes.catalog()["choices"]}:
                    raise ValueError("Choose a discovered mode")
                elif len(tokens) == 1 and self.host.modes.current() == name:
                    name = None  # Pinned CLI's no-suffix toggle semantics.
                if trailing:

                    async def activate_then_prompt():
                        result = await self.host.modes.execute(
                            {"operation": "set", "name": name}, explicit=True
                        )
                        if not result.success or self.host.modes.current() != name:
                            raise ValueError(
                                "Mode transition refused; trailing prompt was not sent"
                            )
                        return trailing

                    return self.host.submit(text, preflight=activate_then_prompt)
                return self.host.modes.select({"mode": name, "current": self.host.modes.current()})
        except ValueError as exc:
            return False, str(exc)
        self.host._stop_requested = False
        self.host._force_requested = False
        self.coordinator.cancellation.reset()
        self.host._execution_started = False
        self.host._finalizing = False
        self.host.task = asyncio.create_task(self.run(command, args, tokens))
        return True, "Local control accepted; no conversation turn submitted"

    async def run(self, command, args, tokens):
        host = self.host
        auth = command == "/provider" and tokens[:1] == ["login"]
        try:
            host._execution_started = True
            if host._stop_requested:
                raise asyncio.CancelledError
            if self.wire:
                self.wire(
                    {
                        "type": "state",
                        "session_id": host.session_id,
                        "ready": True,
                        "busy": True,
                        "status": "Provider login · Stop cancels"
                        if auth
                        else "Applying local control",
                    }
                )
            if auth:
                provider = self.coordinator.get("providers")[tokens[1]]
                prompts = []

                def display(value):
                    prompts.append(str(value)[:4096])
                    del prompts[:-16]
                    self.wire(
                        {
                            "type": "auth_prompt",
                            "session_id": host.session_id,
                            "text": "\n".join(prompts),
                            "active": True,
                        }
                    )

                display(
                    "Provider-owned login. Credentials stay in its configured store. Stop cancels; dismissal does not authorize anything."
                )
                await asyncio.wait_for(provider.login(print_fn=display), timeout=600)
                host.show_message(
                    "Provider login: " + self.auth_status(provider), source="provider"
                )
            elif command == "/goal":
                from amplifier_app_cli.main import CommandProcessor

                self.save("pending")
                message = await CommandProcessor(host.session, "runtime")._handle_goal(args)
                if args.strip():
                    self.goal_detector.reset()
                    self.coordinator.session_state.pop("goal_circuit_breaker", None)
                self.save()
                host.emit("goal.status", "goal-status", **self.goal_status())
                host.show_message(
                    message
                    + " No turn started. A goal may continue provider work (and incur charges) after your next Send; /goal clear removes it.",
                    source="goal",
                )
            elif command == "/config":
                if len(tokens) == 3 and tokens[1] in ("disable", "enable"):
                    note = await self.configuration.toggle(*tokens)
                    host.report["tools"] = sorted(self.coordinator.get("tools") or {})
                    if self.wire:
                        self.wire(
                            {
                                "type": "runtime_tools",
                                "session_id": host.session_id,
                                "tools": host.report["tools"],
                            }
                        )
                        self.wire(
                            {
                                "type": "providers",
                                "session_id": host.session_id,
                                **host.controls.catalog(),
                            }
                        )
                    host.show_message(
                        f"{tokens[0]} · {tokens[2]} · {tokens[1]} applied. "
                        + note
                        + self.config_scope,
                        source="config",
                    )
                elif tokens == ["diff"]:
                    snapshot = self.configuration.snapshot()
                    rows = [
                        f"{category}: {', '.join(names)} disabled"
                        for category, names in snapshot["disabled"].items()
                        if names
                    ]
                    rows += [
                        f"{path}: metadata edited (value omitted)"
                        for path in snapshot["config_overrides"]
                    ]
                    host.show_message(
                        "Configuration changes from prepared mounts\n"
                        + ("\n".join(rows) if rows else "No changes")
                        + "\nShared settings unchanged; edited metadata does not reinitialize modules.",
                        source="config",
                    )
                elif tokens[:1] == ["set"]:
                    path, value = self.configuration.parse_setting(tokens)
                    self.save("pending")
                    self.configurator.config_set(path, value)
                    self.configuration.overrides[path] = value
                    self.state["configuration"] = self.configuration.snapshot()
                    self.save()
                    host.show_message(
                        "Configuration metadata edited (value omitted). Modules were not reinitialized; live adoption is module-owned. /config diff inspects changes; shared settings unchanged.",
                        source="config",
                    )
                elif tokens[:1] == ["save"]:
                    self.configuration.persist(tokens[2])
                    host.show_message(
                        f"Configuration saved · {tokens[2]} scope. Applies to future compatible launches; current modules were not reinitialized. YAML formatting may change.",
                        source="config",
                    )
                else:
                    host.show_message(self.config_report(tokens), source="config")
            elif command in ("/allowed-dirs", "/denied-dirs"):
                key, mounts, paths = self.directory_change(command, tokens)
                if paths is None:
                    host.show_message(
                        "\n".join(f"{t.name}: {getattr(t, key)}" for t in mounts)
                        + "\nUse add PATH or remove PATH. "
                        + self.scope
                    )
                else:
                    self.save("pending")
                    self.state["directories"][key] = paths
                    self.apply_directories(self.state["directories"])
                    self.save()
                    host.show_message(
                        "Filesystem policy applied to write_file and edit_file. Deny takes precedence. "
                        + self.scope
                    )
            elif command == "/provider":
                if tokens[:1] == ["models"] and len(tokens) <= 2:
                    value = await host.controls.discover_models(
                        tokens[1] if len(tokens) == 2 else None,
                        progress=lambda name: host.show_message(
                            f"Discovering models · {name}", source="provider"
                        ),
                    )
                elif tokens[:1] == ["test"] and len(tokens) <= 2:
                    value = await host.controls.validate_providers(
                        tokens[1] if len(tokens) == 2 else None
                    )
                elif not tokens or tokens == ["status"]:
                    value = host.controls.catalog()
                    value["authentication"] = {}
                    for name, provider in (self.coordinator.get("providers") or {}).items():
                        value["authentication"][name] = self.auth_status(provider)
                else:
                    raise ValueError("Usage: /provider status | models [NAME] | test [NAME]")
                host.show_message(
                    json.dumps(value, ensure_ascii=False, indent=2), source="provider"
                )
        except asyncio.CancelledError:
            host.show_message(
                "Local control stopped; external effects may already have occurred. No automatic retry."
            )
            raise
        except Exception as exc:
            host.show_message(
                f"Local control failed ({type(exc).__name__})"
                if auth or command == "/config"
                else f"Local control refused: {exc}"
            )
        finally:
            host._finalizing = True
            self.refresh_completion()
            if self.state["status"] != "ready":
                host.ready = False
                host.show_message(
                    "Local control outcome uncertain; session disabled, no automatic retry"
                )
            if auth and self.wire:
                self.wire(
                    {
                        "type": "auth_prompt",
                        "session_id": host.session_id,
                        "active": False,
                        "text": "Login finished or stopped; transient prompts cleared",
                    }
                )
            if host.store:
                try:
                    host.store.checkpoint(
                        await self.coordinator.get("context").get_messages(),
                        host.sequence,
                        host.fingerprint,
                        host.ready,
                    )
                except Exception:
                    host.ready = False
                    host.show_message(
                        "Local control checkpoint failed; session disabled, no automatic retry"
                    )
            if self.wire:
                self.wire(
                    {
                        "type": "state",
                        "session_id": host.session_id,
                        "ready": host.ready,
                        "busy": False,
                        "status": "Ready" if host.ready else "Control recovery required",
                    }
                )


class RuntimeControls:
    def __init__(self, host):
        self.host = host
        coordinator = host.session.coordinator
        self.steer_cap = coordinator.get_capability("session.steer")
        self.pin = coordinator.get_capability("conversation.provider_pin")
        if not all(
            callable(getattr(self.pin, method, None))
            for method in ("available", "current", "pin", "unpin")
        ):
            self.pin = None
        host.capabilities["steer"] = callable(self.steer_cap)
        host.capabilities["conversation_provider"] = self.pin is not None
        self.pending = {}
        self.count = 0
        self.state = {
            "version": 1,
            "session_id": host.session_id,
            "fingerprint": host.fingerprint,
            "status": "ready",
            "revision": 0,
            "provider": self.pin.current() if self.pin else None,
            "changes": [],
        }
        self.path = host.store.path / "controls.json" if host.store else None
        if self.path and self.path.exists():
            value = json.loads(self.path.read_text())
            if (
                not isinstance(value, dict)
                or value.get("version") != 1
                or value.get("session_id") != host.session_id
                or value.get("fingerprint") != host.fingerprint
                or value.get("status") != "ready"
                or type(value.get("revision")) is not int
                or not 0 <= value["revision"] <= 1000
                or not isinstance(value.get("changes"), list)
                or len(value["changes"]) != value["revision"]
                or "provider" not in value
                or (value.get("provider") is not None and not isinstance(value["provider"], str))
                or any(
                    not isinstance(change, dict)
                    or set(change) != {"request_id", "from", "to"}
                    or any(
                        change[key] is not None and not isinstance(change[key], str)
                        for key in change
                    )
                    for change in value["changes"]
                )
                or (value["changes"] and value["changes"][-1]["to"] != value["provider"])
            ):
                raise ValueError("Invalid or uncertain runtime controls; resume refused")
            self.state = value
            if self.pin is None and (value["provider"] is not None or value["revision"]):
                raise ValueError("Saved conversation provider capability unavailable")
            if self.pin:
                self.pin.unpin() if value["provider"] is None else self.pin.pin(value["provider"])
                if self.pin.current() != value["provider"]:
                    raise ValueError("Saved conversation provider could not be restored")
        elif self.path:
            if host.store.metadata.get("runtime_controls"):
                raise ValueError("Missing runtime controls; resume refused")
            self.save(self.state)
        if host.store and not host.store.metadata.get("runtime_controls"):
            metadata = {**host.store.metadata, "runtime_controls": True}
            atomic_json(host.store.path / "metadata.json", metadata)
            host.store.metadata = metadata

    def save(self, value):
        if self.path:
            atomic_json(self.path, value)
        self.state = value

    def catalog(self):
        choices = []
        if self.pin:
            mounted = self.host.session.coordinator.get("providers") or {}
            for name in self.pin.available():
                vendor, model = "unknown", "configured by module"
                try:
                    info = mounted[name].get_info()
                    vendor = info.id
                    model = (info.defaults or {}).get("model", model)
                except Exception:
                    pass
                choices.append({"name": name, "vendor": str(vendor), "model": str(model)})
        return {
            "supported": self.pin is not None,
            "current": self.pin.current() if self.pin else None,
            "revision": self.state["revision"],
            "choices": choices,
            "changes": copy.deepcopy(self.state["changes"]),
            "durable": self.path is not None,
            "scope": "Top-level conversation only. Model-role routing, goal utilities and delegated agents are unchanged. Same-vendor mounted choices only; other configuration needs a new launch.",
        }

    async def discover_models(self, name=None, *, progress=None):
        """Explicit advisory discovery, outside painting/keypress and without mutation."""
        from amplifier_app_cli.provider_diagnostics import invoke_list_models

        mounted = self.host.session.coordinator.get("providers") or {}
        if name is not None:
            if name not in mounted:
                raise ValueError("Provider is not mounted; nothing queried")
            mounted = {name: mounted[name]}
        rows, partial = [], False
        for name, provider in mounted.items():
            if progress:
                progress(name)
            try:
                models = await asyncio.wait_for(invoke_list_models(provider), timeout=3)
                if not isinstance(models, list):
                    raise ValueError("Invalid model catalog")
                partial |= len(models) > 128
                for model in models[:128]:
                    identity = (
                        model.get("id") if isinstance(model, dict) else getattr(model, "id", None)
                    )
                    if (
                        not isinstance(identity, str)
                        or not 0 < len(identity) <= 256
                        or not identity.isprintable()
                    ):
                        partial = True
                        continue
                    limits = {}
                    for key in ("context_window", "max_output_tokens"):
                        value = (
                            model.get(key) if isinstance(model, dict) else getattr(model, key, None)
                        )
                        if type(value) is int and 0 < value <= 2**31 - 1:
                            limits[key] = value
                    capabilities = (
                        model.get("capabilities", [])
                        if isinstance(model, dict)
                        else getattr(model, "capabilities", [])
                    )
                    capabilities = (
                        [
                            c
                            for c in capabilities[:32]
                            if isinstance(c, str)
                            and c in ("tools", "vision", "thinking", "streaming", "json_mode")
                        ]
                        if isinstance(capabilities, list)
                        else []
                    )
                    rows.append(
                        {
                            "provider": str(name)[:160],
                            "model": identity,
                            "status": "provider reported",
                            "limits": limits,
                            "capabilities": capabilities,
                        }
                    )
                if not models:
                    rows.append(
                        {
                            "provider": str(name)[:160],
                            "model": "",
                            "status": "empty catalog; availability unknown",
                        }
                    )
            except Exception as exc:
                # Exception messages can contain URLs/credentials; expose type only.
                rows.append(
                    {
                        "provider": str(name)[:160],
                        "model": "",
                        "status": f"unavailable ({type(exc).__name__})",
                    }
                )
                partial = True
        return {
            "rows": rows,
            "partial": partial,
            "scope": "Provider-reported IDs, model limits and advertised capabilities, possibly a static catalog; not credential, access, image support or selection validation. Context window is not the current request budget or remaining capacity; output reserves, tools, instructions and module policy still apply. Missing limits remain unknown. Every selected mounted provider / up to 128 IDs each; cooperative 3-second timeout per provider. Use /provider models NAME for one instance. Copy an ID for --setup / a new overlay. Current conversation and routing are unchanged.",
        }

    async def validate_providers(self, name=None):
        """CLI's explicit all-or-one test; sequential, cancellable, no turn admission."""
        mounted = self.host.session.coordinator.get("providers") or {}
        if name is not None:
            if name not in mounted:
                raise ValueError("Provider is not mounted; nothing sent")
            return await self.validate_provider(name)
        results = {}
        for name in mounted:
            self.host.show_message(
                f"Testing provider · {name} · standalone request may incur cost", source="provider"
            )
            results[name] = await self.validate_provider(name)
        return {
            "providers": results,
            "scope": "Explicit standalone probes; conversation and routing unchanged",
        }

    async def validate_provider(self, name):
        """An explicit standalone probe, not a conversation turn or model change."""
        from amplifier_core import ChatRequest, Message

        provider = (self.host.session.coordinator.get("providers") or {}).get(name)
        if provider is None:
            return {"ok": False, "message": "Provider is not mounted; nothing sent"}
        self.host.validation_active = True
        try:
            request = ChatRequest(
                messages=[Message(role="user", content="Reply OK.")],
                tools=None,
                max_output_tokens=16,
                stream=False,
                timeout=15,
                metadata={"purpose": "explicit credential/access validation"},
            )
            await asyncio.wait_for(provider.complete(request), timeout=20)
            return {
                "ok": True,
                "message": "Provider returned a response to the standalone probe. This proves only this configured request succeeded now; not other models, routing, tools, quotas or future access.",
            }
        except Exception as exc:
            return {
                "ok": False,
                "message": f"Provider probe failed ({type(exc).__name__}). Check credentials, model access and provider settings privately. Error text/response withheld; no automatic retry by the app.",
            }
        finally:
            self.host.validation_active = False

    def select(self, request):
        host = self.host
        if not host.ready or (host.task and not host.task.done()):
            return False, "Finish the active turn before selecting a conversation provider"
        if not self.pin:
            return False, "This orchestrator has no conversation-provider selection capability"
        if (
            request.get("revision") != self.state["revision"]
            or request.get("current") != self.pin.current()
        ):
            return False, "Provider choice changed; reopen the provider menu"
        name = request.get("provider")
        if name is not None and (not isinstance(name, str) or name not in self.pin.available()):
            return False, "Choose a currently mounted provider"
        if self.state["revision"] >= 1000:
            return False, "Provider change history full (1000); start a new conversation"
        before = copy.deepcopy(self.state)
        try:
            # Before any module mutation: a crash or failed final save refuses
            # reopening rather than silently selecting the previous provider.
            self.save({**before, "status": "pending"})
            try:
                self.pin.unpin() if name is None else self.pin.pin(name)
            except ValueError as exc:
                # Public capability promises validation before mutation.
                if self.pin.current() != request.get("current"):
                    raise RuntimeError("Provider changed during a rejected selection") from exc
                self.save(before)
                return False, str(exc)
            if self.pin.current() != name:
                raise RuntimeError("Provider capability did not apply the requested selection")
            self.save(
                {
                    **before,
                    "revision": before["revision"] + 1,
                    "provider": name,
                    "changes": [
                        *before["changes"],
                        {
                            "request_id": request.get("request_id"),
                            "from": request.get("current"),
                            "to": name,
                        },
                    ],
                }
            )
        except Exception:
            host.ready = False
            return False, "Provider control storage/outcome uncertain; session disabled, no retry"
        return True, "Conversation provider saved; routing elsewhere is unchanged"

    def steer(self, request):
        host = self.host
        text = request.get("text")
        if not isinstance(text, str) or not text.strip() or len(text) > 65536:
            return False, "Correction requires 1–65536 characters"
        if not callable(self.steer_cap):
            return False, "This orchestrator has no steering capability"
        if (
            not host.ready
            or not host.task
            or host.task.done()
            or host._stop_requested
            or request.get("turn_id") != host.turn_id
        ):
            return False, "Correction targets a turn that is no longer active; text retained"
        if not host._request_index:
            return False, "Turn is still starting; wait for its first provider request"
        if self.count >= 20:
            return False, "Correction limit reached (20 per turn); text retained"
        identity = uuid.uuid4().hex
        wire = f"[User correction {identity} for active turn {host.turn_id}]\n{text}"
        row = {"text": text, "status": "pending", "request_id": request.get("request_id")}
        # record() fsyncs this admission before handing intent to the module.
        try:
            host.emit("steering.updated", identity, **row)
        except Exception:
            host.ready = False
            return False, "Correction admission could not be saved; session disabled, no retry"
        self.pending[wire] = (identity, row)
        self.count += 1
        try:
            self.steer_cap(wire)
        except Exception:
            self.pending.pop(wire, None)
            host.emit("steering.updated", identity, **{**row, "status": "unconfirmed"})
            return False, "Correction delivery unconfirmed; no retry or automatic follow-up"
        return (
            True,
            "Correction accepted; waits for the next input boundary. Stop requests cancellation.",
        )

    def applied(self, data):
        pending = self.pending.pop(data.get("content"), None)
        if pending:
            identity, row = pending
            self.host.emit("steering.updated", identity, **{**row, "status": "applied"})

    def ended(self):
        for identity, row in self.pending.values():
            self.host.emit("steering.updated", identity, **{**row, "status": "unconfirmed"})
        self.pending.clear()
        self.count = 0

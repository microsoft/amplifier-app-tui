"""App-side adapters over public coordinator capabilities; no kernel policy.

Steering uses an identified envelope because the module's queue accepts strings.
Provider selection is a separate, fail-closed control record, not model context.
"""

import asyncio
import copy
import json
import uuid

from .conversations import atomic_json


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

    async def discover_models(self):
        """Explicit advisory discovery, outside painting/keypress and without mutation."""
        mounted = self.host.session.coordinator.get("providers") or {}
        rows, partial = [], len(mounted) > 8
        for name, provider in list(mounted.items())[:8]:
            try:
                models = await asyncio.wait_for(provider.list_models(), timeout=3)
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
                    rows.append(
                        {
                            "provider": str(name)[:160],
                            "model": identity,
                            "status": "provider reported",
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
            "scope": "Provider-reported IDs, possibly a static catalog; not credential, access, image support or selection validation. Up to 8 mounted providers / 128 IDs each; cooperative 3-second timeout per provider. Copy an ID for --setup / a new overlay. Current conversation and routing are unchanged.",
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
        return True, "Correction accepted; waiting for runtime insertion, not a new turn"

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

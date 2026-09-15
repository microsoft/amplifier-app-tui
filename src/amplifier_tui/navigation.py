"""App-owned local discovery and explicit conversation changes, not orchestration."""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
from pathlib import Path

from .conversations import ConversationStore, atomic_json, catalog, resolve_resume
from .followups import Followups
from .host import RuntimeBridge, SessionHost


def file_candidates(cwd, query):
    """One directory, at most 2000 inspected names and 80 returned suggestions.

    No recursion, file-content reads, shell expansion or symlink suggestions.
    This is a discovery scope, not an OS sandbox against concurrent filesystem edits.
    """
    if (
        not isinstance(query, str)
        or len(query) > 4096
        or not query.startswith("./")
        or not query.isprintable()
    ):
        raise ValueError("File completion starts with ./ and stays inside the working directory")
    relative = query[2:]
    parent, _, prefix = relative.rpartition("/")
    if ".." in Path(relative).parts:
        raise ValueError("Completion cannot traverse outside the working directory")
    root = Path(cwd).resolve()
    directory = (root / parent).resolve()
    if not directory.is_relative_to(root):
        raise ValueError("Completion cannot follow a link outside the working directory")
    matches = []
    truncated = False
    with os.scandir(directory) as entries:
        for index, entry in enumerate(entries):
            if index >= 2000:
                truncated = True
                break
            name = entry.name
            if not name.startswith(prefix) or (name.startswith(".") and not prefix.startswith(".")):
                continue
            if not name.isprintable() or entry.is_symlink():
                continue
            value = "./" + (parent + "/" if parent else "") + name
            if entry.is_dir(follow_symlinks=False):
                value += "/"
            if any(c.isspace() or c in '\\"' for c in value):
                value = json.dumps(value, ensure_ascii=False)
            matches.append(value)
    matches.sort()
    return {"candidates": matches[:80], "truncated": truncated or len(matches) > 80}


def session_choices(state_dir, current, *, offset=0, query=""):
    if type(offset) is not int or not 0 <= offset <= 100000:
        raise ValueError("Invalid conversation page")
    if not isinstance(query, str) or len(query) > 256 or (query and not query.isprintable()):
        raise ValueError("Search requires at most 256 printable characters")
    entries = catalog(state_dir)
    choices = []
    matches, partial = {}, False
    if query:
        from .history_index import search

        matches, partial = search(state_dir, entries, query)
        entries = [
            entry
            for entry in entries
            if entry["id"] in matches
            or query.casefold()
            in f"{entry['id']} {entry.get('title', '')} {entry.get('launch', {}).get('cwd', '')}".casefold()
        ]
    for entry in entries[offset : offset + 100]:
        identity = entry["id"]
        launch = entry.get("launch")
        if not isinstance(launch, dict) or not isinstance(launch.get("cwd"), str):
            continue
        label = entry.get("title")
        if not label:
            # Older checkpoints predate title metadata. Inspect only a bounded
            # prefix of this app's private journal, never the tool workspace.
            try:
                with (
                    Path(state_dir) / "conversations" / identity / "events.jsonl"
                ).open() as stream:
                    for line in stream.read(65536).splitlines():
                        event = json.loads(line)
                        if event.get("kind") == "turn.accepted":
                            label = " ".join(event["payload"]["text"].split())[:100]
                            break
            except (OSError, ValueError, KeyError, TypeError):
                pass
        label = label or "Untitled conversation"
        status = "current" if identity == current else "saved · validated when opened"
        if identity != current:
            try:
                with (
                    Path(state_dir) / "conversations" / identity / "checkpoint.json"
                ).open() as stream:
                    raw = stream.read(65537)
                # Large canonical checkpoints (including images) are validated on
                # opening, not loaded wholesale just to populate a discovery menu.
                checkpoint = json.loads(raw) if len(raw) <= 65536 else None
                if checkpoint is not None and checkpoint.get("status") != "ready":
                    status = "recovery required · original preserved"
            except (OSError, ValueError):
                status = "unavailable · invalid checkpoint"
        match = matches.get(identity, "")
        choices.append(
            {"id": identity, "title": label, "cwd": launch["cwd"], "status": status, "match": match}
        )
    return {
        "sessions": choices,
        "truncated": offset + 100 < len(entries),
        "offset": offset,
        "next_offset": offset + 100 if offset + 100 < len(entries) else None,
        "query": query,
        "partial": partial,
        "scope": "This app's state directory; 100 matching conversations per page. Private full-text index of submitted/final messages, not tool output. Refresh reads up to 16 MiB / 1 second; repeat search to continue incomplete indexing. Records over 1 MiB are skipped with partial disclosure; no context imported. Pages may shift as sources change.",
    }


class WorkspaceBridge(RuntimeBridge):
    def __init__(self, *args, state_dir, open_launch, **kwargs):
        super().__init__(*args, **kwargs)
        self.navigation_enabled = True
        self.state_dir, self.open_launch = state_dir, open_launch
        self.switch_task = None
        self.lookup_task = None
        self.switch_committing = False
        self.followups = None
        self.review_task = None
        self.review = None
        self.history_loading = True
        self.history_state = None
        self.transport_emit = self.emit
        self.emit = self.publish

    def publish(self, value):
        if self.history_loading and value.get("type") == "state" and value.get("ready"):
            self.history_state = value
            value = {**value, "ready": False, "status": "Loading directory history; not ready"}
        self.transport_emit(value)

    async def open(self):
        try:
            await super().open()
            await self.history()
        finally:
            self.history_loading = False

    async def history(self):
        from .input_history import recall

        identity = self.host.session_id
        value = await asyncio.to_thread(
            recall, self.state_dir, self.cwd, identity, include_current=True
        )
        if identity == self.host.session_id:
            self.emit({"type": "input_history", "session_id": identity, **value})
        self.history_loading = False
        if self.history_state and self.host.ready:
            self.emit(self.history_state)
        self.history_state = None

    def snapshot(self, reset=False):
        if self.followups is None:
            self.followups = Followups(self.host, self.emit)
        super().snapshot(reset)
        self.followups.publish()
        self.publish_image()
        self.emit(
            {
                "type": "title",
                "text": self.host.store.metadata.get("title", "Untitled conversation"),
            }
        )

    def command(self, request):
        # Existing non-navigation clients remain usable until a switch is requested.
        # The working client always supplies identity; after switching it is required.
        identity = request.get("session_id")
        if identity is not None and identity != self.host.session_id:
            return False, "Conversation changed; stale request rejected"
        if getattr(self, "switched", False) and identity is None:
            return False, "Conversation identity required after switching"
        preserved, reason = self.preserve_startup_draft(request)
        if not preserved:
            return False, reason
        if request.get("op") == "cancel_switch":
            if self.switch_task and not self.switch_task.done() and not self.switch_committing:
                self.switch_task.cancel()
                return True, "Cancelling opening; source draft retained"
            return False, "No cancellable opening; wait for the current change to finish"
        if self.switch_task and not self.switch_task.done():
            return False, "Opening conversation; editing is paused, source draft saved"
        op = request.get("op")
        if self.host.validation_active and op == "stop":
            if self.lookup_task:
                self.lookup_task.cancel()
            return (
                True,
                "Provider probe cancellation requested; remote delivery may already have occurred",
            )
        if self.host.validation_active and op not in ("draft", "editor_draft"):
            return False, "Standalone provider validation is running; draft retained"
        if op == "validate_provider":
            if (
                identity != self.host.session_id
                or not self.host.ready
                or (self.host.task and not self.host.task.done())
            ):
                return False, "Provider validation requires the idle current conversation"
            if request.get("confirm_remote") is not True:
                return False, "Confirm a standalone remote provider request; charges may apply"
            if not isinstance(request.get("provider"), str):
                return False, "Choose a mounted provider"
            if self.lookup_task and not self.lookup_task.done():
                return False, "A lookup is still running"
            self.followups.hold()
            self.host.validation_active = True
            self.lookup_task = asyncio.create_task(self.validate_provider(request))
            return True, "Standalone provider probe; no conversation or workspace content sent"
        if self.history_loading and op in ("submit", "queue", "queue_run", "switch"):
            return False, "Loading directory history; draft retained, send when ready"
        if op == "inspect" and request.get("category") == "stored_context":
            if (
                identity != self.host.session_id
                or not self.host.ready
                or (self.host.task and not self.host.task.done())
            ):
                return False, "Stored context inspection requires the idle current conversation"
            if self.lookup_task and not self.lookup_task.done():
                return False, "A lookup is still running"
            self.lookup_task = asyncio.create_task(self.inspect_context(request))
            return True, "Reading stored context; no provider request or compaction"
        if op == "discover_models":
            if identity != self.host.session_id or not self.host.ready:
                return False, "Model discovery requires the ready current conversation"
            if self.lookup_task and not self.lookup_task.done():
                return False, "A lookup is still running"
            self.lookup_task = asyncio.create_task(self.discover_models(request))
            return True, "Querying provider-reported model catalogs; no completion or selection"
        if op in ("image_select", "image_remove"):
            if identity != self.host.session_id or not self.host.images:
                return False, "Image input requires the current conversation"
            try:
                if op == "image_select":
                    self.followups.hold()
                    self.host.images.select(request.get("id"))
                else:
                    self.host.images.remove(request.get("id"), request.get("item_id"))
            except (OSError, ValueError) as exc:
                return False, str(exc)
            self.publish_image()
            return True, "Image draft updated; nothing sent"
        if op == "export":
            from .recovery import export

            path = export(self.state_dir, self.host.session_id)
            self.emit(
                {
                    "type": "error",
                    "message": f"Private transcript saved: {path} (may contain sensitive data)",
                }
            )
            return True, f"Exported to {path}"
        if op in ("file_snapshot", "image_snapshot", "clipboard_image"):
            if identity != self.host.session_id:
                return False, "File input requires the current conversation identity"
            if self.lookup_task and not self.lookup_task.done():
                return False, "Local lookup is still running"
            self.lookup_task = asyncio.create_task(self.file_snapshot(request))
            return True, "Reading the explicitly selected local file; nothing submitted"
        if op in ("workspace_changes", "workspace_diff"):
            if identity != self.host.session_id:
                return False, "Workspace review requires the current conversation identity"
            if self.review_task and not self.review_task.done():
                return False, "Workspace review is still reading; try again"
            self.review_task = asyncio.create_task(self.workspace_review(request))
            return True, "Reading local Git state; no model or tool execution"
        if op in ("provider_select", "mode_select"):
            # Changing the provider is not permission to release waiting work.
            self.followups.hold()
        if op == "rename":
            title = request.get("text")
            if (
                not isinstance(title, str)
                or not title.strip()
                or len(title) > 100
                or not title.isprintable()
            ):
                return False, "Use 1–100 printable characters for the name"
            metadata = {**self.host.store.metadata, "title": title.strip()}
            atomic_json(self.host.store.path / "metadata.json", metadata)
            self.host.store.metadata = metadata
            self.emit({"type": "title", "text": metadata["title"]})
            return True, "Conversation renamed"
        if op in (
            "queue",
            "queue_run",
            "queue_pause",
            "queue_remove",
            "queue_edit",
            "queue_resolve",
        ):
            if not self.host.ready:
                return False, "Session not ready; draft retained"
            if (
                op == "queue"
                and self.host.images
                and self.host.images.value
                and self.host.images.value["state"] == "attached"
                and request.get("image_id") != self.host.images.value["id"]
            ):
                return False, "Attached images require their explicit identity; draft retained"
            result = self.followups.command(request)
            self.publish_image()
            return result
        if op == "stop":
            if self.followups is not None:
                self.followups.hold()
        if op in ("conversations", "complete_path"):
            if self.lookup_task and not self.lookup_task.done():
                return False, "Local lookup is still running; try again"
            self.lookup_task = asyncio.create_task(self.lookup(request))
            return True, "Looking up local choices"
        if op == "switch":
            if not self.host.ready or (self.host.task and not self.host.task.done()):
                return False, "Finish or stop the active turn before changing conversations"
            if not isinstance(request.get("draft"), str):
                return False, "Switch requires the current draft"
            target = request.get("target")
            if target == self.host.session_id:
                return False, "Already in that conversation"
            if target != "new" and not isinstance(target, str):
                return False, "Choose a saved conversation or new"
            try:
                self.host.store.save_draft(request["draft"])
            except OSError:
                return False, "Could not save source draft; conversation unchanged"
            self.followups.hold()
            self.switch_task = asyncio.create_task(
                self.switch(target, request["request_id"], recover=bool(request.get("recover")))
            )
            self.switch_task.add_done_callback(
                lambda task: self.cancelled_before_start(task, request["request_id"])
            )
            return True, "Opening conversation; source draft saved"
        result = super().command(request)
        if op == "submit":
            self.publish_image()
        return result

    def publish_image(self):
        self.emit(
            {
                "type": "image_draft",
                "session_id": self.host.session_id,
                "image": self.host.images.public() if self.host.images else None,
                "supported": self.host.supports_images(),
            }
        )

    async def discover_models(self, request):
        identity = self.host.session_id
        value = await self.host.controls.discover_models()
        if identity == self.host.session_id:
            self.emit(
                {
                    "type": "model_catalog",
                    "session_id": identity,
                    "request_id": request.get("request_id"),
                    **value,
                }
            )

    async def validate_provider(self, request):
        identity = self.host.session_id
        try:
            value = await self.host.controls.validate_provider(request["provider"])
            if identity == self.host.session_id:
                self.emit(
                    {
                        "type": "provider_validation",
                        "session_id": identity,
                        "request_id": request.get("request_id"),
                        **value,
                    }
                )
        except asyncio.CancelledError:
            self.emit(
                {
                    "type": "provider_validation",
                    "session_id": identity,
                    "request_id": request.get("request_id"),
                    "ok": False,
                    "message": "Probe stopped; remote delivery/charges may already have occurred. No conversation was submitted.",
                }
            )
            raise
        finally:
            self.host.validation_active = False

    async def inspect_context(self, request):
        identity = self.host.session_id
        try:
            value = await self.host.inspection.context_snapshot(self.host)
        except Exception as exc:
            value = {
                "rows": [],
                "partial": True,
                "scope": f"Context unavailable ({type(exc).__name__}); no request made",
            }
        if identity == self.host.session_id:
            self.emit(
                {
                    "type": "inspection",
                    "session_id": identity,
                    "request_id": request.get("request_id"),
                    "category": "stored_context",
                    **value,
                }
            )

    async def file_snapshot(self, request):
        from .file_input import snapshot

        identity = self.host.session_id
        image = request.get("op") in ("image_snapshot", "clipboard_image")
        try:
            if image and not self.host.supports_images():
                raise ValueError("All mounted providers must advertise vision for image input")
            if request.get("op") == "clipboard_image":
                from .file_input import clipboard_image

                result = await clipboard_image()
            else:
                result = await asyncio.to_thread(
                    snapshot, self.cwd, request.get("path"), image=image
                )
            if image and identity == self.host.session_id:
                self.host.images.preview = result
                result = {k: v for k, v in result.items() if k != "data"}
        except (OSError, ValueError) as exc:
            result = {"error": str(exc)}
        if identity == self.host.session_id:
            self.emit(
                {
                    "type": "image_snapshot" if image else "file_snapshot",
                    "session_id": identity,
                    "request_id": request.get("request_id"),
                    **result,
                }
            )

    def cancelled_before_start(self, task, request_id):
        if task.cancelled():
            self.emit(
                {
                    "type": "switch_result",
                    "request_id": request_id,
                    "ok": False,
                    "session_id": self.host.session_id,
                    "message": "Opening cancelled; source draft retained",
                }
            )

    async def lookup(self, request):
        identity = self.host.session_id
        kind = "conversations" if request["op"] == "conversations" else "completion"
        value = {"type": kind, "request_id": request["request_id"], "session_id": identity}
        try:
            if kind == "conversations":
                result = await asyncio.to_thread(
                    session_choices,
                    self.state_dir,
                    identity,
                    offset=request.get("offset", 0),
                    query=request.get("query", ""),
                )
            else:
                result = await asyncio.to_thread(file_candidates, self.cwd, request.get("query"))
            value.update(result)
        except (OSError, ValueError, KeyError, TypeError, sqlite3.Error):
            value["error"] = "Local lookup unavailable or outside the working directory"
        self.emit(value)

    async def workspace_review(self, request):
        from .workspace_review import GitReview

        identity = self.host.session_id
        value = {"type": request["op"], "session_id": identity, "request_id": request["request_id"]}
        try:
            if request["op"] == "workspace_changes":
                self.review = GitReview(self.cwd)
                value.update(await self.review.refresh())
            elif self.review is None:
                raise ValueError("Refresh Workspace changes first")
            else:
                value.update(await self.review.diff(request.get("id"), request.get("token")))
        except (OSError, ValueError, TimeoutError) as exc:
            value["error"] = str(exc)
        if identity == self.host.session_id:
            self.emit(value)

    async def switch(self, target, request_id, recover=False):
        candidate = None
        committed = False
        self.switch_committing = False
        try:
            if recover:
                from .recovery import recover as recover_history

                target = await asyncio.to_thread(recover_history, self.state_dir, target)
            if self.review_task and not self.review_task.done():
                self.review_task.cancel()
                await asyncio.gather(self.review_task, return_exceptions=True)
            self.review = None
            launch = (
                self.host.store.metadata["launch"]
                if target == "new"
                else resolve_resume(self.state_dir, target)["launch"]
            )
            if not Path(launch["cwd"]).is_dir():
                raise ValueError("Recorded working directory no longer exists")
            candidate = SessionHost(
                ConversationStore(self.state_dir, launch, None if target == "new" else target)
            )
            # Target initialization is not a permission grant. Mount-time questions
            # cannot steal the source conversation's decision UI while preparing.
            candidate.auto_deny_approvals = True
            candidate.interactive_questions = True
            await self.open_launch(candidate, launch)
            candidate.auto_deny_approvals = False
            if not candidate.ready:
                raise RuntimeError("Target did not become ready")
            next_followups = Followups(candidate, self.emit)
            from .input_history import recall

            # Finish disk discovery before exposing the target as ready. No await
            # between publishing its snapshot and the completed switch response.
            next_history = await asyncio.to_thread(
                recall,
                self.state_dir,
                Path(launch["cwd"]),
                candidate.session_id,
                include_current=True,
            )
            self.switch_committing = True
            if self.pump:
                self.pump.cancel()
                await asyncio.gather(self.pump, return_exceptions=True)
            await self.host.close()
            self.followups.close()
            self.host = candidate
            self.host.delivery_failed = self.failure
            self.followups = next_followups
            committed = True
            self.switched = True
            self.cwd, self.fixture = Path(launch["cwd"]), launch["fixture"]
            self.pending, self.decisions, self.tools = None, {}, {}
            self.snapshot(reset=True)
            self.pump = asyncio.create_task(self.events())
            self.emit({"type": "input_history", "session_id": candidate.session_id, **next_history})
            self.emit(
                {
                    "type": "switch_result",
                    "request_id": request_id,
                    "ok": True,
                    "session_id": candidate.session_id,
                }
            )
        except (Exception, asyncio.CancelledError) as exc:
            self.emit(
                {
                    "type": "switch_result",
                    "request_id": request_id,
                    "ok": False,
                    "session_id": self.host.session_id,
                    "message": "Opening cancelled; source draft retained"
                    if isinstance(exc, asyncio.CancelledError)
                    else f"Could not open conversation: {exc}",
                }
            )
            if not self.pump or self.pump.done():
                self.pump = asyncio.create_task(self.events())
        finally:
            if candidate and not committed:
                await candidate.close()
            self.switch_committing = False

    async def close(self):
        if self.followups:
            self.followups.close()
        for task in (self.lookup_task, self.switch_task, self.review_task):
            if task and not task.done():
                task.cancel()
        await asyncio.gather(
            *[t for t in (self.lookup_task, self.switch_task, self.review_task) if t],
            return_exceptions=True,
        )
        await super().close()

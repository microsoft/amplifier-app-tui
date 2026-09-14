"""App-owned local discovery and explicit conversation changes, not orchestration."""

from __future__ import annotations

import asyncio
import json
import os
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


def session_choices(state_dir, current):
    entries = catalog(state_dir)
    choices = []
    for entry in entries[:100]:
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
                checkpoint = json.loads(
                    (Path(state_dir) / "conversations" / identity / "checkpoint.json").read_text()
                )
                if checkpoint.get("status") != "ready":
                    status = "recovery required · original preserved"
            except (OSError, ValueError):
                status = "unavailable · invalid checkpoint"
        choices.append({"id": identity, "title": label, "cwd": launch["cwd"], "status": status})
    return {"sessions": choices, "truncated": len(entries) > 100}


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

    async def open(self):
        await super().open()
        await self.history()

    async def history(self):
        from .input_history import recall

        identity = self.host.session_id
        value = await asyncio.to_thread(recall, self.state_dir, self.cwd, identity)
        if identity == self.host.session_id:
            self.emit({"type": "input_history", "session_id": identity, **value})

    def snapshot(self, reset=False):
        if self.followups is None:
            self.followups = Followups(self.host, self.emit)
        super().snapshot(reset)
        self.followups.publish()
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
        if request.get("op") == "cancel_switch":
            if self.switch_task and not self.switch_task.done() and not self.switch_committing:
                self.switch_task.cancel()
                return True, "Cancelling opening; source draft retained"
            return False, "No cancellable opening; wait for the current change to finish"
        if self.switch_task and not self.switch_task.done():
            return False, "Opening conversation; editing is paused, source draft saved"
        op = request.get("op")
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
        if op == "file_snapshot":
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
        if op in ("queue", "queue_run", "queue_pause", "queue_remove", "queue_edit"):
            if not self.host.ready:
                return False, "Session not ready; draft retained"
            return self.followups.command(request)
        if op == "stop":
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
        return super().command(request)

    async def file_snapshot(self, request):
        from .file_input import snapshot

        identity = self.host.session_id
        try:
            result = await asyncio.to_thread(snapshot, self.cwd, request.get("path"))
        except (OSError, ValueError) as exc:
            result = {"error": str(exc)}
        if identity == self.host.session_id:
            self.emit(
                {
                    "type": "file_snapshot",
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
                result = await asyncio.to_thread(session_choices, self.state_dir, identity)
            else:
                result = await asyncio.to_thread(file_candidates, self.cwd, request.get("query"))
            value.update(result)
        except (OSError, ValueError, KeyError, TypeError):
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
            await self.history()
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

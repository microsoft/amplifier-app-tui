"""Durable host admission, not orchestration. Pending work never replays on open."""

import copy
import json
import uuid

from .conversations import atomic_json
from .file_input import ImageDraft


class Followups:
    def __init__(self, host, emit):
        self.host, self.emit = host, emit
        host.capabilities["queue"] = True
        self.path = host.store.path / "followups.json"
        self.rows = []
        if self.path.exists():
            with self.path.open("rb") as stream:
                raw = stream.read(24 * 1024 * 1024 + 1)
            if len(raw) > 24 * 1024 * 1024:
                raise ValueError("Follow-up storage exceeds limit; original retained")
            value = json.loads(raw)
            if value.get("version") != 1 or value.get("session_id") != host.session_id:
                raise ValueError("Invalid follow-up identity/version")
            self.rows = value["rows"]
            if (
                not isinstance(self.rows, list)
                or len(self.rows) > 20
                or any(
                    not isinstance(r, dict)
                    or not isinstance(r.get("id"), str)
                    or not isinstance(r.get("text"), str)
                    or not 0 < len(r["text"]) <= 65536
                    or r.get("state") not in ("queued", "dispatched", "dismissed")
                    for r in self.rows
                )
                or len({r["id"] for r in self.rows}) != len(self.rows)
            ):
                raise ValueError("Invalid follow-up records; no work retried")
            for row in self.rows:
                if row.get("image"):
                    ImageDraft.validate(row["image"])
        self.paused = bool(self.rows)  # Reopening is never consent to execute.
        self.closed = False
        self.watching = None

    def save(self, rows):
        atomic_json(
            self.path,
            {"version": 1, "session_id": self.host.session_id, "rows": rows},
        )
        self.rows = rows

    def publish(self):
        self.emit(
            {
                "type": "followups",
                "session_id": self.host.session_id,
                "rows": [
                    {**r, "image": ImageDraft.metadata(r["image"])} if r.get("image") else dict(r)
                    for r in self.rows
                ],
                "paused": self.paused,
            }
        )

    def command(self, request):
        op = request["op"]
        if op == "queue":
            text = request.get("text")
            if not isinstance(text, str) or not text.strip() or len(text) > 65536:
                return False, "Queue requires 1–65536 characters"
            if len(self.rows) >= 20:
                return False, "Queue full (20); draft retained"
            row = {"id": uuid.uuid4().hex, "text": text, "state": "queued"}
            if request.get("image_id"):
                value = self.host.images.value if self.host.images else None
                if not self.host.supports_attachments(value):
                    return False, "Mounted provider/context does not support these attachments"
                if (
                    not value
                    or sum(r.get("image", {}).get("bytes", 0) for r in self.rows) + value["bytes"]
                    > 16 * 1024 * 1024
                ):
                    return False, "Queued image budget exceeded (16 MiB); draft retained"
                # Claim before persistence/admission: a crash may leave uncertain
                # intent, but cannot resurrect a queued image as an unsent draft.
                try:
                    row["image"] = self.host.images.admit(request["image_id"])
                except (ValueError, OSError) as exc:
                    return False, str(exc)
            self.save([*self.rows, row])
        elif op == "queue_pause":
            self.paused = True
        elif op == "queue_run":
            if not self.host.ready or self.host._closed:
                return False, "Session not ready; pending work held"
            if any(r["state"] == "dispatched" for r in self.rows):
                return False, "An admitted follow-up is running or uncertain; no retry"
            self.paused = False
        elif op == "queue_resolve":
            row = next((r for r in self.rows if r["id"] == request.get("id")), None)
            if not row or row["state"] != "dispatched":
                return False, "Only an uncertain dispatched follow-up can be resolved"
            if not self.host.ready or (self.host.task and not self.host.task.done()):
                return False, "Finish or stop work and restore a ready conversation first"
            if request.get("acknowledge_unknown") is not True:
                return (
                    False,
                    "Acknowledge that delivery/effects remain unknown; this will not retry or undo",
                )
            self.paused = True
            self.save(
                [
                    {
                        **r,
                        "state": "dismissed",
                        "resolution": "User acknowledged unknown delivery; no retry or rollback",
                    }
                    if r["id"] == row["id"]
                    else r
                    for r in self.rows
                ]
            )
        elif op in ("queue_remove", "queue_edit"):
            row = next((r for r in self.rows if r["id"] == request.get("id")), None)
            if not row or (
                row["state"] != "queued"
                and not (op == "queue_remove" and row["state"] == "dismissed")
            ):
                return False, "Already admitted or missing; use Stop for active work"
            if op == "queue_edit":
                text = request.get("text")
                if not isinstance(text, str) or not text.strip() or len(text) > 65536:
                    return False, "Queue requires 1–65536 characters"
                self.save([{**r, "text": text} if r["id"] == row["id"] else r for r in self.rows])
            else:
                self.save([r for r in self.rows if r["id"] != row["id"]])
        else:
            return False, "Unsupported queue operation"
        self.publish()
        self.advance()
        return True, "Follow-up queue updated"

    def advance(self):
        if self.closed or self.host._closed:
            return
        task = self.host.task
        if task and not task.done():
            if task is not self.watching:
                self.watching = task
                identity = getattr(self.host, "current_input_id", None)
                task.add_done_callback(lambda task: self.finished(task, identity))
            return
        if self.paused or not self.host.ready or not self.rows:
            return
        row = next((r for r in self.rows if r["state"] != "dismissed"), None)
        if row is None:
            return
        if row["state"] != "queued":
            self.paused = True
            self.publish()
            return
        # Persist the uncertain boundary BEFORE admission. A crash here sacrifices
        # automatic progress, never safety: dispatched input is not retried on open.
        changed = copy.deepcopy(self.rows)
        next(r for r in changed if r["id"] == row["id"])["state"] = "dispatched"
        try:
            self.save(changed)
            media = {"queued_image": row["image"]} if row.get("image") else {}
            accepted, _ = self.host.submit(row["text"], input_id=row["id"], **media)
            if not accepted:
                self.paused = True
        except Exception:
            self.paused = True
            self.emit({"type": "error", "message": "Queue admission uncertain; no retry"})
        self.publish()
        if not self.paused:
            self.advance()

    def finished(self, task, identity):
        if self.closed:
            return
        try:
            if task.result() != "completed" or not self.host.ready:
                self.paused = True
            # The completed task owns exactly one dispatched row, if any. The
            # journal retains its input_id and outcome even when removed here.
            self.save([r for r in self.rows if r["id"] != identity])
            self.publish()
            self.advance()
        except BaseException:
            self.paused = True
            self.publish()
            self.emit({"type": "error", "message": "Follow-up completion uncertain; queue held"})

    def hold(self):
        self.paused = True
        self.publish()

    def close(self):
        self.closed = True
        self.paused = True

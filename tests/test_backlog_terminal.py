"""Native interaction with real fixture modules; no visual-model quality claims."""

import base64
import json
import os
import signal
import sys
import time
from pathlib import Path

import pytest
from PIL import Image
from test_daily_terminal import action, dismiss
from test_reading_terminal import draft_is

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from interaction_probe import capture  # noqa: E402
from questions_probe import wait_ready  # noqa: E402
from terminal_probe import Probe, record  # noqa: E402

pytestmark = pytest.mark.skipif(
    os.environ.get("TUI_TEST_CANDIDATES") != "1", reason="Build native client"
)


def test_image_attachment_and_saved_content_search_are_explicit(tmp_path):
    path = tmp_path / "image.png"
    Image.new("RGB", (32, 32), "red").save(path)
    original = path.read_bytes()
    overlay = tmp_path / "vision.yaml"
    overlay.write_text(
        json.dumps(
            {
                "bundle": {"name": "vision-transport-fixture", "version": "1.0.0"},
                "providers": [
                    {"module": "provider-fixture", "config": {"capabilities": ["vision"]}}
                ],
            }
        )
    )
    probe = Probe(
        [
            sys.executable,
            str(ROOT / "scripts/run.py"),
            "--fixture",
            "--no-install",
            "--overlay",
            str(overlay),
            "--cwd",
            str(tmp_path),
            "--state-dir",
            str(tmp_path / "state"),
        ],
        cols=160,
    )
    try:
        wait_ready(probe)
        probe.send(b"Image prompt retained")
        action(probe, "Attach image", "Workspace-relative PNG/JPEG")
        probe.send(b"image.png\r")
        probe.wait("Image snapshot · confirm attachment")
        probe.wait("SHA-256")
        capture(probe, "backlog-image-preview")
        path.write_bytes(b"Changed after preview")
        probe.send(b"\r")
        probe.wait("[Image attached]")
        draft_is(probe, "Image prompt retained")
        probe.send(b"\r")
        probe.wait("Completed")
        root = next((tmp_path / "state/conversations").glob("*/metadata.json")).parent
        messages = json.loads((root / "checkpoint.json").read_text())["messages"]
        image = next(
            block
            for message in messages
            if isinstance(message.get("content"), list)
            for block in message["content"]
            if block.get("type") == "image"
        )
        assert base64.b64decode(image["source"]["data"]) == original
        probe.send(b"Keep this draft")
        action(probe, "Attached image", "Attachment draft · inspect")
        probe.wait("dispatched")
        dismiss(probe, "Attachment draft · inspect")
        action(probe, "Search saved conversations", "Saved message text")
        probe.send(b"Fixture round trip complete\r")
        probe.wait("Saved conversations")
        probe.wait("Image prompt retained")
        capture(probe, "backlog-content-search")
        dismiss(probe, "Saved conversations")
        draft_is(probe, "Keep this draft")
        action(probe, "Model catalog", "Model catalog · explicit discovery")
        probe.send(b"\r")
        probe.wait("Model catalog · advisory IDs")
        probe.wait("empty catalog")
        dismiss(probe, "Model catalog · advisory IDs")
        draft_is(probe, "Keep this draft")
        events = [json.loads(line) for line in (root / "events.jsonl").read_text().splitlines()]
        assert sum(e["kind"] == "turn.accepted" for e in events) == 1
    finally:
        probe.close()


def test_multiple_queued_images_and_stored_context_keep_native_intent(tmp_path):
    originals = []
    for color in ("red", "blue"):
        path = tmp_path / f"{color}.png"
        Image.new("RGB", (8, 8), color).save(path)
        originals.append(path.read_bytes())
    overlay = tmp_path / "vision.yaml"
    overlay.write_text(
        json.dumps(
            {
                "bundle": {"name": "media-transport-fixture", "version": "1.0.0"},
                "providers": [
                    {"module": "provider-fixture", "config": {"capabilities": ["vision"]}}
                ],
            }
        )
    )
    probe = Probe(
        [
            sys.executable,
            str(ROOT / "scripts/run.py"),
            "--fixture",
            "--no-install",
            "--overlay",
            str(overlay),
            "--cwd",
            str(tmp_path),
            "--state-dir",
            str(tmp_path / "state"),
        ],
        cols=160,
    )
    try:
        wait_ready(probe)
        probe.send(b"Describe both snapshots")
        for color in ("red", "blue"):
            action(probe, "Attach image", "Workspace-relative PNG/JPEG")
            probe.send(f"{color}.png\r".encode())
            probe.wait("Image snapshot · confirm attachment")
            probe.send(b"\r")
            probe.wait("[Image attached]")
        action(probe, "Attached images", "Attachment draft · inspect")
        probe.wait("2 attachment snapshots")
        capture(probe, "approachability-multiple-images")
        dismiss(probe, "Attachment draft · inspect")
        action(probe, "Queue current draft", "[Pending 1] (paused)")
        action(probe, "Pending follow-ups", "Pending follow-ups · paused")
        probe.send(b"queued\r")
        probe.wait("Follow-up · inspect before changing")
        probe.wait("Frozen attachments travel")
        capture(probe, "approachability-queued-images")
        dismiss(probe, "Follow-up · inspect")
        action(probe, "Pending follow-ups", "Pending follow-ups · paused")
        probe.send(b"Run pending\r")
        probe.wait("Completed")
        root = next((tmp_path / "state/conversations").glob("*/metadata.json")).parent
        messages = json.loads((root / "checkpoint.json").read_text())["messages"]
        images = [
            block
            for message in messages
            if isinstance(message.get("content"), list)
            for block in message["content"]
            if block.get("type") == "image"
        ]
        assert [base64.b64decode(block["source"]["data"]) for block in images] == originals
        probe.send(b"Unsent correction")
        action(probe, "Stored context", "Stored context · module snapshot")
        probe.wait("NOT the exact next provider request")
        capture(probe, "approachability-stored-context")
        dismiss(probe, "Stored context · module snapshot")
        draft_is(probe, "Unsent correction")
        action(probe, "Conversation provider", "Conversation provider · choose then confirm")
        probe.send(b"Validate fixture\r")
        probe.wait("Validate provider access?")
        probe.wait("Charges may")
        probe.send(b"\r")
        probe.wait("Provider validation · observed result")
        probe.wait("Provider returned a response")
        capture(probe, "approachability-provider-validation-fixture")
        dismiss(probe, "Provider validation · observed result")
        draft_is(probe, "Unsent correction")
        events = [json.loads(line) for line in (root / "events.jsonl").read_text().splitlines()]
        assert sum(e["kind"] == "turn.accepted" for e in events) == 1
    finally:
        probe.close()


def test_semantic_file_reference_confirmation_queue_and_text_only_send(tmp_path):
    path = tmp_path / "source.txt"
    path.write_text("Do not include this line\nSelected source evidence\n")
    probe = Probe(
        [
            sys.executable,
            str(ROOT / "scripts/run.py"),
            "--fixture",
            "--no-install",
            "--cwd",
            str(tmp_path),
            "--state-dir",
            str(tmp_path / "state"),
        ],
        cols=160,
    )
    try:
        wait_ready(probe)
        probe.send(b"Review this selection")
        action(probe, "Attach file reference", "Workspace-relative file[:line")
        probe.send(b"source.txt:2\r")
        probe.wait("File reference · confirm attachment")
        probe.wait("source.txt:2-2")
        probe.wait("Selected source evidence")
        capture(probe, "reference-confirmation")
        path.unlink()
        probe.send(b"\r")
        probe.wait("[References attached]")
        draft_is(probe, "Review this selection")
        action(probe, "Attached images", "Attachment draft · inspect")
        probe.wait("source.txt:2-2")
        dismiss(probe, "Attachment draft · inspect")
        action(probe, "Queue current draft", "[Pending 1] (paused)")
        action(probe, "Pending follow-ups", "Pending follow-ups · paused")
        probe.send(b"queued\r")
        probe.wait("Follow-up · inspect before changing")
        probe.wait("source.txt:2-2")
        dismiss(probe, "Follow-up · inspect")
        action(probe, "Pending follow-ups", "Pending follow-ups · paused")
        probe.send(b"Run pending\r")
        probe.wait("Completed")
        root = next((tmp_path / "state/conversations").glob("*/metadata.json")).parent
        messages = json.loads((root / "checkpoint.json").read_text())["messages"]
        reference = next(
            json.loads(block["text"].split("\n", 1)[1])
            for message in messages
            if isinstance(message.get("content"), list)
            for block in message["content"]
            if block.get("type") == "text"
            and block.get("text", "").startswith("User-selected file reference")
        )
        assert reference["path"] == "source.txt" and reference["start_line"] == 2
        assert reference["text"] == "Selected source evidence\n"
        events = [json.loads(line) for line in (root / "events.jsonl").read_text().splitlines()]
        assert sum(e["kind"] == "turn.accepted" for e in events) == 1
        capture(probe, "reference-completed")
    finally:
        probe.close()


def test_request_diagnostic_controls_are_confirmed_without_execution(tmp_path):
    probe = Probe(
        [
            sys.executable,
            str(ROOT / "scripts/run.py"),
            "--fixture",
            "--no-install",
            "--cwd",
            str(tmp_path),
            "--state-dir",
            str(tmp_path / "state"),
        ],
        cols=160,
    )
    try:
        wait_ready(probe)
        probe.send(b"Diagnostic must not send this")
        action(probe, "Provider request diagnostic", "Provider request · private diagnostic")
        probe.wait("private prompts")
        probe.send(b"\r")
        probe.wait("Waiting for the next root provider request")
        capture(probe, "request-diagnostic-armed")
        dismiss(probe, "Provider request · memory-only projection")
        action(probe, "Provider request diagnostic", "Provider request · private diagnostic")
        probe.send(b"Clear capture\r")
        probe.wait("Provider request · memory-only projection")
        assert "Waiting for the next root provider request" not in probe.text
        dismiss(probe, "Provider request · memory-only projection")
        draft_is(probe, "Diagnostic must not send this")
        root = next((tmp_path / "state/conversations").glob("*/metadata.json")).parent
        assert "turn.accepted" not in (root / "events.jsonl").read_text()
    finally:
        probe.close()


def test_dialog_copies_keep_original_scope_without_applying(tmp_path):
    probe = Probe(
        [
            sys.executable,
            str(ROOT / "scripts/run.py"),
            "--fixture",
            "--no-install",
            "--cwd",
            str(tmp_path),
            "--state-dir",
            str(tmp_path / "state"),
        ],
        cols=160,
    )
    try:
        wait_ready(probe)
        probe.send(b"Main draft unchanged")
        action(probe, "Rename conversation", "New name")
        probe.send(b"Unapplied local name")
        dismiss(probe, "Rename conversation")
        action(probe, "Saved local drafts", "Saved local drafts · never")
        probe.wait("Unapplied local name")
        probe.send(b"Unapplied\r")
        probe.wait("Saved draft · historical intent")
        probe.wait("dialog:Rename conversation:local")
        capture(probe, "dialog-retained-scope")
        dismiss(probe, "Saved draft · historical intent")
        draft_is(probe, "Main draft unchanged")
        root = next((tmp_path / "state/conversations").glob("*/metadata.json")).parent
        drafts = json.loads((root / "editors.json").read_text())["rows"]
        assert any(r["kind"] == "dialog" and r["text"] == "Unapplied local name" for r in drafts)
        assert "Unapplied local name" not in (root / "metadata.json").read_text()
        assert "turn.accepted" not in (root / "events.jsonl").read_text()
    finally:
        probe.close()


@pytest.mark.skipif(sys.platform != "linux", reason="Linux /proc descendant-liveness evidence")
def test_nonreading_host_cannot_trap_exit_or_leave_inherited_group_running(tmp_path):
    # Deliberately uncooperative transport fixture, not an Amplifier module claim.
    program = """
import json, os, pathlib, subprocess, sys, time
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
pathlib.Path(sys.argv[1]).write_text(json.dumps([os.getpid(), child.pid]))
print(json.dumps(dict(version=1, type='snapshot', session_id='transport-fixture', navigation=True,
    ready=True, durable=True, draft='', items=[], system=[], mode='FIXTURE RUNTIME')), flush=True)
print(json.dumps(dict(version=1, type='state', status='Ready', ready=True)), flush=True)
time.sleep(60)
"""
    pids = tmp_path / "owned-processes.json"
    probe = Probe(
        [
            str(ROOT / "frontends/ratatui/target/release/amplifier-ratatui"),
            "--host-json",
            json.dumps([sys.executable, "-c", program, str(pids)]),
        ],
        cols=120,
    )
    host = None
    closed = False
    try:
        probe.wait("Ready")
        host, child = json.loads(pids.read_text())
        assert os.getpgid(host) == host and os.getpgid(child) == host
        record(host, "active")
        # Larger than a pipe: old synchronous writes freeze here before Drop.
        probe.send(b"\x1b[200~" + b"x" * 32768 + b"\x1b[201~")
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            probe.read()
        started = time.monotonic()
        closed = True
        probe.close()
        assert time.monotonic() - started < 4
        assert b"forced to exit" in probe.raw and b"uncertain" in probe.raw
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            proc = Path(f"/proc/{child}/stat")
            if not proc.exists() or proc.read_text().split(") ", 1)[1].startswith("Z"):
                break
            time.sleep(0.01)
        else:
            pytest.fail("Inherited host descendant remains running after exit")
        assert not Path(f"/proc/{host}").exists()
    finally:
        try:
            if not closed:
                probe.close()
        finally:
            if host is not None:
                try:
                    os.killpg(host, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                record(host, "reaped")


def test_recipe_review_draft_and_live_child_refresh_keep_intent():
    # Identified protocol fixture exercises UI only. Actual runner continuation is
    # covered by test_ecosystem_workflows against both real prepared presets.
    program = """
import asyncio
from amplifier_tui.frontend_bridge import serve
class Backend:
    def __init__(self, emit): self.emit, self.refreshes = emit, 0
    async def open(self):
        self.emit(dict(type="snapshot", session_id="fixture", navigation=True, mode="FIXTURE RUNTIME", draft="Keep draft", items=[], system=[]))
        self.emit(dict(type="state", status="Ready"))
    def command(self, r):
        if r["op"] == "inspect":
            category = r["category"]
            self.refreshes += category == "children"
            row = dict(id="identified-source", source="fixture", turn="turn-a", sequence=7,
                       first_sequence=3, label="Agent sample" if category == "children" else "recipes",
                       status="completed" if self.refreshes > 1 else "running", detail="Exact source observation",
                       recipe_ids=["recipe-123"] if category == "recipes" else [], live=self.refreshes == 1)
            self.emit(dict(type="inspection", session_id="fixture", request_id=r["request_id"],
                           category=category, rows=[row], scope="SIMULATED transport observations", partial=False))
        if r["op"] == "submit": self.emit(dict(type="state", status="Unexpected submission"))
        return True, "Fixture command observed"
    async def close(self): pass
asyncio.run(serve(Backend))
"""
    probe = Probe(
        [
            str(ROOT / "frontends/ratatui/target/release/amplifier-ratatui"),
            "--host-json",
            json.dumps([sys.executable, "-c", program]),
        ],
        cols=160,
    )
    try:
        probe.wait("Ready")
        action(probe, "Recipe activity", "Recipe activity · observed tool calls")
        probe.send(b"recipes\r")
        probe.wait("Observed evidence")
        probe.send(b"Prepare recipe review\r")
        draft_is(probe, "Keep draft")
        draft_is(probe, "recipe-123")
        assert "Unexpected submission" not in probe.text
        action(probe, "Delegated work", "Delegated work · scoped")
        probe.send(b"Agent")
        probe.wait("completed")
        probe.wait("Search: Agent")
        probe.send(b"\r")
        probe.wait("Identity: identified-source")
        dismiss(probe, "Observed evidence")
        draft_is(probe, "recipe-123")
        assert "Unexpected submission" not in probe.text
    finally:
        probe.close()


def test_delayed_switch_confirmation_never_presents_early_ready():
    program = """
import asyncio
from amplifier_tui.frontend_bridge import serve
class Backend:
    def __init__(self, emit): self.emit, self.tasks = emit, []
    async def open(self):
        self.emit(dict(type="snapshot", session_id="source", navigation=True, mode="FIXTURE RUNTIME", ready=True, draft="Source draft", items=[], system=[]))
        self.emit(dict(type="state", status="Ready"))
    def command(self, r):
        if r["op"] == "switch":
            async def change():
                self.emit(dict(type="snapshot", reset=True, session_id="target", navigation=True, mode="FIXTURE RUNTIME", ready=True, draft="Target draft", items=[], system=[]))
                self.emit(dict(type="state", status="Ready", ready=True))
                await asyncio.sleep(.8)
                self.emit(dict(type="switch_result", request_id=r["request_id"], session_id="target", ok=True))
            self.tasks.append(asyncio.create_task(change()))
        if r["op"] == "submit": self.emit(dict(type="state", status="Submission observed"))
        return True, "Fixture operation"
    async def close(self):
        await asyncio.gather(*self.tasks)
asyncio.run(serve(Backend))
"""
    probe = Probe(
        [
            str(ROOT / "frontends/ratatui/target/release/amplifier-ratatui"),
            "--host-json",
            json.dumps([sys.executable, "-c", program]),
        ]
    )
    try:
        probe.wait("Ready")
        action(probe, "New conversation", "Target draft")
        probe.wait("Opening conversation · input paused")
        assert "Ready" not in probe.text
        probe.send(b"\r")
        probe.wait("Ready")
        assert "Submission observed" not in probe.text
        draft_is(probe, "Target draft")
        probe.send(b"\r")
        probe.wait("Submission observed")
    finally:
        probe.close()

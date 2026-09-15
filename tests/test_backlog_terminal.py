"""Native interaction with real fixture modules; no visual-model quality claims."""

import base64
import json
import os
import sys
from pathlib import Path

import pytest
from PIL import Image
from test_daily_terminal import action, dismiss
from test_reading_terminal import draft_is

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from interaction_probe import capture  # noqa: E402
from questions_probe import wait_ready  # noqa: E402
from terminal_probe import Probe  # noqa: E402

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
        action(probe, "Attached image", "Image draft · inspect")
        probe.wait("dispatched")
        dismiss(probe, "Image draft · inspect")
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

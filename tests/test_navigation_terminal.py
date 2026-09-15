"""Native picker/completion proof over actual Foundation/core fixture modules."""

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from interaction_probe import action, capture  # noqa: E402
from terminal_probe import Probe  # noqa: E402
from test_reading_terminal import draft_is  # noqa: E402

pytestmark = pytest.mark.skipif(
    os.environ.get("TUI_TEST_CANDIDATES") != "1", reason="Build Ratatui first"
)


def start(tmp_path):
    return Probe(
        [
            sys.executable,
            str(ROOT / "scripts/run.py"),
            "--fixture",
            "--no-install",
            "--cwd",
            str(tmp_path),
            "--state-dir",
            str(tmp_path / "state"),
        ]
    )


def test_picker_new_return_and_drafts(tmp_path):
    probe = start(tmp_path)
    try:
        probe.wait("Ready")
        probe.send(b"Conversation alpha\r")
        probe.wait("Completed")
        probe.send(b"Keep alpha draft")
        action(probe, "New conversation", "[ Send ]")
        # Native terminal history deliberately retains previous conversations;
        # canonical context isolation is asserted from checkpoints below.
        probe.wait("Keep alpha draft", absent=True)
        probe.wait("Ready")
        probe.send(b"\x1aConversation beta")  # Undo cannot resurrect source text.
        draft_is(probe, "Conversation beta")
        assert "Keep alpha draft" not in probe.text
        probe.send(b"\r")
        probe.wait("Completed")
        probe.send(b"Keep beta draft")
        action(probe, "Resume", "Saved conversations")
        probe.wait("Conversation alpha")
        capture(probe, "navigation-conversations")
        probe.send(b"Conversation alpha\r")
        probe.wait("Saved conversations", absent=True)
        draft_is(probe, "Keep alpha draft")
        probe.wait("Ready")
        assert "Conversation beta" in probe.text
        probe.send(b"\r")
        probe.wait("Completed")
    finally:
        probe.close()
    records = [
        json.loads(path.read_text())
        for path in (tmp_path / "state/conversations").glob("*/metadata.json")
    ]
    assert len(records) == 2
    alpha = next(row for row in records if row["title"] == "Conversation alpha")
    beta = next(row for row in records if row["title"] == "Conversation beta")
    root = tmp_path / "state/conversations"
    assert json.loads((root / beta["id"] / "draft.json").read_text())["text"] == "Keep beta draft"
    messages = json.loads((root / alpha["id"] / "checkpoint.json").read_text())["messages"]
    assert "Conversation alpha" in str(messages) and "Keep alpha draft" in str(messages)
    assert "Conversation beta" not in str(messages)


def test_explicit_provider_fork_confirmation_and_retained_public_context(tmp_path):
    overlay = tmp_path / "provider.yaml"
    overlay.write_text(
        "bundle:\n  name: alternate-provider-fixture\nproviders:\n  - module: provider-fixture\n    config:\n      vendor: alternate-fixture-vendor\n"
    )
    probe = start(tmp_path)
    try:
        probe.wait("Ready")
        probe.send(b"Remember the original conversation\r")
        probe.wait("Completed")
        probe.send(b"Unsent retained draft")
        action(probe, "New provider composition", "New provider overlay")
        probe.send(str(overlay).encode() + b"\r")
        probe.wait("Adopt new provider composition?")
        probe.wait("model call until your next explicit Send")
        capture(probe, "provider-fork-confirmation")
        probe.send(b"\r")
        probe.wait("Adopt new provider composition?", absent=True)
        probe.wait("Ready", timeout=30)
        draft_is(probe, "Unsent retained draft")
        records = list((tmp_path / "state/conversations").glob("*/metadata.json"))
        assert len(records) == 2
        target = next(p.parent for p in records if (p.parent / "imported-context.json").exists())
        assert '"kind": "turn.accepted"' not in (target / "events.jsonl").read_text()
        assert "Remember the original conversation" in (target / "checkpoint.json").read_text()
        capture(probe, "provider-fork-ready")
    finally:
        probe.close()


def test_continuous_typing_flushes_before_idle(tmp_path):
    import time

    probe = start(tmp_path)
    try:
        probe.wait("Ready")
        metadata = next((tmp_path / "state/conversations").glob("*/metadata.json"))
        draft = metadata.parent / "draft.json"
        saved_while_typing = False
        for _ in range(30):
            probe.send(b"x")
            probe.read(0.035)
            saved_while_typing |= bool(json.loads(draft.read_text())["text"])
            time.sleep(0.01)
        assert saved_while_typing
        probe.wait("xxxxxxxx")
        assert '"kind": "turn.accepted"' not in (metadata.parent / "events.jsonl").read_text()
    finally:
        probe.close()


def test_file_completion_quotes_directory_names_and_keeps_neighbors(tmp_path):
    (tmp_path / "docs space").mkdir()
    (tmp_path / "docs space" / "alpha.md").write_text("not read by completion")
    (tmp_path / "docs space" / "beta.md").touch()
    probe = start(tmp_path)
    try:
        probe.wait("Ready")
        probe.send(b"Read ./do suffix")
        probe.send(b"\x1b[D" * len(" suffix"))
        probe.send(b"\t")
        draft_is(probe, 'Read "./docs space/" suffix')
        probe.send(b"\t")
        probe.wait("Workspace paths")
        probe.wait("alpha.md")
        capture(probe, "navigation-files")
        probe.send(b"\x1b")
        probe.wait("Workspace paths", absent=True)
        draft_is(probe, 'Read "./docs space/" suffix')
        probe.send(b"\t")
        probe.wait("Workspace paths")
        probe.send(b"\x1b[B\t")
        draft_is(probe, 'Read "./docs space/beta.md" suffix')
        assert "Working" not in probe.text
        # Busy/failed local lookup must not submit any user message either.
        metadata = list((tmp_path / "state/conversations").glob("*/metadata.json"))
        journal = (metadata[0].parent / "events.jsonl").read_text()
        assert '"kind": "turn.accepted"' not in journal
    finally:
        probe.close()


def test_late_completion_cannot_overwrite_a_newer_edit(tmp_path):
    # Controlled delayed protocol fixture, not runtime success evidence.
    program = """
import asyncio, json
from amplifier_tui.frontend_bridge import serve
class Backend:
    def __init__(self, emit): self.emit, self.tasks = emit, []
    async def open(self):
        self.emit(dict(type="snapshot", session_id="fixture", navigation=True, mode="SIMULATED", draft="./a", items=[], system=[]))
        self.emit(dict(type="state", status="Ready"))
    def command(self, r):
        async def reply():
            await asyncio.sleep(.25)
            self.emit(dict(type="completion", request_id=r["request_id"], session_id="fixture", candidates=["./alpha"]))
            self.emit(dict(type="state", status="Delayed reply delivered"))
        if r["op"] == "complete_path": self.tasks.append(asyncio.create_task(reply()))
        return True, "local lookup"
    async def close(self):
        for t in self.tasks: t.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
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
        probe.send(b"\tb")
        probe.wait("Delayed reply delivered")
        draft_is(probe, "./ab")
        assert "./alpha" not in probe.text
    finally:
        probe.close()

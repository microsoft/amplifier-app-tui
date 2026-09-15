"""PTY reading/editor probes are simulated; resume runs actual Amplifier modules."""

import json
import os
import re
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from terminal_probe import Probe  # noqa: E402

pytestmark = pytest.mark.skipif(
    os.environ.get("TUI_TEST_CANDIDATES") != "1", reason="Build Ratatui first"
)


def scene(tmp_path, items, draft="", skills=None):
    path = tmp_path / "reading-scene.json"
    path.write_text(
        json.dumps(
            {
                "title": "Reading probe",
                "context": "simulated projection only",
                "draft": draft,
                "items": items,
                "skills": skills or [],
                "system": [],
                "response": "Streaming new content without disturbing the reading anchor.",
                "stream_interval_ms": 15,
            }
        )
    )
    return Probe(
        [
            str(ROOT / "frontends/ratatui/target/release/amplifier-ratatui"),
            "--host-json",
            json.dumps(
                [sys.executable, "-m", "amplifier_tui.frontend_bridge", "--scene", str(path)]
            ),
        ]
    )


def draft_is(probe, expected):
    until = time.monotonic() + 4
    while time.monotonic() < until:
        probe.read(0.02)
        display = probe.screen.display
        tops = [i for i, row in enumerate(display) if row.strip().startswith("Message ·")]
        actual = ""
        if tops:
            start = tops[-1] + 1
            end = next(
                (i for i in range(start, len(display)) if "[ Actions ]" in display[i]), start
            )
            actual = "\n".join(display[start:end])
        if expected in actual:
            return
    raise AssertionError(f"Composer did not reach {expected!r}:\n{probe.text}")


def test_markdown_visual_line_scroll_anchor_stream_and_resize(tmp_path):
    source = (
        "# Markdown reading\n\n**Bold** and `inline` [docs](https://example.test)\n\n- list item\n\n```text\n"
        + "\n".join(f"row {n:03d}" for n in range(1, 81))
        + "\n```"
    )
    probe = scene(tmp_path, [{"id": "long", "kind": "assistant", "text": source}])
    try:
        probe.wait("row 080")
        assert "row 001" not in probe.text
        probe.send(b"\x1b[<64;50;15M")  # wheel up: exactly three visual rows
        probe.wait("[ Latest")
        probe.wait("row 080", absent=True)
        probe.wait("row 079")
        rows = re.findall(r"row (\d+)", "\n".join(probe.screen.display[6:32]))
        assert rows[-1] == "079"  # two trailing Markdown spacer rows, then row 80
        probe.send(b"\x1b[5~")
        probe.wait("row 079", absent=True)
        before = probe.screen.display[6:32]
        assert len(re.findall(r"row \d+", "\n".join(before))) > 20
        probe.send(b"continue\r")
        probe.wait("Completed")
        assert probe.screen.display[6:32] == before
        probe.resize(160, 40)
        probe.wait("row " + re.findall(r"row (\d+)", "\n".join(before))[-1])
        probe.send(b"\x1b[5~" * 8)
        probe.wait("Markdown reading")
        assert "**Bold**" not in probe.text
        probe.wait("• list item")
        assert any(cell.bold for row in probe.screen.buffer.values() for cell in row.values())
        from interaction_probe import capture

        capture(probe, "reading-markdown")
        probe.send(b"\x1b[1;5F")  # Ctrl+End: follow tail
        probe.wait("Streaming new content")
        probe.wait("[ Latest", absent=True)
    finally:
        probe.close()


def test_boundary_history_and_tab_completion_keep_neighbors(tmp_path):
    probe = scene(
        tmp_path,
        [
            {"id": "old", "kind": "user", "text": "history oldest"},
            {"id": "new", "kind": "user", "text": "history newest"},
        ],
        draft="original draft",
        skills=["context-alpha", "context-beta"],
    )
    try:
        probe.wait("Ready")
        probe.send(b"\x1b[A")
        draft_is(probe, "history newest")
        probe.send(b"\x1b[A")
        draft_is(probe, "history oldest")
        probe.send(b"\x1b[B\x1b[B")
        draft_is(probe, "original draft")
        # Bottom-line Up must edit within the multiline draft first.
        probe.send(b"\x1b\rsecond line\x1b[A!")
        draft_is(probe, "original dr!aft")
        probe.send(b"\x1b[A\x1b")  # recall then cancel restores that exact draft
        draft_is(probe, "original dr!aft")
    finally:
        probe.close()
    probe = scene(tmp_path, [], draft="Use @co suffix", skills=["context-alpha", "context-beta"])
    try:
        probe.wait("Ready")
        probe.send(b"\x1b[D" * len(" suffix"))
        probe.send(b"\t")
        probe.wait("Complete locally")
        probe.send(b"\x1b[B\t")
        draft_is(probe, "Use @context-beta suffix")
        assert "Working" not in probe.text
        probe.send(b"\t\r")  # complete exact token, then explicit submit
        probe.wait("Completed")
    finally:
        probe.close()


def test_launcher_resume_restores_draft_and_next_real_context(tmp_path):
    state = tmp_path / "state"
    base = [sys.executable, str(ROOT / "scripts/run.py"), "--no-install", "--state-dir", str(state)]
    probe = Probe([*base, "--fixture"])
    try:
        probe.wait("Ready")
        probe.send(b"Remember terminal-resume-281\r")
        probe.wait("Completed")
        probe.send(b"unfinished correction")
        draft_is(probe, "unfinished correction")
    finally:
        probe.close()
    from amplifier_tui.conversations import resolve_resume

    entry = resolve_resume(state, "latest")
    path = state / "conversations" / entry["id"]
    before = (path / "events.jsonl").read_text().count('"kind": "tool.updated"')
    probe = Probe([*base, "--resume"])
    try:
        probe.wait("Resume conversation")
        assert (path / "events.jsonl").read_text().count('"kind": "tool.updated"') == before
        probe.send(b"\r")
        probe.wait("Ready")
        draft_is(probe, "unfinished correction")
        assert (path / "events.jsonl").read_text().count('"kind": "tool.updated"') == before
        probe.send(b"\x1b[A")
        draft_is(probe, "Remember terminal-resume-281")
        probe.send(b"\x1b[B")
        draft_is(probe, "unfinished correction")
        probe.send(b"\r")
        probe.wait("Completed")
    finally:
        probe.close()
    checkpoint = json.loads((path / "checkpoint.json").read_text())
    assert "terminal-resume-281" in str(checkpoint["messages"])
    assert "unfinished correction" in str(checkpoint["messages"])
    assert checkpoint["status"] == "ready"

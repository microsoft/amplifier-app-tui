"""Native structured reading; module-backed fixture and clearly labelled scene edge cases."""

import base64
import json
import os
import re
import sys
import time
from pathlib import Path

import pytest
from test_workspace_review import git

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from interaction_probe import action, capture  # noqa: E402
from questions_probe import wait_ready  # noqa: E402
from shared_session_probe import READING_REPLY  # noqa: E402
from terminal_probe import Probe  # noqa: E402
from test_reading_terminal import draft_is, scene  # noqa: E402
from test_workflow_terminal import events  # noqa: E402

pytestmark = pytest.mark.skipif(
    os.environ.get("TUI_TEST_CANDIDATES") != "1", reason="Build Ratatui"
)


def copied(probe, count=1):
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        copies = re.findall(rb"\x1b\]52;c;([^\x07]*)\x07", probe.raw)
        if len(copies) >= count:
            return base64.b64decode(copies[-1]).decode()
        probe.read(0.02)
    raise AssertionError("Missing a new clipboard observation")


def code_colours(probe, needle):
    probe.wait(needle)
    row = next(i for i, line in enumerate(probe.screen.display) if needle in line)
    start = probe.screen.display[row].index(needle)
    return {probe.screen.buffer[row][x].fg for x in range(start, start + len(needle))}


@pytest.mark.parametrize("width", [40, 80, 175])
def test_mixed_markdown_retains_exact_copy_and_draft_at_terminal_widths(tmp_path, width):
    path = tmp_path / "reading-scene.json"
    path.write_text(
        json.dumps(
            {
                "title": "Structured reading fixture",
                "draft": "Keep this draft",
                "items": [{"id": "reading", "kind": "assistant", "text": READING_REPLY}],
                "system": [],
            }
        )
    )
    probe = Probe(
        [
            str(ROOT / "frontends/ratatui/target/release/amplifier-ratatui"),
            "--host-json",
            json.dumps(
                [sys.executable, "-m", "amplifier_tui.frontend_bridge", "--scene", str(path)]
            ),
        ],
        cols=width,
        rows=50,
    )
    try:
        probe.wait("Reading check complete.")
        if width >= 80:
            rows = probe.screen.display
            continuation = next(row for row in rows if "A continuation paragraph" in row)
            assert continuation.startswith("   A continuation paragraph")
            heading = next(i for i, row in enumerate(rows) if "### Sources" in row)
            assert not rows[heading - 1].strip()
        capture(probe, f"mixed-markdown-{width}")
        action(probe, "Assistant replies", "Assistant replies · latest")
        probe.send(b"\r")
        probe.wait("Message · retained source preview")
        probe.send(b"Copy message\r")
        probe.wait("Source copied")
        assert copied(probe) == READING_REPLY
        draft_is(probe, "Keep this draft")
    finally:
        probe.close()


@pytest.mark.parametrize("no_colour", [False, True])
def test_syntax_colour_native_inspection_copy_and_plain_fallback(tmp_path, no_colour):
    code = 'def greeting():\n    return "Hello, world"\n'
    path = tmp_path / "syntax-scene.json"
    path.write_text(
        json.dumps(
            {
                "title": "Syntax colour fixture",
                "draft": "Keep this draft",
                "items": [
                    {
                        "id": "code",
                        "kind": "assistant",
                        "text": "```python\n"
                        + code
                        + "```\n\n```unknown-language\nplain = 'unchanged'\n```",
                    }
                ],
                "system": [],
            }
        )
    )
    probe = Probe(
        [
            str(ROOT / "frontends/ratatui/target/release/amplifier-ratatui"),
            "--host-json",
            json.dumps(
                [sys.executable, "-m", "amplifier_tui.frontend_bridge", "--scene", str(path)]
            ),
        ],
        cols=80,
        env={"NO_COLOR": "1"} if no_colour else None,
    )
    try:
        probe.wait("Ready")
        assert (len(code_colours(probe, 'return "Hello, world"')) > 1) == (not no_colour)
        assert len(code_colours(probe, "plain = 'unchanged'")) == 1
        capture(probe, "syntax-native-plain" if no_colour else "syntax-native-colour")
        action(probe, "Code blocks", "Code blocks · inspect")
        probe.send(b"python\r")
        probe.wait("Code block · captured source")
        assert (len(code_colours(probe, 'return "Hello, world"')) > 1) == (not no_colour)
        capture(probe, "syntax-inspection-plain" if no_colour else "syntax-inspection-colour")
        probe.resize(40, 40)
        probe.wait("Hello, world")
        probe.send(b"Copy code\r")
        probe.wait("Source copied")
        assert copied(probe) == code
        draft_is(probe, "Keep this draft")
    finally:
        probe.close()


def test_real_fixture_tables_code_copy_and_resume(tmp_path):
    command = [
        sys.executable,
        str(ROOT / "scripts/run.py"),
        "--no-install",
        "--state-dir",
        str(tmp_path / "state"),
    ]
    probe = Probe(
        [*command, "--fixture", "--overlay", str(ROOT / "examples/fixture-reading.yaml")], cols=160
    )
    try:
        wait_ready(probe)
        probe.send(b"Show the reading fixture\r")
        probe.wait_idle()
        probe.send(b"Keep my draft")
        probe.send(b"\x1b[5~" * 8)
        probe.wait("Structured reading fixture")
        probe.wait("┬")
        capture(probe, "structured-table-wide")
        probe.resize(60, 40)
        probe.wait("Notes:")  # wait for the narrow-column layout, not the old width
        probe.send(b"\x1b[5~")  # narrower table reflow needs an earlier visual page
        probe.wait("State:")
        probe.send(b"\x1b[5~" * 8)
        probe.wait("stacked for this width")
        probe.wait("Component:")
        capture(probe, "structured-table-narrow")
        probe.resize(160, 40)
        probe.wait("┬")
        action(probe, "Code blocks", "Code blocks · inspect")
        probe.send(b"python\r")
        probe.wait("Code block · captured source")
        probe.wait("def greeting():")
        assert len(code_colours(probe, "def greeting():")) > 1
        capture(probe, "structured-code-preview")
        probe.send(b"Copy code\r")
        probe.wait("Source copied")
        assert copied(probe) == 'def greeting():\n    return "Hello, 界"\n'
        draft_is(probe, "Keep my draft")
        assert len([e for e in events(tmp_path) if e["kind"] == "turn.accepted"]) == 1
        tools = [e["payload"] for e in events(tmp_path) if e["kind"] == "tool.updated"]
        assert {e["name"] for e in tools} == {"fixture_probe"}
        assert any(e["status"] == "succeeded" for e in tools)
        identity = next((tmp_path / "state/conversations").iterdir()).name
    finally:
        probe.close()
    probe = Probe([*command, "--resume", identity], cols=160)
    try:
        wait_ready(probe)
        action(probe, "Code blocks", "Code blocks · inspect")
        probe.send(b"python\r")
        probe.wait("Code block · captured source")
        probe.send(b"Copy code\r")
        probe.wait("Source copied")
        assert copied(probe) == 'def greeting():\n    return "Hello, 界"\n'
        draft_is(probe, "Keep my draft")
        assert len([e for e in events(tmp_path) if e["kind"] == "turn.accepted"]) == 1
    finally:
        probe.close()


def test_code_catalog_limits_and_oversized_copy_explanation(tmp_path):
    source = (
        "```text\n" + "x" * (1024 * 1024 + 1) + "\n```\n" + "```py\nprint('small')\n```\n" * 101
    )
    probe = scene(
        tmp_path, [{"id": "bounded", "kind": "assistant", "text": source}], draft="Unsent scratch"
    )
    try:
        probe.wait("Ready")
        action(probe, "Code blocks", "Partial catalog")
        probe.send(b"text\r")
        probe.wait("Copy unavailable")
        assert "Copy code content" not in probe.text
        probe.send(b"\x1b")
        draft_is(probe, "Unsent scratch")
    finally:
        probe.close()


def test_open_code_snapshot_does_not_change_with_simulated_source_updates(tmp_path):
    trigger = tmp_path / "update-source"
    program = f"""
import json, pathlib, select, sys
def emit(**value):
    print(json.dumps(dict(version=1, **value)), flush=True)
emit(type="snapshot", session_id="simulated", mode="SIMULATED", draft="Main scratch", items=[dict(id="source",kind="assistant",text="```py\\nprint('before')\\n```")], system=[])
emit(type="state", status="Ready")
updated = False
while True:
    if pathlib.Path({str(trigger)!r}).exists() and not updated:
        updated = True
        emit(type="item",id="source",kind="assistant",text="```py\\nprint('after')\\n```")
        emit(type="error",message="Simulated source update received")
    ready, _, _ = select.select([sys.stdin], [], [], 0.01)
    if ready:
        line = sys.stdin.readline()
        if not line or json.loads(line).get("op") == "shutdown": break
"""
    probe = Probe(
        [
            str(ROOT / "frontends/ratatui/target/release/amplifier-ratatui"),
            "--host-json",
            json.dumps([sys.executable, "-u", "-c", program]),
        ]
    )
    try:
        probe.wait("Ready")
        action(probe, "Code blocks", "Code blocks · inspect")
        probe.send(b"\r")
        probe.wait("Code block · captured source")
        trigger.write_text("update")
        probe.wait("Simulated source update received")
        probe.send(b"Copy code\r")
        probe.wait("Source copied")
        assert copied(probe) == "print('before')\n"
        action(probe, "Code blocks", "Code blocks · inspect")
        probe.send(b"\r")
        probe.wait("Code block · captured source")
        probe.send(b"Copy code\r")
        probe.wait("Source copied")
        assert copied(probe, count=2) == "print('after')\n"
        draft_is(probe, "Main scratch")
    finally:
        probe.close()


def test_real_git_hunks_are_coloured_copyable_and_stable_snapshots(tmp_path):
    repository = tmp_path / "repo"
    repository.mkdir()
    git(repository, "init")
    path = repository / "sample.txt"
    base = [f"line {n:03d}\n" for n in range(80)]
    path.write_text("".join(base))
    git(repository, "add", "sample.txt")
    git(repository, "commit", "-m", "fixture")
    changed = base.copy()
    changed[2], changed[70] = "first changed\n", "second changed\n"
    path.write_text("".join(changed))
    probe = Probe(
        [
            sys.executable,
            str(ROOT / "scripts/run.py"),
            "--fixture",
            "--no-install",
            "--cwd",
            str(repository),
            "--state-dir",
            str(tmp_path / "state"),
        ],
        cols=160,
    )
    try:
        wait_ready(probe)
        probe.send(b"Draft stays mine")
        action(probe, "Workspace changes", "Workspace changes · observed")
        probe.send(b"unstaged\r")
        probe.wait("Browse hunks")
        probe.send(b"Browse hunks\r")
        probe.wait("Hunk 2")
        path.write_text("External change after the snapshot\n")
        probe.send(b"Hunk 2\r")
        probe.wait("+second changed")
        probe.wait("not a complete patch")
        capture(probe, "structured-diff-hunk")
        coloured = [
            (cell.data, cell.fg) for row in probe.screen.buffer.values() for cell in row.values()
        ]
        assert any(fg == "00d9f5" for _, fg in coloured)
        assert any(fg == "f85149" for _, fg in coloured)
        probe.send(b"Copy this hunk\r")
        probe.wait("Source copied")
        content = copied(probe)
        assert content.startswith("@@ -") and "+second changed\n" in content
        assert "first changed" not in content and "External change" not in content
        assert path.read_text() == "External change after the snapshot\n"
        draft_is(probe, "Draft stays mine")
        assert not any(e["kind"] == "turn.accepted" for e in events(tmp_path))
    finally:
        probe.close()

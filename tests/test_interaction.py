"""Real-terminal ordinary interactions, not source-layout or successful-engine mocks."""

import json
import os
import signal
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from terminal_probe import Probe  # noqa: E402

pytestmark = pytest.mark.skipif(
    os.environ.get("TUI_TEST_CANDIDATES") != "1", reason="Build Ratatui first"
)


def click(probe, label):
    probe.wait(label)
    for y, row in enumerate(probe.screen.display):
        if label in row:
            x = row.index(label) + 1
            probe.send(f"\x1b[<0;{x + 1};{y + 1}M\x1b[<0;{x + 1};{y + 1}m".encode())
            return
    raise AssertionError(label)


def action(probe, query, expected):
    click(probe, "[ Actions ]")
    probe.wait("Search:")
    probe.send(query.encode())
    probe.wait(f"Search: {query}")
    probe.send(b"\r")
    probe.wait(expected)


def test_actions_cancel_preserves_selection_and_paste_is_local():
    probe = Probe([sys.executable, str(ROOT / "scripts/compare.py"), "ratatui"])
    try:
        probe.wait("Waiting for your decision")
        probe.send(b"\x1b[1;2D")  # select final draft character
        click(probe, "[ Actions ]")
        probe.wait("Search:")
        probe.send(b"\x1b[200~quit\n\x1b[201~")
        probe.wait("Search: quit")
        assert probe.process.poll() is None
        probe.send(b"\x1b")
        probe.wait("Search:", absent=True)
        probe.send(b"!")
        probe.wait("are not retried!")
        # Tab visits Actions in the compact footer; Enter discovers, never submits.
        probe.send(b"\t\r")
        probe.wait("Search:")
        assert "Busy" not in probe.text
        probe.send(b"\x1b")
        probe.wait("Search:", absent=True)
        click(probe, "Review decision")
        probe.wait("Options (exact runtime scope)")
        probe.send(b"deny\r")
        probe.wait("command denied")
        probe.wait("are not retried!")
        click(probe, "[ Actions ]")
        probe.wait("Search:")
        probe.send(b"quit\r")
        probe.process.wait(timeout=4)
    finally:
        probe.close()


def test_functional_launcher_two_turns_approval_evidence_history(tmp_path):
    overlay = tmp_path / "approval.yaml"
    overlay.write_text(
        "bundle:\n  name: approval-probe\n  version: 0.1.0\ntools:\n  - module: tool-fixture\n    config:\n      approval: true\n"
    )
    probe = Probe(
        [
            sys.executable,
            str(ROOT / "scripts/run.py"),
            "--fixture",
            "--no-install",
            "--overlay",
            str(overlay),
            "--state-dir",
            str(tmp_path / "state"),
        ]
    )
    try:
        probe.wait("Ready")
        probe.wait("FIXTURE RUNTIME")
        # Empty-composer slash opens local actions, not a submitted message.
        probe.send(b"/system\r")
        probe.wait("Tools (mounted")
        probe.wait("fixture_probe")
        action(probe, "work", "[ Send ]")
        for prompt in ["Compute first digest", "Compute second digest"]:
            probe.send(prompt.encode())
            click(probe, "[ Send ]")
            probe.wait("Waiting for your decision")
            # Arrival does not take focus from the draft. Protected choice does.
            probe.send(b"Keep this correction")
            click(probe, "Review decision")
            probe.wait("Compute the fixture digest?")
            probe.send(b"allow\r")
            probe.wait_idle()
            action(probe, "expand selected", "sha256")
            probe.wait("Keep this correction")
            probe.send(b"\x1b")
            probe.wait("Evidence ·", absent=True)
            # Recall is explicit; opening/cancelling history never changes draft.
            action(probe, "history", "Directory history")
            probe.send(b"\x1b")
            probe.wait("Search:", absent=True)
            probe.wait("Keep this correction")
            probe.send(b"\x7f" * len("Keep this correction"))
            probe.wait("Keep this correction", absent=True)
        action(probe, "history", "Directory history")
        probe.send(b"\r")
        probe.wait("Compute second digest")
    finally:
        probe.close()


def test_launcher_configuration_is_explicit(monkeypatch):
    from run import arguments

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(SystemExit):
        arguments(["--settings-policy", "isolated"])
    _, command = arguments(["--fixture", "--no-install"])
    assert "--fixture" in command and "--bridge" in command
    _, command = arguments(["--preset", "anchors-amp-dev", "--overlay", "custom.yaml"])
    assert "anchors-amp-dev" in command[command.index("--bundle") + 1]
    overlays = [command[i + 1] for i, arg in enumerate(command) if arg == "--overlay"]
    assert overlays[0].endswith("examples/user-questions.yaml")
    assert overlays[1:] == ["custom.yaml"]  # Explicit overlays retain final precedence.
    assert "ANTHROPIC_API_KEY" not in json.dumps(command)


def test_menu_resize_keeps_draft_and_keyboard_access():
    probe = Probe([sys.executable, str(ROOT / "scripts/compare.py"), "ratatui"], cols=160)
    try:
        probe.wait("Waiting for your decision")
        click(probe, "[ Actions ]")
        probe.wait("Search:")
        for cols, rows in [(60, 20), (80, 24), (200, 40)]:
            probe.resize(cols, rows)
            probe.wait("Search:")
            probe.send(b"x")
            probe.wait("Search: x")
            probe.send(b"\x7f")
            probe.wait("Search: x", absent=True)
        probe.send(b"\x1b")
        probe.wait("Search:", absent=True)
        probe.wait("Also check that permanent failures are not retried.")
    finally:
        probe.close()


def test_visible_stop_interrupts_real_tool_without_losing_correction(tmp_path):
    overlay = tmp_path / "slow-tool.yaml"
    overlay.write_text(
        "bundle:\n  name: slow-tool\n  version: 0.1.0\ntools:\n  - module: tool-fixture\n    config:\n      delay: 5\n"
    )
    probe = Probe(
        [
            sys.executable,
            str(ROOT / "scripts/run.py"),
            "--fixture",
            "--no-install",
            "--overlay",
            str(overlay),
            "--state-dir",
            str(tmp_path / "state"),
        ]
    )
    try:
        probe.wait("Ready")
        probe.send(b"Compute digest\r")
        probe.wait("fixture_probe")
        probe.send(b"Keep this correction")
        action(probe, "Stop active", "Interrupted")
        probe.wait("Keep this correction")
        assert "undone" in probe.text.lower() or "partial" in probe.text.lower()
    finally:
        probe.close()


def test_keyboard_only_approval_and_actions(tmp_path):
    probe = Probe(
        [
            sys.executable,
            str(ROOT / "scripts/run.py"),
            "--fixture",
            "--no-install",
            "--overlay",
            str(ROOT / "examples/fixture-approval.yaml"),
            "--state-dir",
            str(tmp_path / "state"),
        ]
    )
    try:
        probe.wait("Ready")
        probe.send(b"Compute digest\r")
        probe.wait("Waiting for your decision")
        probe.send(b"\t\r")  # Actions first, without memorizing a dashboard tab count.
        probe.wait("Search:")
        probe.send(b"Decisions\r")
        probe.wait("Options (exact runtime scope)")
        probe.send(b"allow\r")
        probe.wait_idle()
        probe.send(b"\t\r")
        probe.wait("Search:")
        probe.send(b"expand selected\r")
        probe.wait("sha256")
        probe.send(b"\x1b")
        probe.wait("Evidence ·", absent=True)
        probe.send(b"\t\r")
        probe.wait("Search:")
        probe.send(b"quit\r")
        probe.process.wait(timeout=4)
    finally:
        probe.close()


def test_open_decision_keeps_identity_when_backend_replaces_it(tmp_path):
    # Controlled event fixture for the stale-focus race; separate from real-module tests.
    record = tmp_path / "requests.jsonl"
    backend = """
import json, signal, sys
def emit(value):
    print(json.dumps({"version": 1, **value}), flush=True)
def state(identity, status):
    emit({"type":"state", "status":status, "approval":{"id":identity,"prompt":"Scoped choice", "command":identity,"options":["once","deny"]}})
signal.signal(signal.SIGUSR1, lambda *_: state("second", "replacement pending"))
emit({"type":"snapshot", "mode":"EVENT FIXTURE", "title":"Stale focus test", "context":"test", "draft":"Keep draft", "items":[],"system":[]})
state("first", "first pending")
for line in sys.stdin:
    request=json.loads(line)
    with open(sys.argv[1], "a") as output:
        output.write(json.dumps(request)+"\\n")
    if request["op"] == "shutdown": break
    emit({"type":"state", "status":"second answered", "approval":None})
"""
    command = [
        str(ROOT / "frontends/ratatui/target/release/amplifier-ratatui"),
        "--host-json",
        json.dumps([sys.executable, "-u", "-c", backend, str(record)]),
    ]
    probe = Probe(command)
    try:
        probe.wait("first pending")
        click(probe, "Review decision")
        probe.wait("Options (exact runtime scope)")
        children = (
            Path(f"/proc/{probe.process.pid}/task/{probe.process.pid}/children").read_text().split()
        )
        assert len(children) == 1
        os.kill(int(children[0]), signal.SIGUSR1)
        probe.wait("replacement pending")
        probe.send(b"once\r")
        probe.wait("Decision no longer pending")
        assert not record.exists(), "Stale focus emitted a request"
        probe.wait("Keep draft")
        click(probe, "Review decision")
        probe.wait("Options (exact runtime scope)")
        probe.send(b"deny\r")
        probe.wait("second answered")
        request = json.loads(record.read_text().splitlines()[0])
        assert request["approval_id"] == "second" and request["option"] == "deny"
    finally:
        probe.close()

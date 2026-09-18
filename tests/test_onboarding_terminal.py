"""Task help uses the real native client but never sends its examples to the runtime."""

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from interaction_probe import capture  # noqa: E402
from questions_probe import wait_ready  # noqa: E402
from test_daily_terminal import action, dismiss  # noqa: E402
from test_navigation_terminal import start  # noqa: E402
from test_reading_terminal import draft_is  # noqa: E402

pytestmark = pytest.mark.skipif(
    os.environ.get("TUI_TEST_CANDIDATES") != "1", reason="Build native client"
)


@pytest.mark.parametrize("width", [40, 160])
def test_task_help_preserves_draft_and_never_submits(tmp_path, width):
    probe = start(tmp_path)
    try:
        wait_ready(probe)
        probe.send("Keep my 界 draft".encode())
        action(probe, "Getting started", "Help · choose a topic")
        probe.send(b"Queue or steer\r")
        probe.wait("Help · Queue or steer?")
        probe.resize(width, 40)
        probe.wait("Queue stores")
        capture(probe, f"onboarding-help-{width}")
        for _ in range(6):
            probe.send(b"\x1b[6~")  # PageDown reaches the end even at narrow widths.
            probe.read(0.03)
        probe.wait("undo file or command effects")
        capture(probe, f"onboarding-help-end-{width}")
        dismiss(probe, "Help · Queue or steer?")
        draft_is(probe, "Keep my 界 draft")
        for path in (tmp_path / "state/conversations").glob("*/events.jsonl"):
            assert not any(
                json.loads(line)["kind"] == "turn.accepted"
                for line in path.read_text().splitlines()
            )
        # The untouched composer still participates in a real tool round trip.
        probe.send(b"\r")
        probe.wait("Fixture round trip complete")
    finally:
        probe.close()

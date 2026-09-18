"""Inspect real fixture hook stdout/stderr through the native terminal, not a mock UI."""

import json
import os
import sys
from pathlib import Path

import pytest
from test_runtime_output import command

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from interaction_probe import action, capture  # noqa: E402
from terminal_probe import Probe  # noqa: E402

pytestmark = pytest.mark.skipif(
    os.environ.get("TUI_TEST_CANDIDATES") != "1", reason="Build Ratatui"
)


@pytest.mark.parametrize("size", [(175, 50), (40, 20)])
def test_private_runtime_output_is_inspectable_and_not_transcript(tmp_path, size):
    probe = Probe(
        [
            str(ROOT / "frontends/ratatui/target/release/amplifier-ratatui"),
            "--host-json",
            json.dumps(command(tmp_path)),
        ],
        cols=size[0],
        rows=size[1],
    )
    try:
        probe.wait("Ready", timeout=30)
        assert "BOOT-DIAGNOSTIC" not in probe.text
        probe.send(b"Exercise fixture tool\r")
        probe.wait("Fixture round trip complete.", timeout=15)
        probe.wait("[ Send ]")
        assert "HOOK-DIAGNOSTIC" not in probe.text
        probe.send(b"Preserve draft")
        action(probe, "Runtime output", "Runtime output")
        probe.wait("Refresh observations")
        capture(probe, f"runtime-output-{size[0]}-catalog")
        probe.send(b"HOOK-DIAGNOSTIC")
        probe.wait("Search: HOOK-DIAGNOSTIC")
        probe.send(b"\r")
        probe.wait("Private process output;")
        probe.wait("HOOK-DIAGNOSTIC")
        assert "null" not in probe.text and "Observed sequences" not in probe.text
        probe.wait("Copy private diagnostic")
        capture(probe, f"runtime-output-{size[0]}-detail")
        probe.send(b"\x1b")
        probe.wait("Actions / choices", absent=True)
        probe.wait("Preserve draft")
        assert b"fixture-clipboard" not in probe.raw
        assert b"fixture-auth-value" not in probe.raw
        assert b"\x1b[3J" not in probe.raw
    finally:
        probe.close()
    journal = next((tmp_path / "state/conversations").glob("*/events.jsonl")).read_text()
    assert "DIAGNOSTIC" not in journal
    events = [json.loads(row) for row in journal.splitlines()]
    assert sum(row["kind"] == "turn.accepted" for row in events) == 1

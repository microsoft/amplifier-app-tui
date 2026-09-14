"""Four billed live turns: active corrections and retained model selection in both presets."""

import argparse
import hashlib
import json
import os
import sys
import time
import uuid

from interaction_probe import action, capture
from navigation_probe import read_events
from terminal_probe import ROOT, Probe

from amplifier_tui.conversations import resolve_resume


def observed(probe, path, kind, count=1, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        probe.read(0.02)
        matches = [e for e in read_events(path) if e["kind"] == kind]
        if len(matches) >= count:
            return matches
    raise AssertionError(f"Missing {count} {kind} observations")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", required=True, action="store_true")
    parser.parse_args()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        parser.error("Supply ANTHROPIC_API_KEY; no credential migration")
    state = ROOT / ".state/controls-live" / uuid.uuid4().hex
    results = []
    for preset in ("anchors", "anchors-amp-dev"):
        directory = state / preset
        command = [
            sys.executable,
            str(ROOT / "scripts/run.py"),
            "--no-install",
            "--state-dir",
            str(directory),
        ]
        probe = Probe(
            [
                *command,
                "--preset",
                preset,
                "--overlay",
                str(ROOT / "examples/anthropic-models.yaml"),
            ],
            cols=160,
        )
        marker = "correction-" + uuid.uuid4().hex[:12]
        try:
            probe.wait("Ready", timeout=60)
            record = resolve_resume(directory, "latest")
            path = directory / "conversations" / record["id"]
            ready = observed(probe, path, "session.ready")[-1]["payload"]
            assert ready["providers"] == ["anthropic-haiku", "anthropic-sonnet"]
            probe.send(
                b"Use only read_file to read pyproject.toml and report the project name. Do not edit, delegate, run commands or use any other tool.\r"
            )
            observed(probe, path, "steering.ready")
            action(probe, "Correct active turn", "Correction for this turn only")
            probe.send(
                (
                    f"Remember correction marker {marker}. After the requested read_file, reply only with that marker. Do not use other tools.\r"
                ).encode()
            )
            ending = observed(probe, path, "turn.ended")[-1]
            assert ending["payload"]["status"] == "completed"
            observations = read_events(path)
            corrections = [e for e in observations if e["kind"] == "steering.updated"]
            assert [e["payload"]["status"] for e in corrections] == ["pending", "applied"]
            assert corrections[0]["item_id"] == corrections[1]["item_id"]
            assert len([e for e in observations if e["kind"] == "turn.accepted"]) == 1
            assert any(
                e["kind"] == "tool.updated"
                and e["payload"].get("name") == "read_file"
                and e["payload"].get("status") == "succeeded"
                for e in observations
            )
            assert marker in "".join(
                e["payload"]["text"] for e in observations if e["kind"] == "text.final"
            )
            assert (
                next(e for e in observations if e["kind"] == "provider.selected")["payload"][
                    "provider"
                ]
                == "anthropic-haiku"
            )
            probe.wait("[ Send ]")
            action(probe, "Conversation provider", "Conversation provider · choose then confirm")
            capture(probe, f"controls-live-{preset}-providers")
            probe.send(b"anthropic-sonnet\r")
            probe.wait("Apply conversation provider?")
            probe.send(b"\r")
            probe.wait("Conversation provider saved")
        finally:
            probe.close()

        probe = Probe([*command, "--resume", record["id"]], cols=160)
        try:
            probe.wait("Ready", timeout=60)
            action(probe, "Conversation provider", "Conversation provider · choose then confirm")
            probe.wait("Current: anthropic-sonnet")
            probe.send(b"\x1b")
            assert len([e for e in read_events(path) if e["kind"] == "turn.accepted"]) == 1
            probe.send(
                b"Without any tools, reply only with the correction marker from my earlier active-turn correction.\r"
            )
            endings = observed(probe, path, "turn.ended", count=2)
            assert all(e["payload"]["status"] == "completed" for e in endings)
            observations = read_events(path)
            turns = [e for e in observations if e["kind"] == "turn.accepted"]
            assert len(turns) == 2
            second = [e for e in observations if e["turn_id"] == turns[-1]["turn_id"]]
            assert not any(e["kind"] == "tool.updated" for e in second)
            assert marker not in turns[-1]["payload"]["text"]
            assert marker in "".join(
                e["payload"]["text"] for e in second if e["kind"] == "text.final"
            )
            selected = next(e for e in second if e["kind"] == "provider.selected")["payload"]
            assert selected["provider"] == "anthropic-sonnet" and selected["basis"] == "pinned"
            assert selected["model"] == "claude-sonnet-4-5"
            probe.wait("[ Send ]")
            probe.send(b"Unsent control review draft")
            action(probe, "Corrections —", "Corrections · latest")
            capture(probe, f"controls-live-{preset}-correction")
            probe.send(b"\x1b")
            results.append(
                {
                    "preset": preset,
                    "completed_turns": 2,
                    "active_correction_inserted": True,
                    "same_turn_read_file": True,
                    "distinct_mounted_models": True,
                    "resumed_pin_observed_on_execution": True,
                    "correction_recalled_without_tool_replay": True,
                }
            )
            print(json.dumps(results[-1]), flush=True)
        finally:
            probe.close()
        assert (
            json.loads((path / "draft.json").read_text())["text"] == "Unsent control review draft"
        )
    files = [
        *sorted((ROOT / "frontends/ratatui/src").glob("*.rs")),
        *sorted((ROOT / "src/amplifier_tui").rglob("*.py")),
        ROOT / "frontends/ratatui/Cargo.lock",
        ROOT / "scripts/run.py",
        ROOT / "scripts/controls_probe.py",
        ROOT / "examples/anthropic-models.yaml",
    ]
    receipt = {
        "scope": "Live corrections and conversation-only mounted-model selection; four billed turns, not complete parity or a latency comparison",
        "results": results,
        "source_fingerprints": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files
        },
    }
    (ROOT / "notes/evidence/controls-live.json").write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()

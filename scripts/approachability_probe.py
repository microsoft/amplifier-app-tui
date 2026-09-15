"""Explicitly billed native gate: durable image sets and isolated provider validation."""

import argparse
import base64
import hashlib
import json
import os
import sys
import uuid
from pathlib import Path

from controls_probe import observed
from interaction_probe import action, capture
from navigation_probe import read_events
from PIL import Image
from questions_probe import wait_ready
from terminal_probe import ROOT, Probe

from amplifier_tui.conversations import resolve_resume


def dismiss(probe, label):
    probe.send(b"\x1b")
    probe.wait(label, absent=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", required=True, action="store_true")
    parser.add_argument("--output", default="notes/evidence/approachability-live.json")
    args = parser.parse_args()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        parser.error("Supply ANTHROPIC_API_KEY explicitly; no credential migration")
    directory = ROOT / ".state/approachability-live" / uuid.uuid4().hex
    directory.mkdir(parents=True, mode=0o700)
    results = []
    for preset in ("anchors", "anchors-amp-dev"):
        cwd = directory / preset
        cwd.mkdir()
        state = cwd / "state"
        originals = []
        for color in ("red", "blue"):
            path = cwd / f"{color}.png"
            Image.new("RGB", (32, 32), color).save(path)
            originals.append(path.read_bytes())
        command = [
            sys.executable,
            str(ROOT / "scripts/run.py"),
            "--no-install",
            "--state-dir",
            str(state),
        ]
        probe = Probe([*command, "--preset", preset, "--cwd", str(cwd)], cols=160)
        try:
            wait_ready(probe)
            record = resolve_resume(state, "latest")
            path = state / "conversations" / record["id"]
            probe.send(
                b"Name the dominant colour of image 1 and image 2, in that order. "
                b"Do not read files, use tools, delegate or change anything."
            )
            for color in ("red", "blue"):
                action(probe, "Attach image", "Workspace-relative PNG/JPEG")
                probe.send(f"{color}.png\r".encode())
                probe.wait("Image snapshot · confirm attachment")
                capture(probe, f"approachability-live-{preset}-{color}-preview")
                probe.send(b"\r")
                probe.wait("[Image attached]")
                # A later file version must not substitute for captured intent.
                Image.new("RGB", (32, 32), "black").save(cwd / f"{color}.png")
            action(probe, "Queue current draft", "[Pending 1] (paused)")
            assert not any(e["kind"] == "turn.accepted" for e in read_events(path))
        finally:
            probe.close()
        probe = Probe([*command, "--resume", record["id"]], cols=160)
        try:
            wait_ready(probe)
            assert not any(e["kind"] == "turn.accepted" for e in read_events(path))
            action(probe, "Pending follow-ups", "Pending follow-ups · paused")
            probe.send(b"queued\r")
            probe.wait("Frozen attachments travel")
            capture(probe, f"approachability-live-{preset}-queue")
            dismiss(probe, "Follow-up · inspect")
            action(probe, "Pending follow-ups", "Pending follow-ups · paused")
            probe.send(b"Run pending\r")
            assert observed(probe, path, "turn.ended")[-1]["payload"]["status"] == "completed"
            probe.wait("[ Send ]")
            rows = read_events(path)
            reply = " ".join(e["payload"]["text"] for e in rows if e["kind"] == "text.final")
            assert "red" in reply.lower() and "blue" in reply.lower()
            assert not any(e["kind"] == "tool.updated" for e in rows)
            checkpoint = (path / "checkpoint.json").read_bytes()
            images = [
                block
                for msg in json.loads(checkpoint)["messages"]
                if isinstance(msg.get("content"), list)
                for block in msg["content"]
                if block.get("type") == "image"
            ]
            assert [base64.b64decode(block["source"]["data"]) for block in images] == originals
            capture(probe, f"approachability-live-{preset}-reply")
            probe.send(b"Unsent correction")
            action(probe, "Stored context", "Stored context · module snapshot")
            probe.wait("NOT the exact next provider request")
            capture(probe, f"approachability-live-{preset}-context")
            dismiss(probe, "Stored context · module snapshot")
            action(probe, "Conversation provider", "Conversation provider · choose then confirm")
            probe.send(b"Validate anthropic\r")
            probe.wait("Validate provider access?")
            probe.send(b"\r")
            probe.wait("Provider validation · observed result", timeout=35)
            probe.wait("Provider returned a response")
            capture(probe, f"approachability-live-{preset}-validation")
            dismiss(probe, "Provider validation · observed result")
            assert "Unsent correction" in probe.text
            assert (path / "checkpoint.json").read_bytes() == checkpoint
            assert sum(e["kind"] == "turn.accepted" for e in read_events(path)) == 1
            results.append(
                {
                    "preset": preset,
                    "frozen_images": 2,
                    "queue_survives_reopen": True,
                    "changed_source_not_substituted": True,
                    "canonical_bytes_match": True,
                    "controlled_colours_identified": True,
                    "completed_turns": 1,
                    "tool_calls": 0,
                    "context_inspection_no_submission": True,
                    "explicit_provider_probe_succeeded": True,
                    "probe_no_conversation_change": True,
                    "draft_retained": True,
                }
            )
            print(json.dumps(results[-1]), flush=True)
        finally:
            probe.close()
    files = [
        *sorted((ROOT / "frontends/ratatui/src").glob("*.rs")),
        *sorted((ROOT / "src/amplifier_tui").rglob("*.py")),
        ROOT / "frontends/ratatui/Cargo.lock",
        Path(__file__).resolve(),
    ]
    (ROOT / args.output).write_text(
        json.dumps(
            {
                "scope": "Two real-preset vision turns plus two confirmed standalone remote probes; may incur charges. Controlled inputs and local state. Not universal image/provider support or credential migration.",
                "results": results,
                "source_fingerprints": {
                    str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in files
                },
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()

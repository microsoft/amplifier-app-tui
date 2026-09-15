"""Two explicit billed vision turns; isolated inputs/state, native attachment and source UI."""

import argparse
import base64
import hashlib
import json
import os
import sys
import uuid

from controls_probe import observed
from interaction_probe import action, capture
from navigation_probe import read_events
from PIL import Image, ImageDraw
from questions_probe import wait_ready
from terminal_probe import ROOT, Probe

from amplifier_tui.conversations import resolve_resume


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", required=True, action="store_true")
    parser.add_argument("--output", default="notes/evidence/backlog-live.json")
    args = parser.parse_args()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        parser.error("Supply ANTHROPIC_API_KEY explicitly; no credential migration")
    directory = ROOT / ".state/backlog-live" / uuid.uuid4().hex
    directory.mkdir(parents=True, mode=0o700)
    image = Image.new("RGB", (320, 160), "red")
    ImageDraw.Draw(image).rectangle((160, 0, 319, 159), fill="blue")
    image.save(directory / "board.png")
    raw = (directory / "board.png").read_bytes()
    results = []
    for preset in ("anchors", "anchors-amp-dev"):
        state = directory / preset
        probe = Probe(
            [
                sys.executable,
                str(ROOT / "scripts/run.py"),
                "--no-install",
                "--preset",
                preset,
                "--cwd",
                str(directory),
                "--state-dir",
                str(state),
            ],
            cols=160,
        )
        try:
            wait_ready(probe)
            record = resolve_resume(state, "latest")
            path = state / "conversations" / record["id"]
            action(probe, "Attach image", "Workspace-relative PNG/JPEG")
            probe.send(b"board.png\r")
            probe.wait("Image snapshot · confirm attachment")
            capture(probe, f"backlog-live-{preset}-attachment")
            probe.send(b"\r")
            probe.wait("[Image attached]")
            probe.send(
                b"Describe the left and right halves of the attached image in one sentence. Do not read files, use tools, delegate, or change anything.\r"
            )
            assert observed(probe, path, "turn.ended")[-1]["payload"]["status"] == "completed"
            probe.wait("[ Send ]")
            events = read_events(path)
            reply = " ".join(e["payload"]["text"] for e in events if e["kind"] == "text.final")
            assert "red" in reply.lower() and "blue" in reply.lower(), (
                "Provider did not identify controlled image colours"
            )
            assert not [e for e in events if e["kind"] == "tool.updated"]
            messages = json.loads((path / "checkpoint.json").read_text())["messages"]
            attached = next(
                block
                for message in messages
                if isinstance(message.get("content"), list)
                for block in message["content"]
                if block.get("type") == "image"
            )
            assert base64.b64decode(attached["source"]["data"]) == raw
            capture(probe, f"backlog-live-{preset}-reply")
            action(probe, "Instruction sources", "Instruction sources · last observed resolution")
            capture(probe, f"backlog-live-{preset}-instructions")
            probe.send(b"\x1b")
            probe.wait("Instruction sources · last observed resolution", absent=True)
            action(probe, "Model catalog", "Model catalog · explicit discovery")
            probe.send(b"\r")
            probe.wait("Model catalog · advisory IDs")
            capture(probe, f"backlog-live-{preset}-models")
            assert sum(e["kind"] == "turn.accepted" for e in read_events(path)) == 1
            results.append(
                {
                    "preset": preset,
                    "image_bytes_preserved": True,
                    "colours_identified": True,
                    "completed_turns": 1,
                    "tool_calls": 0,
                    "instruction_inspection_added_no_turn": True,
                    "explicit_model_catalog_added_no_turn": True,
                }
            )
            print(json.dumps(results[-1]), flush=True)
        finally:
            probe.close()
    files = [
        *sorted((ROOT / "frontends/ratatui/src").glob("*.rs")),
        *sorted((ROOT / "src/amplifier_tui").rglob("*.py")),
        ROOT / "frontends/ratatui/Cargo.lock",
        ROOT / "scripts/backlog_probe.py",
    ]
    (ROOT / args.output).write_text(
        json.dumps(
            {
                "scope": "Two billed vision turns over both real presets. Controlled PNG input, no tools. Not a universal provider/model or image-format certification.",
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

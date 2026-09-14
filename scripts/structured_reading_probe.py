"""Two billed read-only turns: real tool execution, rendered tables and code-content copy."""

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import uuid

from controls_probe import observed
from interaction_probe import action, capture
from navigation_probe import read_events
from questions_probe import wait_ready
from terminal_probe import ROOT, Probe

from amplifier_tui.conversations import resolve_resume


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", required=True, action="store_true")
    parser.parse_args()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        parser.error("Supply ANTHROPIC_API_KEY explicitly; no credential migration")
    state = ROOT / ".state/structured-reading-live" / uuid.uuid4().hex
    results = []
    for preset in ("anchors", "anchors-amp-dev"):
        directory = state / preset
        probe = Probe(
            [
                sys.executable,
                str(ROOT / "scripts/run.py"),
                "--no-install",
                "--preset",
                preset,
                "--state-dir",
                str(directory),
            ],
            cols=160,
        )
        try:
            wait_ready(probe)
            record = resolve_resume(directory, "latest")
            path = directory / "conversations" / record["id"]
            probe.send(
                b"Use only read_file to read pyproject.toml. Then reply with a Markdown table with columns Field and Value and rows for the project name and Python requirement. After that include exactly one fenced python code block containing print('read-only example') as illustrative text. Do not run that code, write files, run commands, delegate, or use other tools.\r"
            )
            assert observed(probe, path, "turn.ended")[-1]["payload"]["status"] == "completed"
            probe.wait("[ Send ]")
            rows = read_events(path)
            tools = [e["payload"] for e in rows if e["kind"] == "tool.updated"]
            assert {t["name"] for t in tools} == {"read_file"}
            assert any(t["status"] == "succeeded" for t in tools)
            reply = "".join(e["payload"]["text"] for e in rows if e["kind"] == "text.final")
            code = re.search(r"```python[^\n]*\n(.*?)\n```", reply, re.S)
            assert code, "Live provider did not supply the requested illustrative code"
            probe.wait("┬")
            probe.send(b"Main draft retained")
            capture(probe, f"structured-live-{preset}-table")
            action(probe, "Code blocks", "Code blocks · inspect")
            probe.send(b"python\r")
            probe.wait("Code block · captured source")
            capture(probe, f"structured-live-{preset}-code")
            probe.send(b"Copy code\r")
            probe.wait("Source copied")
            copied = base64.b64decode(
                re.findall(rb"\x1b\]52;c;([^\x07]*)\x07", probe.raw)[-1]
            ).decode()
            assert copied == code.group(1) + "\n"
            top = next(i for i, row in enumerate(probe.screen.display) if "╭ Message" in row)
            assert "Main draft retained" in "\n".join(probe.screen.display[top + 1 : top + 4])
            assert len([e for e in read_events(path) if e["kind"] == "turn.accepted"]) == 1
            results.append(
                {
                    "preset": preset,
                    "completed_turns": 1,
                    "read_file_succeeded": True,
                    "table_rendered": True,
                    "code_content_copied_exactly": True,
                    "copy_added_no_execution": True,
                    "main_draft_retained": True,
                }
            )
            print(json.dumps(results[-1]), flush=True)
        finally:
            probe.close()
    files = [
        *sorted((ROOT / "frontends/ratatui/src").glob("*.rs")),
        *sorted((ROOT / "src/amplifier_tui").rglob("*.py")),
        ROOT / "scripts/run.py",
        ROOT / "scripts/structured_reading_probe.py",
        ROOT / "frontends/ratatui/Cargo.lock",
    ]
    receipt = {
        "scope": "Two billed read-only turns across both presets; tables and code snapshots. Diff navigation is separately verified against temporary real Git repositories. Not full ecosystem or CLI latency parity.",
        "results": results,
        "source_fingerprints": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files
        },
    }
    (ROOT / "notes/evidence/structured-reading-live.json").write_text(
        json.dumps(receipt, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()

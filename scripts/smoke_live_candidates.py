"""Billed, read-only live-provider smoke; requires ANTHROPIC_API_KEY.

Presets retain authored permissions. This prompt restricts the requested work,
not the operating system. Never run this as part of deterministic unit tests.
"""

import json
import os
import sys

from terminal_probe import ROOT, Probe


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("Supply ANTHROPIC_API_KEY explicitly; no credential-store migration")
    receipts = []
    prompt = "Use read_file to read pyproject.toml. Report only the project name. Do not edit files, run commands, delegate, or use any other tool."
    for frontend, preset in [("ratatui", "anchors"), ("opentui", "anchors-amp-dev")]:
        probe = Probe(
            [
                sys.executable,
                str(ROOT / "scripts/compare.py"),
                frontend,
                "--runtime",
                "--bundle",
                str(ROOT.parent / "amplifier-foundation/bundles" / preset),
                "--overlay",
                str(ROOT / "examples/anthropic.yaml"),
                "--sources",
                str(ROOT.parent / "tui-sources.json"),
                "--require-tool",
                "read_file",
                "--state-dir",
                str(ROOT / ".state/live-candidates"),
            ]
        )
        try:
            probe.wait("Ready", timeout=45)
            probe.send(prompt.encode() + b"\r")
            probe.wait("Completed", timeout=60)
            probe.wait("✓  read_file")
            probe.wait("amplifier-app-tui")
            receipts.append(
                {
                    "frontend": frontend,
                    "bundle": preset,
                    "provider": "Anthropic / claude-haiku-4-5",
                    "fixture": False,
                    "read_file": "observed succeeded",
                    "ending": "completed",
                    "answer": "amplifier-app-tui",
                    "scope": "One real read-only turn; not all-module or CLI policy parity",
                }
            )
            print(json.dumps(receipts[-1]), flush=True)
        finally:
            probe.close()
    (ROOT / "notes/evidence/live-candidates.json").write_text(json.dumps(receipts, indent=2) + "\n")


if __name__ == "__main__":
    main()

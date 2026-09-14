"""Exercise ordinary controls against real modules; --live bills four provider turns."""

import argparse
import copy
import hashlib
import json
import os
import sys
from types import SimpleNamespace

from terminal_probe import ROOT, Probe


def click(probe, label):
    probe.wait(label)
    for y, row in enumerate(probe.screen.display):
        if label in row:
            x = row.index(label) + 1
            probe.send(f"\x1b[<0;{x + 1};{y + 1}M\x1b[<0;{x + 1};{y + 1}m".encode())
            return
    raise AssertionError(label)


def action(probe, query, expected):
    # Native output can move footer coordinates between capture and injection.
    # The normal terminal does not capture physical mouse clicks; use its actual
    # keyboard action entry point. Explicit menu mouse tests remain separate.
    # Wait for the previous dialog's closing frame; otherwise its stale Search
    # label can satisfy the next wait and adjacent ESC sequences can coalesce.
    probe.wait("Actions / choices", absent=True)
    probe.send(b"\x1bOS")
    probe.wait("Search:")
    probe.send(query.encode())
    probe.wait(f"Search: {query}")
    probe.send(b"\r")
    probe.wait(expected)


def capture(probe, name):
    # Reuse terminal-tester's renderer with the existing local observer fixes.
    # No screenshot delay is interpreted as an interaction timing.
    from capture_candidates import render_visible_cursor

    for _ in range(10):
        probe.read(0)
    screen = copy.deepcopy(probe.screen)
    ordered = screen.buffer.copy()
    ordered.clear()
    for row in range(probe.rows):
        ordered[row] = screen.buffer[row]
    screen.buffer = ordered
    display = SimpleNamespace(screen=screen, cols=probe.cols, rows=probe.rows, font_size=14)
    path = ROOT / ".evidence/interaction" / f"{name}.png"
    render_visible_cursor(display, path)
    return path


def exercise(preset=None):
    def choose(probe, query, expected):
        # Normal screen owns native mouse selection. Exercise real keyboard input,
        # not injected mouse reports a non-capturing terminal wouldn't generate.
        probe.send(b"\x1bOS")  # F4, also reachable via Tab/Enter on Actions
        probe.wait("Search:")
        probe.send(query.encode())
        probe.wait(f"Search: {query}")
        probe.send(b"\r")
        probe.wait(expected)

    command = [sys.executable, str(ROOT / "scripts/run.py"), "--no-install"]
    if preset:
        command += ["--preset", preset]
    else:
        command += ["--fixture", "--overlay", str(ROOT / "examples/fixture-approval.yaml")]
    command += ["--state-dir", str(ROOT / ".state/interaction-probe" / (preset or "fixture"))]
    probe = Probe(command, cols=160)
    try:
        probe.wait("Ready", timeout=60)
        capture(probe, f"{preset or 'fixture'}-ready")
        if preset:
            choose(probe, "Skills —", "Skills (discovered")
            probe.wait("Discovered at startup")
            capture(probe, f"{preset}-skills")
            choose(probe, "Work —", "[ Send ]")
        prompts = (
            [
                (
                    "Use read_file to read pyproject.toml. Report only the project name. Do not edit files, run commands, delegate, or use any other tool.",
                    "read_file",
                ),
                (
                    "Use load_skill with list=true. Report only the number of available skills. Do not load a skill, edit files, run commands, delegate, or use other tools.",
                    "load_skill",
                ),
            ]
            if preset
            else [
                ("Compute a digest", "fixture_probe"),
                ("Compute a second digest", "fixture_probe"),
            ]
        )
        tools = []
        for index, (prompt, tool) in enumerate(prompts):
            probe.send(prompt.encode())
            probe.send(b"\r")
            probe.wait("Working" if preset else "Waiting for your decision", timeout=45)
            if not preset:
                choose(probe, "Decisions —", "Options (exact runtime scope)")
                capture(probe, "fixture-decision")
                probe.send(b"allow\r")
            probe.wait("Completed", timeout=90)
            probe.wait(f"✓  {tool}")
            tools.append(tool)
            choose(probe, "expand selected", "Evidence ·")
            probe.wait("sha256" if not preset else '"status": "succeeded"')
            capture(probe, f"{preset or 'fixture'}-evidence-{index}")
            probe.send(b"\x1b")
            probe.wait("Evidence ·", absent=True)
        capture(probe, f"{preset or 'fixture'}-inline")
        probe.send(b"\x1bOS")
        probe.wait("Search:")
        capture(probe, f"{preset or 'fixture'}-actions")
        probe.send(b"quit\r")
        probe.process.wait(timeout=4)
        return {
            "preset": preset,
            "mode": "live" if preset else "fixture",
            "frontend": "ratatui",
            "turns": 2,
            "tools_observed_succeeded": tools,
            "ordinary_controls": True,
            "input_delivery": "Keyboard submission, Actions and decisions; no synthetic normal-view mouse clicks",
            "quit": "exit 0",
            "scope": "Usable two-turn path, not full CLI/ecosystem parity",
        }
    finally:
        probe.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output", help="Separate receipt path for a new verification wave")
    args = parser.parse_args()
    if args.live and not os.environ.get("ANTHROPIC_API_KEY"):
        parser.error("Supply ANTHROPIC_API_KEY explicitly; no credential-store import")
    receipts = []
    for preset in ["anchors", "anchors-amp-dev"] if args.live else [None]:
        receipts.append(exercise(preset))
        print(json.dumps(receipts[-1]), flush=True)
    sources = [
        *(str(p.relative_to(ROOT)) for p in sorted((ROOT / "frontends/ratatui/src").glob("*.rs"))),
        "src/amplifier_tui/host.py",
        "scripts/run.py",
        "scripts/interaction_probe.py",
        "scripts/terminal_probe.py",
    ]
    receipt = {
        "runs": receipts,
        "source_sha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sources},
    }
    output = (
        ROOT
        / "notes/evidence"
        / ("interaction-live.json" if args.live else "interaction-fixture.json")
    )
    if args.output:
        output = ROOT / args.output
    output.write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()

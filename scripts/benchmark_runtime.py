"""Real fixture-host measurements, plus explicitly NON-EQUIVALENT CLI context.

CLI adds modes, skills, routing and other policies absent from the current TUI
host. These numbers cannot settle performance P2 or select the final topology.
"""

import argparse
import hashlib
import json
import sys
import time

from benchmark_candidates import summary
from terminal_probe import ROOT, Probe


def run(name):
    if name == "cli":
        executable = ROOT / ".state/cli-baseline-env/bin/amplifier"
        command = [
            str(executable),
            "run",
            "--bundle",
            "tui-benchmark",
            "--provider",
            "fixture",
            "--mode",
            "chat",
        ]
        env = {"AMPLIFIER_HOME": str(ROOT / ".state/cli-baseline")}
    else:
        command = [
            sys.executable,
            str(ROOT / "scripts/compare.py"),
            name,
            "--runtime",
            "--fixture",
            "--no-install",
            "--sources",
            str(ROOT.parent / "tui-sources.json"),
            "--state-dir",
            str(ROOT / ".state/runtime-benchmark"),
        ]
        env = {}
    probe = Probe(command, env=env, alternate_screen=name != "cli")
    try:
        ready = probe.wait("> " if name == "cli" else "Ready", timeout=30)
        start = probe.send(b"Compute a digest\r")
        first = probe.wait("Fixture round", timeout=30)
        probe.wait("evidence.")
        if name != "cli":
            probe.wait("Completed")
        else:
            deadline = time.monotonic() + 5
            while not probe.text.rstrip().endswith(">") and time.monotonic() < deadline:
                probe.read()
        return {
            "startup_to_ready_ms": (ready - probe.start) / 1e6,
            "submit_to_first_visible_ms": (first - start) / 1e6,
            "rss_kib": probe.rss(),
        }
    finally:
        probe.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=int, default=30)
    args = parser.parse_args()
    result = {
        "scope": "Real fixture runtime; CLI policy composition differs, so CLI parity unresolved",
        "core": "1.6.1",
        "cli_source": "772bdb42f135fa310e217d6634dd727039d2d840",
        "provider": "FixtureProvider; delay=0.05 seconds; two requests and one real SHA-256 tool",
        "cache": "Fresh processes; warm installed module/source caches",
        "samples": {"ratatui": [], "opentui": [], "cli": []},
    }
    try:
        for pair in range(args.pairs):
            for name in (
                ["ratatui", "opentui", "cli"] if pair % 2 == 0 else ["cli", "opentui", "ratatui"]
            ):
                sample = run(name)
                result["samples"][name].append(sample)
                print(json.dumps({"candidate": name, "sample": sample}), flush=True)
        result["summary"] = {
            name: {
                metric: summary([r[metric] for r in samples])
                for metric in ["startup_to_ready_ms", "submit_to_first_visible_ms"]
            }
            for name, samples in result["samples"].items()
        }
    finally:
        path = ROOT / "notes/evidence/runtime-benchmark.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        result["source_fingerprints"] = {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [
                ROOT / "src/amplifier_tui/host.py",
                ROOT / "src/amplifier_tui/frontend_bridge.py",
                ROOT / "frontends/ratatui/src/main.rs",
                ROOT / "frontends/opentui/src/main.ts",
            ]
        }
        path.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()

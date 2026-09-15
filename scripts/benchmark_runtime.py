"""Real fixture-host measurements, plus explicitly NON-EQUIVALENT CLI context.

CLI adds modes, skills, routing and other policies absent from the current TUI
host. These numbers cannot settle performance P2 or select the final topology.
"""

import argparse
import hashlib
import json
import os
import sys
import time
import uuid
from pathlib import Path

from benchmark_candidates import summary
from terminal_probe import ROOT, Probe


def run(name, state):
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
            str(state / uuid.uuid4().hex),
        ]
        env = {}
    # Probe's historical flag also selects the native Ctrl-Q versus CLI Ctrl-D
    # exit path. It does not force an alternate-screen startup.
    probe = Probe(command, env=env, alternate_screen=name != "cli")
    try:
        ready = probe.wait("> " if name == "cli" else "Ready", timeout=30)
        start = probe.send(b"Compute a digest\r")
        first = probe.wait("Fixture round", timeout=30)
        completed = probe.wait("evidence.")
        if name != "cli":
            probe.wait("Completed")
        else:
            deadline = time.monotonic() + 5
            while not probe.text.rstrip().endswith(">") and time.monotonic() < deadline:
                probe.read()
        return {
            "startup_to_ready_ms": (ready - probe.start) / 1e6,
            "submit_to_first_visible_ms": (first - start) / 1e6,
            "submit_to_final_visible_ms": (completed - start) / 1e6,
            "rss_kib": probe.rss(),
        }
    finally:
        probe.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=int, default=30)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--policy-comparison", type=Path, required=True)
    parser.add_argument(
        "--native-only",
        action="store_true",
        help="Compare working native TUI and CLI, omitting historical OpenTUI",
    )
    args = parser.parse_args()
    if not 1 <= args.pairs <= 100:
        parser.error("Choose 1–100 paired repetitions")
    policy = json.loads(args.policy_comparison.read_text())
    if (
        type(policy.get("prepared_fields_match")) is not bool
        or policy.get("latency_verdict") != "NOT ESTABLISHED"
    ):
        parser.error("Supply the strict prepared-policy comparison receipt")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    receipt = os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w")
    state = ROOT / ".state/runtime-benchmark" / uuid.uuid4().hex
    names = ["ratatui", "cli"] if args.native_only else ["ratatui", "opentui", "cli"]
    result = {
        "scope": "Real fixture runtime; CLI policy composition differs, so CLI parity unresolved",
        "core": "1.6.1",
        "cli_source": "772bdb42f135fa310e217d6634dd727039d2d840",
        "provider": "FixtureProvider; delay=0.05 seconds; two requests and one real SHA-256 tool",
        "cache": "Fresh processes; warm installed module/source caches",
        "policy_comparison_sha256": hashlib.sha256(args.policy_comparison.read_bytes()).hexdigest(),
        "prepared_fields_match": policy["prepared_fields_match"],
        "latency_verdict": "NOT ESTABLISHED",
        "samples": {name: [] for name in names},
    }
    try:
        for pair in range(args.pairs):
            for name in names if pair % 2 == 0 else list(reversed(names)):
                sample = run(name, state)
                result["samples"][name].append(sample)
                print(json.dumps({"candidate": name, "sample": sample}), flush=True)
        result["summary"] = {
            name: {
                metric: summary([r[metric] for r in samples])
                for metric in [
                    "startup_to_ready_ms",
                    "submit_to_first_visible_ms",
                    "submit_to_final_visible_ms",
                ]
            }
            for name, samples in result["samples"].items()
        }
    finally:
        result["source_fingerprints"] = {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [
                ROOT / "src/amplifier_tui/host.py",
                ROOT / "src/amplifier_tui/frontend_bridge.py",
                ROOT / "frontends/ratatui/src/main.rs",
                ROOT / "frontends/opentui/src/main.ts",
            ]
        }
        with receipt:
            receipt.write(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()

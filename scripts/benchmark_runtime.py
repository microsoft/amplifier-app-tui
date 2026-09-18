"""Real fixture-host measurements, plus explicitly NON-EQUIVALENT CLI context.

Isolated TUI policy differs substantially; CLI-compatible policy still needs
request-time equivalence proof. These numbers cannot settle performance P2.
"""

import argparse
import hashlib
import json
import os
import random
import statistics
import sys
import time
import uuid
from pathlib import Path

from benchmark_candidates import summary, wait_edit
from release_wheel import source_fingerprint
from terminal_probe import ROOT, Probe


def process_tree_rss(pid):
    """Linux point-in-time RSS, including native host/children; not peak or PSS."""
    pending, seen, total = [pid], set(), 0
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        try:
            status = Path(f"/proc/{current}/status").read_text()
            for line in status.splitlines():
                if line.startswith("VmRSS:"):
                    total += int(line.split()[1])
            pending.extend(
                int(value)
                for value in Path(f"/proc/{current}/task/{current}/children").read_text().split()
            )
        except (OSError, ValueError):
            # The observation cannot distinguish a raced exit from denied access.
            return {"rss_kib": None, "processes": len(seen), "complete": False}
    return {"rss_kib": total, "processes": len(seen), "complete": True}


def timing_summary(values):
    result = summary(values)
    rng = random.Random(0)
    medians = sorted(statistics.median(rng.choices(values, k=len(values))) for _ in range(2000))
    result["median_bootstrap_95pct_ms"] = [medians[49], medians[1949]]
    result["uncertainty"] = (
        "Empirical warm samples; percentile median interval, not provider/cold-cache or policy equivalence"
    )
    return result


def run(name, state, cli_compatible=False, *, cli_home=None, cli_executable=None):
    cli_home = cli_home or ROOT / ".state/cli-baseline"
    if name == "cli":
        executable = cli_executable or ROOT / ".state/cli-baseline-env/bin/amplifier"
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
        env = {"AMPLIFIER_HOME": str(cli_home)}
    elif cli_compatible:
        command = [
            sys.executable,
            str(ROOT / "scripts/run.py"),
            "--settings-policy",
            "cli",
            "--cli-home",
            str(cli_home),
            "--bundle",
            str(ROOT / "src/amplifier_tui/fixtures/bundle.yaml"),
            "--sources",
            str(state / "sources.json"),
            "--no-install",
            "--state-dir",
            str(state / uuid.uuid4().hex),
        ]
        env = {}
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
        ready_rss = process_tree_rss(probe.process.pid)
        start = probe.send(b"Compute a digest\r")
        tool = probe.wait("▸ fixture_probe · done", timeout=30) if name == "ratatui" else None
        first = probe.wait("Fixture round", timeout=30)
        completed = probe.wait("evidence.")
        if name != "cli":
            probe.wait_idle()
        else:
            deadline = time.monotonic() + 5
            while not probe.text.rstrip().endswith(">") and time.monotonic() < deadline:
                probe.read()
        completed_rss = process_tree_rss(probe.process.pid)
        controls = {}
        if name == "ratatui":
            probe.wait("[ Send ]")
            edit_start = probe.send(b"benchmark-unsent-draft")
            controls["idle_edit_ms"] = (
                wait_edit(probe, "benchmark-unsent-draft") - edit_start
            ) / 1e6
            menu_start = probe.send(b"\x1bOS")
            controls["actions_open_ms"] = (
                probe.wait("Actions · type to search") - menu_start
            ) / 1e6
            close_start = probe.send(b"\x1b")
            controls["actions_return_ms"] = (
                probe.wait("Actions / choices", absent=True) - close_start
            ) / 1e6
            wait_edit(probe, "benchmark-unsent-draft")
            probe.send(b"\x1bOS")
            probe.wait("Search:")
            probe.send("Transcript —".encode())
            probe.wait("Search: Transcript —")
            inspect_start = probe.send(b"\r")
            controls["inspection_open_ms"] = (probe.wait("[ Latest") - inspect_start) / 1e6
            probe.wait("Fixture round")
            y = next(i for i, line in enumerate(probe.screen.display) if "Fixture round" in line)
            x = probe.screen.display[y].index("Fixture round")
            select_start = probe.send(
                f"\x1b[<0;{x + 1};{y + 1}M\x1b[<32;{x + 8};{y + 1}M\x1b[<0;{x + 8};{y + 1}m".encode()
            )
            controls["inspection_select_ms"] = (probe.wait("Text selected") - select_start) / 1e6
            previous_bytes = probe.bytes
            probe.send(b"\x1b")  # Clear selection before returning to native history.
            deadline = time.monotonic() + 5
            while probe.bytes == previous_bytes:
                if time.monotonic() >= deadline:
                    raise AssertionError("Selection did not redraw after Escape")
                probe.read()
            # A second Escape closes inspection; neither step copies to the OS.
            return_start = probe.send(b"\x1b")
            controls["inspection_return_ms"] = (
                probe.wait("[ Latest", absent=True) - return_start
            ) / 1e6
            wait_edit(probe, "benchmark-unsent-draft")
        return {
            "startup_to_ready_ms": (ready - probe.start) / 1e6,
            "submit_to_first_visible_ms": (first - start) / 1e6,
            "submit_to_final_visible_ms": (completed - start) / 1e6,
            "rss_kib": probe.rss(),
            "process_tree_ready": ready_rss,
            "process_tree_completed": completed_rss,
            "native_controls": controls,
            "submit_to_tool_success_visible_ms": (tool - start) / 1e6 if tool else None,
        }
    finally:
        probe.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=int, default=30)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--policy-comparison", type=Path, required=True)
    parser.add_argument("--cli-home", type=Path)
    parser.add_argument("--cli-executable", type=Path)
    parser.add_argument(
        "--cli-compatible",
        action="store_true",
        help="Measure configured-policy native launch; still no parity verdict",
    )
    parser.add_argument(
        "--native-only",
        action="store_true",
        help="Compare working native TUI and CLI, omitting historical OpenTUI",
    )
    args = parser.parse_args()
    for name in ("cli_home", "cli_executable"):
        path = getattr(args, name)
        if path:
            path = path.resolve()
            if not path.is_relative_to(ROOT / ".state") or path == ROOT / ".state":
                parser.error("Use only an app-owned isolated baseline home/environment")
            setattr(args, name, path)
    if args.cli_compatible and not args.native_only:
        parser.error("CLI compatibility is a native-only host policy")
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
    if args.cli_compatible:
        state.mkdir(parents=True, exist_ok=False)
        # Empty map deliberately uses declared sources, as the CLI capture does.
        # Workspace launch selects the current native build, not a stale/missing
        # packaged binary from an editable Python installation.
        (state / "sources.json").write_text("{}\n")
    names = ["ratatui", "cli"] if args.native_only else ["ratatui", "opentui", "cli"]
    result = {
        "scope": "Real fixture runtime; CLI policy composition differs, so CLI parity unresolved",
        "core": "1.6.1",
        "cli_source": "f0ba88398043f6b012d151360397893e46cd5d52",
        "tui_settings_policy": "cli" if args.cli_compatible else "isolated",
        "native_entrypoint": "Workspace product launcher; current release build; no Cargo/build time included",
        "provider": "FixtureProvider; delay=0.05 seconds; real SHA-256 tool; app hooks can insert user-role context and induce additional fixture requests/tools",
        "cache": "Fresh processes; warm installed module/source caches",
        "resource_scope": "Two Linux process-tree RSS snapshots include renderer, host and live descendants; shared pages may be counted twice. Not peak RSS, PSS or detached/remote work.",
        "policy_comparison_sha256": hashlib.sha256(args.policy_comparison.read_bytes()).hexdigest(),
        "prepared_fields_match": policy["prepared_fields_match"],
        "latency_verdict": "NOT ESTABLISHED",
        "samples": {name: [] for name in names},
    }
    try:
        for pair in range(args.pairs):
            for name in names if pair % 2 == 0 else list(reversed(names)):
                sample = run(
                    name,
                    state,
                    args.cli_compatible,
                    cli_home=args.cli_home,
                    cli_executable=args.cli_executable,
                )
                result["samples"][name].append(sample)
                print(json.dumps({"candidate": name, "sample": sample}), flush=True)
        result["summary"] = {
            name: {
                metric: timing_summary([r[metric] for r in samples])
                for metric in [
                    "startup_to_ready_ms",
                    "submit_to_first_visible_ms",
                    "submit_to_final_visible_ms",
                ]
            }
            for name, samples in result["samples"].items()
        }
        native = result["samples"]["ratatui"]
        result["native_controls_summary"] = {
            key: timing_summary([sample["native_controls"][key] for sample in native])
            for key in native[0]["native_controls"]
        }
        result["native_tool_visible_summary"] = timing_summary(
            [sample["submit_to_tool_success_visible_ms"] for sample in native]
        )
    finally:
        result["source_fingerprints"] = {
            str(p.relative_to(ROOT)): source_fingerprint(p)
            for p in [
                *sorted((ROOT / "src/amplifier_tui").glob("*.py")),
                *sorted((ROOT / "frontends/ratatui/src").glob("*.rs")),
                ROOT / "frontends/opentui/src/main.ts",
                Path(__file__).resolve(),
            ]
        }
        with receipt:
            receipt.write(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()

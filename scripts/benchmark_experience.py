"""Measure native pending-decision and resize paint; simulated scene, no model calls."""

import argparse
import json
import sys
import time
from pathlib import Path

from benchmark_candidates import editor_contains
from benchmark_runtime import timing_summary
from release_wheel import source_fingerprint
from terminal_probe import ROOT, Probe


def measure(samples=30):
    probe = Probe([sys.executable, str(ROOT / "scripts/compare.py"), "ratatui"], cols=175, rows=50)
    result = {"decision_open_ms": [], "shrink_ms": [], "grow_ms": []}
    draft = "Also check that permanent failures are not retried."
    try:
        probe.wait("Waiting for your decision")
        for _ in range(samples):
            probe.wait("Actions / choices", absent=True)
            probe.send(b"\x1bOS")
            probe.wait("Search:")
            probe.send(b"Decisions")
            probe.wait("Search: Decisions")
            start = probe.send(b"\r")
            result["decision_open_ms"].append((probe.wait("Decision · c18") - start) / 1e6)
            for name, cols, rows in (("shrink_ms", 80, 24), ("grow_ms", 175, 50)):
                previous = probe.bytes
                start = time.monotonic_ns()
                probe.resize(cols, rows)
                deadline = time.monotonic() + 5
                while True:
                    probe.read()
                    if (
                        probe.bytes > previous
                        and "Waiting for your decision" in probe.screen.display[-1]
                        and "Decision · c18" in probe.text
                        and editor_contains(probe.screen.display, draft)
                    ):
                        break
                    if time.monotonic() >= deadline:
                        raise AssertionError("Resized decision/footer/draft did not paint")
                result[name].append((time.monotonic_ns() - start) / 1e6)
            probe.send(b"\x1b")
            probe.wait("Actions / choices", absent=True)
            assert "Waiting for your decision" in probe.text
            # No permission choice is submitted by opening, resizing or cancelling.
        return result
    finally:
        probe.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=30)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.samples < 1:
        parser.error("Samples must be positive")
    with args.output.open("x") as stream:
        result = {
            "scope": "Warm native simulated pending decision; Enter after selecting the Decisions action, then resize 175x50→80x24→175x50. Draft and request remain pending. No provider, physical device or CLI parity claim; observer/scheduler time included.",
            "source_sha256": {
                str(p.relative_to(ROOT)): source_fingerprint(p)
                for p in [
                    Path(__file__).resolve(),
                    ROOT / "scenes/retry.json",
                    ROOT / "scripts/terminal_probe.py",
                    ROOT / "scripts/benchmark_runtime.py",
                    *sorted((ROOT / "frontends/ratatui/src").glob("*.rs")),
                ]
            },
        }
        try:
            result["samples"] = measure(args.samples)
            result["summary"] = {k: timing_summary(v) for k, v in result["samples"].items()}
            print(json.dumps(result["summary"], indent=2))
        finally:
            json.dump(result, stream, indent=2)
            stream.write("\n")


if __name__ == "__main__":
    main()

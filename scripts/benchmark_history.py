"""Synthetic private-journal index measurements, never a CLI-performance claim."""

import argparse
import hashlib
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path

from amplifier_tui.history_index import search
from amplifier_tui.navigation import session_choices

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions", type=int, default=200)
    parser.add_argument("--messages", type=int, default=500)
    parser.add_argument("--samples", type=int, default=30)
    parser.add_argument("--output", default="notes/evidence/history-index-benchmark.json")
    parser.add_argument(
        "--terminal",
        action="store_true",
        help="Measure real native Resume picker paint as a separate synthetic workload",
    )
    args = parser.parse_args()
    if min(args.sessions, args.messages, args.samples) <= 0:
        parser.error("Counts must be positive")
    (ROOT / ".state").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="history-benchmark-", dir=ROOT / ".state") as value:
        directory = Path(value)
        entries, originals = [], {}
        for index in range(args.sessions):
            identity = f"{index + 1:032x}"
            path = directory / "conversations" / identity / "events.jsonl"
            path.parent.mkdir(parents=True)
            with path.open("w") as stream:
                for message in range(args.messages):
                    stream.write(
                        json.dumps(
                            {
                                "session_id": identity,
                                "sequence": message + 1,
                                "timestamp_ns": index * args.messages + message + 1,
                                "kind": "text.final",
                                "item_id": f"message-{message}",
                                "payload": {
                                    "text": (
                                        "unique-index-marker "
                                        if message == 0
                                        else "ordinary observation "
                                    )
                                    + "synthetic history " * 24
                                },
                            }
                        )
                        + "\n"
                    )
            entries.append({"id": identity})
            (path.parent / "metadata.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "id": identity,
                        "title": f"Synthetic conversation {index}",
                        "launch": {"cwd": str(directory)},
                    }
                )
            )
            (path.parent / "checkpoint.json").write_text(json.dumps({"status": "ready"}))
            originals[path] = hashlib.sha256(path.read_bytes()).hexdigest()
        indexing, samples, catalogs = [], [], []
        for _ in range(1000):
            start = time.perf_counter()
            matches, partial = search(directory, entries, "unique-index-marker")
            indexing.append((time.perf_counter() - start) * 1000)
            if not partial:
                break
        else:
            raise AssertionError(
                "Incremental indexing failed to converge within 1000 explicit queries"
            )
        assert len(matches) == args.sessions
        for _ in range(args.samples):
            start = time.perf_counter()
            matches, partial = search(directory, entries, "unique-index-marker")
            samples.append((time.perf_counter() - start) * 1000)
            assert not partial and len(matches) == args.sessions
            start = time.perf_counter()
            page = session_choices(directory, "none", query="unique-index-marker")
            catalogs.append((time.perf_counter() - start) * 1000)
            assert len(page["sessions"]) == min(100, args.sessions) and not page["partial"]
        assert all(
            hashlib.sha256(p.read_bytes()).hexdigest() == digest for p, digest in originals.items()
        )
        paints = []
        if args.terminal:
            from interaction_probe import action
            from terminal_probe import Probe

            probe = Probe(
                [
                    sys.executable,
                    str(ROOT / "scripts/run.py"),
                    "--fixture",
                    "--no-install",
                    "--cwd",
                    str(directory),
                    "--state-dir",
                    str(directory),
                ]
            )
            try:
                probe.wait("Ready", timeout=60)
                for _ in range(args.samples):
                    start = time.perf_counter()
                    action(probe, "Resume", "Saved conversations")
                    probe.wait("Synthetic conversation")
                    paints.append((time.perf_counter() - start) * 1000)
                    probe.send(b"\x1b")
                    probe.wait("Saved conversations", absent=True)
            finally:
                probe.close()
        receipt = {
            "scope": "Synthetic append-only journals; indexed search plus separate full metadata catalog/search/checkpoint-page measurements. Optional native Resume timings include F4/action query/selection and observed picker paint, not only backend work. Warm local filesystem. Excludes model, CLI and cold installation; not parity evidence.",
            "native_resume_ms": paints,
            "native_resume_p95_ms": sorted(paints)[min(len(paints) - 1, int(len(paints) * 0.95))]
            if paints
            else None,
            "sessions": args.sessions,
            "messages": args.sessions * args.messages,
            "journal_bytes": sum(p.stat().st_size for p in originals),
            "index_bytes": (directory / "history-index.sqlite3").stat().st_size,
            "index_refreshes_to_complete": len(indexing),
            "indexing_total_ms": sum(indexing),
            "indexing_max_call_ms": max(indexing),
            "warm_search_ms": samples,
            "full_catalog_search_ms": catalogs,
            "full_catalog_search_median_ms": statistics.median(catalogs),
            "full_catalog_search_p95_ms": sorted(catalogs)[
                min(len(catalogs) - 1, int(len(catalogs) * 0.95))
            ],
            "warm_search_median_ms": statistics.median(samples),
            "warm_search_p95_ms": sorted(samples)[min(len(samples) - 1, int(len(samples) * 0.95))],
            "all_first_message_matches_found": True,
            "source_journals_unchanged": True,
            "source_fingerprints": {
                str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (ROOT / "src/amplifier_tui/history_index.py", Path(__file__).resolve())
            },
        }
    (ROOT / args.output).write_text(json.dumps(receipt, indent=2) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in receipt.items()
                if k not in ("warm_search_ms", "source_fingerprints")
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

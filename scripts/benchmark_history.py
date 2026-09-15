"""Synthetic private-journal index measurements, never a CLI-performance claim."""

import argparse
import hashlib
import json
import statistics
import tempfile
import time
from pathlib import Path

from amplifier_tui.history_index import search

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions", type=int, default=200)
    parser.add_argument("--messages", type=int, default=500)
    parser.add_argument("--samples", type=int, default=30)
    parser.add_argument("--output", default="notes/evidence/history-index-benchmark.json")
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
            originals[path] = hashlib.sha256(path.read_bytes()).hexdigest()
        indexing, samples = [], []
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
        assert all(
            hashlib.sha256(p.read_bytes()).hexdigest() == digest for p, digest in originals.items()
        )
        receipt = {
            "scope": "Synthetic append-only journals; complete indexed search includes bounded refresh. Warm local filesystem. Excludes metadata catalog, UI, model, CLI and cold installation; not parity evidence.",
            "sessions": args.sessions,
            "messages": args.sessions * args.messages,
            "journal_bytes": sum(p.stat().st_size for p in originals),
            "index_bytes": (directory / "history-index.sqlite3").stat().st_size,
            "index_refreshes_to_complete": len(indexing),
            "indexing_total_ms": sum(indexing),
            "indexing_max_call_ms": max(indexing),
            "warm_search_ms": samples,
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

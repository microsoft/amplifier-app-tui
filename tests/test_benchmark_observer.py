from pathlib import Path


def test_runtime_resource_and_uncertainty_observations(monkeypatch):
    import os

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    from benchmark_runtime import process_tree_rss, timing_summary

    if Path("/proc/self/status").exists():
        result = process_tree_rss(os.getpid())
        assert result["complete"] and result["rss_kib"] > 0 and result["processes"] >= 1
    assert process_tree_rss(-1)["complete"] is False
    values = [float(i) for i in range(30)]
    result = timing_summary(values)
    lo, hi = result["median_bootstrap_95pct_ms"]
    assert lo <= result["median_ms"] <= hi
    assert result["n"] == 30 and result == timing_summary(values)


def test_edit_observer_counts_wrapped_token_not_transcript(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    from benchmark_candidates import editor_contains

    assert editor_contains(["╭ Message ╮", "│abc key00│", "│42 rest  │", "╰─────────╯"], "key0042 ")
    assert not editor_contains(["key0042", "╭ Message ╮", "│unrelated│", "╰─────────╯"], "key0042 ")
    assert not editor_contains(["╭ Message ╮", "│key004   │", "╰─────────╯"], "key0042 ")
    assert editor_contains(["╭─ Message ╮", "│key0042   │", "╰──────────╯"], "key0042 ")
    assert editor_contains(
        ["  Message · Mode: default  ", "  abc key00  ", "  42 rest    ", "  [ Actions ]  "],
        "key0042 ",
    )
    assert not editor_contains(
        ["key0042", "Message · Mode: default", "unrelated", "[ Actions ]"], "key0042 "
    )
    assert editor_contains(
        ["Message · Mode: default", "abc key00", "42 rest", "[ Actions ]"], "key0042 "
    )

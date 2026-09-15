from pathlib import Path


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

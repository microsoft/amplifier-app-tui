import json
import stat
from pathlib import Path

from test_input_history import journal

from amplifier_tui.conversations import catalog
from amplifier_tui.history_index import open_index, refresh, search
from amplifier_tui.navigation import session_choices


def append(path, identity, text, stamp=1):
    with (path / "events.jsonl").open("a") as stream:
        stream.write(
            json.dumps(
                {
                    "session_id": identity,
                    "sequence": stamp,
                    "timestamp_ns": stamp,
                    "kind": "text.final",
                    "payload": {"text": text},
                }
            )
            + "\n"
        )


def test_index_appends_replaces_deletes_without_mutating_journals(tmp_path):
    identity = "a" * 32
    path = journal(tmp_path, tmp_path, identity, ["old needle"], 1)
    original = (path / "events.jsonl").read_bytes()
    assert identity in search(tmp_path, catalog(tmp_path), "needle")[0]
    assert (path / "events.jsonl").read_bytes() == original
    assert stat.S_IMODE((tmp_path / "history-index.sqlite3").stat().st_mode) == 0o600
    append(path, identity, "newest needle", 42)
    assert "newest" in search(tmp_path, catalog(tmp_path), "needle")[0][identity]
    (path / "events.jsonl").write_text("")
    append(path, identity, "replacement", 43)
    assert not search(tmp_path, catalog(tmp_path), "needle")[0]
    assert search(tmp_path, catalog(tmp_path), "replacement")[0]
    (path / "events.jsonl").unlink()
    matches, partial = search(tmp_path, catalog(tmp_path), "replacement")
    assert not matches and partial


def test_directory_search_retains_other_indexes_and_filters_before_result_limit(tmp_path):
    local, foreign = "a" * 32, "b" * 32
    journal(tmp_path, tmp_path / "local", local, ["local needle"], 1)
    journal(tmp_path, tmp_path / "foreign", foreign, ["foreign needle"], 2)
    search(tmp_path, catalog(tmp_path), "needle")
    db = open_index(tmp_path)
    try:
        # Newer foreign matches must not consume the 10,000-result query budget.
        with db:
            db.executemany(
                "INSERT INTO messages VALUES (?,?,?,?,?,?,?)",
                (
                    (foreign, i, i, "text.final", "answer", "foreign needle", i)
                    for i in range(100, 10200)
                ),
            )
            db.executemany(
                "INSERT INTO search VALUES (?,?,?)",
                ((foreign, i, "foreign needle") for i in range(100, 10200)),
            )
        prior = db.execute("SELECT COUNT(*) FROM messages WHERE session=?", (foreign,)).fetchone()
    finally:
        db.close()
    for query in ("needle", "le"):
        matches, partial = search(
            tmp_path, catalog(tmp_path, cwd=tmp_path / "local"), query, scoped=True
        )
        assert set(matches) == {local} and not partial
    assert search(tmp_path, [], "needle", scoped=True) == ({}, False)
    db = open_index(tmp_path)
    try:
        assert (
            db.execute("SELECT COUNT(*) FROM messages WHERE session=?", (foreign,)).fetchone()
            == prior
        )
    finally:
        db.close()
    # A separate workspace can still query its retained index.
    assert set(
        search(tmp_path, catalog(tmp_path, cwd=tmp_path / "foreign"), "foreign", scoped=True)[0]
    ) == {foreign}


def test_corrupt_cache_is_preserved_and_rebuilt(tmp_path):
    identity = "a" * 32
    journal(tmp_path, tmp_path, identity, ["recoverable"], 1)
    (tmp_path / "history-index.sqlite3").write_bytes(b"not a sqlite database")
    assert search(tmp_path, catalog(tmp_path), "recoverable")[0]
    saved = list(tmp_path.glob("history-index.corrupt-*.sqlite3"))
    assert len(saved) == 1 and saved[0].read_bytes() == b"not a sqlite database"


def test_incomplete_and_oversized_records_progress_with_disclosure(tmp_path):
    identity = "a" * 32
    path = journal(tmp_path, tmp_path, identity, ["first"], 1)
    with (path / "events.jsonl").open("a") as stream:
        stream.write("x" * (4 * 1024 * 1024) + "\n")
    append(path, identity, "after oversized")
    db = open_index(tmp_path)
    try:
        for _ in range(6):
            assert refresh(db, tmp_path, catalog(tmp_path), budget=1500000)
        assert (
            db.execute("SELECT text FROM messages ORDER BY position DESC").fetchone()[0]
            == "after oversized"
        )
    finally:
        db.close()
    # An unfinished append is not indexed until the newline arrives.
    incomplete = json.dumps(
        {"session_id": identity, "kind": "text.final", "payload": {"text": "later"}}
    )
    with (path / "events.jsonl").open("a") as stream:
        stream.write(incomplete)
    assert not search(tmp_path, catalog(tmp_path), "later")[0]
    with (path / "events.jsonl").open("a") as stream:
        stream.write("\n")
    assert search(tmp_path, catalog(tmp_path), "later")[0]


def test_unicode_and_query_syntax_are_literal(tmp_path):
    identity = "a" * 32
    journal(tmp_path, tmp_path, identity, ['ÉTÉ Straße "quoted" OR other'], 1)
    for query in ("é", "ÉTÉ", "STRASSE", '"quoted"', '" OR'):
        assert identity in search(tmp_path, catalog(tmp_path), query)[0]
    assert not search(tmp_path, catalog(tmp_path), "missing OR Straße")[0]


def test_unicode_excerpt_maps_casefold_expansion_back_to_source(tmp_path):
    identity = "a" * 32
    journal(tmp_path, tmp_path, identity, ["ß" * 1000 + "visible needle"], 1)
    assert "visible needle" in search(tmp_path, catalog(tmp_path), "needle")[0][identity]


def test_out_of_range_metadata_is_partial_not_a_search_failure(tmp_path):
    identity = "a" * 32
    path = journal(tmp_path, tmp_path, identity, ["valid needle"], 1)
    append(path, identity, "invalid sequence needle", 2**100)
    with (path / "events.jsonl").open("a") as stream:
        stream.write(
            json.dumps(
                {
                    "session_id": identity,
                    "sequence": 3,
                    "timestamp_ns": 2**100,
                    "kind": "text.final",
                    "payload": {"text": "timestamp needle"},
                }
            )
            + "\n"
        )
    original = (path / "events.jsonl").read_bytes()
    matches, partial = search(tmp_path, catalog(tmp_path), "needle")
    assert identity in matches and partial
    assert (path / "events.jsonl").read_bytes() == original
    db = open_index(tmp_path)
    try:
        texts = [row[0] for row in db.execute("SELECT text FROM messages")]
        assert "invalid sequence needle" not in texts and "timestamp needle" in texts
    finally:
        db.close()


def test_refresh_budget_counts_fingerprint_reads(tmp_path, monkeypatch):
    entries = []
    for number in range(8):
        identity = f"{number:032x}"
        journal(tmp_path, tmp_path, identity, ["large first record " + "x" * 10000], 1)
        entries.append({"id": identity})
    original_open = Path.open
    consumed = 0

    class Counted:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.stream.close()

        def __getattr__(self, name):
            return getattr(self.stream, name)

        def readline(self, limit=-1):
            nonlocal consumed
            value = self.stream.readline(limit)
            consumed += len(value)
            return value

    def counted(path, *args, **kwargs):
        stream = original_open(path, *args, **kwargs)
        return Counted(stream) if path.name == "events.jsonl" else stream

    monkeypatch.setattr(Path, "open", counted)
    db = open_index(tmp_path)
    try:
        assert refresh(db, tmp_path, entries, budget=20000)
        assert consumed <= 20000
    finally:
        db.close()


def test_search_filters_before_paging_and_reads_old_messages(tmp_path):
    wanted = "a" * 32
    path = journal(tmp_path, tmp_path, wanted, ["needle at the beginning"], 1)
    for index in range(101):
        journal(tmp_path, tmp_path, f"{index + 1:032x}", ["unrelated"], index + 2)
    # The former tail-only search could not find this message.
    for _ in range(20):
        append(path, wanted, "padding " * 10000)
    result = session_choices(tmp_path, None, query="needle")
    assert [row["id"] for row in result["sessions"]] == [wanted]
    assert result["next_offset"] is None and not result["partial"]


def test_timestamped_recall_ignores_catalog_activity_order(tmp_path):
    from amplifier_tui.input_history import recall

    for identity, activity, values in (
        ("a" * 32, 100, [(1, "one"), (3, "three")]),
        ("b" * 32, 1, [(2, "two"), (4, "four")]),
    ):
        path = journal(tmp_path, tmp_path, identity, [], activity)
        (path / "events.jsonl").write_text(
            "".join(
                json.dumps(
                    {
                        "session_id": identity,
                        "kind": "turn.accepted",
                        "timestamp_ns": stamp,
                        "payload": {"text": text},
                    }
                )
                + "\n"
                for stamp, text in values
            )
        )
    assert recall(tmp_path, tmp_path, "current")["entries"] == ["one", "two", "three", "four"]

"""Native-history discovery/reader policy over the real shared Foundation API."""

import json

import pytest
from test_shared_sessions import shared as shared

from amplifier_tui.cli_compat import native_history, shared_session_catalog, shared_session_entry


@pytest.mark.parametrize("missing", [False, True])
def test_discovery_and_read_recover_complete_backups_without_writes(shared, missing):
    launch, cli, identity, messages = shared
    root = cli.base_dir / identity
    originals = {}
    for name in ("metadata.json", "transcript.jsonl"):
        path = root / name
        originals[name] = path.read_bytes()
        path.with_suffix(path.suffix + ".backup").write_bytes(originals[name])
        if missing:
            path.unlink()
        else:
            path.write_text("{incomplete")
    before = {path.name: path.read_bytes() for path in root.iterdir() if path.is_file()}
    entry = shared_session_entry(launch["cli_home"], launch["cwd"], identity)
    assert entry["title"] == "Shared fixture"
    assert [row[1]["id"] for row in shared_session_catalog(launch["cli_home"], launch["cwd"])] == [
        identity
    ]
    history = native_history(launch["cli_home"], launch["cwd"], identity)
    assert history.messages == messages
    assert {d.source for d in history.diagnostics if d.code == "recovered_backup"} == {
        "transcript",
        "metadata",
    }
    assert {path.name: path.read_bytes() for path in root.iterdir() if path.is_file()} == before
    assert not (root / ".tui").exists()


def test_native_reader_uses_shared_parser_without_losing_unknown_fields(shared):
    launch, cli, identity, _ = shared
    root = cli.base_dir / identity
    messages = [
        {
            "role": "assistant",
            "content": "Visible",
            "content_blocks": [{"type": "opaque", "vendor": "retained"}],
            "provider_state": {"continuation": "synthetic"},
        }
    ]
    (root / "transcript.jsonl").write_text(json.dumps(messages[0]) + "\n")
    assert native_history(launch["cli_home"], launch["cwd"], identity).messages == messages


def test_native_reader_never_opens_ci_log_and_refuses_unrecoverable_history(shared):
    from amplifier_foundation.session import SessionHistoryError

    launch, cli, identity, _ = shared
    root = cli.base_dir / identity
    (root / "context-intelligence").mkdir()
    (root / "context-intelligence/events.jsonl").mkdir()  # Opening it would fail.
    assert native_history(launch["cli_home"], launch["cwd"], identity).messages
    (root / "transcript.jsonl").write_text('{"role": "user"}\n{bad')
    with pytest.raises(SessionHistoryError):
        native_history(launch["cli_home"], launch["cwd"], identity)


def test_native_reader_refuses_symlink_swap_inside_foundation_read(shared, tmp_path, monkeypatch):
    from amplifier_foundation.session.history import SessionHistoryStore

    launch, cli, identity, _ = shared
    root = cli.base_dir / identity
    target = tmp_path / "unrelated.jsonl"
    target.write_text('{"role":"assistant","content":"must not read"}\n')
    original = SessionHistoryStore.load

    def swap(store, **kwargs):
        (root / "transcript.jsonl").unlink()
        (root / "transcript.jsonl").symlink_to(target)
        return original(store, **kwargs)

    monkeypatch.setattr(SessionHistoryStore, "load", swap)
    with pytest.raises((OSError, ValueError)):
        native_history(launch["cli_home"], launch["cwd"], identity)


def test_log_only_session_is_not_a_resume_candidate(shared):
    launch, cli, identity, _ = shared
    (cli.base_dir / identity / "transcript.jsonl").unlink()
    assert shared_session_catalog(launch["cli_home"], launch["cwd"]) == []


def test_metadata_discovery_never_reads_conversation_or_activity(shared, monkeypatch):
    from contextlib import contextmanager

    from amplifier_tui import cli_compat

    launch, _, identity, _ = shared
    opened = []
    original = cli_compat._open_session_file

    @contextmanager
    def metadata_only(home, cwd, session_id, filename):
        opened.append(filename)
        assert filename in ("metadata.json", "metadata.json.backup")
        with original(home, cwd, session_id, filename) as stream:
            yield stream

    monkeypatch.setattr(cli_compat, "_open_session_file", metadata_only)
    entry = shared_session_entry(launch["cli_home"], launch["cwd"], identity)
    assert entry["title"] == "Shared fixture"
    assert opened == ["metadata.json"]


def test_native_read_reports_change_between_message_read_and_revision_check(shared, monkeypatch):
    from amplifier_foundation.session.history import SessionHistoryStore

    launch, cli, identity, messages = shared
    transcript = cli.base_dir / identity / "transcript.jsonl"
    original = SessionHistoryStore._recover
    changed = False

    def changed_after_read(store, path, source, reader, empty):
        nonlocal changed
        result = original(store, path, source, reader, empty)
        if source == "transcript" and not changed:
            changed = True
            transcript.write_text(
                "".join(
                    json.dumps(m) + "\n" for m in [*messages, {"role": "user", "content": "Later"}]
                )
            )
        return result

    monkeypatch.setattr(SessionHistoryStore, "_recover", changed_after_read)
    history = native_history(launch["cli_home"], launch["cwd"], identity)
    assert history.messages == messages
    assert any(
        d.code == "changed_during_read" and d.source == "transcript" for d in history.diagnostics
    )


def test_native_corruption_diagnostic_never_echoes_payload(shared):
    from amplifier_foundation.session import SessionHistoryError

    launch, cli, identity, _ = shared
    marker = "SYNTHETIC-PRIVATE-PAYLOAD"
    (cli.base_dir / identity / "transcript.jsonl").write_text(
        '{"role":"user","content":"' + marker + '"}\n' + marker
    )
    with pytest.raises(SessionHistoryError) as caught:
        native_history(launch["cli_home"], launch["cwd"], identity)
    assert marker not in str(caught.value)
    assert marker not in repr(caught.value.diagnostics)
    assert any(d.line == 2 for d in caught.value.diagnostics)


@pytest.mark.parametrize("entrypoint", ["reader", "store"])
def test_large_native_history_streams_without_import_limits_or_whole_file_copy(
    shared, monkeypatch, tmp_path, entrypoint
):
    """A synthetic >66 MiB session is ordinary history, not a bounded import."""
    from contextlib import contextmanager

    from amplifier_tui import cli_compat

    launch, cli, identity, _ = shared
    root = cli.base_dir / identity
    transcript, metadata = root / "transcript.jsonl", root / "metadata.json"
    count = 11002  # Also exceeds the old public-import message limit.
    with transcript.open("w") as stream:
        for index in range(count):
            stream.write(
                json.dumps(
                    {
                        "role": "user" if index % 2 == 0 else "assistant",
                        "content": f"Synthetic row {index}: " + "x" * 6500,
                    }
                )
                + "\n"
            )
    assert transcript.stat().st_size > 66 * 1024 * 1024
    extension = {"opaque": "m" * (900 * 1024)}
    value = json.loads(metadata.read_text())
    metadata.write_text(json.dumps({**value, "third_party_large": extension}))
    before = [(path.stat().st_size, path.stat().st_mtime_ns) for path in (transcript, metadata)]
    (root / "context-intelligence").mkdir()
    (root / "context-intelligence/events.jsonl").mkdir()  # Native load never opens CI.
    original = cli_compat._open_session_file
    row_reads = 0

    class TranscriptStream:
        def __init__(self, stream):
            self.stream = stream

        def fileno(self):
            return self.stream.fileno()

        def read(self, *_args, **_kwargs):
            raise AssertionError("Native transcript must not be read as a whole byte string")

        def __iter__(self):
            nonlocal row_reads
            for line in self.stream:
                row_reads += 1
                yield line

    @contextmanager
    def streaming_source(home, cwd, session_id, filename):
        with original(home, cwd, session_id, filename) as stream:
            yield TranscriptStream(stream) if filename.startswith("transcript.") else stream

    monkeypatch.setattr(cli_compat, "_open_session_file", streaming_source)
    entry = shared_session_entry(launch["cli_home"], launch["cwd"], identity)
    assert entry["title"] == "Shared fixture"
    assert row_reads == 0  # Discovery did not parse any transcript bodies.
    if entrypoint == "reader":
        history = native_history(launch["cli_home"], launch["cwd"], identity)
        assert len(history.messages) == row_reads == count
        assert history.messages[0]["content"].startswith("Synthetic row 0:")
        assert history.messages[-1]["content"].startswith(f"Synthetic row {count - 1}:")
        assert history.metadata["third_party_large"] == extension
        assert not history.events and not history.diagnostics
        assert not (root / ".tui").exists()
    else:
        from amplifier_tui.conversations import SharedConversationStore

        store = SharedConversationStore(tmp_path, launch, identity)
        try:
            assert len(store.canonical_messages) == row_reads == count
            assert store.saved["messages"] is store.canonical_messages
            assert store.canonical_messages[0]["content"].startswith("Synthetic row 0:")
            assert store.canonical_messages[-1]["content"].startswith(f"Synthetic row {count - 1}:")
            assert store.canonical_metadata["third_party_large"] == extension
            store.assert_current()
            assert row_reads == count  # Revision validation does not reread transcript bodies.
            projected = store.projection()
            assert projected[0]["id"] == "history:window"
            assert 1 < len(projected) <= 102
            assert any(row["text"].startswith(f"Synthetic row {count - 1}:") for row in projected)
            assert len(json.dumps(projected).encode()) < 9 * 1024 * 1024
            assert len(store.canonical_messages) == count  # View paging never trims context.
            assert not store.history_diagnostics
            assert not (store.path / "events.jsonl").exists()
            assert not (store.path / "checkpoint.json").exists()
        finally:
            store.close()
    assert [
        (path.stat().st_size, path.stat().st_mtime_ns) for path in (transcript, metadata)
    ] == before


def test_oversized_latest_message_remains_visible_as_a_disclosed_preview(shared, tmp_path):
    from amplifier_tui.conversations import SharedConversationStore

    launch, cli, identity, _ = shared
    transcript = cli.base_dir / identity / "transcript.jsonl"
    text = "Synthetic latest answer " + "界" * (3 * 1024 * 1024)
    with transcript.open("w") as stream:
        json.dump({"role": "assistant", "content": text}, stream, ensure_ascii=False)
        stream.write("\n")
    before = (transcript.stat().st_size, transcript.stat().st_mtime_ns)
    assert before[0] > 8 * 1024 * 1024
    store = SharedConversationStore(tmp_path, launch, identity)
    try:
        projected = store.projection()
        answer = next(row for row in projected if row["kind"] == "assistant")
        assert answer["text"].startswith("Synthetic latest answer")
        assert "preview shortened" in answer["text"].lower()
        assert len(answer["text"]) < len(text)
        assert isinstance(json.loads(answer["detail"]), dict)
        assert store.canonical_messages[0]["content"] == text
        assert (transcript.stat().st_size, transcript.stat().st_mtime_ns) == before
    finally:
        store.close()


def test_native_parser_keeps_roles_and_reused_call_ids_accepted_by_foundation(shared):
    """Import-only role/ID policy cannot narrow shared canonical read semantics."""
    launch, cli, identity, _ = shared
    root = cli.base_dir / identity
    messages = [{"role": "developer", "content": "Synthetic provider instruction"}]
    for number in range(2):
        messages.extend(
            [
                {"role": "user", "content": f"Synthetic turn {number}"},
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "reused-call-id",
                            "function": {"name": "synthetic_tool", "arguments": "{}"},
                        }
                    ],
                },
                {"role": "tool", "tool_call_id": "reused-call-id", "content": "Stored result"},
                {"role": "assistant", "content": f"Synthetic answer {number}"},
            ]
        )
    (root / "transcript.jsonl").write_text("".join(json.dumps(row) + "\n" for row in messages))
    history = native_history(launch["cli_home"], launch["cwd"], identity)
    assert history.messages == messages
    assert not history.diagnostics


def test_large_descendant_metadata_does_not_hide_shared_usage(shared):
    from test_shared_usage import ci_logs, receipt

    from amplifier_tui.cli_compat import historical_usage

    launch, cli, identity, _ = shared
    child = identity + "_synthetic-child"
    cli.save(child, [], {"parent_id": identity, "config": {"opaque": "m" * (900 * 1024)}})
    metadata = cli.base_dir / child / "metadata.json"
    assert metadata.stat().st_size > 900 * 1024
    before = metadata.read_bytes()
    ci_logs(cli, identity, [receipt(identity, 0, "0.10")])
    ci_logs(cli, child, [receipt(child, 1, "0.20")])
    rows, partial = historical_usage(launch["cli_home"], launch["cwd"], identity)
    assert {row["usage_session_id"] for row in rows} == {identity, child}
    assert not partial
    assert metadata.read_bytes() == before

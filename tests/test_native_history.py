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
    from amplifier_tui import cli_compat

    launch, _, identity, _ = shared
    opened = []
    original = cli_compat.read_session_file

    def metadata_only(home, cwd, session_id, filename, limit):
        opened.append(filename)
        assert filename in ("metadata.json", "metadata.json.backup")
        return original(home, cwd, session_id, filename, limit)

    monkeypatch.setattr(cli_compat, "read_session_file", metadata_only)
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

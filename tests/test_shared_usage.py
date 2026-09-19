"""Synthetic shared accounting from canonical logs, never a TUI event copy."""

import json
from decimal import Decimal

import pytest
from test_shared_sessions import shared as shared

from amplifier_tui.conversations import SharedConversationStore
from amplifier_tui.events import Event
from amplifier_tui.inspection import CallUsage, Inspection, usage_receipt_id


def receipt(owner, index, cost="0.25", **extra):
    return {
        "event": "llm:response",
        "ts": f"2026-01-01T00:{index // 60:02}:{index % 60:02}+00:00",
        "session_id": owner,
        "duration_ms": 1200,
        "data": {
            "provider": "fixture",
            "model": "fixture-model",
            "usage": {
                "input_tokens": 100,
                "output_tokens": 10,
                "cache_read_tokens": 60,
                "cost_usd": cost,
            },
            **extra,
        },
    }


def logs(cli, owner, records):
    path = cli.base_dir / owner / "events.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in records))
    return path


def ci_logs(cli, owner, records, *, root=None):
    """Use the actual CI envelope/layout, not the CLI logging envelope."""
    directory = cli.base_dir / owner
    if root is not None:
        directory = root / cli.base_dir.parent.name / "sessions" / owner
    path = directory / "context-intelligence" / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(
                {
                    "event": record["event"],
                    "timestamp": record.get("ts"),
                    "data": {
                        **record["data"],
                        "session_id": record["session_id"],
                        "timestamp": record.get("ts"),
                        "duration_ms": record.get("duration_ms"),
                    },
                }
            )
            + "\n"
            for record in records
        )
    )
    return path


def ledger(store):
    return CallUsage(store.activity_events())


def test_resume_derives_current_baseline_without_private_journal(shared, tmp_path):
    launch, cli, identity, messages = shared
    store = SharedConversationStore(tmp_path, launch, identity)
    old_text = "Turn: $0.25 · Session: $0.25 (earlier usage unavailable)"
    old = Event(
        identity,
        len(store.restored_events) + 1,
        "old-turn",
        "display.message",
        "old-total",
        {"source": "usage", "text": old_text},
    )
    store.record(old)
    store.checkpoint(messages, old.sequence, None, True)
    assert any(event.item_id == "old-total" for event in store.activity_events())
    assert not (store.path / "events.jsonl").exists()
    marker = json.loads((store.path / "checkpoint.json").read_text())
    assert marker["status"] == "ready" and "messages" not in marker
    store.close()
    logs(cli, identity, [receipt(identity, 0, "0.25"), receipt(identity, 1, "0.50")])
    canonical = cli.base_dir / identity / "transcript.jsonl"
    original = canonical.read_bytes()
    resumed = SharedConversationStore(tmp_path, launch, identity)
    try:
        before = list(resumed.activity_events())
        first = resumed.projection()
        assert first == resumed.projection()
        assert first[-1]["text"] == "On resume · Session: $0.75"
        # Unlogged UI observations are not another shared history authority.
        assert not any(i["id"] == "old-total" for i in first)
        assert canonical.read_bytes() == original
        assert list(resumed.activity_events()) == before
        assert not (resumed.path / "events.jsonl").exists()
        assert json.loads((resumed.path / "checkpoint.json").read_text()) == marker
        assert ledger(resumed).progress("new-turn")["turn"]["calls"] == 0
    finally:
        resumed.close()


def test_root_nested_utility_receipts_are_read_only_deduplicated_and_session_scoped(
    shared, tmp_path
):
    launch, cli, identity, _ = shared
    child, grandchild, foreign = identity + "_child", identity + "_nested", "unrelated_child"
    cli.save(child, [], {"parent_id": identity})
    cli.save(grandchild, [], {"parent_id": child})
    cli.save(foreign, [], {"parent_id": "unrelated"})
    root = receipt(identity, 0)
    paths = [
        logs(cli, identity, [root, root, receipt(identity, 1, "0.10", purpose="session-naming")]),
        logs(cli, child, [receipt(child, 0, "0.40")]),
        logs(cli, grandchild, [receipt(grandchild, 0, "0.05")]),
        logs(cli, foreign, [receipt(foreign, 0, "100")]),
        cli.base_dir / identity / "transcript.jsonl",
        cli.base_dir / identity / "metadata.json",
    ]
    before = {path: path.read_bytes() for path in paths}
    store = SharedConversationStore(tmp_path, launch, identity)
    count = len(store.restored_events)
    try:
        usage = ledger(store)
        assert usage.session["requests"] == 4
        assert usage.session["totals"]["cost_usd"] == Decimal("0.80")
        assert usage.progress("new-turn")["turn"]["calls"] == 0
        assert not usage.legacy
        tree = Inspection(store.activity_events()).activity_tree("shared:usage")
        assert len(tree["rows"]) == 4
        assert tree["focus"]["label"] == "Earlier session usage"
        assert "4 recorded calls" in tree["focus"]["preview"]
        assert all("Input: 100" in row["preview"] for row in tree["rows"])
        assert all("Cost: $" in row["preview"] for row in tree["rows"])
        assert any("session-naming" in row["detail"] for row in tree["rows"])
        assert not any("Recorded model call" in row["text"] for row in store.projection())
    finally:
        store.close()
    reopened = SharedConversationStore(tmp_path, launch, identity)
    try:
        assert ledger(reopened).session["requests"] == 4
        assert len(reopened.restored_events) == count  # Resume is idempotent.
    finally:
        reopened.close()
    assert all(path.read_bytes() == original for path, original in before.items())


def test_canonical_receipts_replace_unpersisted_native_observations_on_resume(shared, tmp_path):
    launch, cli, identity, messages = shared
    root = receipt(identity, 0)
    logs(cli, identity, [root])
    store = SharedConversationStore(tmp_path, launch, identity)
    data = {**root["data"], "session_id": identity, "timestamp": root["ts"]}
    event = Event(
        identity,
        len(store.restored_events) + 1,
        "native-turn",
        "display.message",
        "native-observation",
        {
            "source": "usage",
            "text": "Native call",
            "usage_call": root["data"]["usage"],
            "usage_receipt_id": usage_receipt_id(data),
            "usage_session_id": identity,
        },
    )
    store.record(event)
    store.checkpoint(messages, event.sequence, None, True)
    store.close()
    # CLI advances history with another distinct response having IDENTICAL values.
    logs(cli, identity, [root, receipt(identity, 1)])
    cli.save(
        identity,
        messages + [{"role": "user", "content": "Next"}, {"role": "assistant", "content": "Again"}],
        cli.get_metadata(identity),
    )
    resumed = SharedConversationStore(tmp_path, launch, identity)
    try:
        usage = ledger(resumed)
        assert usage.session["requests"] == 2
        assert usage.session["totals"]["cost_usd"] == Decimal("0.50")
        assert not usage.legacy
        assert not any(e.item_id == "native-observation" for e in resumed.activity_events())
        assert not (resumed.path / "events.jsonl").exists()
    finally:
        resumed.close()


@pytest.mark.parametrize("damage", ["missing", "corrupt", "symlink", "no-usage", "foreign-owner"])
def test_missing_or_bad_receipts_never_invent_complete_cost(shared, tmp_path, damage):
    launch, cli, identity, _ = shared
    record = receipt(identity, 0)
    if damage == "foreign-owner":
        record["session_id"] = "foreign"
    if damage == "no-usage":
        record["data"]["usage"].pop("cost_usd")
    if damage != "missing":
        path = logs(cli, identity, [record])
        if damage == "corrupt":
            path.write_text('{"truncated":')
        elif damage == "symlink":
            outside = tmp_path / "outside.log"
            outside.write_bytes(path.read_bytes())
            path.unlink()
            path.symlink_to(outside)
    store = SharedConversationStore(tmp_path, launch, identity)
    try:
        usage = ledger(store)
        assert "cost_usd" not in usage.session["totals"]
        assert "not reported" in usage.costs()
        if damage != "no-usage":
            assert usage.legacy
    finally:
        store.close()


def test_unlogged_live_usage_never_becomes_shared_cost_authority(shared, tmp_path):
    launch, cli, identity, messages = shared
    store = SharedConversationStore(tmp_path, launch, identity)
    event = Event(
        identity,
        len(store.restored_events) + 1,
        "old-turn",
        "display.message",
        "unidentified",
        {
            "source": "usage",
            "text": "Unidentified observation",
            "usage_call": {"cost_usd": "0.25"},
        },
    )
    store.record(event)
    store.checkpoint(messages, event.sequence, None, True)
    store.close()
    resumed = SharedConversationStore(tmp_path, launch, identity)
    try:
        usage = ledger(resumed)
        assert "cost_usd" not in usage.session["totals"]
        assert usage.legacy
        assert "not reported" in usage.costs()
        assert not any(e.item_id == "unidentified" for e in resumed.activity_events())
        assert not (resumed.path / "events.jsonl").exists()
    finally:
        resumed.close()


def test_recorded_forks_find_log_only_children_without_guessing_id_prefixes(shared):
    from amplifier_tui.cli_compat import historical_usage

    launch, cli, identity, _ = shared
    child = "independent-child-id"
    (cli.base_dir / child).mkdir()
    fork = {
        "event": "session:fork",
        "session_id": identity,
        "data": {"parent_session_id": identity, "child_session_id": child},
    }
    logs(cli, identity, [receipt(identity, 0), fork])
    path = logs(cli, child, [receipt(child, 1, "0.50")])
    rows, partial = historical_usage(launch["cli_home"], launch["cwd"], identity)
    assert not partial
    assert {r["usage_session_id"] for r in rows} == {identity, child}
    rows, partial = historical_usage(launch["cli_home"], launch["cwd"], identity, file_limit=1)
    assert partial and len(rows) == 1
    path.unlink()
    rows, partial = historical_usage(launch["cli_home"], launch["cwd"], identity)
    assert partial and len(rows) == 1
    fork["data"]["parent_session_id"] = "unrelated"
    logs(cli, identity, [receipt(identity, 0), fork])
    rows, partial = historical_usage(launch["cli_home"], launch["cwd"], identity)
    assert partial and len(rows) == 1


def test_conflicting_receipts_and_capture_bounds_disclose_partial_totals(shared):
    from amplifier_tui.cli_compat import historical_usage

    launch, cli, identity, _ = shared
    logs(cli, identity, [receipt(identity, 0), receipt(identity, 0, "99")])
    rows, partial = historical_usage(launch["cli_home"], launch["cwd"], identity)
    assert partial and len(rows) == 1
    assert rows[0]["usage_call"]["cost_usd"] == "0.25"
    rows, partial = historical_usage(launch["cli_home"], launch["cwd"], identity, byte_limit=16)
    assert partial and not rows


def test_ci_normalization_uses_one_capture_and_retains_kernel_receipt_identity(shared):
    from amplifier_tui.cli_compat import historical_usage

    launch, cli, identity, _ = shared
    record = receipt(identity, 0, request_id="exact-request", span_id="exact-span")
    root = logs(cli, identity, [record, receipt(identity, 1, "9")])
    ci = ci_logs(cli, identity, [record, record])
    before = {path: path.read_bytes() for path in (root, ci)}
    rows, partial = historical_usage(launch["cli_home"], launch["cwd"], identity)
    assert not partial
    assert len(rows) == 1
    assert rows[0]["usage_call"]["cost_usd"] == "0.25"
    assert rows[0]["usage_receipt_id"] == usage_receipt_id(
        {**record["data"], "session_id": identity, "timestamp": record["ts"]}
    )
    assert rows[0]["duration_ms"] == 1200
    assert all(path.read_bytes() == data for path, data in before.items())


def test_relocated_ci_applies_to_explicit_descendants_and_utility_calls(
    shared, tmp_path, monkeypatch
):
    from amplifier_tui.cli_compat import historical_usage

    launch, cli, identity, _ = shared
    child = "recorded-child"
    cli.save(child, [], {"parent_id": identity})
    relocated = tmp_path / "capture-root"
    monkeypatch.setenv("AMPLIFIER_CONTEXT_INTELLIGENCE_BASE_PATH", str(relocated))
    ci_logs(cli, identity, [receipt(identity, 0, "0.10", purpose="session-naming")], root=relocated)
    ci_logs(cli, child, [receipt(child, 1, "0.20")], root=relocated)
    ci_logs(cli, identity, [receipt(identity, 0, "99")])
    logs(cli, identity, [receipt(identity, 0, "999")])
    rows, partial = historical_usage(launch["cli_home"], launch["cwd"], identity)
    assert not partial
    assert {row["usage_session_id"] for row in rows} == {identity, child}
    assert sum(Decimal(row["usage_call"]["cost_usd"]) for row in rows) == Decimal("0.30")
    assert rows[0]["purpose"] == "session-naming"


@pytest.mark.parametrize("root", ["relative-capture", "${UNEXPANDED_CAPTURE_ROOT}", ""])
def test_invalid_ci_relocation_matches_cli_path_policy(shared, monkeypatch, root):
    from amplifier_app_cli.cost_history import session_events_path

    from amplifier_tui.cli_compat import historical_usage

    launch, cli, identity, _ = shared
    monkeypatch.setenv("AMPLIFIER_CONTEXT_INTELLIGENCE_BASE_PATH", root)
    path = ci_logs(cli, identity, [receipt(identity, 0)])
    assert session_events_path(cli.base_dir / identity) == path
    rows, partial = historical_usage(launch["cli_home"], launch["cwd"], identity)
    assert not partial and len(rows) == 1


@pytest.mark.parametrize("damage", ["corrupt", "conflicting-owner", "symlink", "directory-symlink"])
def test_bad_ci_never_silently_falls_back_to_another_capture(shared, tmp_path, damage):
    from amplifier_tui.cli_compat import historical_usage

    launch, cli, identity, _ = shared
    path = ci_logs(cli, identity, [receipt(identity, 0)])
    logs(cli, identity, [receipt(identity, 0, "99")])
    if damage == "corrupt":
        path.write_text('{"incomplete":')
    elif damage == "conflicting-owner":
        record = json.loads(path.read_text())
        record["session_id"] = "another-owner"
        path.write_text(json.dumps(record) + "\n")
    else:
        outside = tmp_path / "outside-capture"
        outside.mkdir()
        target = outside / "events.jsonl"
        target.write_bytes(path.read_bytes())
        path.unlink()
        if damage == "symlink":
            path.symlink_to(target)
        else:
            path.parent.rmdir()
            path.parent.symlink_to(outside, target_is_directory=True)
    rows, partial = historical_usage(launch["cli_home"], launch["cwd"], identity)
    assert partial and not rows


def test_event_scan_is_bounded_by_physical_rows_including_filtered_and_bad_rows(shared):
    from amplifier_tui.cli_compat import historical_usage

    launch, cli, identity, _ = shared
    path = ci_logs(cli, identity, [receipt(identity, 0)])
    good = path.read_text()
    foreign = json.loads(good)
    foreign["data"]["session_id"] = "another-owner"
    path.write_text("\nnot json\n" + json.dumps(foreign) + "\n" + good)
    rows, partial = historical_usage(launch["cli_home"], launch["cwd"], identity, line_limit=3)
    assert partial and not rows
    rows, partial = historical_usage(launch["cli_home"], launch["cwd"], identity, line_limit=4)
    assert partial and len(rows) == 1  # Malformed row remains a disclosed gap.


def test_byte_budget_is_shared_across_descendant_logs_and_preserves_complete_prefix(shared):
    from amplifier_tui.cli_compat import historical_usage

    launch, cli, identity, _ = shared
    child = "bounded-child"
    cli.save(child, [], {"parent_id": identity})
    root = ci_logs(cli, identity, [receipt(identity, 0)])
    ci_logs(cli, child, [receipt(child, 1)])
    rows, partial = historical_usage(
        launch["cli_home"], launch["cwd"], identity, byte_limit=root.stat().st_size + 16
    )
    assert partial
    assert [row["usage_session_id"] for row in rows] == [identity]


def test_ci_symlink_swap_after_open_does_not_change_read_authority(shared, tmp_path, monkeypatch):
    from amplifier_foundation.session import SessionHistoryStore

    from amplifier_tui.cli_compat import historical_usage

    launch, cli, identity, _ = shared
    path = ci_logs(cli, identity, [receipt(identity, 0)])
    outside = tmp_path / "outside-events.jsonl"
    value = json.loads(path.read_text())
    value["data"]["usage"]["cost_usd"] = "99"
    outside.write_text(json.dumps(value) + "\n")
    original = SessionHistoryStore.iter_events

    def swap_before_read(self, **limits):
        path.rename(path.with_name("retained-events.jsonl"))
        path.symlink_to(outside)
        yield from original(self, **limits)

    monkeypatch.setattr(SessionHistoryStore, "iter_events", swap_before_read)
    rows, _ = historical_usage(launch["cli_home"], launch["cwd"], identity)
    assert len(rows) == 1 and rows[0]["usage_call"]["cost_usd"] == "0.25"


def test_ci_activity_uses_exact_shared_associations_without_reordering_messages(shared):
    from amplifier_tui.cli_compat import read_session_activity

    launch, cli, identity, _ = shared
    messages = [
        {"role": "user", "content": "Inspect two fixture files"},
        {
            "role": "assistant",
            "tool_calls": [
                {"id": "first-call", "tool": "read_file", "arguments": {}},
                {"id": "second-call", "tool": "read_file", "arguments": {}},
            ],
        },
        {"role": "tool", "tool_call_id": "first-call", "content": "First result"},
        {"role": "tool", "tool_call_id": "second-call", "content": "Second result"},
    ]
    before = json.dumps(messages)
    records = [
        {"event": "tool:post", "session_id": identity, "data": {"tool_call_id": "second-call"}},
        {"event": "tool:post", "session_id": identity, "data": {"tool_call_id": "first-call"}},
        receipt(identity, 0, purpose="session-naming"),
    ]
    path = ci_logs(cli, identity, records)
    raw = path.read_bytes()
    activity = read_session_activity(launch["cli_home"], launch["cwd"], identity, messages)
    assert not activity["partial"]
    assert [event["session_id"] for event in activity["events"]] == [identity] * 3
    associations = activity["associations"]
    assert [item.message_indices for item in associations] == [(3,), (2,), ()]
    assert associations[0].method == "tool_call_id"
    assert associations[0].turn_message_index == 0
    assert associations[2].auxiliary
    assert json.dumps(messages) == before and path.read_bytes() == raw


def test_ambiguous_or_unscoped_ci_activity_never_invents_message_ownership(shared):
    from amplifier_tui.cli_compat import read_session_activity

    launch, cli, identity, _ = shared
    messages = [
        {"role": "user", "content": "First"},
        {"role": "assistant", "tool_calls": [{"id": "reused", "tool": "read_file"}]},
        {"role": "tool", "tool_call_id": "reused", "content": "First result"},
        {"role": "user", "content": "Second"},
        {"role": "assistant", "tool_calls": [{"id": "reused", "tool": "read_file"}]},
    ]
    path = ci_logs(
        cli,
        identity,
        [{"event": "tool:post", "session_id": identity, "data": {"tool_call_id": "reused"}}],
    )
    raw = json.loads(path.read_text())
    raw["data"].pop("session_id")
    path.write_text(path.read_text() + json.dumps(raw) + "\n")
    activity = read_session_activity(launch["cli_home"], launch["cwd"], identity, messages)
    assert activity["partial"]
    assert "unscoped_event" in activity["diagnostics"]
    assert all(not item.message_indices for item in activity["associations"])


def test_activity_missing_or_bounded_capture_is_a_view_gap_not_a_resume_failure(shared):
    from amplifier_tui.cli_compat import read_session_activity

    launch, cli, identity, messages = shared
    absent = read_session_activity(launch["cli_home"], launch["cwd"], identity, messages)
    assert absent["partial"] and not absent["events"]
    ci_logs(cli, identity, [receipt(identity, 0), receipt(identity, 1)])
    limited = read_session_activity(
        launch["cli_home"], launch["cwd"], identity, messages, line_limit=1
    )
    assert limited["partial"] and len(limited["events"]) == 1
    assert "scan_limit" in limited["diagnostics"]


@pytest.mark.parametrize("field", ["request_id", "span_id", "timestamp"])
def test_conflicting_ci_receipt_identity_is_not_silently_overridden(shared, field):
    from amplifier_tui.cli_compat import historical_usage

    launch, cli, identity, _ = shared
    path = ci_logs(cli, identity, [receipt(identity, 0)])
    record = json.loads(path.read_text())
    record["data"][field] = "nested-identity"
    record[field] = "different-envelope-identity"
    path.write_text(json.dumps(record) + "\n")
    rows, partial = historical_usage(launch["cli_home"], launch["cwd"], identity)
    assert partial and not rows


def test_shared_activity_read_does_not_bootstrap_cli(shared, monkeypatch):
    import builtins

    from amplifier_tui.cli_compat import historical_usage, read_session_activity

    launch, cli, identity, messages = shared
    ci_logs(cli, identity, [receipt(identity, 0)])
    original = builtins.__import__

    def no_cli(name, *args, **kwargs):
        if name == "amplifier_app_cli" or name.startswith("amplifier_app_cli."):
            raise AssertionError("Read-only activity must not initialize CLI policy/keys")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_cli)
    rows, partial = historical_usage(launch["cli_home"], launch["cwd"], identity)
    activity = read_session_activity(launch["cli_home"], launch["cwd"], identity, messages)
    assert len(rows) == 1 and not partial
    assert len(activity["events"]) == 1 and not activity["partial"]


def test_oversized_ci_payload_is_bounded_and_never_treated_as_zero_cost(shared):
    from amplifier_tui.cli_compat import historical_usage

    launch, cli, identity, _ = shared
    path = ci_logs(cli, identity, [receipt(identity, 0)])
    record = json.loads(path.read_text())
    record["data"]["oversized_payload"] = "x" * (4 * 1024 * 1024)
    path.write_text(json.dumps(record) + "\n")
    rows, partial = historical_usage(launch["cli_home"], launch["cwd"], identity)
    assert partial and not rows

"""Synthetic accounting receipts through the actual canonical/sidecar stores."""

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


def ledger(store):
    return CallUsage(store.restored_events)


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
        tree = Inspection.journal_activity(store.path / "events.jsonl", "shared:usage")
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


def test_native_and_cli_observers_join_only_by_kernel_receipt_identity(shared, tmp_path):
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


def test_receipt_without_identity_is_not_guessed_from_equal_amounts(shared, tmp_path):
    launch, cli, identity, messages = shared
    logs(cli, identity, [receipt(identity, 0)])
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
        assert usage.session["totals"]["cost_usd"] == Decimal("0.25")
        assert usage.legacy
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

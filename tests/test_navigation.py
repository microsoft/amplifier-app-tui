import asyncio
import copy
import json
from pathlib import Path

import pytest

from amplifier_tui.conversations import ConversationStore
from amplifier_tui.host import SessionHost
from amplifier_tui.navigation import WorkspaceBridge, file_candidates, session_choices


def test_large_uncertain_checkpoint_offers_recovery_before_opening(tmp_path):
    store = ConversationStore(tmp_path, {"cwd": str(tmp_path)})
    store.checkpoint(
        [{"role": "user", "content": "Synthetic large history " * 5000}], 0, "fixture", False
    )
    store.close()
    choices = session_choices(tmp_path, None, cwd=tmp_path)
    assert choices["sessions"][0]["status"].startswith("recovery required")
    assert choices["sessions"][0]["id"] == store.identity


def test_directory_scope_precedes_paging_and_full_text_search(tmp_path):
    from amplifier_tui.events import Event
    from amplifier_tui.history_index import search

    local, foreign = tmp_path / "local", tmp_path / "foreign"
    identities = []
    for index in range(102):
        store = ConversationStore(tmp_path, {"cwd": str(local)})
        identities.append(store.identity)
        store.record(
            Event(
                store.identity,
                1,
                "turn",
                "turn.accepted",
                "turn",
                {"text": f"Local source {index}"},
            )
        )
        store.record(
            Event(store.identity, 2, "turn", "text.final", "answer", {"text": "Shared needle"})
        )
        store.checkpoint([], 2, {}, True)
        store.close()
    other = ConversationStore(tmp_path, {"cwd": str(foreign)})
    other.record(
        Event(other.identity, 1, "turn", "turn.accepted", "turn", {"text": "Foreign secret needle"})
    )
    other.checkpoint([], 1, {}, True)
    other.close()
    # Seed a global cache first; old indexed matches must not escape directory scope.
    from amplifier_tui.conversations import catalog

    search(tmp_path, catalog(tmp_path), "needle")
    for query in ("", "needle"):
        first = session_choices(tmp_path, None, cwd=local, query=query)
        second = session_choices(tmp_path, None, cwd=local, query=query, offset=100)
        assert len(first["sessions"]) == 100 and first["next_offset"] == 100
        assert len(second["sessions"]) == 2 and second["next_offset"] is None
        assert {r["id"] for r in first["sessions"] + second["sessions"]} == set(identities)
        assert "Foreign secret" not in str(first) + str(second)
    assert not session_choices(tmp_path, None, cwd=local, query="Foreign secret")["sessions"]
    assert not session_choices(tmp_path, None, cwd=tmp_path, query="needle")["sessions"]


async def bridge_for(prepared, state, cwd):
    launch = {"fixture": True, "bundle": None, "overlays": [], "sources": None, "cwd": str(cwd)}
    events = []

    async def open_launch(host, spec):
        await host.open(prepared[0], copy.deepcopy(prepared[1]), Path(spec["cwd"]))

    bridge = WorkspaceBridge(
        SessionHost(),
        lambda host: open_launch(host, launch),
        events.append,
        True,
        cwd,
        lambda: ConversationStore(state, launch),
        state_dir=state,
        open_launch=open_launch,
    )
    await bridge.open()
    await asyncio.sleep(0)
    return bridge, events


async def test_switch_new_and_back_retains_context_and_isolates_stale_requests(prepared, tmp_path):
    bridge, events = await bridge_for(prepared, tmp_path, tmp_path)
    try:
        original = bridge.host.session_id
        assert bridge.command(
            {"op": "submit", "text": "Original remembered question", "session_id": original}
        )[0]
        await bridge.host.task
        assert bridge.command(
            {
                "op": "switch",
                "target": "new",
                "draft": "source correction",
                "request_id": "switch-1",
                "session_id": original,
            }
        )[0]
        await bridge.switch_task
        second = bridge.host.session_id
        assert second != original
        assert bridge.host.session.coordinator.get("providers")["fixture"].calls == []
        assert bridge.host.session.coordinator.get("tools")["fixture_probe"].calls == 0
        assert not bridge.command(
            {"op": "submit", "text": "wrong conversation", "session_id": original}
        )[0]
        assert not bridge.command({"op": "draft", "text": "wrong draft", "session_id": original})[0]
        assert not bridge.command({"op": "submit", "text": "missing identity"})[0]
        assert bridge.command(
            {
                "op": "switch",
                "target": original,
                "draft": "second scratch",
                "request_id": "switch-2",
                "session_id": second,
            }
        )[0]
        await bridge.switch_task
        assert bridge.host.session_id == original
        assert bridge.host.store.draft == "source correction"
        assert bridge.host.session.coordinator.get("providers")["fixture"].calls == []
        assert bridge.command({"op": "submit", "text": "Continue", "session_id": original})[0]
        await bridge.host.task
        provider = bridge.host.session.coordinator.get("providers")["fixture"]
        assert "Original remembered question" in str(provider.calls[0].messages)
        snapshots = [e for e in events if e["type"] == "snapshot"]
        assert len(snapshots) == 3 and snapshots[-1]["reset"] is True
        assert any(i["text"] == "Original remembered question" for i in snapshots[-1]["items"])
    finally:
        await bridge.close()


async def test_failed_target_and_busy_switch_preserve_source(prepared, tmp_path):
    bridge, events = await bridge_for(prepared, tmp_path, tmp_path)
    try:
        source = bridge.host
        assert bridge.command(
            {"op": "switch", "target": "0" * 32, "draft": "keep this", "request_id": "bad"}
        )[0]
        await bridge.switch_task
        assert bridge.host is source and source.ready
        assert source.store.draft == "keep this"
        assert any(e["type"] == "switch_result" and not e["ok"] for e in events)
        source.session.coordinator.get("tools")["fixture_probe"].config["delay"] = 0.1
        source.submit("busy")
        assert not bridge.command(
            {"op": "switch", "target": "new", "draft": "busy correction", "request_id": "busy"}
        )[0]
        await source.task
    finally:
        await bridge.close()


async def test_target_initialization_failure_leaves_current_usable(prepared, tmp_path):
    bridge, _ = await bridge_for(prepared, tmp_path, tmp_path)
    original = bridge.host

    async def fail(target, launch):
        raise ValueError("deliberate test failure")

    bridge.open_launch = fail
    try:
        assert bridge.command(
            {"op": "switch", "target": "new", "draft": "retained", "request_id": "fail"}
        )[0]
        await bridge.switch_task
        assert bridge.host is original and original.ready
        assert original.store.draft == "retained"
        assert original.submit("still usable")[0]
        await original.task
    finally:
        await bridge.close()


@pytest.mark.parametrize("during_open", [False, True])
async def test_cancel_opening_keeps_source_and_releases_candidate(prepared, tmp_path, during_open):
    bridge, events = await bridge_for(prepared, tmp_path, tmp_path)
    source = bridge.host
    entered = asyncio.Event()
    candidates = []

    async def delayed(target, launch):
        candidates.append(target)
        entered.set()
        await asyncio.Event().wait()

    bridge.open_launch = delayed
    try:
        assert bridge.command(
            {
                "op": "switch",
                "target": "new",
                "draft": "saved before opening",
                "request_id": "cancel",
            }
        )[0]
        if during_open:
            await asyncio.wait_for(entered.wait(), 2)
        assert bridge.command({"op": "cancel_switch"})[0]
        await asyncio.gather(bridge.switch_task, return_exceptions=True)
        await asyncio.sleep(0)
        assert bridge.host is source and source.ready
        assert source.store.draft == "saved before opening"
        assert all(target.store.lock is None for target in candidates)
        assert any(e["type"] == "switch_result" and not e["ok"] for e in events)
    finally:
        await bridge.close()


def test_path_names_are_bounded_quoted_and_confined(tmp_path):
    (tmp_path / "docs space").mkdir()
    (tmp_path / "docs space" / "résumé.md").touch()
    (tmp_path / ".hidden").touch()
    (tmp_path / "control\x85name").touch()
    (tmp_path / "escape").symlink_to(tmp_path.parent, target_is_directory=True)
    assert file_candidates(tmp_path, "./do")["candidates"] == ['"./docs space/"']
    assert file_candidates(tmp_path, "./docs space/r")["candidates"] == ['"./docs space/résumé.md"']
    assert "./.hidden" not in file_candidates(tmp_path, "./")["candidates"]
    assert file_candidates(tmp_path, "./.")["candidates"] == ["./.hidden"]
    assert not file_candidates(tmp_path, "./esc")["candidates"]
    assert not file_candidates(tmp_path, "./control")["candidates"]
    for query in ("../", "./../", "./escape/", "/etc/", "~/"):
        with pytest.raises(ValueError):
            file_candidates(tmp_path, query)
    for index in range(90):
        (tmp_path / f"file-{index:03}").touch()
    result = file_candidates(tmp_path, "./file-")
    assert len(result["candidates"]) == 80 and result["truncated"]


async def test_catalog_titles_and_correlated_lookup(prepared, tmp_path):
    bridge, events = await bridge_for(prepared, tmp_path, tmp_path)
    try:
        bridge.host.submit("Find the meaningful conversation")
        await bridge.host.task
        rows = session_choices(tmp_path, bridge.host.session_id)["sessions"]
        assert rows[0]["title"] == "Find the meaningful conversation"
        assert rows[0]["status"] == "current"
        assert bridge.command({"op": "conversations", "request_id": "lookup"})[0]
        await bridge.lookup_task
        assert events[-1]["request_id"] == "lookup"
        assert events[-1]["session_id"] == bridge.host.session_id
        assert events[-1]["sessions"] == rows
        # Discovery never causes a new model request.
        assert len(bridge.host.session.coordinator.get("providers")["fixture"].calls) == 2
        assert (
            json.loads((bridge.host.store.path / "metadata.json").read_text())["title"]
            == rows[0]["title"]
        )
    finally:
        await bridge.close()


@pytest.mark.parametrize("recover", [False, True])
async def test_foreign_directory_switch_cannot_retarget_or_recover(prepared, tmp_path, recover):
    other = tmp_path / "other-workspace"
    other.mkdir()
    (other / "only-in-target.txt").touch()
    target, _ = await bridge_for(prepared, tmp_path, other)
    identity = target.host.session_id
    await target.close()
    source, events = await bridge_for(prepared, tmp_path, tmp_path)
    try:
        original = source.host
        before = {p: p.read_bytes() for p in target.host.store.path.iterdir() if p.is_file()}
        count = len(list((tmp_path / "conversations").iterdir()))
        assert source.command(
            {
                "op": "switch",
                "target": identity,
                "draft": "source",
                "request_id": "cwd",
                "recover": recover,
            }
        )[0]
        await source.switch_task
        assert source.host is original and source.cwd == tmp_path
        assert source.host.store.draft == "source"
        assert len(list((tmp_path / "conversations").iterdir())) == count
        assert all(p.read_bytes() == data for p, data in before.items())
        assert any(e["type"] == "switch_result" and not e["ok"] for e in events)
        assert any("not found in this working directory" in str(e) for e in events)
        assert source.command(
            {
                "op": "complete_path",
                "query": "./only",
                "request_id": "names",
                "session_id": original.session_id,
            }
        )[0]
        await source.lookup_task
        assert events[-1]["candidates"] == []
        assert source.command({"op": "conversations", "request_id": "local"})[0]
        await source.lookup_task
        assert [row["id"] for row in events[-1]["sessions"]] == [original.session_id]
        assert "Launch directory only" in events[-1]["scope"]
        assert source.host.session.coordinator.get("providers")["fixture"].calls == []
    finally:
        await source.close()

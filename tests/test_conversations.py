import asyncio
import json
import stat

import pytest

from amplifier_tui.conversations import ConversationStore, catalog, resolve_resume
from amplifier_tui.host import SessionHost


def test_catalog_scope_is_exact_resolved_directory_and_filters_invalid_metadata(tmp_path):
    state = tmp_path / "state"
    work = tmp_path / "work"
    work.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(work, target_is_directory=True)
    saved = []
    for cwd in (
        work,
        alias,
        tmp_path,
        work / "child",
        tmp_path / "sibling",
        "relative",
        "",
        None,
        42,
    ):
        store = ConversationStore(state, {"cwd": str(cwd) if hasattr(cwd, "resolve") else cwd})
        saved.append(store.identity)
        store.close()
    assert {r["id"] for r in catalog(state, cwd=work)} == set(saved[:2])
    assert catalog(state, cwd=alias) == catalog(state, cwd=work)
    assert resolve_resume(state, "latest", cwd=work)["id"] == saved[1]
    assert len(catalog(state)) == len(saved)  # Global export/inspection still owns its catalog.
    for identity in (saved[2], saved[3], saved[4], "latest"):
        with pytest.raises(ValueError, match="this working directory"):
            resolve_resume(state, identity, cwd=tmp_path / "empty")
    with pytest.raises(ValueError, match="this working directory"):
        resolve_resume(state, saved[3], cwd=work)


async def complete(host, prompt):
    assert host.submit(prompt)[0]
    await host.task
    assert host.outcome == "success"


async def test_resume_restores_context_draft_identity_without_reexecution(prepared, tmp_path):
    launch = {"cwd": str(tmp_path), "bundle": "fixture"}
    first = ConversationStore(tmp_path, launch)
    host = SessionHost(first)
    await host.open(*prepared, tmp_path)
    await complete(host, "Remember violet-lantern-739; compute a digest")
    first.save_draft("unfinished\ncorrection")
    original = await host.session.coordinator.get("context").get_messages()
    identity = host.session_id
    await host.close()

    restored = ConversationStore(tmp_path, launch, identity)
    assert restored.draft == "unfinished\ncorrection"
    assert any(
        item["kind"] == "tool" and item["status"] == "succeeded" for item in restored.projection()
    )
    second = SessionHost(restored)
    try:
        await second.open(*prepared, tmp_path)
        assert second.session_id == identity
        provider = second.session.coordinator.get("providers")["fixture"]
        tool = second.session.coordinator.get("tools")["fixture_probe"]
        assert provider.calls == []
        assert tool.calls == 0
        assert await second.session.coordinator.get("context").get_messages() == original
        await complete(second, "What did I ask previously?")
        assert "violet-lantern-739" in str(provider.calls[0].messages)
        assert tool.calls == 1
        assert resolve_resume(tmp_path, "latest")["id"] == identity
    finally:
        await second.close()
    assert len(catalog(tmp_path)) == 1
    for name in ("metadata.json", "checkpoint.json", "events.jsonl", "draft.json", "lock"):
        assert stat.S_IMODE((first.path / name).stat().st_mode) == 0o600


async def test_drained_tool_interruption_resumes_without_replay(prepared, tmp_path):
    store = ConversationStore(tmp_path, {})
    host = SessionHost(store)
    await host.open(*prepared, tmp_path)
    tool = host.session.coordinator.get("tools")["fixture_probe"]
    tool.config["delay"] = 10
    host.submit("Slow tool")
    async with asyncio.timeout(5):
        while not tool.calls:
            await asyncio.sleep(0.01)
    await host.close()
    assert tool.calls == 1
    restored = SessionHost(ConversationStore(tmp_path, {}, store.identity))
    try:
        await restored.open(*prepared, tmp_path)
        assert restored.ready
        assert restored.session.coordinator.get("tools")["fixture_probe"].calls == 0
        assert not restored.session.coordinator.get("providers")["fixture"].calls
    finally:
        await restored.close()


async def test_interrupted_unpaired_context_still_refuses_resume(prepared, tmp_path, monkeypatch):
    store = ConversationStore(tmp_path, {})
    host = SessionHost(store)
    await host.open(*prepared, tmp_path)
    provider = host.session.coordinator.get("providers")["fixture"]
    entered = asyncio.Event()

    async def incomplete(request, **kwargs):
        await host.session.coordinator.get("context").add_message(
            {"role": "assistant", "content": "", "tool_calls": [{"id": "unresolved-fixture"}]}
        )
        entered.set()
        await asyncio.Future()

    monkeypatch.setattr(provider, "complete", incomplete)
    try:
        assert host.submit("Controlled incomplete context")[0]
        await asyncio.wait_for(entered.wait(), 5)
        await asyncio.wait_for(host.close(), 5)
        assert json.loads((store.path / "checkpoint.json").read_text())["status"] == "uncertain"
        with pytest.raises(ValueError, match="uncertain/incomplete"):
            ConversationStore(tmp_path, {}, store.identity)
    finally:
        await host.close()


async def test_journal_ahead_of_checkpoint_and_changed_composition_fail_closed(prepared, tmp_path):
    store = ConversationStore(tmp_path, {"cwd": "original"})
    host = SessionHost(store)
    await host.open(*prepared, tmp_path)
    await complete(host, "one")
    await host.close()
    with pytest.raises(ValueError, match="composition or working directory"):
        ConversationStore(tmp_path, {"cwd": "changed"}, store.identity)
    checkpoint = json.loads((store.path / "checkpoint.json").read_text())
    checkpoint["sequence"] -= 1
    from amplifier_tui.conversations import atomic_json

    atomic_json(store.path / "checkpoint.json", checkpoint)
    with pytest.raises(ValueError, match="differs from its checkpoint"):
        ConversationStore(tmp_path, {"cwd": "original"}, store.identity)


async def test_lock_and_effective_configuration_guard(prepared, tmp_path):
    store = ConversationStore(tmp_path, {})
    host = SessionHost(store)
    await host.open(*prepared, tmp_path)
    with pytest.raises(BlockingIOError):
        ConversationStore(tmp_path, {}, store.identity)
    await host.close()
    prepared[0].mount_plan["tools"][0]["config"]["different"] = True
    restored = SessionHost(ConversationStore(tmp_path, {}, store.identity))
    try:
        with pytest.raises(ValueError, match="configuration changed"):
            await restored.open(*prepared, tmp_path)
        assert restored.session is None
    finally:
        await restored.close()


def test_invalid_identity_cannot_escape_state_directory(tmp_path):
    with pytest.raises(ValueError, match="Invalid conversation"):
        ConversationStore(tmp_path, {}, "../../outside")


@pytest.mark.parametrize("mutation", ["empty", "missing", "duplicate", "truncated"])
async def test_corrupt_journal_never_reopens_as_empty_history(prepared, tmp_path, mutation):
    store = ConversationStore(tmp_path, {})
    host = SessionHost(store)
    await host.open(*prepared, tmp_path)
    await complete(host, "must retain this")
    await host.close()
    path = store.path / "events.jsonl"
    lines = path.read_text().splitlines()
    damaged = {
        "empty": "",
        "missing": "\n".join(lines[1:]),
        "duplicate": "\n".join([lines[0], *lines]),
        "truncated": "\n".join(lines)[:-10],
    }[mutation]
    path.write_text(damaged)
    with pytest.raises(ValueError):
        ConversationStore(tmp_path, {}, store.identity)


def test_local_bundle_references_survive_a_changed_launch_directory(tmp_path, monkeypatch):
    from amplifier_tui.__main__ import reference

    bundle = tmp_path / "bundle.yaml"
    bundle.write_text("bundle: {name: example}\n")
    monkeypatch.chdir(tmp_path)
    assert reference("bundle.yaml") == str(bundle)
    assert (
        reference("git+https://example.test/bundle@main") == "git+https://example.test/bundle@main"
    )


def test_autosave_does_not_exhaust_execution_admission():
    from amplifier_tui.frontend_bridge import Admission

    admission = Admission()
    for index in range(5000):
        assert admission.apply(
            {"version": 1, "request_id": str(index), "op": "draft", "text": "draft"},
            lambda request: (True, "saved"),
        )["accepted"]
    assert not admission.replies


async def test_loop_durable_checkpoint_supports_private_fixture_store(prepared, tmp_path, monkeypatch):
    store = ConversationStore(tmp_path, {"cwd": str(tmp_path), "bundle": "fixture"})
    host = SessionHost(store)
    await host.open(*prepared, tmp_path)
    try:
        context = host.session.coordinator.get("context")
        await context.add_message({"role": "user", "content": "Checkpoint fixture"})
        checkpoint = host.session.coordinator.get_capability("session.durable_checkpoint")
        await checkpoint()
        saved = json.loads((store.path / "checkpoint.json").read_text())
        assert saved["messages"] == await context.get_messages()
        assert saved["status"] == "uncertain"  # Mid-turn durability is not resumability.
        def fail(*args):
            raise OSError("fixture write failure")
        monkeypatch.setattr(store, "checkpoint", fail)
        with pytest.raises(OSError, match="fixture write failure"):
            await checkpoint()
    finally:
        await host.close()
    with pytest.raises(RuntimeError, match="no longer active"):
        store.check_open()

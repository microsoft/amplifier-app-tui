"""Replacement backlog regressions: real sessions and read-only local discovery."""

import asyncio
import copy
import json

import pytest
from test_navigation import bridge_for

from amplifier_tui.composition import create_owned_session
from amplifier_tui.conversations import ConversationStore, atomic_json
from amplifier_tui.followups import Followups
from amplifier_tui.host import SessionHost
from amplifier_tui.navigation import session_choices


def test_startup_picker_pages_without_starting_work(monkeypatch):
    import curses

    from amplifier_tui.resume_picker import picker

    def page(offset):
        return {
            "offset": offset,
            "next_offset": 100 if offset == 0 else None,
            "sessions": [
                {"id": str(offset), "title": "Saved", "cwd": "fixture", "status": "saved"}
            ],
        }

    class Screen:
        keys = iter([curses.KEY_NPAGE, curses.KEY_PPAGE, curses.KEY_NPAGE, "\n"])

        def keypad(self, _):
            pass

        def erase(self):
            pass

        def refresh(self):
            pass

        def getmaxyx(self):
            return 30, 120

        def addnstr(self, *_):
            pass

        def get_wch(self):
            return next(self.keys)

    monkeypatch.setattr(curses, "curs_set", lambda _: None)
    loads = []

    def load(offset):
        loads.append(offset)
        return page(offset)

    assert picker(Screen(), page(0), load) == ("100", False)
    assert loads == [100, 0, 100]


@pytest.mark.parametrize("routed", [False, True])
async def test_nested_child_restore_requires_live_ancestor_and_preserves_routing(
    prepared, tmp_path, routed
):
    from amplifier_foundation import ProviderPreference

    value, report = prepared
    value.bundle.providers[0].setdefault("config", {})["delay"] = 0.2
    value.mount_plan["providers"][0].setdefault("config", {})["delay"] = 0.2
    store = ConversationStore(tmp_path / "state", {})
    host = SessionHost(store)
    preferences = (
        [ProviderPreference(provider="fixture", model="fixture-explicit", config={"delay": 0.01})]
        if routed
        else None
    )

    async def live_parent(owner, task):
        for _ in range(500):
            if owner.children.active and all(owner.children.active.values()):
                return next(iter(owner.children.active.values()))
            if task.done():
                await task
                pytest.fail("Parent finished before nested continuation")
            await asyncio.sleep(0.002)
        pytest.fail("Parent did not mount")

    await host.open(value, report, tmp_path)
    outer = asyncio.create_task(host.children.spawn("self", "Parent", host.session, {}))
    try:
        parent = await live_parent(host, outer)
        child = await host.children.spawn(
            "self", "Nested", parent, {}, provider_preferences=preferences
        )
        ancestor = await outer
        child_id = child["session_id"]
        prior = copy.deepcopy(host.children.records[child_id]["messages"])
        assert host.submit("Save root")[0]
        await host.task
    finally:
        await asyncio.gather(outer, return_exceptions=True)
        await host.close()
    restored = SessionHost(ConversationStore(tmp_path / "state", {}, store.identity))
    await restored.open(value, report, tmp_path)
    try:
        with pytest.raises(ValueError, match="parent"):
            await restored.children.resume(child_id, "Do not start ancestors")
        assert not restored.children.records
        outer = asyncio.create_task(
            restored.children.resume(ancestor["session_id"], "Parent continued explicitly")
        )
        await live_parent(restored, outer)
        result = await restored.children.resume(child_id, "Nested continued explicitly")
        assert result["session_id"] == child_id
        row = restored.children.records[child_id]
        assert row["messages"][: len(prior)] == prior
        assert row["routing"] == [p.to_dict() for p in preferences or []]
        assert row["status"] == "completed"
        await outer
    finally:
        await asyncio.gather(outer, return_exceptions=True)
        await restored.close()


@pytest.mark.parametrize("cancel", [False, True])
async def test_owned_factory_cleans_acquired_real_session_on_failed_startup(
    prepared, tmp_path, monkeypatch, cancel
):
    import amplifier_core

    constructor = amplifier_core.AmplifierSession
    acquired, cleaned = [], []
    mounted = asyncio.Event()

    class FaultAfterMount:
        def __init__(self, *args, **kwargs):
            self.inner = constructor(*args, **kwargs)
            self.coordinator = self.inner.coordinator
            acquired.append(self)

        async def initialize(self):
            await self.inner.initialize()
            mounted.set()
            if cancel:
                await asyncio.Future()
            raise RuntimeError("Injected failure after actual mounts")

        async def cleanup(self):
            await self.inner.cleanup()
            cleaned.append(self)

    monkeypatch.setattr(amplifier_core, "AmplifierSession", FaultAfterMount)
    plan = copy.deepcopy(prepared[0].mount_plan)
    task = asyncio.create_task(create_owned_session(prepared[0], session_cwd=tmp_path))
    await asyncio.wait_for(mounted.wait(), 5)
    if cancel:
        task.cancel()
    with pytest.raises(asyncio.CancelledError if cancel else RuntimeError):
        await task
    assert cleaned == acquired and len(cleaned) == 1
    assert prepared[0].mount_plan == plan


async def test_owned_factory_matches_foundation_prompt_and_public_capabilities(prepared, tmp_path):
    bundle = prepared[0]
    (tmp_path / "instructions.md").write_text("Unique instruction source")
    bundle.bundle.instruction = "Read @instructions.md"
    original = await bundle.create_session(session_cwd=tmp_path)
    owned = await create_owned_session(bundle, session_cwd=tmp_path)
    try:
        assert (
            await bundle.create_system_prompt_factory(original, session_cwd=tmp_path)()
            == await bundle.create_system_prompt_factory(owned, session_cwd=tmp_path)()
        )
        for name in (
            "session.working_dir",
            "mention_resolver",
            "mention_deduplicator",
            "hook_metadata",
        ):
            assert owned.coordinator.get_capability(name) is not None
        assert sorted(owned.coordinator.get("tools")) == sorted(original.coordinator.get("tools"))
    finally:
        await original.cleanup()
        await owned.cleanup()


async def test_instruction_sources_are_observed_without_inspection_execution(prepared, tmp_path):
    (tmp_path / "instructions.md").write_text("Unique instruction source")
    prepared[0].bundle.instruction = "Read @instructions.md"
    host = SessionHost()
    try:
        await host.open(*prepared, tmp_path)
        assert host.submit("Compute")[0]
        await host.task
        calls = len(host.session.coordinator.get("providers")["fixture"].calls)
        rows = host.inspection.catalog(host, "instructions")
        assert any("instructions.md" in row["detail"] for row in rows["rows"])
        assert "not the complete current provider request" in rows["context_note"]
        assert len(host.session.coordinator.get("providers")["fixture"].calls) == calls
    finally:
        await host.close()


def test_saved_content_search_pages_and_preserves_source(tmp_path):
    ids = []
    for index in range(105):
        store = ConversationStore(tmp_path, {"cwd": str(tmp_path)})
        ids.append(store.identity)
        atomic_json(store.path / "checkpoint.json", {"status": "ready"})
        # The catalog is non-executing; fixture journal deliberately lacks canonical context.
        from amplifier_tui.events import Event

        store.record(
            Event(store.identity, 1, "t", "text.final", "reply", {"text": f"needle number {index}"})
        )
        store.close()
    first = session_choices(tmp_path, None, query="needle")
    second = session_choices(tmp_path, None, offset=100, query="needle")
    assert len(first["sessions"]) == 100 and len(second["sessions"]) == 5
    assert first["next_offset"] == 100 and second["next_offset"] is None
    assert set(r["id"] for r in first["sessions"]).isdisjoint(r["id"] for r in second["sessions"])
    assert all("excerpt" in r["match"] for r in first["sessions"])
    assert not session_choices(tmp_path, None, query="absent")["sessions"]
    assert session_choices(tmp_path, None, query="absent")["next_offset"] == 100
    with pytest.raises(ValueError):
        session_choices(tmp_path, None, offset=-1)


async def test_uncertain_followup_resolution_never_retries_and_reopens_paused(prepared, tmp_path):
    bridge, _ = await bridge_for(prepared, tmp_path, tmp_path)
    try:
        row = {"id": "uncertain", "text": "Do not retry me", "state": "dispatched"}
        bridge.followups.save([row])
        request = {"op": "queue_resolve", "id": row["id"], "session_id": bridge.host.session_id}
        assert not bridge.command(request)[0]
        assert bridge.command({**request, "acknowledge_unknown": True})[0]
        assert bridge.followups.paused
        assert bridge.followups.rows[0]["text"] == row["text"]
        assert bridge.followups.rows[0]["state"] == "dismissed"
        restored = Followups(bridge.host, lambda _: None)
        assert restored.paused and restored.rows == bridge.followups.rows
        assert bridge.command({"op": "queue", "text": "Only this new task"})[0]
        assert bridge.command({"op": "queue_run"})[0]
        await bridge.host.task
        accepted = [
            json.loads(line)["payload"]["text"]
            for line in (bridge.host.store.path / "events.jsonl").read_text().splitlines()
            if json.loads(line)["kind"] == "turn.accepted"
        ]
        assert accepted == ["Only this new task"]
    finally:
        await bridge.close()


def test_provider_setup_never_reads_keys_or_overwrites(tmp_path, monkeypatch, capsys):
    import sys

    from amplifier_tui.onboarding import setup_provider

    monkeypatch.setenv("ANTHROPIC_API_KEY", "private-credential-sentinel")
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    path = tmp_path / "provider.yaml"
    answers = iter(["anthropic", "chosen-model", str(path), "y"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    setup_provider()
    raw = path.read_text()
    assert "${ANTHROPIC_API_KEY}" in raw and "chosen-model" in raw
    assert "private-credential-sentinel" not in raw + capsys.readouterr().out
    assert path.stat().st_mode & 0o777 == 0o600
    answers = iter(["anthropic", "another-model", str(path)])
    with pytest.raises(ValueError, match="new file"):
        setup_provider()
    assert path.read_text() == raw


async def test_image_snapshot_preserves_bytes_and_never_replays(prepared, tmp_path):
    from PIL import Image

    from amplifier_tui.file_input import ImageDraft

    image_path = tmp_path / "image.png"
    Image.new("RGB", (32, 32), "red").save(image_path)
    original = image_path.read_bytes()
    bridge, events = await bridge_for(prepared, tmp_path / "state", tmp_path)
    identity = bridge.host.session_id
    launch = bridge.host.store.metadata["launch"]
    try:
        request = {
            "op": "image_snapshot",
            "path": "image.png",
            "request_id": "image",
            "session_id": identity,
        }
        assert bridge.command(request)[0]
        await bridge.lookup_task
        assert "error" in events[-1]  # A text-only provider cannot silently accept media.
        provider = bridge.host.session.coordinator.get("providers")["fixture"]
        provider.config["capabilities"] = ["vision"]  # Transport fixture, not visual AI evidence.
        assert bridge.command(request)[0]
        await bridge.lookup_task
        result = events[-1]
        assert result["type"] == "image_snapshot" and "data" not in result
        image_path.write_bytes(b"changed after capture")
        assert bridge.command({"op": "image_select", "id": result["id"], "session_id": identity})[0]
        assert bridge.followups.paused
        restored = ImageDraft(bridge.host.store)
        assert restored.value["state"] == "attached"
        assert not bridge.command({"op": "queue", "text": "do not lose image"})[0]
        assert not bridge.command({"op": "submit", "text": "missing image identity"})[0]
        assert bridge.command(
            {"op": "submit", "text": "Describe attached image", "image_id": result["id"]}
        )[0]
        await bridge.host.task
        import base64

        messages = provider.calls[0].model_dump()["messages"]
        blocks = [
            block
            for message in messages
            if isinstance(message["content"], list)
            for block in message["content"]
        ]
        image = next(block for block in blocks if block["type"] == "image")
        assert base64.b64decode(image["source"]["data"]) == original
        assert ImageDraft(bridge.host.store).value["state"] == "dispatched"
        assert not bridge.command({"op": "submit", "text": "No repeat", "image_id": result["id"]})[
            0
        ]
    finally:
        await bridge.close()
    resumed = SessionHost(ConversationStore(tmp_path / "state", launch, identity))
    try:
        await resumed.open(*prepared, tmp_path)
        assert not resumed.session.coordinator.get("providers")["fixture"].calls
        assert resumed.images.public()["state"] == "dispatched"
    finally:
        await resumed.close()


async def test_explicit_model_discovery_is_bounded_advisory_and_redacts_errors(prepared, tmp_path):
    from types import SimpleNamespace

    bridge, events = await bridge_for(prepared, tmp_path / "state", tmp_path)
    try:
        provider = bridge.host.session.coordinator.get("providers")["fixture"]
        before = copy.deepcopy(bridge.host.controls.state)

        async def models():
            return [SimpleNamespace(id=f"model-{i}") for i in range(200)]

        provider.list_models = models
        request = {
            "op": "discover_models",
            "request_id": "catalog",
            "session_id": bridge.host.session_id,
        }
        assert bridge.command(request)[0]
        await bridge.lookup_task
        result = events[-1]
        assert result["type"] == "model_catalog" and result["partial"]
        assert len(result["rows"]) == 128 and result["rows"][0]["model"] == "model-0"
        assert bridge.host.controls.state == before and not provider.calls

        async def failure():
            raise RuntimeError("private-credential-sentinel")

        provider.list_models = failure
        assert bridge.command(request)[0]
        await bridge.lookup_task
        assert "private-credential-sentinel" not in json.dumps(events[-1])
        assert events[-1]["rows"][0]["status"] == "unavailable (RuntimeError)"
        assert bridge.host.controls.state == before and not provider.calls
    finally:
        await bridge.close()


def test_native_wheel_target_does_not_inherit_universal_python_tag(monkeypatch):
    import runpy
    import sys
    import types
    from pathlib import Path

    # Only the build framework interface is stubbed; the actual wheel hook is
    # also executed by the isolated local build and the four-platform CI gate.
    interface = types.ModuleType("hatchling.builders.hooks.plugin.interface")
    interface.BuildHookInterface = object
    monkeypatch.setitem(sys.modules, interface.__name__, interface)
    target = runpy.run_path(str(Path(__file__).resolve().parents[1] / "hatch_build.py"))[
        "wheel_target"
    ]
    assert target("darwin", "arm64", "14.8.1") == (
        "macosx_14_0_arm64",
        {"MACOSX_DEPLOYMENT_TARGET": "14.0"},
    )
    assert target("darwin", "x86_64", "15.7.1") == (
        "macosx_15_0_x86_64",
        {"MACOSX_DEPLOYMENT_TARGET": "15.0"},
    )
    assert target("linux", "aarch64", "") == ("linux_aarch64", {})
    with pytest.raises(RuntimeError, match="support"):
        target("darwin", "universal2", "15.7.1")


def test_release_privacy_guard_rejects_paths_credentials_and_runtime_identity(monkeypatch):
    import runpy
    from pathlib import Path

    verify = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/release_wheel.py"))[
        "verify_payload"
    ]
    token = "controlled-release-secret-12345"
    monkeypatch.setenv("TUI_TEST_API_KEY", token)
    for data in (
        b"/home/example/.cargo/src",
        b"/Users/example/code",
        b"https://name:password@example.test",
        token.encode(),
        str(Path.home()).encode(),
    ):
        with pytest.raises(RuntimeError, match="artifact withheld") as exc:
            verify(data)
        assert token not in str(exc.value)
    verify(b"/cargo/registry/src; /source/frontends; public GitHub source provenance")


async def test_switch_finishes_history_lookup_before_exposing_ready_target(
    prepared, tmp_path, monkeypatch
):
    import threading

    from amplifier_tui import input_history

    bridge, events = await bridge_for(prepared, tmp_path / "state", tmp_path)
    identity = bridge.host.session_id
    original = input_history.recall
    entered, release = threading.Event(), threading.Event()

    def delayed(*args):
        entered.set()
        assert release.wait(5)
        return original(*args)

    monkeypatch.setattr(input_history, "recall", delayed)
    try:
        assert bridge.command(
            {"op": "switch", "target": "new", "draft": "preserve", "request_id": "switch"}
        )[0]
        async with asyncio.timeout(5):
            while not entered.is_set():
                await asyncio.sleep(0.005)
        assert bridge.host.session_id == identity
        assert not any(e["type"] == "snapshot" and e.get("reset") for e in events)
        release.set()
        await bridge.switch_task
        assert bridge.host.session_id != identity
        assert any(e["type"] == "switch_result" and e["ok"] for e in events)
    finally:
        release.set()
        await bridge.close()

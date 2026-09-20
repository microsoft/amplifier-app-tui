"""Real locks/sockets and TUI mounts; CLI/Unified adapters use synthetic sessions."""

import asyncio
import copy
import uuid
from pathlib import Path

import pytest
from amplifier_foundation.session import (
    CannotRelease,
    ReadyToRelease,
    SessionBusyError,
    SharedSessionStore,
    register_release_handler,
    request_release,
)
from test_shared_ownership import native as native

from amplifier_tui.conversations import SharedConversationStore, portable_history
from amplifier_tui.frontend_bridge import Admission
from amplifier_tui.host import SessionHost
from amplifier_tui.navigation import WorkspaceBridge


async def bridge_for(native, prepared, tmp_path):
    launch, identity, _, _ = native
    events = []

    async def open_launch(host, spec):
        await host.open(prepared[0], copy.deepcopy(prepared[1]), Path(spec["cwd"]))

    bridge = WorkspaceBridge(
        SessionHost(),
        lambda host: open_launch(host, launch),
        events.append,
        False,
        Path(launch["cwd"]),
        lambda: SharedConversationStore(tmp_path, launch, identity),
        state_dir=tmp_path,
        open_launch=open_launch,
    )
    await bridge.open()
    return bridge, events


def control(bridge, op, **values):
    return dict(
        version=1, request_id=uuid.uuid4().hex, session_id=bridge.host.session_id, op=op, **values
    )


def bytes_of(history):
    return [
        (p.read_bytes(), p.stat().st_mtime_ns)
        for p in (history.transcript_path, history.metadata_path)
    ]


async def idle_clock(bridge):
    bridge.parking.cancel()
    await asyncio.gather(bridge.parking, return_exceptions=True)
    now = [0.0]
    bridge._idle_clock = lambda: now[0]
    bridge.last_interaction = 0.0
    return now


async def test_five_minutes_without_work_or_input_before_parking(native, prepared, tmp_path):
    bridge, _ = await bridge_for(native, prepared, tmp_path)
    now = await idle_clock(bridge)
    before = bytes_of(native[2])
    try:
        assert bridge.idle_seconds == 300
        now[0] = 299
        assert not await bridge.idle_tick()
        bridge.user_activity(control(bridge, "user_activity"))
        assert bridge.last_interaction == 299
        now[0] = 598.99
        assert not await bridge.idle_tick()
        # Background snapshot polling is not user input.
        await bridge.dispatch(control(bridge, "inspect", id="missing"))
        assert bridge.last_interaction == 299
        assert not bridge.host.session.coordinator.get("providers")["fixture"].calls
        now[0] = 599
        assert await bridge.idle_tick()
        assert bridge.ownership_status == "parked"
        bridge.user_activity(control(bridge, "user_activity"))
        assert bridge.ownership_status == "parked" and bridge.host.session is None
        assert bytes_of(native[2]) == before
    finally:
        await bridge.close()


@pytest.mark.parametrize(
    "invalid", [{"session_id": "other"}, {"version": 2}, {"external_editor": "yes"}]
)
async def test_stale_or_malformed_activity_cannot_renew_idle(native, prepared, tmp_path, invalid):
    bridge, _ = await bridge_for(native, prepared, tmp_path)
    now = await idle_clock(bridge)
    try:
        now[0] = 299
        bridge.user_activity({**control(bridge, "user_activity"), **invalid})
        assert bridge.last_interaction == 0 and not bridge.external_editor
        now[0] = 300
        assert await bridge.idle_tick()
    finally:
        await bridge.close()


async def test_work_and_changed_drafts_restart_the_full_idle_interval(native, prepared, tmp_path):
    bridge, _ = await bridge_for(native, prepared, tmp_path)
    now = await idle_clock(bridge)
    try:
        bridge.host.validation_active = True
        now[0] = 600
        assert not await bridge.idle_tick()
        bridge.host.validation_active = False
        now[0] = 650
        assert not await bridge.idle_tick()  # Settling starts a fresh five minutes.
        now[0] = 900
        assert (await bridge.dispatch(control(bridge, "draft", text="Still editing")))[0]
        assert bridge.last_interaction == 900
        now[0] = 1199
        await bridge.dispatch(control(bridge, "draft", text="Still editing"))
        assert bridge.last_interaction == 900  # Duplicate autosave is not activity.
        assert not await bridge.idle_tick()
        now[0] = 1200
        assert await bridge.idle_tick()
        assert bridge.host.store.draft == "Still editing"
    finally:
        bridge.host.validation_active = False
        await bridge.close()


async def test_external_editor_prevents_auto_park_but_not_explicit_handoff(
    native, prepared, tmp_path
):
    bridge, _ = await bridge_for(native, prepared, tmp_path)
    now = await idle_clock(bridge)
    try:
        bridge.user_activity(control(bridge, "user_activity", external_editor=True))
        # An already queued autosave can dispatch after the editor-open signal.
        # It is activity, not permission to clear the external-editor hold.
        await bridge.dispatch(control(bridge, "draft", text="Editor source draft"))
        assert bridge.external_editor
        now[0] = 900
        assert not await bridge.idle_tick()
        bridge.user_activity(control(bridge, "user_activity", external_editor=False))
        assert not bridge.external_editor and bridge.last_interaction == 900
        assert not await bridge.idle_tick()
        bridge.user_activity(control(bridge, "user_activity", external_editor=True))
        held = bridge.host.store._owner
        result = await request_release(
            SharedSessionStore(native[0]["cwd"], native[1]),
            expected_owner=held.owner,
            request_id=uuid.uuid4().hex,
            requester_app="synthetic-web",
            timeout=5,
        )
        assert result.status == "released"
        await bridge.release_waiter
        assert not held.active and bridge.ownership_status == "yielded"
        bridge.user_activity(control(bridge, "user_activity", external_editor=False))
        assert not bridge.external_editor and bridge.host.session is None
    finally:
        await bridge.close()


async def test_input_arriving_while_listener_closes_aborts_auto_park(native, prepared, tmp_path):
    bridge, _ = await bridge_for(native, prepared, tmp_path)
    now = await idle_clock(bridge)
    old = bridge.registration
    close = old.close

    async def close_with_input():
        await close()
        bridge.user_activity(control(bridge, "user_activity"))

    old.close = close_with_input
    try:
        now[0] = 300
        assert not await bridge.idle_tick()
        assert bridge.ownership_status == "owned" and bridge.host.store._owner.active
        assert bridge.registration is not old
        assert bridge.last_interaction == 300
    finally:
        await bridge.close()


async def test_idle_park_releases_without_rewriting_and_reload_is_fresh(native, prepared, tmp_path):
    launch, identity, history, messages = native
    bridge, events = await bridge_for(native, prepared, tmp_path)
    old_host, old_store = bridge.host, bridge.host.store
    before = bytes_of(history)
    try:
        assert await bridge.park()
        assert bridge.ownership_status == "parked"
        assert old_host.session is None and not old_store._owner.active
        assert bytes_of(history) == before
        with pytest.raises(RuntimeError):
            old_store.check_open()
        owner = SharedSessionStore(launch["cwd"], identity).acquire(app="synthetic-web")
        messages += [
            {"role": "user", "content": "External continuation"},
            {"role": "assistant", "content": "External answer"},
        ]
        history.save_messages(messages)
        owner.release()
        assert (await bridge.dispatch(control(bridge, "draft", text="Editable unsent draft")))[0]
        assert (await bridge.dispatch(control(bridge, "continue_here")))[0]
        assert bridge.host is not old_host
        assert bridge.host.store.draft == "Editable unsent draft"
        assert not bridge.host.session.coordinator.get("providers")["fixture"].calls
        restored = await bridge.host.session.coordinator.get("context").get_messages()
        assert portable_history(restored) == messages
        assert any(e.get("type") == "item" and e.get("text") == "External answer" for e in events)
        assert (await bridge.dispatch(control(bridge, "submit", text="Explicit next turn")))[0]
        await bridge.host.task
        assert history.load_messages()[-1]["role"] == "assistant"
    finally:
        await bridge.close()


async def test_busy_open_is_read_only_and_continue_here_never_sends(native, prepared, tmp_path):
    launch, identity, history, _ = native
    held = SharedSessionStore(launch["cwd"], identity).acquire(app="amplifier-cli")
    calls = []

    async def release(request):
        calls.append(request.requester_app)
        request.report_progress("draining")
        return ReadyToRelease()

    registration = await register_release_handler(held, prepare_release=release)
    bridge = None
    before = bytes_of(history)
    try:
        bridge, events = await bridge_for(native, prepared, tmp_path)
        assert bridge.ownership_status == "blocked" and bridge.host.session is None
        assert not (history.session_dir / ".tui").exists()
        assert not (await bridge.dispatch(control(bridge, "submit", text="Do not send")))[0]
        assert bytes_of(history) == before and not calls
        assert (await bridge.dispatch(control(bridge, "draft", text="Keep this draft")))[0]
        assert (await bridge.dispatch(control(bridge, "continue_here")))[0]
        assert calls == ["Amplifier TUI"] and not held.active
        assert bridge.ownership_status == "owned" and bridge.host.ready
        assert bridge.host.store.draft == "Keep this draft"
        assert not bridge.host.session.coordinator.get("providers")["fixture"].calls
        assert bytes_of(history) == before
    finally:
        if bridge:
            await bridge.close()
        await registration.close()
        held.release()


async def test_incoming_release_waits_for_current_tool_and_keeps_lock(native, prepared, tmp_path):
    launch, identity, history, _ = native
    bridge, events = await bridge_for(native, prepared, tmp_path)
    entered, finish = asyncio.Event(), asyncio.Event()
    tool = bridge.host.session.coordinator.get("tools")["fixture_probe"]
    original = tool.execute

    async def slow(arguments):
        entered.set()
        await finish.wait()
        return await original(arguments)

    tool.execute = slow
    try:
        assert (await bridge.dispatch(control(bridge, "submit", text="Run fixture")))[0]
        await asyncio.wait_for(entered.wait(), 3)
        held = bridge.host.store._owner
        response = asyncio.create_task(
            request_release(
                SharedSessionStore(launch["cwd"], identity),
                expected_owner=held.owner,
                request_id=uuid.uuid4().hex,
                requester_app="synthetic-web",
                timeout=5,
            )
        )
        async with asyncio.timeout(3):
            while bridge.ownership_status != "yielding":
                await asyncio.sleep(0.01)
        assert not response.done() and held.active
        assert not (await bridge.dispatch(control(bridge, "submit", text="Do not admit")))[0]
        with pytest.raises(SessionBusyError):
            SharedSessionStore(launch["cwd"], identity).acquire(app="contender")
        finish.set()
        assert (await response).status == "released"
        await bridge.release_waiter
        assert bridge.ownership_status == "yielded" and not held.active
        assert any(m.get("role") == "tool" for m in history.load_messages())
        assert bridge.host.store.saved["status"] == "view"
    finally:
        finish.set()
        await bridge.close()


@pytest.mark.parametrize("failure", ["uncertain", "cleanup", "save"])
async def test_failed_preparation_never_releases(native, prepared, tmp_path, monkeypatch, failure):
    launch, identity, _, _ = native
    bridge, _ = await bridge_for(native, prepared, tmp_path)
    held = bridge.host.store._owner
    session = bridge.host.session

    async def broken_cleanup():
        raise RuntimeError("synthetic cleanup failure")

    class FailingSession:
        def __getattr__(self, name):
            return getattr(session, name)

        cleanup = staticmethod(broken_cleanup)

    def broken_save(*args):
        raise OSError("synthetic save failure")

    if failure == "uncertain":
        bridge.host._execution_uncertain = True
    elif failure == "cleanup":
        bridge.host.session = FailingSession()
    else:
        await session.coordinator.get("context").add_message(
            {"role": "user", "content": "Unpersisted"}
        )
        monkeypatch.setattr(bridge.host.store, "checkpoint", broken_save)
    try:
        result = await request_release(
            SharedSessionStore(launch["cwd"], identity),
            expected_owner=held.owner,
            request_id=uuid.uuid4().hex,
            requester_app="synthetic-cli",
            timeout=3,
        )
        assert result.status == "cannot_release" and held.active
        assert bridge.ownership_status == "failed"
        with pytest.raises(SessionBusyError):
            SharedSessionStore(launch["cwd"], identity).acquire(app="contender")
    finally:
        # Tests explicitly finish the synthetic failed cleanup before releasing.
        if failure == "cleanup":
            bridge.host.session = session
            bridge.host._close_task = None
        await bridge.close()


async def test_takeover_never_silently_retargets_another_acquisition(native, prepared, tmp_path):
    launch, identity, _, _ = native
    store = SharedSessionStore(launch["cwd"], identity)
    owner = store.acquire(app="synthetic-cli")
    bridge, _ = await bridge_for(native, prepared, tmp_path)
    owner.release()
    replacement = store.acquire(app="synthetic-web")
    calls = []

    async def refuse(request):
        calls.append(request)
        return CannotRelease("busy", "Not ready")

    registration = await register_release_handler(replacement, prepare_release=refuse)
    try:
        assert not (await bridge.dispatch(control(bridge, "continue_here")))[0]
        assert calls == []  # New owner is shown first; explicit second attempt is required.
        assert not (await bridge.dispatch(control(bridge, "continue_here")))[0]
        assert len(calls) == 1 and replacement.active
    finally:
        await bridge.close()
        await registration.close()
        replacement.release()


async def test_async_admission_reserves_identity_before_waiting():
    admission = Admission()
    started, finish = asyncio.Event(), asyncio.Event()
    calls = []

    async def dispatch(request):
        calls.append(request)
        started.set()
        await finish.wait()
        return True, "Admitted"

    request = dict(version=1, request_id="one-send", op="submit", text="Synthetic")
    first = asyncio.create_task(admission.apply_async(request, dispatch))
    await started.wait()
    second = asyncio.create_task(admission.apply_async(request, dispatch))
    rejected = await admission.apply_async({**request, "text": "Different"}, dispatch)
    assert not rejected["accepted"] and len(calls) == 1
    finish.set()
    assert await first == await second
    assert (await admission.apply_async(request, dispatch))["accepted"]
    assert len(calls) == 1


async def test_takeover_timeout_retains_draft_and_late_release_does_not_send(
    native, prepared, tmp_path, monkeypatch
):
    import amplifier_foundation.session as shared

    launch, identity, history, _ = native
    held = SharedSessionStore(launch["cwd"], identity).acquire(app="amplifier-cli")
    finish = asyncio.Event()

    async def release(request):
        await finish.wait()
        return ReadyToRelease()

    async def bounded_request(*args, **kwargs):
        return await request_release(*args, **{**kwargs, "timeout": 0.05})

    registration = await register_release_handler(held, prepare_release=release)
    monkeypatch.setattr(shared, "request_release", bounded_request)
    bridge, _ = await bridge_for(native, prepared, tmp_path)
    before = bytes_of(history)
    try:
        await bridge.dispatch(control(bridge, "draft", text="Unsent after timeout"))
        ok, reason = await bridge.dispatch(control(bridge, "continue_here"))
        assert not ok and "timed out" in reason and held.active
        assert bridge.ownership_status == "blocked" and bridge.host.session is None
        finish.set()
        await registration.pending
        assert not held.active and bridge.host.session is None
        assert bytes_of(history) == before
        assert (await bridge.dispatch(control(bridge, "continue_here")))[0]
        assert bridge.host.store.draft == "Unsent after timeout"
        assert not bridge.host.session.coordinator.get("providers")["fixture"].calls
    finally:
        finish.set()
        await bridge.close()
        await registration.close()
        held.release()


@pytest.mark.parametrize("pending", ["approval", "question", "validation", "lookup", "queue"])
async def test_idle_parking_never_discards_pending_work(native, prepared, tmp_path, pending):
    bridge, _ = await bridge_for(native, prepared, tmp_path)
    host = bridge.host
    future = asyncio.get_running_loop().create_future()
    try:
        if pending == "approval":
            host._pending["synthetic"] = (future, {})
        elif pending == "question":
            host.questions.pending["synthetic"] = (future, {})
        elif pending == "validation":
            host.validation_active = True
        elif pending == "lookup":
            bridge.lookup_task = future
        else:
            bridge.followups.rows = [{"state": "queued"}]
            bridge.followups.paused = False
        assert not await bridge.park()
        assert bridge.host is host and host.store._owner.active
        assert bridge.ownership_status == "owned"
    finally:
        host._pending.clear()
        host.questions.pending.clear()
        host.validation_active = False
        bridge.lookup_task = None
        bridge.followups.rows = []
        future.cancel()
        await bridge.close()


@pytest.mark.parametrize("cancel", [False, True])
async def test_failed_or_cancelled_remount_retires_candidate_without_sending(
    native, prepared, tmp_path, cancel
):
    launch, identity, history, _ = native
    bridge, _ = await bridge_for(native, prepared, tmp_path)
    await bridge.park()
    await bridge.dispatch(control(bridge, "draft", text="Still unsent"))
    before = bytes_of(history)

    async def broken_mount(host, launch):
        raise asyncio.CancelledError() if cancel else RuntimeError("synthetic mount failure")

    bridge.open_launch = broken_mount
    try:
        if cancel:
            with pytest.raises(asyncio.CancelledError):
                await bridge.dispatch(control(bridge, "continue_here"))
        else:
            ok, reason = await bridge.dispatch(control(bridge, "continue_here"))
            assert not ok and "synthetic mount failure" in reason
        assert bridge.host.session is None
        assert bridge.host.store.draft == "Still unsent"
        assert bytes_of(history) == before
        SharedSessionStore(launch["cwd"], identity).acquire(app="successor").release()
    finally:
        await bridge.close()


async def test_actual_cli_controllers_handoff_both_directions(
    native, prepared, tmp_path, monkeypatch
):
    from io import StringIO
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    from amplifier_app_cli.session_handoff import CLIHandoff, acquire_root
    from amplifier_app_cli.session_runner import SessionConfig
    from amplifier_app_cli.shared_root_state import SharedRootSession
    from rich.console import Console

    launch, identity, history, _ = native
    monkeypatch.chdir(launch["cwd"])
    root = SharedRootSession.acquire(identity)
    initialized = SimpleNamespace(
        root_state=root,
        cleanup=AsyncMock(),
        session=SimpleNamespace(
            coordinator=SimpleNamespace(cancellation=SimpleNamespace(request_graceful=Mock()))
        ),
    )
    cli = await CLIHandoff(initialized, Console(file=StringIO())).start()
    bridge, _ = await bridge_for(native, prepared, tmp_path)
    before = bytes_of(history)
    try:
        taking = asyncio.create_task(bridge.dispatch(control(bridge, "continue_here")))
        await asyncio.wait_for(cli.requested.wait(), 3)
        await cli.finish()
        assert (await taking)[0]
        initialized.session.coordinator.cancellation.request_graceful.assert_called_once()
        initialized.cleanup.assert_awaited_once_with(release_ownership=False)
        config = SessionConfig(
            {}, [], False, session_id=identity, invocation_mode="single", takeover=True
        )
        returned = await asyncio.wait_for(acquire_root(config, cli.console), 3)
        try:
            await bridge.release_waiter
            assert bridge.ownership_status == "yielded"
            assert returned.held.active
            assert bytes_of(history) == before
        finally:
            returned.release()
    finally:
        await bridge.close()
        await cli.registration.close()
        root.release()


async def test_unified_worker_release_to_tui_uses_the_same_handle_and_history(
    native, prepared, tmp_path, monkeypatch
):
    """Installed Unified lifecycle adapter, not its web UI or a paid live model."""
    runtime_module = pytest.importorskip("amplifier_module_loop_live.runtime")
    worker_module = pytest.importorskip("amplifier_web.runtime_worker")
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from amplifier_web.shared_state import ActivationGate

    launch, identity, history, messages = native
    events = []
    monkeypatch.setattr(worker_module, "publish", events.append)
    worker = worker_module.Worker()
    worker.workspace = Path(launch["cwd"])
    worker.shared_store = SharedSessionStore(worker.workspace, identity)
    worker.shared_handle = worker.shared_store.acquire(app="amplifier-unified")
    held = worker.shared_handle
    worker.activation_gate = ActivationGate()
    worker.activation = worker.activation_gate.activate()
    worker.runtime = runtime_module.Runtime(session_id=identity)
    worker.runtime.capture_activation = worker.activation_gate.current

    async def execute():
        kind, command = await worker.runtime.inbox.get()
        assert kind == "input" and command.kind == "stop"
        worker.runtime.closed = True

    async def checkpoint(status):
        held.check()
        worker.activation_gate.check_current()
        history.save_messages(messages + [{"role": "assistant", "content": "Saved by web fixture"}])

    worker.execution = asyncio.create_task(execute())
    worker.execution.add_done_callback(worker.executed)
    worker.session = SimpleNamespace(
        cleanup=AsyncMock(),
        coordinator=SimpleNamespace(
            get_capability=lambda key: checkpoint if key == "live.checkpoint" else None
        ),
    )
    worker.controls = SimpleNamespace(close=AsyncMock())
    await worker.ownership.register()
    bridge, _ = await bridge_for(native, prepared, tmp_path)
    previous = worker.activation
    try:
        assert (await bridge.dispatch(control(bridge, "continue_here")))[0]
        assert not held.active
        restored = await bridge.host.session.coordinator.get("context").get_messages()
        assert restored[-1]["content"] == "Saved by web fixture"
        assert not bridge.host.session.coordinator.get("providers")["fixture"].calls
        with pytest.raises(RuntimeError):
            worker.activation_gate.check(previous)
        await worker.command({"op": "send", "id": "late", "text": "Do not execute"})
        assert events[-1]["code"] == "session_busy"
    finally:
        await bridge.close()
        await worker.ownership.registration.close()
        held.release()

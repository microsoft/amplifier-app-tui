"""Real-runtime finalization ownership under repeated terminal controls."""

import asyncio
import json

import pytest

from amplifier_tui.conversations import ConversationStore
from amplifier_tui.host import SessionHost


@pytest.mark.parametrize("phase", ["messages", "cleanup"])
async def test_child_repeated_cancellation_retains_finalization(
    prepared, tmp_path, monkeypatch, phase
):
    from amplifier_tui import composition

    store = ConversationStore(tmp_path / "state", {})
    host = SessionHost(store)
    await host.open(*prepared, tmp_path)
    entered, release = asyncio.Event(), asyncio.Event()
    original = composition.create_owned_session
    calls = []

    async def owned(*args, **kwargs):
        session = await original(*args, **kwargs)
        cleanup = session.cleanup
        context = session.coordinator.get("context")
        get_messages = context.get_messages
        reads = 0

        async def gated_messages():
            nonlocal reads
            reads += 1
            if phase == "messages" and reads == 2:
                entered.set()
                await release.wait()
            return await get_messages()

        async def gated_cleanup():
            calls.append("cleanup started")
            if phase == "cleanup":
                entered.set()
                await release.wait()
            await cleanup()
            calls.append("cleanup ended")

        monkeypatch.setattr(context, "get_messages", gated_messages)

        # Public session handle proxy: no kernel internals replaced.
        class Handle:
            def __getattr__(self, name):
                return getattr(session, name)

            async def cleanup(self):
                await gated_cleanup()

        return Handle()

    monkeypatch.setattr(composition, "create_owned_session", owned)
    task = asyncio.create_task(host.children.spawn("probe", "check", host.session, {"probe": {}}))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        identity = next(iter(host.children.active))
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        assert identity in host.children.active
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert calls == ["cleanup started", "cleanup ended"]
        saved = json.loads((store.path / "children" / f"{identity}.json").read_text())
        assert saved["status"] == "interrupted"
        assert not host.children.active and not host.children.tasks
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        await host.close()


@pytest.mark.parametrize("second_control", ["stop", "close", "cancelled_close"])
async def test_repeated_control_does_not_cancel_interrupted_checkpoint(
    prepared, tmp_path, monkeypatch, second_control
):
    store = ConversationStore(tmp_path / "state", {})
    host = SessionHost(store)
    entered, release = asyncio.Event(), asyncio.Event()
    closing = None
    await host.open(*prepared, tmp_path)
    try:
        provider = host.session.coordinator.get("providers")["fixture"]
        provider.config["delay"] = 5
        assert host.submit("Interrupted work")[0]
        async with asyncio.timeout(5):
            while not provider.calls:
                await asyncio.sleep(0.001)
        context = host.session.coordinator.get("context")
        original = context.get_messages

        async def checkpoint_messages():
            entered.set()
            await release.wait()
            return await original()

        monkeypatch.setattr(context, "get_messages", checkpoint_messages)
        assert host.stop()
        await asyncio.wait_for(entered.wait(), 5)
        if second_control == "stop":
            assert host.stop()
        else:
            closing = asyncio.create_task(host.close())
            await asyncio.sleep(0)
            if second_control == "cancelled_close":
                closing.cancel()
                await asyncio.sleep(0)
                assert not closing.done()
        release.set()
        assert await host.task == "interrupted"
        if closing:
            if second_control == "cancelled_close":
                with pytest.raises(asyncio.CancelledError):
                    await closing
            else:
                await closing
        saved = json.loads((store.path / "checkpoint.json").read_text())
        assert saved["status"] == "uncertain"
        rows = [json.loads(line) for line in (store.path / "events.jsonl").read_text().splitlines()]
        assert sum(row["kind"] == "turn.ended" for row in rows) == 1
        assert len(provider.calls) == 1
    finally:
        release.set()
        if closing:
            await asyncio.gather(closing, return_exceptions=True)
        await host.close()


async def test_failed_cleanup_remains_observable_without_implicit_retry(prepared, tmp_path):
    store = ConversationStore(tmp_path / "state", {})
    host = SessionHost(store)
    await host.open(*prepared, tmp_path)
    original = host.session
    calls = []

    class FailedCleanup:
        async def cleanup(self):
            calls.append("failed")
            raise RuntimeError("Injected cleanup failure")

    host.session = FailedCleanup()
    try:
        for _ in range(2):
            with pytest.raises(RuntimeError, match="Injected cleanup failure"):
                await host.close()
        assert calls == ["failed"]
        assert host.session is not None
        assert not host.ready
        assert not host.submit("Do not run")[0]
    finally:
        await original.cleanup()
        store.close()


async def test_stop_during_completed_checkpoint_preserves_completion(
    prepared, tmp_path, monkeypatch
):
    store = ConversationStore(tmp_path / "state", {})
    host = SessionHost(store)
    entered, release = asyncio.Event(), asyncio.Event()
    await host.open(*prepared, tmp_path)
    context = host.session.coordinator.get("context")
    original = context.get_messages
    ended = asyncio.Event()
    emit = host.emit

    def observe_end(kind, *args, **kwargs):
        emit(kind, *args, **kwargs)
        if kind == "turn.ended":
            ended.set()

    async def checkpoint_messages():
        if ended.is_set():
            entered.set()
            await release.wait()
        return await original()

    monkeypatch.setattr(host, "emit", observe_end)
    monkeypatch.setattr(context, "get_messages", checkpoint_messages)
    try:
        assert host.submit("Complete this work")[0]
        await asyncio.wait_for(entered.wait(), 5)
        assert not host.stop()  # Execution already ended; checkpoint is still owned.
        release.set()
        assert await host.task == "completed"
        saved = json.loads((store.path / "checkpoint.json").read_text())
        assert saved["status"] == "ready"
    finally:
        release.set()
        await host.close()


async def test_concurrent_cancelled_close_waiters_keep_single_cleanup(prepared, tmp_path):
    host = SessionHost()
    await host.open(*prepared, tmp_path)
    original = host.session
    entered, release = asyncio.Event(), asyncio.Event()
    calls = []

    class GatedCleanup:
        def __getattr__(self, name):
            return getattr(original, name)

        async def cleanup(self):
            calls.append("started")
            entered.set()
            await release.wait()
            await original.cleanup()
            calls.append("finished")

    host.session = GatedCleanup()
    first = asyncio.create_task(host.close())
    await asyncio.wait_for(entered.wait(), 5)
    second = asyncio.create_task(host.close())
    try:
        await asyncio.sleep(0)
        first.cancel()
        await asyncio.sleep(0)
        first.cancel()
        await asyncio.sleep(0)
        assert not first.done()
        assert not second.done()
        assert not host.submit("Do not run")[0]
        assert calls == ["started"]
        release.set()
        results = await asyncio.gather(first, second, return_exceptions=True)
        assert isinstance(results[0], asyncio.CancelledError)
        assert results[1] is None
        assert calls == ["started", "finished"]
        assert host.session is None
        await host.close()
        assert calls == ["started", "finished"]
    finally:
        release.set()
        await asyncio.gather(first, second, return_exceptions=True)
        await host.close()


@pytest.mark.parametrize("cleanup_fails", [False, True])
async def test_close_during_startup_drains_acquired_session(
    prepared, tmp_path, monkeypatch, cleanup_fails
):
    import amplifier_core

    constructor = amplifier_core.AmplifierSession
    mounted, cleaning, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    calls = []

    class GatedStartup:
        def __init__(self, *args, **kwargs):
            self.inner = constructor(*args, **kwargs)
            self.coordinator = self.inner.coordinator

        async def initialize(self):
            await self.inner.initialize()
            mounted.set()
            await asyncio.Future()

        async def cleanup(self):
            calls.append("started")
            cleaning.set()
            await release.wait()
            await self.inner.cleanup()
            calls.append("finished")
            if cleanup_fails:
                raise RuntimeError("Injected startup cleanup failure")

    monkeypatch.setattr(amplifier_core, "AmplifierSession", GatedStartup)
    host = SessionHost()
    opening = asyncio.create_task(host.open(*prepared, tmp_path))
    closing = None
    try:
        await asyncio.wait_for(mounted.wait(), 5)
        closing = asyncio.create_task(host.close())
        await asyncio.wait_for(cleaning.wait(), 2)
        assert not closing.done()
        assert not host.ready
        assert not host.submit("Do not run")[0]
        release.set()
        if cleanup_fails:
            with pytest.raises(RuntimeError, match="Injected startup cleanup failure"):
                await asyncio.wait_for(closing, 5)
            assert isinstance(opening.exception(), RuntimeError)
        else:
            await asyncio.wait_for(closing, 5)
            assert opening.cancelled()
        assert host.session is None
        assert calls == ["started", "finished"]
        with pytest.raises(RuntimeError, match="closed"):
            await host.open(*prepared, tmp_path)
    finally:
        release.set()
        opening.cancel()
        await asyncio.gather(opening, return_exceptions=True)
        if closing:
            await asyncio.gather(closing, return_exceptions=True)
        await asyncio.gather(host.close(), return_exceptions=True)

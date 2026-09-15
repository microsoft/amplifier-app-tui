import asyncio
from types import SimpleNamespace

import pytest

from amplifier_tui.composition import execute_owned


@pytest.mark.parametrize("cooperative", [True, False])
async def test_owned_execution_cancellation_drains_once(cooperative):
    entered, stopped, finalized = asyncio.Event(), asyncio.Event(), asyncio.Event()
    forced, cancelled = [], []

    async def execute(prompt):
        assert prompt == "original"
        entered.set()
        try:
            if cooperative:
                await stopped.wait()
            else:
                await asyncio.Future()
            return "late success must not undo stop"
        except asyncio.CancelledError:
            cancelled.append(True)
            raise
        finally:
            finalized.set()

    session = SimpleNamespace(
        execute=execute,
        coordinator=SimpleNamespace(cancellation=SimpleNamespace(request_immediate=stopped.set)),
    )
    task = asyncio.create_task(
        execute_owned(session, "original", grace=0.02, on_forced=lambda: forced.append(True))
    )
    await entered.wait()
    task.cancel()
    await stopped.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 1)
    assert finalized.is_set()
    assert forced == ([] if cooperative else [True])
    assert cancelled == ([] if cooperative else [True])


async def test_owned_execution_keeps_natural_failure():
    async def execute(prompt):
        raise ValueError("original failure")

    with pytest.raises(ValueError, match="original failure"):
        await execute_owned(SimpleNamespace(execute=execute), "run")

"""Opt-in independent packages, not substitutes for the live-provider gates.

Persistent-context storage is explicitly isolated: its default uses the shared home.
These tests do not certify interrupted-context recovery or every module policy seam.
"""

import copy
import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from amplifier_tui.conversations import ConversationStore
from amplifier_tui.host import SessionHost

pytestmark = pytest.mark.skipif(
    os.environ.get("TUI_TEST_SWAPS") != "1",
    reason="Install the independent packages documented in SMOKE_TESTS.md",
)


@pytest.mark.parametrize("loop", ["loop-streaming", "loop-basic"])
@pytest.mark.parametrize("context", ["context-simple", "context-persistent"])
async def test_independent_loop_context_roundtrip_and_completed_resume(
    prepared, tmp_path, loop, context
):
    workspace = Path(
        os.environ.get("AMPLIFIER_TUI_SOURCE_ROOT", Path(__file__).resolve().parents[2])
    )
    value, report = prepared
    plan = copy.deepcopy(value.mount_plan)
    for slot, name in (("orchestrator", loop), ("context", context)):
        source = workspace / f"amplifier-module-{name}"
        assert source.is_dir()
        plan["session"][slot] = {"module": name, "source": str(source), "config": {}}
    if context == "context-persistent":
        plan["session"]["context"]["config"] = {
            "transcript_path": str(tmp_path / "module-history.jsonl"),
            "memory_files": [],
        }
    value = replace(value, mount_plan=plan)
    store = ConversationStore(tmp_path / "store", {})
    host = SessionHost(store)
    try:
        await host.open(value, report, tmp_path)
        assert host.ready
        assert host.submit("Exercise the independently selected loop and context")[0]
        await host.task
        assert json.loads((store.path / "checkpoint.json").read_text())["status"] == "ready"
        messages = await host.session.coordinator.get("context").get_messages()
        assert any(m["role"] == "tool" for m in messages)
        assert "Fixture round trip complete" in str(messages[-1])
        assert len(host.session.coordinator.get("providers")["fixture"].calls) == 2
    finally:
        await host.close()
    restored = SessionHost(ConversationStore(tmp_path / "store", {}, store.identity))
    try:
        await restored.open(value, report, tmp_path)
        assert restored.ready
        assert await restored.session.coordinator.get("context").get_messages() == messages
        assert not restored.session.coordinator.get("providers")["fixture"].calls
        assert restored.submit("Exercise a second turn after explicit resume")[0]
        await restored.task
        assert (
            json.loads((restored.store.path / "checkpoint.json").read_text())["status"] == "ready"
        )
        assert len(restored.session.coordinator.get("providers")["fixture"].calls) == 2
    finally:
        await restored.close()
    if context == "context-persistent":
        module_path = tmp_path / "module-history.jsonl"
        with module_path.open("a") as stream:
            stream.write(json.dumps({"role": "user", "content": "Foreign module history"}) + "\n")
        original = (store.path / "checkpoint.json").read_bytes()
        refused = SessionHost(ConversationStore(tmp_path / "store", {}, store.identity))
        with pytest.raises(RuntimeError, match="did not restore canonical history"):
            await refused.open(value, report, tmp_path)
        assert not refused.ready
        assert (store.path / "checkpoint.json").read_bytes() == original


async def test_persistent_context_restoration_policy_is_not_generic_recovery(tmp_path):
    # Characterization of a compatibility limit, NOT evidence that arbitrary recovery
    # works: this package deliberately ignores set_messages once its own file exists.
    from amplifier_module_context_persistent import PersistentContextManager

    path = tmp_path / "history.jsonl"
    first = PersistentContextManager(transcript_path=path)
    await first.initialize()
    await first.add_message({"role": "user", "content": "Module-owned original"})
    original = path.read_bytes()
    second = PersistentContextManager(transcript_path=path)
    await second.initialize()
    await second.set_messages([{"role": "user", "content": "Requested replacement"}])
    assert path.read_bytes() == original
    assert "Module-owned original" in str(await second.get_messages())
    assert "Requested replacement" not in str(await second.get_messages())

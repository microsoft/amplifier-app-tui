import asyncio
import copy
import hashlib
import json

import pytest
from test_navigation import bridge_for

from amplifier_tui.recovery import recovery_catalog


@pytest.mark.parametrize("recover_root", [False, True])
async def test_interrupted_child_adoption_is_owned_new_execution(prepared, tmp_path, recover_root):
    bridge, events = await bridge_for(prepared, tmp_path, tmp_path)
    host = bridge.host
    try:
        task = asyncio.create_task(host.children.spawn("self", "wait", host.session, {}))
        async with asyncio.timeout(5):
            while not any(host.children.active.values()):
                await asyncio.sleep(0.001)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        identity = next(iter(host.children.records))
        path = host.store.path / "children" / f"{identity}.json"
        original = path.read_bytes()
        row = json.loads(original)
        assert row["status"] == "interrupted"
        catalog = recovery_catalog(host.store)
        offered = next(r for r in catalog["rows"] if r["id"] == identity)
        assert offered["recover_child"]
        source_id = host.session_id
        if recover_root:
            assert bridge.command(
                {
                    "op": "switch",
                    "target": "new",
                    "session_id": source_id,
                    "draft": "retained",
                    "request_id": "leave-original",
                }
            )[0]
            await bridge.switch_task
            assert bridge.command(
                {
                    "op": "switch",
                    "target": source_id,
                    "recover": True,
                    "session_id": bridge.host.session_id,
                    "draft": "retained",
                    "request_id": "historical",
                }
            )[0]
            await bridge.switch_task
            host = bridge.host
            assert host.session_id != source_id
            assert not host.children.records
            assert not host.session.coordinator.get("providers")["fixture"].calls
        request = {
            "op": "recover_child",
            "session_id": host.session_id,
            "source": source_id,
            "child": identity,
            "sha256": hashlib.sha256(original).hexdigest(),
            "text": "Compute once now",
        }
        assert not bridge.command(request)[0]
        request["confirm"] = True
        assert not bridge.command({**request, "sha256": "stale"})[0]
        assert not bridge.command({**request, "source": "f" * 32})[0]
        # Even a valid source capture cannot authorize a private context module.
        original_session = copy.deepcopy(host.children.prepared.bundle.session)
        operation = host.children.recovery_operation(
            source_id, identity, request["sha256"], request["text"]
        )
        host.children.prepared.bundle.session["context"]["module"] = "unsupported-private-context"
        try:
            with pytest.raises(ValueError, match="private-state reconstruction refused"):
                await operation()
            assert not host.children.active and not host.children.recovering
            assert path.read_bytes() == original
        finally:
            host.children.prepared.bundle.session = original_session
        assert bridge.command(request)[0]
        await host.task
        assert path.read_bytes() == original
        new_id = next(key for key in host.children.records if key != identity)
        adopted = host.children.records[new_id]
        assert adopted["status"] == "completed", events[-5:]
        assert adopted["metadata"]["recovery"]["child"] == identity
        assert not host.children.active and not host.children.tasks
        assert json.loads((host.store.path / "checkpoint.json").read_text())["status"] == "ready"
        assert any("continued as" in str(e) for e in events)
    finally:
        await bridge.close()

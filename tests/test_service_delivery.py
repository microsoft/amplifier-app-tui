"""Actual service modules with disposable storage and a loopback HTTP receiver.

No personal memory, remote ingestion endpoint, timer or credentials are used.
"""

import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from amplifier_tui.conversations import atomic_json

MAX_RECEIVER_BODY = 1024 * 1024


def receiver_resource(identity, status, port):
    manifest = Path(__file__).resolve().parents[2] / "WORKSPACE-MANIFEST.json"
    if not manifest.exists():  # Standalone app checkout has no workspace lifecycle.
        return
    value = json.loads(manifest.read_text())
    now = datetime.now(timezone.utc).isoformat()
    row = next((r for r in value["resources"] if r["id"] == identity), None)
    if row is None:
        row = {
            "kind": "http-test-receiver",
            "id": identity,
            "pid": os.getpid(),
            "port": port,
            "created_at": now,
            "note": "In-process loopback fixture, closed in test finally",
            "teardown": "Terminate only the owning pytest process if it is still running",
        }
        value["resources"].append(row)
    row["status"] = status
    if status == "reaped":
        row["reaped_at"] = now
    atomic_json(manifest, value)


@pytest.mark.skipif(
    os.environ.get("TUI_TEST_PRESETS") != "1", reason="Optional ecosystem module setup"
)
async def test_memory_save_inject_and_nonhuman_refusal(host, prepared, tmp_path, monkeypatch):
    import amplifier_memory
    from amplifier_module_hooks_memory_inject import MemoryInjectHook
    from amplifier_module_tool_memory import MemoryTool

    home = tmp_path / "owned-memory"
    monkeypatch.setenv("AMPLIFIER_SESSION_ORIGIN", "human")
    amplifier_memory.init(home, timer=False)
    coordinator = host.session.coordinator
    text = "For the disposable test, prefer spaces in YAML."
    await coordinator.get("context").add_message({"role": "user", "content": text})
    tool = MemoryTool(coordinator, {"home": str(home)})
    result = await tool.execute({"operation": "save", "text": text, "writer": "human"})
    assert result.success, result
    assert text in amplifier_memory.read_memory_text(home)
    assert (await tool.execute({"operation": "list"})).success
    hook = MemoryInjectHook(coordinator, {"home": str(home)})
    hook.register(coordinator.hooks)
    assert host.submit("Exercise the next request with owned memory")[0]
    await asyncio.wait_for(host.task, 10)
    calls = coordinator.get("providers")["fixture"].calls
    assert calls and text in str(calls[0])
    # Independent conversation: the new prompt/context never supplies the marker.
    # Request observation, not a model's recollection, establishes actual injection.
    from amplifier_tui.host import SessionHost

    await host.close()
    later = SessionHost()
    try:
        await later.open(*prepared, tmp_path / "later-session")
        assert later.session_id != host.session_id
        later_coordinator = later.session.coordinator
        later_hook = MemoryInjectHook(later_coordinator, {"home": str(home)})
        later_hook.register(later_coordinator.hooks)
        assert later.submit("Exercise a fresh request without supplying a memory marker")[0]
        await asyncio.wait_for(later.task, 10)
        later_calls = later_coordinator.get("providers")["fixture"].calls
        assert later_calls and text in str(later_calls[0])
    finally:
        await later.close()
    # The human-origin policy belongs to the memory module, not a TUI bypass.
    monkeypatch.setenv("AMPLIFIER_SESSION_ORIGIN", "scheduled")
    before = amplifier_memory.read_memory_text(home)
    denied = await tool.execute(
        {"operation": "save", "text": "Unapproved fixture memory", "writer": "human"}
    )
    assert not denied.success
    assert amplifier_memory.read_memory_text(home) == before


async def test_forwarding_inspection_filters_session_and_private_fields(host, tmp_path):
    from types import SimpleNamespace

    from amplifier_tui.inspection import forwarding_observations

    resolver = SimpleNamespace(forwarding_log_dir=tmp_path)
    host.session.coordinator.register_capability(
        "context_intelligence.hook_config_resolver", resolver
    )
    assert "unknown" in forwarding_observations(host)["status"]
    path = tmp_path / ("forwarding-" + datetime.now(timezone.utc).strftime("%Y-%m-%d") + ".jsonl")
    path.write_text(
        "\n".join(
            json.dumps(row)
            for row in [
                {"session_id": "not-this-session", "kind": "private-other-session"},
                {
                    "session_id": host.session_id,
                    "kind": "auth_failure",
                    "destination": "fixture",
                    "http_status": 401,
                    "url": "private-endpoint",
                    "detail": "private-secret",
                },
            ]
        )
    )
    result = forwarding_observations(host)
    assert result["observations"] == [
        {"kind": "auth_failure", "destination": "fixture", "http_status": 401}
    ]
    assert "private" not in json.dumps(result)
    path.write_text(
        json.dumps(
            {
                "session_id": host.session_id,
                "kind": "auth_failure",
                "destination": "https://private-endpoint.example/events",
            }
        )
    )
    assert "destination" not in forwarding_observations(host)["observations"][0]
    catalog = host.inspection.catalog(host, "context")
    assert any(row["id"] == "intelligence-forwarding" for row in catalog["rows"])
    path.unlink()
    path.symlink_to(tmp_path / "absent")
    assert forwarding_observations(host)["partial"]


@pytest.mark.parametrize("http_status", [200, 401])
@pytest.mark.skipif(
    os.environ.get("TUI_TEST_PRESETS") != "1", reason="Optional ecosystem module setup"
)
async def test_intelligence_actual_http_delivery_and_failure(host, tmp_path, http_status):
    from amplifier_module_hook_context_intelligence import mount, on_session_ready

    received, tasks = [], set()

    async def handle(reader, writer):
        task = asyncio.current_task()
        tasks.add(task)
        try:
            headers = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 3)
            size = next(
                int(line.split(b":", 1)[1])
                for line in headers.split(b"\r\n")
                if line.lower().startswith(b"content-length:")
            )
            if not 0 <= size <= MAX_RECEIVER_BODY:
                raise ValueError("Fixture request body exceeds receiver limit")
            body = await asyncio.wait_for(reader.readexactly(size), 3)
            received.append((headers, json.loads(body)))
            writer.write(
                f"HTTP/1.1 {http_status} Fixture\r\nContent-Length: 2\r\nConnection: close\r\n\r\n{{}}".encode()
            )
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()
            tasks.discard(task)

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    identity = "service-probe-" + uuid.uuid4().hex
    receiver_resource(identity, "active", port)
    cleanup = None
    try:
        coordinator = host.session.coordinator
        config = {
            "base_path": str(tmp_path / "capture"),
            "forwarding_log_dir": str(tmp_path / "forwarding"),
            "working_dir": str(tmp_path),
            "close_drain_timeout": 0.2,
            "dispatch_backoff_initial": 0.1,
            "destinations": {
                "owned-fixture": {
                    "url": f"http://127.0.0.1:{port}",
                    "api_key": "synthetic-receiver-key",
                    "include": ["**"],
                },
                "excluded-fixture": {
                    "url": f"http://127.0.0.1:{port}/must-not-receive",
                    "api_key": "synthetic-receiver-key",
                    "include": ["**"],
                    "exclude": ["**"],
                },
            },
        }
        cleanup = await mount(coordinator, config)
        await on_session_ready(coordinator)
        assert host.submit("Synthetic intelligence delivery marker")[0]
        await asyncio.wait_for(host.task, 10)
        await cleanup()
        cleanup = None
        assert received, "Mounted logging hook did not deliver an HTTP event"
        assert all(headers.startswith(b"POST /events ") for headers, _ in received)
        assert all(b"Bearer synthetic-receiver-key" in headers for headers, _ in received)
        assert any(host.session_id in json.dumps(body) for _, body in received)
        local_logs = list((tmp_path / "capture").rglob("events.jsonl"))
        assert local_logs and "Synthetic intelligence delivery marker" in "".join(
            p.read_text() for p in local_logs
        )
        if http_status == 401:
            records = list((tmp_path / "forwarding").rglob("*.jsonl"))
            assert records and "401" in "".join(p.read_text() for p in records)
    finally:
        if cleanup:
            await cleanup()
        server.close()
        await server.wait_closed()
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        receiver_resource(identity, "reaped", port)

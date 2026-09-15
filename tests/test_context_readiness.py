import asyncio
import copy
import json
import threading

from amplifier_core import ChatResponse, TextBlock
from test_navigation import bridge_for


async def test_startup_history_gate_never_advertises_ready_or_auto_submits(
    prepared, tmp_path, monkeypatch
):
    from amplifier_tui import input_history
    from amplifier_tui.conversations import ConversationStore
    from amplifier_tui.host import SessionHost
    from amplifier_tui.navigation import WorkspaceBridge

    entered, release = asyncio.Event(), threading.Event()
    loop = asyncio.get_running_loop()
    original = input_history.recall

    def delayed(*args, **kwargs):
        loop.call_soon_threadsafe(entered.set)
        if not release.wait(5):
            raise AssertionError("History test gate not released")
        return original(*args, **kwargs)

    monkeypatch.setattr(input_history, "recall", delayed)
    events = []
    host = SessionHost()

    async def opener(target):
        await target.open(*prepared, tmp_path)

    bridge = WorkspaceBridge(
        host,
        opener,
        events.append,
        True,
        tmp_path,
        lambda: ConversationStore(tmp_path, {"cwd": str(tmp_path)}),
        state_dir=tmp_path,
        open_launch=None,
    )
    opening = asyncio.create_task(bridge.open())
    try:
        await asyncio.wait_for(entered.wait(), 5)
        assert host.ready and bridge.history_loading
        assert not any(e.get("ready") for e in events)
        assert not bridge.command({"op": "submit", "text": "premature"})[0]
        assert bridge.command({"op": "draft", "text": "preserved"})[0]
        release.set()
        await opening
        assert any(e.get("ready") for e in events)
        assert host.store.draft == "preserved"
        provider = host.session.coordinator.get("providers")["fixture"]
        assert not provider.calls
        assert bridge.command({"op": "submit", "text": "explicit after ready"})[0]
        await host.task
        assert provider.calls
    finally:
        release.set()
        await asyncio.gather(opening, return_exceptions=True)
        await bridge.close()


async def test_context_snapshot_reads_only_stored_messages_and_omits_image_bytes(
    prepared, tmp_path
):
    bridge, events = await bridge_for(prepared, tmp_path, tmp_path)
    try:
        context = bridge.host.session.coordinator.get("context")
        await context.add_message(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "stored context marker"},
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": "private-image-sentinel",
                        },
                    },
                ],
            }
        )
        before = copy.deepcopy(await context.get_messages())
        assert bridge.command(
            {
                "op": "inspect",
                "category": "stored_context",
                "request_id": "snapshot",
                "session_id": bridge.host.session_id,
            }
        )[0]
        await bridge.lookup_task
        value = events[-1]
        assert value["category"] == "stored_context" and "stored context marker" in str(value)
        assert "private-image-sentinel" not in json.dumps(value)
        assert "NOT the exact next provider request" in value["context_note"]
        assert await context.get_messages() == before
        assert not bridge.host.session.coordinator.get("providers")["fixture"].calls
        await bridge.host._observe(
            "llm:request",
            {"model": "chosen", "message_count": 9, "raw": {"secret": "private-wire-sentinel"}},
        )
        observed = bridge.host.inspection.catalog(bridge.host, "context")
        assert "chosen" in str(observed) and "private-wire-sentinel" not in str(observed)
    finally:
        await bridge.close()


async def test_provider_validation_is_explicit_isolated_and_redacts_failures(prepared, tmp_path):
    bridge, events = await bridge_for(prepared, tmp_path, tmp_path)
    try:
        provider = bridge.host.session.coordinator.get("providers")["fixture"]
        context = bridge.host.session.coordinator.get("context")
        before = copy.deepcopy(await context.get_messages())
        selection = copy.deepcopy(bridge.host.controls.state)
        calls = []

        async def complete(request):
            calls.append(request)
            await bridge.host._observe(
                "llm:stream_block_delta", {"text": "not a conversation reply"}
            )
            return ChatResponse(content=[TextBlock(text="private-response-sentinel")])

        provider.complete = complete
        request = {
            "op": "validate_provider",
            "provider": "fixture",
            "session_id": bridge.host.session_id,
            "request_id": "probe",
        }
        assert not bridge.command(request)[0] and not calls
        assert bridge.command({**request, "confirm_remote": True})[0]
        assert not bridge.command({"op": "submit", "text": "must wait"})[0]
        await bridge.lookup_task
        assert events[-1]["type"] == "provider_validation" and events[-1]["ok"]
        assert len(calls) == 1 and calls[0].tools is None
        assert calls[0].messages[0].content == "Reply OK."
        assert await context.get_messages() == before and bridge.host.controls.state == selection
        assert not bridge.host.blocks and "private-response-sentinel" not in str(events)

        async def failed(request):
            raise RuntimeError("private-credential-sentinel")

        provider.complete = failed
        assert bridge.command({**request, "confirm_remote": True})[0]
        await bridge.lookup_task
        assert not events[-1]["ok"] and "private-credential-sentinel" not in str(events)
        assert not bridge.host.validation_active
    finally:
        await bridge.close()

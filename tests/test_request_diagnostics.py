import copy
import json

from test_navigation import bridge_for


async def test_request_capture_is_opt_in_one_shot_bounded_and_not_journaled(prepared, tmp_path):
    bridge, events = await bridge_for(prepared, tmp_path / "state", tmp_path)
    try:
        host = bridge.host
        payload = {
            "provider": "fixture",
            "model": "diagnostic-model",
            "raw": {
                "model": "diagnostic-model",
                "temperature": 0.5,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "PRIVATE_REQUEST_SAMPLE"},
                            {"type": "image", "source": {"data": "IMAGE_BYTES_SAMPLE"}},
                        ],
                    }
                ],
                "headers": {"authorization": "AUTH_HEADER_SAMPLE"},
            },
        }
        original = copy.deepcopy(payload)
        await host._observe("llm:request", payload)
        assert host.inspection.request_preview is None
        assert not bridge.command({"op": "request_capture", "session_id": host.session_id})[0]
        assert not bridge.command(
            {"op": "request_capture", "session_id": "other", "confirm_private_context": True}
        )[0]
        assert bridge.command(
            {
                "op": "request_capture",
                "session_id": host.session_id,
                "confirm_private_context": True,
            }
        )[0]
        host.validation_active = True
        await host._observe("llm:request", payload)
        assert host.inspection.capture_next  # Standalone validation cannot consume the capture.
        host.validation_active = False
        await host._observe("llm:request", {**payload, "session_id": "child"})
        assert host.inspection.capture_next
        host.turn_id = "observed-turn"
        await host._observe("llm:request", payload)
        saved = copy.deepcopy(host.inspection.request_preview)
        assert not host.inspection.capture_next and saved["partial"]
        assert "PRIVATE_REQUEST_SAMPLE" in saved["detail"]
        assert "IMAGE_BYTES_SAMPLE" not in saved["detail"]
        assert "AUTH_HEADER_SAMPLE" not in saved["detail"]
        assert saved["turn"] == "observed-turn"
        assert json.loads(saved["detail"])["temperature"] == 0.5
        payload["raw"]["messages"] = []
        await host._observe("llm:request", payload)
        assert host.inspection.request_preview == saved
        assert bridge.command(
            {
                "op": "inspect",
                "category": "wire_request",
                "session_id": host.session_id,
                "request_id": "capture-view",
            }
        )[0]
        assert events[-1]["rows"] == [saved]
        assert "PRIVATE_REQUEST_SAMPLE" not in (host.store.path / "events.jsonl").read_text()
        assert not host.session.coordinator.get("providers")["fixture"].calls
        assert original["raw"]["messages"][0]["content"][0]["text"] in saved["detail"]
        assert bridge.command({"op": "request_clear", "session_id": host.session_id})[0]
        assert host.inspection.request_preview is None and not host.inspection.capture_next
    finally:
        await bridge.close()


async def test_request_missing_or_oversized_content_never_gets_reconstructed(prepared, tmp_path):
    bridge, _ = await bridge_for(prepared, tmp_path / "state", tmp_path)
    try:
        host = bridge.host
        host.inspection.capture_next = True
        await host._observe("llm:request", {"provider": "fixture"})
        assert host.inspection.request_preview["status"] == "request content unavailable"
        host.inspection.capture_next = True
        await host._observe(
            "llm:request", {"raw": {"messages": ["x" * 1000000] * 10, "max_tokens": 10**5000}}
        )
        preview = host.inspection.request_preview
        assert preview["partial"] and len(preview["detail"].encode()) < 17000
        assert not host.session.coordinator.get("providers")["fixture"].calls
    finally:
        await bridge.close()

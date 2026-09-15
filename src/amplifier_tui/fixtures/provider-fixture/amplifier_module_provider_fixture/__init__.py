"""Deterministic test provider. This is never a live model or model-quality evidence."""

import asyncio
import uuid

from amplifier_core import ChatResponse, TextBlock, ToolCall
from amplifier_core.models import ProviderInfo

__amplifier_module_type__ = "provider"


class FixtureProvider:
    name = "fixture"

    def __init__(self, coordinator, config):
        self.coordinator = coordinator
        self.config = config
        self.calls = []

    def get_info(self):
        return ProviderInfo(
            id=self.config.get("vendor", self.name),
            display_name="Deterministic fixture",
            capabilities=self.config.get("capabilities", []),
            defaults={
                "model": self.config.get("default_model", "fixture"),
                "context_window": 32000,
            },
        )

    async def list_models(self):
        return self.config.get("models", [])

    def parse_tool_calls(self, response):
        return response.tool_calls or []

    async def complete(self, request, **kwargs):
        self.calls.append(request)
        await asyncio.sleep(self.config.get("delay", 0.05))
        if self.config.get("raise_error"):
            raise RuntimeError("Fixture provider failed")
        last_user = max((i for i, m in enumerate(request.messages) if m.role == "user"), default=0)
        has_result = any(m.role == "tool" for m in request.messages[last_user + 1 :])
        if not has_result:
            return ChatResponse(
                content=[],
                tool_calls=[
                    ToolCall(
                        id=uuid.uuid4().hex,
                        name="request_user_input"
                        if self.config.get("questions")
                        else self.config.get("tool", "fixture_probe"),
                        arguments={"questions": self.config["questions"]}
                        if self.config.get("questions")
                        else self.config.get("arguments", {"text": "fixture payload"}),
                    )
                ],
            )
        reply = self.config.get(
            "reply", "Fixture round trip complete. Inspect the tool result for evidence."
        )
        for text in [reply[:17], reply[17:39], reply[39:]]:
            await self.coordinator.hooks.emit(
                "llm:stream_block_delta",
                {
                    "block_index": 0,
                    "block_type": "text",
                    "text": text,
                },
            )
            await asyncio.sleep(self.config.get("delay", 0.05))
        return ChatResponse(content=[TextBlock(text=reply)])


async def mount(coordinator, config):
    await coordinator.mount("providers", FixtureProvider(coordinator, config or {}), name="fixture")

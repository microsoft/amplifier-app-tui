"""Independent fixture tool. Computes a real SHA-256 with no external side effects."""

import asyncio
import hashlib

from amplifier_core import ToolResult

__amplifier_module_type__ = "tool"


class FixtureTool:
    name = "fixture_probe"
    description = "Compute the SHA-256 of supplied text (deterministic fixture)."
    input_schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }

    def __init__(self, coordinator, config):
        self.coordinator = coordinator
        self.config = config
        self.calls = 0

    async def execute(self, input):
        if self.config.get("approval"):
            choice = await self.coordinator.approval_system.request_approval(
                "Compute the fixture digest?", ["allow", "deny"], 30, "deny"
            )
            if choice != "allow":
                return ToolResult(success=False, error={"message": "Denied"})
        self.calls += 1
        await asyncio.sleep(self.config.get("delay", 0))
        if self.config.get("fail"):
            return ToolResult(success=False, error={"message": "Fixture tool failed"})
        value = input["text"].encode()
        return ToolResult(
            success=True, output={"sha256": hashlib.sha256(value).hexdigest(), "bytes": len(value)}
        )


async def mount(coordinator, config):
    if not (config or {}).get("skip_mount"):
        await coordinator.mount(
            "tools", FixtureTool(coordinator, config or {}), name="fixture_probe"
        )

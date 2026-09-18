"""Invented process-boundary fixture; never a live provider or user service."""

import asyncio
import os
import time

from amplifier_core import ToolResult

__amplifier_module_type__ = "tool"


class Probe:
    name = "process_probe"
    description = "Exercise the explicitly selected test process boundary."
    input_schema = {"type": "object", "properties": {}}

    def __init__(self, coordinator):
        self.coordinator = coordinator

    async def execute(self, input):
        coordinator = self.coordinator
        coordinator.display_system.show_message("PROCESS-FIXTURE-NOTICE", source="fixture")
        await coordinator.hooks.emit(
            "llm:response",
            {
                "usage": {"input_tokens": 12, "output_tokens": 3, "cost_usd": 0.01},
                "provider": "fixture",
                "model": "process-fixture",
                "duration_ms": 2,
            },
        )
        operation = input.get("operation", "inspect")
        if operation == "nested":
            child = await coordinator.get_capability("session.spawn")(
                agent_name="leaf",
                instruction="Compute a fixture digest",
                parent_session=coordinator.session,
                agent_configs={
                    "leaf": {
                        "providers": [
                            {
                                "module": "provider-fixture",
                                "config": {"tool": "fixture_probe", "delay": 0},
                            }
                        ]
                    }
                },
                use_subprocess=input.get("subprocess", True),
                self_delegation_depth=2,
            )
            return ToolResult(success=True, output=child)
        if operation == "cooperative":
            await asyncio.sleep(input.get("delay", 0.5))
        elif operation == "uncooperative":
            time.sleep(20)
        elif operation == "crash":
            os._exit(17)
        elif operation == "noisy":
            os.write(1, b"PROCESS-RAW-DIAGNOSTIC\n")
        return ToolResult(
            success=True,
            output={
                "pid": os.getpid(),
                "cwd": os.getcwd(),
                "self_depth": coordinator.get_capability("self_delegation_depth"),
                "interactive": coordinator.get_capability("approval.interactive"),
                "unrelated_env": os.environ.get("FIXTURE_UNRELATED_SECRET"),
            },
        )


async def mount(coordinator, config):
    await coordinator.mount("tools", Probe(coordinator), name="process_probe")

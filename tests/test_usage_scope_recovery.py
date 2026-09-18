"""Actual Foundation tools with controlled provider/source; no captured user content."""

import asyncio
import json
import os

import pytest
from test_ecosystem_workflows import ecosystem as ecosystem

from amplifier_tui.conversations import ConversationStore
from amplifier_tui.host import SessionHost

pytestmark = pytest.mark.skipif(
    os.environ.get("TUI_TEST_PRESETS") != "1", reason="Full preset setup"
)


async def test_unsupported_filesystem_does_not_advertise_controls(host):
    assert "write_file" not in host.session.coordinator.get("tools")
    assert host.submit("Run the controlled fixture only")[0]
    await asyncio.wait_for(host.task, 10)
    provider = host.session.coordinator.get("providers")["fixture"]
    assert provider.calls
    assert all("TUI filesystem permission controls:" not in str(c.messages) for c in provider.calls)


async def test_actual_todo_snapshots_and_count_only_updates_remain_inspectable(ecosystem):
    host, _, _ = ecosystem
    provider = host.session.coordinator.get("providers")["fixture"]
    todos = [
        {"content": "Inspect fixture", "activeForm": "Inspecting fixture", "status": "in_progress"},
        {"content": "Review layout", "activeForm": "Reviewing layout", "status": "pending"},
    ]
    for operation in ("create", "update", "list"):
        if operation == "update":
            todos[0]["status"] = "completed"
            todos[1]["status"] = "in_progress"
        provider.config.update(tool="todo", arguments={"action": operation, "todos": todos})
        assert host.submit(f"Controlled todo {operation}")[0]
        await asyncio.wait_for(host.task, 20)
        # The saved journal is the authoritative path, not only module memory.
        observed = [
            json.loads(line) for line in (host.store.path / "events.jsonl").read_text().splitlines()
        ]
        payload = next(
            e["payload"]
            for e in reversed(observed)
            if e["kind"] == "tool.updated" and e["payload"]["name"] == "todo"
        )
        assert payload["status"] == "succeeded"
        assert payload["result"]["success"] is True
        assert payload["result"]["output"]["count"] == 2
        if operation == "update":
            assert payload["arguments"]["todos"] == todos
            assert payload["result"]["output"]["completed"] == 1
            assert "todos" not in payload["result"]["output"]
        else:
            assert payload["result"]["output"]["todos"] == todos


async def test_actual_delegate_inherits_history_but_titles_only_its_task(ecosystem):
    host, _, _ = ecosystem
    context = host.session.coordinator.get("context")
    for index in range(4):
        await context.add_message(
            {"role": "user", "content": f"Task: Old fixture job {index}\n" + "old context " * 120}
        )
        await context.add_message({"role": "assistant", "content": "Controlled earlier response."})
    provider = host.session.coordinator.get("providers")["fixture"]
    agent = next(a for a in host.session.coordinator.config["agents"] if a.endswith(":explorer"))
    task = "Task: Inspect saved drafts\nKeep all files unchanged."
    provider.config.update(
        tool="delegate", arguments={"agent": agent, "instruction": task, "context_depth": "all"}
    )
    assert host.submit("Run the controlled task using inherited history")[0]
    await asyncio.wait_for(host.task, 20)
    assert len(host.children.records) == 1
    child = next(iter(host.children.records.values()))
    assert child["status"] == "completed"
    assert child["task_title"] == "Inspect saved drafts"
    assert child["instruction"].startswith("[PARENT CONVERSATION CONTEXT]")
    assert child["instruction"].index("[YOUR TASK]") > 4096
    assert task in child["instruction"]


async def test_directory_recovery_is_explicit_scoped_and_persistent(ecosystem, tmp_path_factory):
    host, prepared, cwd = ecosystem
    outside = tmp_path_factory.mktemp("permission-fixture")
    target = outside / "record.txt"
    provider = host.session.coordinator.get("providers")["fixture"]
    provider.config.update(
        tool="write_file", arguments={"file_path": str(target), "content": "controlled record"}
    )
    assert host.submit("Attempt the controlled file operation")[0]
    await asyncio.wait_for(host.task, 20)
    assert not target.exists()
    assert host.local_commands.state["directories"] == {}
    assert any("mkdir does not grant permission" in str(c.messages) for c in provider.calls)
    messages = await host.session.coordinator.get("context").get_messages()
    guidance = [m for m in messages if "TUI filesystem permission controls:" in str(m)]
    assert guidance and all(m.get("metadata", {}).get("ephemeral") for m in guidance)
    assert host.submit(f'/allowed-dirs add "{outside}"')[0]
    await host.task
    tool = host.session.coordinator.get("tools")["write_file"]
    assert (await tool.execute({"file_path": str(target), "content": "explicitly allowed"})).success
    assert target.read_text() == "explicitly allowed"
    assert host.submit(f'/denied-dirs add "{outside}"')[0]
    await host.task
    assert not (
        await tool.execute({"file_path": str(target), "content": "must be refused"})
    ).success
    identity, launch = host.session_id, host.store.metadata["launch"]
    await host.close()
    restored = SessionHost(ConversationStore(cwd, launch, identity))
    try:
        await restored.open(*prepared, cwd)
        result = await restored.session.coordinator.get("tools")["write_file"].execute(
            {"file_path": str(target), "content": "still refused"}
        )
        assert not result.success and target.read_text() == "explicitly allowed"
        assert not restored.session.coordinator.get("providers")["fixture"].calls
    finally:
        await restored.close()

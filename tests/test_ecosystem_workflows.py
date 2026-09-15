import asyncio
import json
import os
from pathlib import Path

import pytest
import pytest_asyncio
import yaml

from amplifier_tui.composition import SourceMap, prepare
from amplifier_tui.conversations import ConversationStore
from amplifier_tui.host import SessionHost

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(
    os.environ.get("TUI_TEST_PRESETS") != "1", reason="Full preset setup"
)


@pytest_asyncio.fixture(params=["anchors", "anchors-amp-dev"])
async def ecosystem(request, tmp_path, monkeypatch):
    monkeypatch.setenv("AMPLIFIER_HOME", str(tmp_path / "foundation"))
    monkeypatch.setenv(
        "AMPLIFIER_CONTEXT_INTELLIGENCE_BASE_PATH", str(tmp_path / "context-intelligence")
    )
    overlay = tmp_path / "fixture.yaml"
    overlay.write_text(
        yaml.safe_dump(
            {
                "bundle": {"name": "ecosystem-fixture", "version": "1.0.0"},
                "providers": [
                    {
                        "module": "provider-fixture",
                        "source": str(ROOT / "src/amplifier_tui/fixtures/provider-fixture"),
                    }
                ],
                "tools": [
                    {
                        "module": "tool-fixture",
                        "source": str(ROOT / "src/amplifier_tui/fixtures/tool-fixture"),
                    }
                ],
            }
        )
    )
    prepared = await prepare(
        str(ROOT.parent / "amplifier-foundation/bundles" / request.param),
        [str(ROOT / "examples/user-questions.yaml"), str(overlay)],
        tmp_path,
        SourceMap.read(ROOT.parent / "tui-sources.json"),
        install_deps=False,
    )
    host = SessionHost(ConversationStore(tmp_path, {"cwd": str(tmp_path)}))
    host.interactive_questions = True
    await host.open(*prepared, tmp_path)
    yield host, prepared, tmp_path
    await host.close()


async def test_file_tool_changes_have_real_call_and_version_evidence(ecosystem):
    import hashlib

    host, _, tmp_path = ecosystem
    provider = host.session.coordinator.get("providers")["fixture"]
    path = tmp_path / "observed.txt"
    path.write_text("before")
    provider.config.update(
        tool="write_file", arguments={"file_path": str(path), "content": "after"}
    )
    host.submit("Write the controlled evidence fixture")
    await asyncio.wait_for(host.task, 10)
    assert path.read_text() == "after"
    rows = host.inspection.catalog(host, "changes")["rows"]
    assert len(rows) == 1
    detail = json.loads(rows[0]["detail"])
    assert detail["source_session"] == host.session_id
    assert detail["tool_call_id"]
    assert detail["before"]["files"]["observed.txt"] == hashlib.sha256(b"before").hexdigest()
    assert detail["after"]["files"]["observed.txt"] == hashlib.sha256(b"after").hexdigest()


async def test_actual_delegate_and_agent_recipe(ecosystem):
    host, _, tmp_path = ecosystem
    provider = host.session.coordinator.get("providers")["fixture"]
    agent = next(a for a in host.session.coordinator.config["agents"] if a.endswith(":explorer"))
    provider.config.update(
        tool="delegate",
        arguments={
            "agent": agent,
            "instruction": "Compute a fixture digest",
            "context_depth": "none",
        },
    )
    assert host.submit("Delegate a check")[0]
    await asyncio.wait_for(host.task, 10)
    assert host.children.records, "Delegate never reached child execution"
    assert all(r["status"] == "completed" for r in host.children.records.values())
    recipe = tmp_path / "recipe.yaml"
    recipe.write_text(
        yaml.safe_dump(
            {
                "name": "child-check",
                "description": "Actual agent execution fixture",
                "version": "1.0.0",
                "schema_version": 2,
                "dependencies": [
                    {
                        "source": str(ROOT.parent / "amplifier-foundation"),
                        "kind": "bundle",
                        "required_agents": ["foundation:explorer"],
                    }
                ],
                "steps": [
                    {
                        "id": "check",
                        "agent": "foundation:explorer",
                        "prompt": "Compute a fixture digest",
                        "output": "checked",
                    }
                ],
            }
        )
    )
    provider.config.update(
        tool="recipes", arguments={"operation": "execute", "recipe_path": str(recipe)}
    )
    assert host.submit("Run the agent recipe")[0]
    await asyncio.wait_for(host.task, 60)
    rows = [
        json.loads(line) for line in (host.store.path / "events.jsonl").read_text().splitlines()
    ]
    result = [r for r in rows if r["kind"] == "tool.updated" and r["payload"]["name"] == "recipes"][
        -1
    ]
    assert result["payload"]["status"] == "succeeded", result
    assert len(host.children.records) == 2
    assert not host.children.active


async def test_modes_model_decision_native_change_restore_and_child_policy(ecosystem):
    host, prepared, tmp_path = ecosystem
    provider = host.session.coordinator.get("providers")["fixture"]
    provider.config.update(tool="mode", arguments={"operation": "set", "name": "explore"})
    assert host.submit("Try explore mode")[0]
    async with asyncio.timeout(5):
        while not host._pending:
            await asyncio.sleep(0.01)
    identity = next(iter(host._pending))
    assert host.answer(identity, "Keep current mode")
    await asyncio.wait_for(host.task, 10)
    assert host.modes.current() is None
    assert host.submit("Try explore mode again")[0]
    async with asyncio.timeout(5):
        while not host._pending:
            await asyncio.sleep(0.01)
    identity = next(iter(host._pending))
    assert host.answer(identity, "Change mode")
    await asyncio.wait_for(host.task, 10)
    assert host.modes.current() == "explore"
    sample = tmp_path / "sample.txt"
    sample.write_text("child mode evidence")
    host.children.prepared.bundle.providers[0].setdefault("config", {}).update(
        tool="read_file", arguments={"file_path": str(sample)}
    )
    result = await asyncio.wait_for(
        host.children.spawn("self", "Compute a digest", host.session, {}), 10
    )
    assert host.children.records[result["session_id"]]["mode"] == "explore"
    host.store.checkpoint(
        await host.session.coordinator.get("context").get_messages(),
        host.sequence,
        host.fingerprint,
        True,
    )
    sid = host.session_id
    launch = host.store.metadata["launch"]
    await host.close()
    restored = SessionHost(ConversationStore(tmp_path, launch, sid))
    try:
        await restored.open(*prepared, tmp_path)
        assert restored.modes.current() == "explore"
        assert not restored.session.coordinator.get("providers")["fixture"].calls
        assert restored.modes.select({"current": "explore", "mode": "plan"})[0]
        await restored.task
        assert restored.modes.current() == "plan"
        await restored.session.coordinator.hooks.emit("mode:activation_failed", {"mode": "plan"})
        assert not restored.ready
        assert not restored.submit("Must not run after failed activation")[0]
    finally:
        await restored.close()


@pytest.mark.parametrize("phase", ["active", "checkpoint"])
async def test_mode_change_stop_scope_after_completed_turn(ecosystem, monkeypatch, phase):
    host, _, _ = ecosystem
    assert host.submit("Complete a fixture turn")[0]
    assert await host.task == "completed"
    entered, release, ended = asyncio.Event(), asyncio.Event(), asyncio.Event()
    original_apply = host.modes.apply
    context = host.session.coordinator.get("context")
    original_messages = context.get_messages
    original_emit = host.emit

    async def apply(value):
        result = await original_apply(value)
        if phase == "active":
            entered.set()
            await release.wait()
        return result

    def emit(kind, *args, **kwargs):
        original_emit(kind, *args, **kwargs)
        if kind == "modes.updated":
            ended.set()

    async def messages():
        if phase == "checkpoint" and ended.is_set():
            entered.set()
            await release.wait()
        return await original_messages()

    monkeypatch.setattr(host.modes, "apply", apply)
    monkeypatch.setattr(context, "get_messages", messages)
    monkeypatch.setattr(host, "emit", emit)
    try:
        assert host.modes.select({"current": None, "mode": "plan"})[0]
        await asyncio.wait_for(entered.wait(), 5)
        assert host.stop() is (phase == "active")
        release.set()
        if phase == "active":
            with pytest.raises(asyncio.CancelledError):
                await host.task
            assert not host.ready
        else:
            await host.task
            assert host.modes.current() == "plan"
        saved = json.loads((host.store.path / "checkpoint.json").read_text())
        assert saved["status"] == ("uncertain" if phase == "active" else "ready")
    finally:
        release.set()
        await asyncio.gather(host.task, return_exceptions=True)


async def test_delegate_child_questions_route_and_stop_cleans_up(ecosystem):
    host, _, _ = ecosystem
    provider = host.session.coordinator.get("providers")["fixture"]
    host.children.prepared.bundle.providers[0].setdefault("config", {})["questions"] = [
        {"id": "scope", "question": "Child asks scope?", "options": [{"label": "Small"}]}
    ]
    provider.config.update(
        tool="delegate",
        arguments={"agent": "self", "instruction": "Ask scope", "context_depth": "none"},
    )
    assert host.submit("Delegate a question")[0]
    async with asyncio.timeout(10):
        while not host.questions.pending:
            await asyncio.sleep(0.01)
    qid = next(iter(host.questions.pending))
    assert host.questions.pending[qid][1]["source"].startswith("Child ")
    assert host.questions.answer(
        {
            "op": "question_answer",
            "session_id": host.session_id,
            "turn_id": host.turn_id,
            "question_id": qid,
            "answers": {"scope": {"option": "Small", "text": ""}},
        }
    )[0]
    await asyncio.wait_for(host.task, 10)
    assert all(r["status"] == "completed" for r in host.children.records.values())
    assert host.submit("Delegate a second question")[0]
    async with asyncio.timeout(10):
        while not host.questions.pending:
            await asyncio.sleep(0.01)
    host.stop()
    await asyncio.wait_for(host.task, 10)
    assert not host.children.active
    assert not host.questions.pending
    assert any(r["status"] == "interrupted" for r in host.children.records.values())


async def test_recipe_resume_after_reopen_skips_completed_steps(ecosystem):
    """Real v2 engine via the ordinary tool path; a failed step is explicitly retried."""
    import shlex

    host, prepared, tmp_path = ecosystem
    recipe = tmp_path / "recover.yaml"
    receipts = tmp_path / "receipts.txt"
    gate = tmp_path / "continue.flag"
    recipe.write_text(
        yaml.safe_dump(
            {
                "name": "recover-check",
                "description": "Explicit failed-step recovery fixture",
                "version": "1.0.0",
                "schema_version": 2,
                "dependencies": [],
                "steps": [
                    {
                        "id": "once",
                        "type": "bash",
                        "command": f"echo once >> {shlex.quote(str(receipts))}",
                    },
                    {
                        "id": "retry-explicitly",
                        "type": "bash",
                        "command": f"test -f {shlex.quote(str(gate))}",
                        "timeout": 5,
                    },
                ],
            }
        )
    )

    async def invoke(owner, arguments):
        owner.session.coordinator.get("providers")["fixture"].config.update(
            tool="recipes", arguments=arguments
        )
        assert owner.submit("Explicit recipe operation")[0]
        await asyncio.wait_for(owner.task, 30)
        events = [
            json.loads(line)
            for line in (owner.store.path / "events.jsonl").read_text().splitlines()
        ]
        return [
            e["payload"]
            for e in events
            if e["kind"] == "tool.updated" and e["payload"]["name"] == "recipes"
        ][-1]

    initial = await invoke(host, {"operation": "execute", "recipe_path": str(recipe)})
    assert initial["status"] == "failed", initial
    assert receipts.read_text() == "once\n"
    listed = await invoke(host, {"operation": "list"})
    sessions = listed["result"]["output"]["sessions"]
    assert len(sessions) == 1, sessions
    recipe_id = sessions[0]["session_id"]
    assert sessions[0]["completed_steps"] == ["once"]
    inspected = host.inspection.catalog(host, "recipes")
    assert any(recipe_id in row["recipe_ids"] for row in inspected["rows"])
    identity, launch = host.session_id, host.store.metadata["launch"]
    await host.close()
    restored = SessionHost(ConversationStore(tmp_path, launch, identity))
    try:
        await restored.open(*prepared, tmp_path)
        assert not restored.session.coordinator.get("providers")["fixture"].calls
        assert receipts.read_text() == "once\n"
        gate.touch()
        result = await invoke(restored, {"operation": "resume", "session_id": recipe_id})
        assert result["status"] == "succeeded", result
        assert result["result"]["output"]["status"] == "completed", result
        assert receipts.read_text() == "once\n"
    finally:
        await restored.close()

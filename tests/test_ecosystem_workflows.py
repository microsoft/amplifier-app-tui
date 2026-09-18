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


async def test_actual_delegate_retains_its_self_depth_policy(ecosystem):
    host, _, _ = ecosystem
    coordinator = host.session.coordinator
    delegate = coordinator.get("tools")["delegate"]
    maximum = delegate.max_self_delegation_depth
    coordinator.register_capability("self_delegation_depth", maximum)
    result = await delegate.execute(
        {"agent": "self", "instruction": "Controlled depth boundary", "context_depth": "none"}
    )
    assert not result.success and "depth limit" in str(result.error)
    assert not host.children.records
    coordinator.register_capability("self_delegation_depth", maximum - 1)
    result = await delegate.execute(
        {"agent": "self", "instruction": "Controlled admitted depth", "context_depth": "none"}
    )
    assert result.success
    row = next(iter(host.children.records.values()))
    assert row["self_depth"] == maximum and row["depth"] == 1
    assert row["status"] == "completed"


async def test_mode_command_arguments_keep_module_policy_and_prompt(ecosystem):
    host, _, _ = ecosystem
    provider = host.session.coordinator.get("providers")["fixture"]
    assert host.submit("/mode explore on")[0]
    await host.task
    assert host.modes.current() == "explore" and not provider.calls
    assert host.submit("/mode explore off")[0]
    await host.task
    assert host.modes.current() is None and not provider.calls
    provider.config.update(tool="read_file", arguments={"file_path": "absent-controlled-file"})
    assert host.submit("Observe current policy without changing it")[0]
    await asyncio.wait_for(host.task, 10)
    assert "TUI current mode observation: default (no named mode active)" in str(provider.calls[-1])
    messages = await host.session.coordinator.get("context").get_messages()
    observations = [m for m in messages if "TUI current mode observation:" in str(m)]
    assert observations and all(m.get("metadata", {}).get("ephemeral") for m in observations)
    provider.calls.clear()
    # Explicit Send carries a trailing prompt through the guarded module change.
    provider.config.update(tool="read_file", arguments={"file_path": "absent-controlled-file"})
    assert host.submit("/mode explore Explain the controlled fixture")[0]
    await asyncio.wait_for(host.task, 10)
    assert host.modes.current() == "explore"
    assert provider.calls and "Explain the controlled fixture" in str(provider.calls[0])
    conversation = [
        call for call in provider.calls if (call.metadata or {}).get("stream") is not False
    ]
    assert "TUI current mode observation: explore." in str(conversation[-1])
    assert not host.submit("/mode unknown keep this draft")[0]


async def test_actual_delegate_resume_threads_changed_provider_preferences(ecosystem):
    host, _, _ = ecosystem
    delegate = host.session.coordinator.get("tools")["delegate"]
    first = await delegate.execute(
        {"agent": "self", "instruction": "Initial controlled delegation", "context_depth": "none"}
    )
    assert first.success
    identity = next(iter(host.children.records))
    second = await delegate.execute(
        {
            "session_id": identity,
            "instruction": "Continue with explicit fixture routing",
            "provider_preferences": [{"provider": "fixture", "model": "fixture-alternate"}],
        }
    )
    assert second.success, second.error
    row = host.children.records[identity]
    assert len(host.children.records) == 1 and row["status"] == "completed"
    assert row["routing"][0]["model"] == "fixture-alternate"
    assert (
        row["prepared"].mount_plan["providers"][0]["config"]["default_model"] == "fixture-alternate"
    )


@pytest.mark.parametrize("force", [False, True])
async def test_actual_delegate_cascades_graceful_stop_and_explicit_force(
    ecosystem, monkeypatch, force
):
    host, _, _ = ecosystem
    provider = host.session.coordinator.get("providers")["fixture"]
    provider.config.update(
        tool="delegate",
        arguments={
            "agent": "self",
            "instruction": "Controlled child boundary",
            "context_depth": "none",
        },
    )
    complete = type(provider).complete
    entered, release = asyncio.Event(), asyncio.Event()
    finished = []

    async def controlled(self, request, **kwargs):
        if self is not provider:
            entered.set()
            await release.wait()
            self.config.update(tool="fixture_probe", arguments={"text": "No new effects"})
        result = await complete(self, request, **kwargs)
        if self is not provider:
            finished.append("child request")
        return result

    monkeypatch.setattr(type(provider), "complete", controlled)
    try:
        host.submit("Exercise the real delegate tool")
        await asyncio.wait_for(entered.wait(), 15)
        child = next(iter(host.children.active.values()))
        assert host.stop(immediate=False)
        assert child.coordinator.cancellation.is_graceful
        await asyncio.sleep(0.3)
        assert not host.task.done() and not finished
        if force:
            host.stop(immediate=True)
        else:
            release.set()
        assert await asyncio.wait_for(host.task, 10) == "interrupted"
        assert not host.children.active and not host.children.tasks
        assert [r["status"] for r in host.children.records.values()] == ["interrupted"]
        assert finished == ([] if force else ["child request"])
        assert child.coordinator.get("tools")["fixture_probe"].calls == 0
        assert json.loads((host.store.path / "checkpoint.json").read_text())["status"] == "ready"
    finally:
        release.set()


@pytest.mark.parametrize("operation", ["mode", "local"])
async def test_explicit_control_after_force_stop_resets_cancellation_scope(ecosystem, operation):
    host, _, _ = ecosystem
    provider = host.session.coordinator.get("providers")["fixture"]
    provider.config["delay"] = 10
    host.submit("Force stop before explicit control")
    async with asyncio.timeout(5):
        while not provider.calls:
            await asyncio.sleep(0.005)
    host.stop()
    assert await asyncio.wait_for(host.task, 5) == "interrupted"
    assert host._force_requested
    if operation == "mode":
        assert host.modes.select({"current": None, "mode": "plan"})[0]
    else:
        assert host.submit("/allowed-dirs")[0]
    await asyncio.wait_for(host.task, 5)
    assert not host._force_requested and not host._stop_requested
    assert not host.session.coordinator.cancellation.is_cancelled
    assert host.ready
    if operation == "mode":
        assert host.modes.current() == "plan"
    assert len(provider.calls) == 1


async def test_directory_policy_survives_real_preset_resume(ecosystem):
    host, prepared, cwd = ecosystem
    directory = cwd / "restricted"
    directory.mkdir()
    assert host.submit(f'/denied-dirs add "{directory}"')[0]
    await host.task
    identity, launch = host.session_id, host.store.metadata["launch"]
    await host.close()
    resumed = SessionHost(ConversationStore(cwd, launch, identity))
    try:
        await resumed.open(*prepared, cwd)
        path = directory / "must-not-exist.txt"
        result = await resumed.session.coordinator.get("tools")["write_file"].execute(
            {"file_path": str(path), "content": "refused"}
        )
        assert not result.success and not path.exists()
        assert not resumed.session.coordinator.get("providers")["fixture"].calls
    finally:
        await resumed.close()


async def test_return_to_default_is_latest_mode_observation_in_request(ecosystem):
    host, _, _ = ecosystem
    provider = host.session.coordinator.get("providers")["fixture"]
    provider.config.update(tool="read_file", arguments={"file_path": "absent-controlled-file"})
    for command, expected in (
        (None, "default (no named mode active)"),
        ("/mode explore on", "explore."),
        ("/mode off", "default (no named mode active)"),
    ):
        if command:
            assert host.submit(command)[0]
            await host.task
        assert host.submit("Read only the controlled missing file; do not change modes")[0]
        await asyncio.wait_for(host.task, 10)
        # Naming is a real background call now, not a conversation request.
        conversation = [
            call for call in provider.calls if (call.metadata or {}).get("stream") is not False
        ]
        observations = [
            str(m.content)
            for m in conversation[-1].messages
            if "TUI current mode observation:" in str(m.content)
        ]
        assert observations and expected in observations[-1]


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


@pytest.mark.parametrize("process", [False, True])
async def test_actual_delegate_and_agent_recipe(ecosystem, process):
    host, _, tmp_path = ecosystem
    provider = host.session.coordinator.get("providers")["fixture"]
    agent = next(a for a in host.session.coordinator.config["agents"] if a.endswith(":explorer"))
    if process:
        host.session.coordinator.config["agents"][agent]["spawn_mode"] = "subprocess"
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
    assert all(r["use_subprocess"] == process for r in host.children.records.values())
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
                        "spawn_mode": "subprocess" if process else "in-process",
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
    assert all(r["use_subprocess"] == process for r in host.children.records.values())
    assert not host.children.active


async def test_recipe_file_catalog_and_guidance_are_distinct_from_active_runs(ecosystem):
    host, _, tmp_path = ecosystem
    recipe_dir = tmp_path / "recipes"
    recipe_dir.mkdir()
    path = recipe_dir / "not-validated.yaml"
    path.write_text("not yet a valid recipe: [")
    provider = host.session.coordinator.get("providers")["fixture"]
    assert not provider.calls
    catalog = host.inspection.catalog(host, "recipe_files")
    assert any(row["recipe_file"] == str(path) for row in catalog["rows"])
    assert not provider.calls  # Browsing never invokes the model or recipe engine.
    provider.config.update(tool="recipes", arguments={"operation": "list"})
    assert host.submit("List active runs only; do not execute a recipe")[0]
    await asyncio.wait_for(host.task, 20)
    assert any("NOT available recipe files" in str(call.messages) for call in provider.calls)
    rows = [
        json.loads(line) for line in (host.store.path / "events.jsonl").read_text().splitlines()
    ]
    result = [
        row["payload"]
        for row in rows
        if row["kind"] == "tool.updated"
        and row["payload"].get("name") == "recipes"
        and row["payload"].get("result")
    ][-1]
    assert result["status"] == "succeeded"
    from amplifier_tui.events import tool_result

    assert tool_result(result["result"])["output"]["sessions"] == []
    assert any(
        row["recipe_file"] == str(path)
        for row in host.inspection.catalog(host, "recipe_files")["rows"]
    )
    accepted, reason = host.submit("/config tools disable recipes")
    assert accepted, reason
    await asyncio.wait_for(host.task, 10)
    assert "recipes" not in host.session.coordinator.get("tools")
    provider.config.update(tool="fixture_probe", arguments={})
    assert host.submit("Use the remaining fixture tool only")[0]
    await asyncio.wait_for(host.task, 20)
    assert "Recipe discovery: recipes(operation='list')" not in str(provider.calls[-1].messages)


async def test_process_child_preserves_actual_inherited_mode(ecosystem):
    host, _, _ = ecosystem
    assert (
        await host.modes.execute({"operation": "set", "name": "explore"}, explicit=True)
    ).success
    result = await host.children.spawn(
        "self", "Inspect an inherited fixture mode", host.session, {}, use_subprocess=True
    )
    row = host.children.records[result["session_id"]]
    assert row["status"] == "completed" and row["mode"] == "explore"
    assert host.modes.current() == "explore"
    row["archived"] = True
    row.pop("prepared")
    row.pop("messages")
    await host.children.resume(result["session_id"], "Continue the explicit mode fixture")
    assert host.children.records[result["session_id"]]["mode"] == "explore"


async def test_actual_memory_skill_metadata_and_cli_arguments_without_memory_writes(
    ecosystem, monkeypatch
):
    from amplifier_tui.cli_compat import skill_commands

    host, _, _ = ecosystem
    monkeypatch.syspath_prepend(str(ROOT.parent / "amplifier-bundle-skills/modules/tool-skills"))
    from amplifier_module_tool_skills import mount

    cleanup = await mount(
        host.session.coordinator,
        {"skills_dir": str(ROOT.parent / "amplifier-bundle-memory/skills")},
    )
    try:
        assert "memory" in skill_commands(host.session)
        provider = host.session.coordinator.get("providers")["fixture"]
        provider.config.update(
            tool="load_skill", arguments={"skill_name": "memory", "arguments": "help"}
        )
        assert host.submit("/memory help")[0]
        await asyncio.wait_for(host.task, 10)
        assert host.outcome == "success"
        assert "memory" in str(provider.calls[0].messages)
        assert "help" in str(provider.calls[0].messages)
        assert "# /memory" in str(provider.calls[-1].messages)
        rows = [
            json.loads(line) for line in (host.store.path / "events.jsonl").read_text().splitlines()
        ]
        results = [
            row["payload"]
            for row in rows
            if row["kind"] == "tool.updated" and row["payload"].get("result")
        ]
        assert results[-1]["name"] == "load_skill" and results[-1]["status"] == "succeeded"
        # Only the skill file was loaded; no memory service was even mounted.
        assert "memory" not in host.session.coordinator.get("tools")
    finally:
        if cleanup:
            await cleanup()


@pytest.mark.parametrize("operation", ["set", "clear"])
@pytest.mark.parametrize("cold", [False, True])
async def test_child_can_request_and_clear_its_own_mode_without_root_local_controls(
    ecosystem, operation, monkeypatch, cold
):
    from amplifier_core import ChatResponse, TextBlock

    host, _, _ = ecosystem
    provider = host.session.coordinator.get("providers")["fixture"]
    complete = type(provider).complete

    async def one_mode_call(self, request, **kwargs):
        # Mode context injection can add a user-role ephemeral observation. The
        # fixture's ordinary last-user heuristic would issue the same mode again.
        if self.calls:
            return ChatResponse(content=[TextBlock(text="Controlled mode task complete")])
        return await complete(self, request, **kwargs)

    monkeypatch.setattr(type(provider), "complete", one_mode_call)
    if operation == "clear":
        assert (
            await host.modes.execute({"operation": "set", "name": "explore"}, explicit=True)
        ).success
    host.children.prepared.bundle.providers[0].setdefault("config", {}).update(
        tool="mode",
        arguments={"operation": operation, **({"name": "explore"} if operation == "set" else {})},
    )
    task = asyncio.create_task(
        host.children.spawn("self", "Explore in child mode", host.session, {})
    )
    try:
        async with asyncio.timeout(10):
            while not host._pending and not task.done():
                await asyncio.sleep(0.01)
        assert host._pending, task.result() if task.done() else "No decision"
        assert host.answer(next(iter(host._pending)), "Change mode")
        result = await asyncio.wait_for(task, 15)
        identity = result["session_id"]
        assert host.children.records[identity]["mode"] == (
            "explore" if operation == "set" else None
        )
        assert host.modes.current() == (None if operation == "set" else "explore")
        expected = "explore" if operation == "set" else None
        observed = []

        async def observe_mode(self, request, **kwargs):
            observed.append(self.coordinator.session_state.get("active_mode"))
            return ChatResponse(content=[TextBlock(text="Explicit continuation keeps child mode")])

        monkeypatch.setattr(type(provider), "complete", observe_mode)
        if cold:
            row = host.children.records[identity]
            row["archived"] = True
            row.pop("prepared")
            row.pop("messages")
        continued = await host.children.resume(identity, "Continue the authorized child mode")
        assert continued["session_id"] == identity and observed == [expected]
        assert host.modes.current() == (None if operation == "set" else "explore")
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_modes_model_decision_native_change_restore_and_child_policy(ecosystem, monkeypatch):
    from amplifier_core import ChatResponse, TextBlock

    host, prepared, tmp_path = ecosystem
    provider = host.session.coordinator.get("providers")["fixture"]
    complete = type(provider).complete
    dispatched = set()

    async def one_operation(self, request, **kwargs):
        if (request.metadata or {}).get("stream") is False:
            return ChatResponse(content=[TextBlock(text="Controlled mode fixture")])
        scope = (self.coordinator.session_id, host.turn_id)
        if scope in dispatched:
            return ChatResponse(content=[TextBlock(text="Controlled operation complete")])
        dispatched.add(scope)
        return await complete(self, request, **kwargs)

    # Ephemeral user-role mode reminders are not a new user request. The generic
    # fixture otherwise repeats mode calls until wait_for cancels the turn; that
    # cancelled result must never be mistaken for a successful mode test.
    monkeypatch.setattr(type(provider), "complete", one_operation)
    provider.config.update(tool="mode", arguments={"operation": "set", "name": "explore"})
    assert host.submit("Try explore mode")[0]
    async with asyncio.timeout(5):
        while not host._pending:
            await asyncio.sleep(0.01)
    identity = next(iter(host._pending))
    assert host.answer(identity, "Keep current mode")
    assert await asyncio.wait_for(host.task, 10) == "completed"
    assert host.modes.current() is None
    assert host.submit("Try explore mode again")[0]
    async with asyncio.timeout(5):
        while not host._pending:
            await asyncio.sleep(0.01)
    identity = next(iter(host._pending))
    assert host.answer(identity, "Change mode")
    assert await asyncio.wait_for(host.task, 10) == "completed"
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


@pytest.mark.parametrize("missing_checkpoint", [False, True])
async def test_recipe_resume_after_reopen_skips_completed_steps(ecosystem, missing_checkpoint):
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
        if missing_checkpoint:
            # Only this test's generated module-owned state: model a lost run outcome.
            manager = restored.session.coordinator.get("tools")["recipes"].session_manager
            state = manager.load_state(recipe_id, tmp_path)
            for key in ("v2_run", "current_stage_index", "current_step_index", "completed_steps"):
                state.pop(key, None)
            manager.save_state(recipe_id, tmp_path, state)
        result = await invoke(restored, {"operation": "resume", "session_id": recipe_id})
        if missing_checkpoint:
            assert result["status"] == "failed", result
            assert result["result"]["error"]["type"] == "V2RunNotRecorded", result
            inspected = restored.inspection.catalog(restored, "recipes")
            assert any("Runner refused unsafe resume" in row["detail"] for row in inspected["rows"])
        else:
            assert result["status"] == "succeeded", result
            assert result["result"]["output"]["status"] == "completed", result
        assert receipts.read_text() == "once\n"
    finally:
        await restored.close()

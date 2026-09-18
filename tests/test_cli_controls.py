"""Real core/Foundation controls; authentication transport is explicitly a fixture."""

import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from test_navigation import bridge_for

from amplifier_tui.cli_compat import import_session, session_directory
from amplifier_tui.conversations import ConversationStore, portable_history
from amplifier_tui.host import SessionHost


async def local(host, command):
    accepted, reason = host.submit(command)
    assert accepted, reason
    if host.task:
        await asyncio.wait_for(host.task, 10)


async def test_cli_goal_breaker_stops_real_loop_and_stays_cleared_on_resume(
    prepared, tmp_path, monkeypatch
):
    monkeypatch.setenv("AMPLIFIER_GOAL_REPEAT_LIMIT", "2")
    bridge, _ = await bridge_for(prepared, tmp_path / "state", tmp_path)
    host = bridge.host
    identity, launch = host.session_id, host.store.metadata["launch"]
    loop = host.session.coordinator.get("orchestrator").module
    evaluator = AsyncMock(side_effect=[(False, "Missing proof"), (False, "Missing  proof (×2)")])
    monkeypatch.setattr(loop, "_evaluate_goal", evaluator)
    try:
        await local(host, "/goal --max-turns 10 Verify the isolated evidence")
        assert host.submit("Exercise repeated evaluator reasons")[0]
        await asyncio.wait_for(host.task, 15)
        assert evaluator.await_count == 2
        assert host.ready
        assert host.session.coordinator.session_state["goal"] is None
        assert (
            host.session.coordinator.session_state["goal_circuit_breaker"]["state"]
            == "needs_manager"
        )
        assert json.loads(host.local_commands.path.read_text())["goal"] is None
        events = (host.store.path / "events.jsonl").read_text()
        assert "Goal stopped" in events and "The goal was not achieved" in events
        assert events.count("Goal continuing") == 1
    finally:
        await bridge.close()
    reopened = SessionHost(ConversationStore(tmp_path / "state", launch, identity))
    try:
        await reopened.open(*prepared, tmp_path)
        assert reopened.session.coordinator.session_state.get("goal") is None
        assert not reopened.session.coordinator.get("providers")["fixture"].calls
        await local(reopened, "/goal New evidence")
        assert reopened.local_commands.goal_detector.observe("different") is None
        await local(reopened, "/goal clear")
        await local(reopened, "/goal Another evidence check")
        assert reopened.local_commands.goal_detector.observe("different") is None
    finally:
        await reopened.close()


async def test_provider_diagnostics_cover_all_instances_without_implicit_requests(host):
    providers = host.session.coordinator.get("providers")
    fixture = providers["fixture"]
    for index in range(14):
        providers[f"instance-{index:02}"] = SimpleNamespace(
            list_models=AsyncMock(return_value=[{"id": f"model-{index}"}]),
            auth_status=lambda: "authenticated",
            complete=AsyncMock(),
        )
    await local(host, "/provider status")
    assert not fixture.calls
    assert all(not p.complete.await_count for n, p in providers.items() if n != "fixture")
    result = await host.controls.discover_models()
    assert {r["provider"] for r in result["rows"]} == set(providers)
    assert not result["partial"]
    result = await host.controls.discover_models("instance-13")
    assert [r["model"] for r in result["rows"]] == ["model-13"]
    assert providers["instance-13"].list_models.await_count == 2
    with pytest.raises(ValueError, match="not mounted"):
        await host.controls.discover_models("missing")
    await local(host, "/provider test instance-13")
    assert providers["instance-13"].complete.await_count == 1
    assert not fixture.calls
    await local(host, "/provider test")
    assert len(fixture.calls) == 1
    assert providers["instance-13"].complete.await_count == 2
    assert providers["instance-00"].complete.await_count == 1
    assert host.controls.pin.current() is None


async def test_command_completion_is_cached_scoped_and_never_executes(host, monkeypatch):
    from amplifier_app_cli.ui.completion import Candidate

    controls = host.local_commands

    def values(text):
        return [c["value"] for c in controls.complete(text, len(text))["candidates"]]

    assert values("/provider use fix") == ["fixture "]
    assert "models " in values("/provider ")
    assert "login " in values("/provider ")
    assert set(values("/config ")) == {"show ", *(c + " " for c in controls.config_categories)}
    assert "fixture " in values("/config show providers ")
    assert "disable " not in values("/config providers ")
    assert not values("/config providers disable ")
    assert "mode " not in values("/config tools disable ")
    assert values("/config tools dis") == ["disable "]
    assert values("/config tools disable fixture") == ["fixture_probe "]
    assert values("/goal --m") == ["--max-turns "]
    assert not values("/goal A free-form condition")
    assert controls.complete("/provider use fixture", 17)["candidates"] == []
    assert controls.complete("/provider use fix next", 17)["candidates"][0]["value"] == "fixture"
    assert not values("/provider\nuse fi")
    monkeypatch.setattr(controls.completion, "complete", lambda *_: [Candidate("unsafe\x1b[31m")])
    assert not values("/skill ")
    assert not host.session.coordinator.get("providers")["fixture"].calls


async def test_loaded_configuration_uses_real_inspector_without_a_model_or_mutation(
    prepared, tmp_path
):
    bridge, events = await bridge_for(prepared, tmp_path / "state", tmp_path)
    host = bridge.host
    try:
        controls = host.local_commands
        before = await host.session.coordinator.get("context").get_messages()
        policy = controls.path.read_bytes() if controls.path.exists() else None
        for command in (
            "/config",
            "/config show",
            "/config show providers fixture",
            "/config agents",
        ):
            await local(host, command)

        def recorded():
            return [
                json.loads(line)
                for line in (host.store.path / "events.jsonl").read_text().splitlines()
            ]

        shown = "\n".join(
            e["payload"].get("text", "")
            for e in recorded()
            if e["payload"].get("source") == "config"
        )
        assert "Orchestrator: loop-streaming" in shown
        assert "Context: context-simple" in shown
        assert "fixture · enabled" in shown
        assert "Available agent definitions" in shown
        assert "Values, source URLs and instruction contents omitted" in shown
        assert not host.session.coordinator.get("providers")["fixture"].calls
        assert await host.session.coordinator.get("context").get_messages() == before
        assert (controls.path.read_bytes() if controls.path.exists() else None) == policy
        assert not any(e["kind"] == "turn.accepted" for e in recorded())
        await local(host, "/config tools disable fixture_probe")
        await local(host, "/config show tools fixture_probe")
        assert any("fixture_probe · disabled" in e["payload"].get("text", "") for e in recorded())
        assert not host.submit("/config save --scope global")[0]
        assert not host.submit("/config providers disable fixture")[0]
        assert host.ready
    finally:
        await bridge.close()


async def test_config_metadata_omits_values_sources_instructions_and_bounds_lists(
    host, monkeypatch
):
    controls = host.local_commands
    records = [
        SimpleNamespace(
            name=f"fixture-agent-{i:03}",
            enabled=i != 2,
            module_id=None,
            source_uri="https://fixture.invalid/private?token=synthetic-secret",
            config_summary={
                "instruction": "synthetic private instructions",
                "api_key": "synthetic-key",
            },
            origins=[SimpleNamespace(bundle="fixture-bundle")],
            runtime_injection="mode",
        )
        for i in range(45)
    ]
    monkeypatch.setattr(controls.configurator, "agents_list", lambda: records)
    report = controls.config_report(["agents"])
    assert "Available agent definitions · 45" in report
    assert "13 more items omitted" in report
    assert "fixture-agent-044" not in report
    detail = controls.config_report(["show", "agents", "fixture-agent-044"])
    assert "fixture-agent-044 · enabled" in detail
    assert "From: fixture-bundle" in detail and "Introduced by: mode" in detail
    assert "fixture-agent-002 · disabled" in controls.config_report(["agents", "fixture-agent-002"])
    for forbidden in (
        "synthetic-secret",
        "synthetic-key",
        "synthetic private instructions",
        "fixture.invalid",
    ):
        assert forbidden not in report + detail
    assert "No matching configuration item" in controls.config_report(["agents", "missing"])
    controls.refresh_completion()

    def fail():
        raise ValueError("synthetic-sensitive-error")

    monkeypatch.setattr(controls.configurator, "agents_list", fail)
    # Tab reads the earlier metadata snapshot, never a live inspector.
    query = "/config show agents fixture-agent-04"
    result = controls.complete(query, len(query))
    assert len(result["candidates"]) == 5
    report = controls.config_report(["agents"])
    assert "inspection unavailable" in report and "synthetic-sensitive-error" not in report
    assert not host.session.coordinator.get("providers")["fixture"].calls


async def test_argument_lookup_preserves_identity_and_refreshes_after_controls(prepared, tmp_path):
    bridge, events = await bridge_for(prepared, tmp_path, tmp_path)
    try:
        request = {
            "op": "complete_command",
            "query": "/config tools enable ",
            "cursor": 21,
            "request_id": "arguments",
            "session_id": bridge.host.session_id,
        }
        # Fix cursor from source, not its bytes; protocol uses Unicode codepoints.
        request["cursor"] = len(request["query"])
        await local(bridge.host, "/config tools disable fixture_probe")
        assert bridge.command(request)[0]
        await bridge.lookup_task
        response = next(
            e for e in events if e.get("request_id") == "arguments" and e["type"] == "completion"
        )
        assert response["session_id"] == bridge.host.session_id
        assert response["candidates"][0]["value"] == "fixture_probe "
        assert not bridge.command({**request, "session_id": "stale"})[0]
        assert not bridge.host.session.coordinator.get("providers")["fixture"].calls
    finally:
        await bridge.close()


@pytest.mark.parametrize("decision", ["Allow", "Deny"])
async def test_computer_gate_uses_real_host_approval_not_stdin(
    prepared, tmp_path, monkeypatch, decision
):
    # Actual upstream policy hook and core/orchestrator/host; desktop effects are
    # a counted fixture, never this machine's display or input devices.
    root = Path(__file__).resolve().parents[2] / "amplifier-bundle-computer-use"
    monkeypatch.syspath_prepend(str(root / "modules/hook-computer-use"))
    import amplifier_module_hook_computer_use as hook
    from amplifier_core import ToolResult

    monkeypatch.setattr(hook.sys.stdin, "isatty", lambda: False)
    bridge, _ = await bridge_for(prepared, tmp_path / "state", tmp_path)
    host = bridge.host
    try:
        coordinator = host.session.coordinator
        assert coordinator.get_capability("approval.interactive") is True
        tool = coordinator.get("tools")["fixture_probe"]
        tool.name = "computer"
        tool._gate_writes = True
        tool._backend = SimpleNamespace(name="fixture-desktop")
        tool.execute = AsyncMock(return_value=ToolResult(success=True, output="fixture click"))
        await coordinator.mount("tools", tool, name="computer")
        coordinator.hooks.register(
            "tool:pre",
            hook._make_gate_handler(coordinator),
            priority=10,
            name="actual-computer-gate",
        )
        coordinator.get("providers")["fixture"].config.update(
            tool="computer", arguments={"action": "left_click"}
        )
        assert host.submit("Exercise a gated fixture click")[0]
        async with asyncio.timeout(5):
            while not host._pending:
                await asyncio.sleep(0.005)
        assert tool.execute.await_count == 0
        assert host.answer(next(iter(host._pending)), decision)
        await asyncio.wait_for(host.task, 10)
        assert tool.execute.await_count == (1 if decision == "Allow" else 0)
        assert tool._unattended_writes_ok is False
    finally:
        await bridge.close()


async def test_headless_host_does_not_advertise_interactive_approval(host):
    assert host.session.coordinator.get_capability("approval.interactive") is False


async def test_computer_hook_development_source_preserves_declared_plan(prepared, tmp_path):
    from amplifier_foundation import Bundle

    from amplifier_tui.composition import SourceMap, create_owned_session

    root = Path(__file__).resolve().parents[2]
    sources = SourceMap.read(root / "tui-sources.json")
    uri = "git+https://github.com/microsoft/amplifier-bundle-computer-use@main#subdirectory=modules/hook-computer-use"
    expected = root / "amplifier-bundle-computer-use/modules/hook-computer-use"
    assert sources.resolve(uri) == str(expected)
    bundle = prepared[0].bundle.compose(
        Bundle(
            name="approval-transport-fixture",
            hooks=[{"module": "hook-computer-use", "source": uri}],
        )
    )
    original = bundle.to_mount_plan()
    actual = await bundle.prepare(
        install_deps=False,
        source_resolver=lambda _module, source: sources.resolve(source) or source,
    )
    assert actual.mount_plan == original  # Source location isn't a policy rewrite.
    session = await create_owned_session(actual, session_cwd=tmp_path, interactive_approval=True)
    try:
        assert session.coordinator.get_capability("approval.interactive") is True
        result = await session.coordinator.hooks.emit(
            "tool:pre", {"tool_name": "unrelated", "tool_input": {}}
        )
        assert result.action == "continue"
    finally:
        await session.cleanup()


async def test_goal_is_local_durable_and_clearable(prepared, tmp_path):
    bridge, _ = await bridge_for(prepared, tmp_path / "state", tmp_path)
    host = bridge.host
    identity = host.session_id
    launch = host.store.metadata["launch"]
    try:
        await local(host, "/goal --max-turns 2 Verify the isolated fixture")
        goal = host.session.coordinator.session_state["goal"]
        assert goal["cap"] == 2 and goal["turns_used"] == 0
        assert not host.session.coordinator.get("providers")["fixture"].calls
        assert host.turn_id is None
    finally:
        await bridge.close()
    reopened = SessionHost(ConversationStore(tmp_path / "state", launch, identity))
    try:
        await reopened.open(*prepared, tmp_path)
        assert reopened.session.coordinator.session_state["goal"] == goal
        assert not reopened.session.coordinator.get("providers")["fixture"].calls
        assert not reopened.submit("/goal --max-turns invalid bad")[0]
        assert reopened.ready
        assert reopened.session.coordinator.session_state["goal"] == goal
        await local(reopened, "/goal clear")
        assert reopened.session.coordinator.session_state["goal"] is None
    finally:
        await reopened.close()


async def test_tool_configuration_changes_actual_mounts_and_restores(prepared, tmp_path):
    bridge, _ = await bridge_for(prepared, tmp_path / "state", tmp_path)
    host = bridge.host
    identity, launch = host.session_id, host.store.metadata["launch"]
    try:
        await local(host, "/config tools disable fixture_probe")
        assert "fixture_probe" not in host.session.coordinator.get("tools")
        assert not host.session.coordinator.get("providers")["fixture"].calls
        state = host.local_commands.path.read_bytes()
        assert not host.submit("/config tools disable fixture_probe")[0]
        assert host.local_commands.path.read_bytes() == state
    finally:
        await bridge.close()
    reopened = SessionHost(ConversationStore(tmp_path / "state", launch, identity))
    try:
        await reopened.open(*prepared, tmp_path)
        assert "fixture_probe" not in reopened.session.coordinator.get("tools")
        await local(reopened, "/config tools enable fixture_probe")
        assert "fixture_probe" in reopened.session.coordinator.get("tools")
        assert not reopened.submit("/config tools enable fixture_probe")[0]
        assert reopened.ready
    finally:
        await reopened.close()


async def test_uncertain_or_missing_controls_refuse_reopen(prepared, tmp_path):
    bridge, _ = await bridge_for(prepared, tmp_path / "state", tmp_path)
    host = bridge.host
    identity, launch, path = (
        host.session_id,
        host.store.metadata["launch"],
        host.local_commands.path,
    )
    await local(host, "/goal --max-turns 1 Preserve local control state")
    await bridge.close()
    value = json.loads(path.read_text())
    value["status"] = "pending"
    path.write_text(json.dumps(value))
    reopened = SessionHost(ConversationStore(tmp_path / "state", launch, identity))
    with pytest.raises(ValueError, match="uncertain"):
        await reopened.open(*prepared, tmp_path)
    await reopened.close()
    path.unlink()
    reopened = SessionHost(ConversationStore(tmp_path / "state", launch, identity))
    with pytest.raises(ValueError, match="missing"):
        await reopened.open(*prepared, tmp_path)
    await reopened.close()


async def test_idle_session_does_not_create_local_control_state(prepared, tmp_path):
    bridge, _ = await bridge_for(prepared, tmp_path / "state", tmp_path)
    host = bridge.host
    identity, launch, path = (
        host.session_id,
        host.store.metadata["launch"],
        host.local_commands.path,
    )
    try:
        assert not path.exists()
        assert "local_controls" not in host.store.metadata
    finally:
        await bridge.close()
    reopened = SessionHost(ConversationStore(tmp_path / "state", launch, identity))
    try:
        await reopened.open(*prepared, tmp_path)
        assert reopened.ready
        assert not path.exists()
    finally:
        await reopened.close()


@pytest.mark.skipif(
    os.environ.get("TUI_TEST_PRESETS") != "1", reason="Optional ecosystem module setup"
)
async def test_filesystem_permissions_are_enforced_by_real_tools(host, tmp_path):
    from amplifier_module_tool_filesystem.edit import EditTool
    from amplifier_module_tool_filesystem.write import WriteTool

    coordinator = host.session.coordinator
    for cls in (WriteTool, EditTool):
        tool = cls(
            {"working_dir": str(tmp_path), "allowed_write_paths": [str(tmp_path)]}, coordinator
        )
        await coordinator.mount("tools", tool, name=tool.name)
    directory = tmp_path / "restricted"
    directory.mkdir()
    target = directory / "probe.txt"
    await local(host, f'/denied-dirs add "{directory}"')
    assert not host.submit(f'/denied-dirs add "{directory}"')[0]
    result = await coordinator.get("tools")["write_file"].execute(
        {"file_path": str(target), "content": "probe"}
    )
    assert not result.success and not target.exists()
    await local(host, f'/denied-dirs remove "{directory}"')
    result = await coordinator.get("tools")["write_file"].execute(
        {"file_path": str(target), "content": "probe"}
    )
    assert result.success and target.read_text() == "probe"
    assert not coordinator.get("providers")["fixture"].calls


async def test_provider_args_and_invalid_controls_never_submit(host):
    await local(host, "/provider use fixture")
    assert host.controls.pin.current() == "fixture"
    await local(host, "/provider auto")
    assert host.controls.pin.current() is None
    assert not host.submit("/provider use fixture extra")[0]
    assert not host.submit("/provider login fixture")[0]
    assert not host.submit("/mode plan do not lose this text")[0]
    assert not host.session.coordinator.get("providers")["fixture"].calls


async def test_controls_are_not_queued_or_replayed(prepared, tmp_path):
    bridge, _ = await bridge_for(prepared, tmp_path / "state", tmp_path)
    try:
        assert not bridge.command(
            {
                "op": "queue",
                "text": "/goal --max-turns 1 not queued",
                "session_id": bridge.host.session_id,
            }
        )[0]
        assert not bridge.followups.rows
        await local(bridge.host, "/goal --max-turns 1 Don't drop apostrophes")
        assert "Don't" in bridge.host.session.coordinator.session_state["goal"]["condition"]
        assert bridge.host.submit("Exercise the capped goal fixture")[0]
        await asyncio.wait_for(bridge.host.task, 15)
        assert bridge.host.session.coordinator.session_state.get("goal") is None
        assert bridge.host.local_commands.state["goal"] is None
        assert bridge.host.ready
    finally:
        await bridge.close()


async def test_module_login_is_transient_owned_and_cancellable(host):
    provider = host.session.coordinator.get("providers")["fixture"]
    started = asyncio.Event()
    cleaned = asyncio.Event()

    async def login(print_fn):
        print_fn("SYNTHETIC DEVICE CODE ONLY")
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaned.set()

    provider.login, provider.auth_status = login, lambda: "unauthenticated"
    wire = []
    host.local_commands.wire = wire.append
    assert host.submit("/provider login fixture")[0]
    await asyncio.wait_for(started.wait(), 2)
    assert not host.submit("do not submit during login")[0]
    assert host.stop()
    await asyncio.gather(host.task, return_exceptions=True)
    assert cleaned.is_set()
    assert wire[-2]["type"] == "auth_prompt" and not wire[-2]["active"]
    assert any("SYNTHETIC DEVICE" in e.get("text", "") for e in wire)
    assert "SYNTHETIC DEVICE" not in str(
        await host.session.coordinator.get("context").get_messages()
    )
    retained = []
    while not host.events.empty():
        retained.append(host.events.get_nowait().payload)
    assert "SYNTHETIC DEVICE" not in json.dumps(retained)
    assert not provider.calls
    assert host.ready


async def test_login_stopped_before_start_never_calls_provider(host):
    provider = host.session.coordinator.get("providers")["fixture"]
    called = []

    async def login(print_fn):
        called.append(True)

    provider.login, provider.auth_status = login, lambda: "unauthenticated"
    wire = []
    host.local_commands.wire = wire.append
    assert host.submit("/provider login fixture")[0]
    assert host.stop()
    await asyncio.gather(host.task, return_exceptions=True)
    assert not called and host.ready
    assert wire[-1]["busy"] is False


async def test_login_reports_unavailable_auth_status_without_failing(host):
    provider = host.session.coordinator.get("providers")["fixture"]

    async def login(print_fn):
        print_fn("Synthetic login completed")

    def auth_status():
        raise RuntimeError("private provider error")

    provider.login = login
    provider.auth_status = auth_status
    host.local_commands.wire = [].append
    await local(host, "/provider login fixture")
    events = []
    while not host.events.empty():
        events.append(host.events.get_nowait())
    assert any(
        event.kind == "display.message"
        and event.payload["text"] == "Provider login: status unavailable"
        for event in events
    )
    assert host.ready


@pytest.mark.skipif(
    os.environ.get("TUI_TEST_PRESETS") != "1", reason="Optional ecosystem module setup"
)
async def test_actual_chatgpt_login_adopts_module_owned_tokens(host, tmp_path, monkeypatch):
    from amplifier_module_provider_openai_chatgpt import provider as module
    from amplifier_module_provider_openai_chatgpt.oauth import save_tokens

    path = tmp_path / "owned-oauth.json"
    tokens = {
        "access_token": "synthetic-not-a-credential",
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    }

    async def oauth_fixture(*, token_file_path, print_fn):
        assert token_file_path == str(path)
        print_fn("SYNTHETIC LOGIN INSTRUCTIONS")
        save_tokens(tokens, token_file_path)
        return tokens

    monkeypatch.setattr(module, "oauth_login", oauth_fixture)
    provider = module.ChatGPTProvider(
        config={"token_file_path": str(path)}, coordinator=host.session.coordinator
    )
    await host.session.coordinator.mount("providers", provider, name="oauth-fixture")
    wire = []
    host.local_commands.wire = wire.append
    await local(host, "/provider login oauth-fixture")
    assert provider.auth_status() == "authenticated"
    assert json.loads(path.read_text())["access_token"] == tokens["access_token"]
    assert any("SYNTHETIC LOGIN" in e.get("text", "") for e in wire)
    assert tokens["access_token"] not in json.dumps(wire)
    assert not host.session.coordinator.get("providers")["fixture"].calls


async def test_structured_cli_adoption_preserves_pairs_and_source(prepared, tmp_path):
    home = tmp_path / "cli"
    directory = session_directory(home, tmp_path) / "example"
    directory.mkdir(parents=True)
    messages = [
        {"role": "user", "content": "Historical question"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "observed-call", "name": "fixture_probe", "arguments": {}}],
        },
        {"role": "tool", "tool_call_id": "observed-call", "content": "Historical result"},
        {"role": "assistant", "content": "Historical answer"},
    ]
    source = directory / "transcript.jsonl"
    from amplifier_app_cli.session_store import SessionStore as CliSessionStore

    CliSessionStore(base_dir=directory.parent).save(
        "example", messages, {"name": "Controlled earlier work"}
    )
    raw = source.read_text()
    value = import_session(home, tmp_path, "example", structured=True)
    assert value["messages"] == messages
    bridge, _ = await bridge_for(prepared, tmp_path / "state", tmp_path)
    try:
        host = bridge.host
        host.report["settings_policy"] = "cli"
        host.store.metadata["launch"].update(settings_policy="cli", cli_home=str(home))
        assert bridge.command(
            {
                "op": "switch",
                "target": "new",
                "cli_import": "example",
                "structured_import": True,
                "confirm_import": True,
                "session_id": host.session_id,
                "request_id": "adopt",
                "draft": "kept",
            }
        )[0]
        await bridge.switch_task
        assert bridge.host.session_id != host.session_id
        assert (
            portable_history(await bridge.host.session.coordinator.get("context").get_messages())
            == messages
        )
        assert not bridge.host.session.coordinator.get("providers")["fixture"].calls
        assert source.read_text() == raw
        assert bridge.host.store.draft == "kept"
    finally:
        await bridge.close()
    source.write_text("\n".join(json.dumps(m) for m in messages[:2]))
    with pytest.raises(ValueError, match="Unfinished"):
        import_session(home, tmp_path, "example", structured=True)

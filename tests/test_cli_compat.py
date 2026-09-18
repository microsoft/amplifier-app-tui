"""Configured policy tests use synthetic settings, never the developer's home."""

from pathlib import Path

import pytest
import yaml

from amplifier_tui.cli_compat import apply_settings, settings_for
from amplifier_tui.composition import SourceMap, compose, prepare


@pytest.fixture
def cli_settings(tmp_path, monkeypatch):
    home = tmp_path / "cli-home"
    home.mkdir()
    cwd = tmp_path / "project"
    cwd.mkdir()
    monkeypatch.setenv("AMPLIFIER_HOME", str(home))
    monkeypatch.chdir(cwd)
    return home, cwd


def write_settings(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value))


def test_cli_bootstrap_reads_owned_keys_without_copying_or_overwriting(cli_settings):
    import os
    import subprocess
    import sys

    home, cwd = cli_settings
    original = 'COMPAT_TEST_SAVED="synthetic-saved"\nCOMPAT_TEST_AMBIENT=synthetic-stored\n'
    (home / "keys.env").write_text(original)
    code = """
import os
from pathlib import Path
from amplifier_tui.cli_compat import settings_for
settings_for(Path.cwd(), Path(os.environ['AMPLIFIER_HOME']))
assert os.environ['COMPAT_TEST_SAVED'] == 'synthetic-saved'
assert os.environ['COMPAT_TEST_AMBIENT'] == 'synthetic-ambient'
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=cwd,
        env={**os.environ, "COMPAT_TEST_AMBIENT": "synthetic-ambient"},
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 0, "Controlled CLI credential bootstrap failed; values withheld"
    assert (home / "keys.env").read_text() == original
    assert not result.stdout and not result.stderr


def test_layers_and_invalid_policy(cli_settings):
    home, cwd = cli_settings
    write_settings(
        home / "settings.yaml",
        {
            "bundle": {"active": "base"},
            "overrides": {"context-simple": {"config": {"token_meter": "actual"}}},
        },
    )
    write_settings(cwd / ".amplifier/settings.yaml", {"bundle": {"active": "project"}})
    write_settings(cwd / ".amplifier/settings.local.yaml", {"bundle": {"active": "local"}})
    settings = settings_for(cwd, home)
    assert settings.get_active_bundle() == "local"
    assert settings.get_config_overrides()["context-simple"]["token_meter"] == "actual"
    (cwd / ".amplifier/settings.local.yaml").write_text("not: [valid")
    assert settings.get_active_bundle() == "local"  # One immutable read for preparation.
    with pytest.raises(ValueError, match="values withheld"):
        settings_for(cwd, home)


def test_named_provider_and_context_policy(cli_settings):
    from amplifier_foundation import Bundle

    home, cwd = cli_settings
    write_settings(
        home / "settings.yaml",
        {
            "config": {
                "providers": [
                    {"module": "provider-fixture", "id": "fast", "config": {"priority": 1}},
                    {"module": "provider-fixture", "id": "deep", "config": {"priority": 2}},
                ]
            },
            "overrides": {
                "context-simple": {"config": {"token_meter": "actual"}},
                "tool-example": {"config": {"policy": "shared"}},
            },
        },
    )
    bundle = Bundle(
        name="test",
        session={"context": {"module": "context-simple"}},
        agents={"worker": {"tools": [{"module": "tool-example"}]}},
        tools=[{"module": "tool-filesystem"}],
    )
    value = apply_settings(bundle, settings_for(cwd, home))
    assert [p["instance_id"] for p in value.providers] == ["fast", "deep"]
    assert value.session["context"]["config"]["token_meter"] == "actual"
    assert value.agents["worker"]["tools"][0]["config"]["policy"] == "shared"
    assert "." in value.tools[0]["config"]["allowed_write_paths"]


async def test_streamed_thinking_precedes_answer_without_final_duplicate(host):
    while not host.events.empty():
        host.events.get_nowait()
    thinking = {"block_type": "thinking", "block_index": 0}
    await host._observe("llm:stream_block_start", thinking)
    await host._observe("llm:stream_block_delta", {**thinking, "text": "Public thinking marker"})
    await host._observe("llm:stream_block_end", thinking)
    await host._observe(
        "llm:stream_block_delta", {"block_type": "text", "block_index": 1, "text": "Answer marker"}
    )
    await host._observe(
        "content_block:end",
        {"block_index": 0, "block": {"type": "thinking", "thinking": "Public thinking marker"}},
    )
    rows = []
    while not host.events.empty():
        rows.append(host.events.get_nowait())
    assert [e.kind for e in rows] == ["display.message", "text.delta"]
    assert rows[0].payload["source"] == "thinking"


def test_public_usage_handles_provider_decimal_without_inventing_cost():
    from decimal import Decimal

    from amplifier_tui.inspection import add_usage, usage_summary, usage_totals, usage_values

    reported = usage_values(
        {
            "input_tokens": 10,
            "cost_usd": Decimal("0.00015"),
            "output_tokens": float("nan"),
            "secret": "omit",
        }
    )
    assert reported == {"input_tokens": 10, "cost_usd": Decimal("0.00015")}
    assert usage_values({"input_tokens": 10**400}) == {}
    total = usage_totals()
    add_usage(total, reported)
    add_usage(total, {})
    text = usage_summary(total, {"provider": "fixture"}, 1)
    assert "cost USD 0.000150 (partial)" in text
    assert "cost not reported" in usage_summary(usage_totals(), {}, 1)


@pytest.mark.asyncio
async def test_matches_actual_cli_policy_and_preserves_destinations(
    cli_settings, monkeypatch, tmp_path
):
    from amplifier_app_cli.lib.bundle_loader import prepare as loader
    from amplifier_app_cli.runtime import config as policy

    import amplifier_tui

    home, cwd = cli_settings
    root = Path(__file__).resolve().parents[2]
    source = Path(amplifier_tui.__file__).parent / "fixtures/bundle.yaml"
    paths = {
        f"https://github.com/microsoft/{n}": str(root / n)
        for n in ("amplifier-module-loop-streaming", "amplifier-module-context-simple")
    }
    # The same controlled app defaults enter BOTH resolvers; no remote hooks or services.
    for name in (
        "_build_modes_behaviors",
        "_build_app_cli_behaviors",
        "_build_skills_behaviors",
        "_build_routing_behaviors",
        "_build_wayfinder_behaviors",
        "_build_notification_behaviors",
    ):
        monkeypatch.setattr(policy, name, lambda *a: [])
    write_settings(
        home / "settings.yaml",
        {
            "sources": {
                "modules": {
                    "loop-streaming": str(root / "amplifier-module-loop-streaming"),
                    "context-simple": str(root / "amplifier-module-context-simple"),
                }
            },
            "overrides": {"context-simple": {"config": {"token_meter": "actual"}}},
        },
    )
    original = loader.load_and_prepare_bundle

    async def offline(*args, **kwargs):
        return await original(*args, **kwargs, install_deps=False)

    monkeypatch.setattr(loader, "load_and_prepare_bundle", offline)
    baseline, _ = await policy.resolve_bundle_config(source.as_uri(), settings_for(cwd, home))
    actual, report = await prepare(
        str(source),
        [],
        tmp_path,
        SourceMap(paths),
        install_deps=False,
        cli_policy={"cwd": cwd, "home": home},
    )
    assert actual.mount_plan == baseline
    assert report["settings_policy"] == "cli"
    assert report["storage_policy"] == {}
    assert "_module_resolver" not in report
    # A configured hook/recipe must not silently acquire local-only destination policy.
    overlay = tmp_path / "policy.yaml"
    original_policy = {
        "hooks": [
            {
                "module": "hook-context-intelligence",
                "config": {"destinations": {"test": {"url": "https://example.invalid"}}},
            }
        ],
        "tools": [{"module": "tool-recipes", "config": {"session_dir": "declared-recipes"}}],
    }
    write_settings(overlay, {"bundle": {"name": "policy", "version": "1"}, **original_policy})
    bundle, _ = await compose(
        str(source),
        [str(overlay)],
        tmp_path,
        SourceMap(paths),
        cli_policy={"cwd": cwd, "home": home},
    )
    assert (
        next(h for h in bundle.hooks if h["module"] == "hook-context-intelligence")["config"]
        == original_policy["hooks"][0]["config"]
    )
    assert (
        next(t for t in bundle.tools if t["module"] == "tool-recipes")["config"]["session_dir"]
        == "declared-recipes"
    )
    # Real kernel round trip, not only dictionary comparison.
    from amplifier_tui.host import SessionHost

    host = SessionHost()
    await host.open(actual, report, cwd)
    try:
        assert host.submit("Compute a digest")[0]
        await host.task
        assert host.outcome == "success"
    finally:
        await host.close()


async def test_commands_and_public_observations(host):
    from amplifier_tui.events import Transcript

    for command in (
        "/goal --max-turns invalid",
        "/config tools disable bash",
        "/unknown",
        "/allowed-dirs /tmp",
    ):
        accepted, reason = host.submit(command)
        assert not accepted and reason
    assert not host.session.coordinator.get("providers")["fixture"].calls
    events = []
    while not host.events.empty():
        host.events.get_nowait()
    await host._observe(
        "context:budget",
        {"effective_budget": 24000, "source": "provider", "secret": "never-project"},
    )
    await host._observe("provider:retry", {"attempt": 2, "delay": 3, "error": "never-project"})
    await host._observe("provider:throttle", {"delay": 1})
    await host._observe(
        "content_block:end", {"block": {"type": "thinking", "thinking": "Public thought fixture"}}
    )
    host.show_message("Hook warning", level="warning", source="policy")
    while not host.events.empty():
        events.append(host.events.get_nowait())
    assert "never-project" not in str(events)
    projection = Transcript()
    for event in events:
        projection.apply(event)
    text = "\n".join(item.text for item in projection.items.values())
    assert "Context budget: 24,000 tokens" in text and "not current occupancy" not in text
    assert "Provider retry" in text and "Provider throttling" in text
    assert "Public thought fixture" in text and "[policy / warning]" in text


async def test_cli_skill_prompt_uses_actual_cli_argument_semantics(host):
    class Discovery:
        def find(self, name):
            return object() if name == "example" else None

        def get_shortcuts(self):
            return {"ex": {"name": "example"}}

    host.session.coordinator.register_capability("skills_discovery", Discovery())
    assert host.submit("/ex explicit fork arguments")[0]
    await host.task
    request = host.session.coordinator.get("providers")["fixture"].calls[0]
    assert "arguments" in str(request.messages)
    assert "explicit fork arguments" in str(request.messages)


async def test_cli_catalog_confirmed_import_is_source_preserving(prepared, tmp_path):
    import json

    from test_navigation import bridge_for

    from amplifier_tui.cli_compat import import_session, session_catalog, session_directory

    home, cwd = tmp_path / "home", tmp_path / "workspace"
    cwd.mkdir()
    source = session_directory(home, cwd) / "cli-example"
    source.mkdir(parents=True)
    (source / "metadata.json").write_text(json.dumps({"name": "Earlier CLI work"}))
    raw = (
        json.dumps({"role": "user", "content": "Historical marker"})
        + "\n"
        + json.dumps(
            {
                "role": "assistant",
                "content": "Recorded answer",
                "tool_calls": [{"name": "never-execute"}],
            }
        )
        + "\n"
    )
    (source / "transcript.jsonl").write_text(raw)
    catalog = session_catalog(home, cwd)
    assert catalog["rows"][0]["cli_import"] == "cli-example"
    imported = import_session(home, cwd, "cli-example")
    assert "Historical marker" in imported["text"]
    assert "never-execute" not in imported["text"]
    bridge, events = await bridge_for(prepared, tmp_path / "state", cwd)
    try:
        host = bridge.host
        host.report["settings_policy"] = "cli"
        host.store.metadata["launch"].update(settings_policy="cli", cli_home=str(home))
        identity = host.session_id
        assert bridge.command(
            {
                "op": "inspect",
                "category": "cli_sessions",
                "session_id": identity,
                "request_id": "catalog",
            }
        )[0]
        assert any(
            e.get("category") == "cli_sessions" and e["rows"][0]["cli_import"] == "cli-example"
            for e in events
        )
        request = {
            "op": "switch",
            "target": "new",
            "cli_import": "cli-example",
            "session_id": identity,
            "request_id": "import-1",
            "draft": "unsent",
        }
        assert not bridge.command(request)[0]
        assert bridge.command({**request, "confirm_import": True})[0]
        await bridge.switch_task
        assert bridge.host.session_id != identity
        assert bridge.host.store.draft == "unsent"
        assert "Historical marker" in str(
            await bridge.host.session.coordinator.get("context").get_messages()
        )
        assert not bridge.host.session.coordinator.get("providers")["fixture"].calls
        assert bridge.host.session.coordinator.get("tools")["fixture_probe"].calls == 0
        assert (source / "transcript.jsonl").read_text() == raw
        from amplifier_tui.conversations import ConversationStore

        other_cwd = tmp_path / "different-workspace"
        other_cwd.mkdir()
        other = ConversationStore(
            tmp_path / "state", {**bridge.host.store.metadata["launch"], "cwd": str(other_cwd)}
        )
        other_id = other.identity
        other.close()
        current_id = bridge.host.session_id
        assert bridge.command(
            {
                "op": "switch",
                "target": other_id,
                "session_id": current_id,
                "request_id": "different-cwd",
                "draft": "unsent",
            }
        )[0]
        await bridge.switch_task
        assert bridge.host.session_id == current_id
        assert any("not found in this working directory" in str(e) for e in events)
        with pytest.raises(ValueError):
            import_session(home, cwd, "../escape")
        linked = source.parent / "linked"
        linked.symlink_to(source, target_is_directory=True)
        with pytest.raises(OSError):
            import_session(home, cwd, "linked")
    finally:
        await bridge.close()


@pytest.mark.skipif(
    __import__("os").environ.get("TUI_TEST_PRESETS") != "1", reason="Full CLI behavior setup"
)
@pytest.mark.parametrize("preset", ["anchors", "anchors-amp-dev"])
async def test_actual_cli_defaults_and_configured_behavior(cli_settings, tmp_path, preset):
    import asyncio

    from amplifier_tui.host import SessionHost

    home, cwd = cli_settings
    root = Path(__file__).resolve().parents[1]
    workspace = root.parent
    sources = SourceMap.read(workspace / "tui-sources.json")
    for repo in (
        "amplifier-bundle-wayfinder",
        "amplifier-bundle-notify",
        "amplifier-bundle-skills",
    ):
        sources.paths[f"https://github.com/microsoft/{repo}"] = str(workspace / repo)
    behavior = tmp_path / "configured.yaml"
    write_settings(
        behavior,
        {
            "bundle": {"name": "configured", "version": "1"},
            "tools": [
                {
                    "module": "tool-fixture",
                    "source": str(root / "src/amplifier_tui/fixtures/tool-fixture"),
                }
            ],
        },
    )
    write_settings(
        home / "settings.yaml",
        {
            "bundle": {"app": [str(behavior)]},
            "config": {
                "providers": [
                    {
                        "module": "provider-fixture",
                        "source": str(root / "src/amplifier_tui/fixtures/provider-fixture"),
                        "config": {
                            "tool": "bash",
                            "arguments": {"command": "printf 'configured-cli-tool-output\\n'"},
                        },
                    }
                ]
            },
        },
    )
    prepared, report = await prepare(
        str(workspace / "amplifier-foundation/bundles" / preset),
        [],
        tmp_path,
        sources,
        install_deps=False,
        cli_policy={"cwd": cwd, "home": home},
    )
    host = SessionHost()
    await host.open(prepared, report, cwd)
    try:
        assert "fixture_probe" in host.report["tools"]
        assert host.report["app_behavior_count"] == 1
        assert host.modes.supported
        assert "hooks-routing" in [h["module"] for h in prepared.mount_plan["hooks"]]
        assert host.submit("Run the controlled printf")[0]
        await asyncio.wait_for(host.task, 30)
        assert host.outcome == "success"
        assert any(
            r["status"] == "succeeded" and "configured-cli-tool-output" in r["detail"]
            for r in host.inspection.catalog(host, "activity")["rows"]
        )
        provider = host.session.coordinator.get("providers")["fixture"]
        provider.config.update(
            tool="delegate",
            arguments={
                "agent": "self",
                "instruction": "Compute a fixture digest",
                "context_depth": "none",
            },
        )
        assert host.submit("Delegate a controlled check")[0]
        await asyncio.wait_for(host.task, 30)
        assert host.children.records and all(
            r["status"] == "completed" for r in host.children.records.values()
        )
    finally:
        await host.close()

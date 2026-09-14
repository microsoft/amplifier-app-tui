"""Opt-in complete preset mounting; requires the --all source bootstrap and dependencies."""

import os
from pathlib import Path

import pytest

import amplifier_tui
from amplifier_tui.composition import SourceMap, prepare
from amplifier_tui.host import SessionHost

pytestmark = pytest.mark.skipif(
    os.environ.get("TUI_TEST_PRESETS") != "1",
    reason="Set TUI_TEST_PRESETS=1 after full preset setup",
)


@pytest.mark.parametrize("preset,agent_count", [("anchors", 9), ("anchors-amp-dev", 13)])
async def test_hydrated_preset_mounts_with_policy_hooks(preset, agent_count, tmp_path, monkeypatch):
    workspace = Path(
        os.environ.get("AMPLIFIER_TUI_SOURCE_ROOT", Path(__file__).resolve().parents[2])
    )
    monkeypatch.setenv("AMPLIFIER_HOME", str(tmp_path / "foundation"))
    monkeypatch.setenv(
        "AMPLIFIER_CONTEXT_INTELLIGENCE_BASE_PATH", str(tmp_path / "context-intelligence")
    )
    fixture_provider = Path(amplifier_tui.__file__).parent / "fixtures/provider-fixture"
    overlay = tmp_path / "provider.yaml"
    overlay.write_text(
        "bundle:\n  name: test-provider\n  version: 0.1.0\nproviders:\n"
        f"  - module: provider-fixture\n    source: {fixture_provider}\n"
    )
    prepared, report = await prepare(
        str(workspace / "amplifier-foundation/bundles" / preset),
        [str(overlay)],
        tmp_path,
        SourceMap.read(workspace / "tui-sources.json"),
        install_deps=False,
    )
    assert len(report["agents"]) == agent_count
    assert set(report["excluded_terminal_hooks"]) == {"hooks-streaming-ui", "hooks-todo-display"}
    report["required_tools"] = ["read_file", "glob", "load_skill", "mode", "recipes"]
    host = SessionHost()
    try:
        await host.open(prepared, report, tmp_path)
        assert host.ready
        handlers = {name for names in host.report["hook_handlers"].values() for name in names}
        assert {
            "approval_hook",
            "hook-redaction",
            "LoggingHandler",
            "hooks-status-context",
        } <= handlers
        assert host.capabilities["delegation"]
        assert callable(host.session.coordinator.get_capability("session.spawn"))
    finally:
        await host.close()

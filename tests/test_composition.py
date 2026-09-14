import io
import json

import pytest

from amplifier_tui.__main__ import headless
from amplifier_tui.composition import SourceMap, expand_environment


def test_provider_instance_names_bridge_public_composition_and_kernel_keys():
    from amplifier_foundation import Bundle

    from amplifier_tui.composition import provider_instances

    parent = Bundle(
        name="parent",
        providers=[
            {"module": "provider-a", "instance_id": "one", "config": {"default_model": "small"}}
        ],
    )
    child = Bundle(
        name="child",
        providers=[{"module": "provider-a", "id": "two", "config": {"default_model": "large"}}],
    )
    merged = provider_instances(parent).compose(provider_instances(child))
    assert [p["instance_id"] for p in merged.providers] == ["one", "two"]
    assert "id" not in parent.providers[0]  # Cached bundle unmodified.
    conflict = Bundle(
        name="conflict", providers=[{"module": "provider-a", "id": "one", "instance_id": "two"}]
    )
    with pytest.raises(ValueError, match="disagree"):
        provider_instances(conflict)


def test_config_expansion_is_explicit_and_credentials_fail_closed(monkeypatch):
    monkeypatch.delenv("TUI_TEST_KEY", raising=False)
    assert expand_environment({"level": "${TUI_TEST_KEY:INFO}", "unset": "${TUI_TEST_KEY}"}) == {
        "level": "INFO",
        "unset": "",
    }
    with pytest.raises(ValueError, match="TUI_TEST_KEY"):
        expand_environment("${TUI_TEST_KEY}", required=True)
    monkeypatch.setenv("TUI_TEST_KEY", "test-value")
    assert expand_environment(["${TUI_TEST_KEY}"], required=True) == ["test-value"]


def test_local_override_keeps_namespaces_with_foundation(tmp_path):
    sources = SourceMap({"https://github.com/microsoft/example": str(tmp_path)})
    assert sources.resolve("example:behaviors/a.yaml") is None
    assert sources.resolve(
        "git+https://github.com/microsoft/example@main#subdirectory=modules/x"
    ) == str(tmp_path / "modules/x")


async def test_headless_uses_identified_events_and_closes(host):
    async def already_open(_host):
        pass

    output = io.StringIO()
    assert await headless(host, already_open, "Headless test", output) == 0
    rows = [json.loads(line) for line in output.getvalue().splitlines()]
    assert rows[0]["kind"] == "session.ready"
    assert rows[-1]["kind"] == "turn.ended"
    assert rows[-1]["payload"]["status"] == "completed"
    assert host.session is None


async def test_headless_denies_during_open_and_execution(host):
    async def initializing(target):
        assert await target.request_approval("Startup?", ["allow", "deny"], 30, "allow") == "deny"

    tool = host.session.coordinator.get("tools")["fixture_probe"]
    tool.config["approval"] = True
    output = io.StringIO()
    assert await headless(host, initializing, "Denied", output) == 0
    assert tool.calls == 0
    rows = [json.loads(line) for line in output.getvalue().splitlines()]
    assert sum(row["kind"] == "approval.resolved" for row in rows) == 2

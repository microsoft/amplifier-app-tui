"""Everyday compatibility regressions; synthetic inputs, real mounted runtime."""

import asyncio
import json
from types import SimpleNamespace

import pytest

from amplifier_tui.cli_compat import skill_commands
from amplifier_tui.events import tool_result, tool_status, tool_text
from amplifier_tui.inspection import recipe_files


@pytest.mark.parametrize("encode", [lambda v: v, str, json.dumps])
@pytest.mark.parametrize("success", [True, False])
def test_result_envelopes_preserve_evidence(encode, success):
    raw = encode({"success": success, "output": {"text": "Result marker"}})
    original = str(raw)
    assert tool_status("tool:post", raw) == ("succeeded" if success else "failed")
    assert "Result marker" in tool_text({"name": "example", "result": raw})
    assert tool_status("tool:error", raw) == "failed"
    assert tool_status("tool:pre", raw) == "running"
    assert str(raw) == original


@pytest.mark.parametrize(
    "raw",
    [
        "success: True",
        '{"success":"true"}',
        "{'success': True, ...truncated",
        "{'success': True, 'output': __import__('os').getcwd()}",
        '{"success":true,"output":' + "[" * 30 + "0" + "]" * 30 + "}",
        json.dumps({"success": True, "output": [0] * 9000}),
        "{'success': True, 'output': '" + "x" * 262144 + "'}",
    ],
)
def test_ambiguous_unsafe_or_unbounded_results_stay_unknown(raw):
    assert tool_result(raw) is None
    assert tool_status("tool:post", raw) == "unknown"
    assert len(tool_text({"name": "example", "result": raw})) < 350


async def test_real_root_and_child_serialize_plain_dict_results(host, monkeypatch):
    tool = host.session.coordinator.get("tools")["fixture_probe"]

    async def execute(_self, _input):
        return {"success": True, "output": "Plain dict marker"}

    monkeypatch.setattr(type(tool), "execute", execute)
    assert host.submit("Run the controlled dict-returning tool")[0]
    await asyncio.wait_for(host.task, 10)
    await host.children.spawn("probe", "Compute once", host.session, {"probe": {}})
    events = []
    while not host.events.empty():
        events.append(host.events.get_nowait())
    roots = [
        e
        for e in events
        if e.kind == "tool.updated"
        and e.payload.get("result")
        and e.payload.get("name") == "fixture_probe"
    ]
    assert roots and roots[-1].payload["status"] == "succeeded"
    assert isinstance(roots[-1].payload["result"], str)  # Loop's original repr retained.
    children = [
        e for e in events if e.kind == "child.observed" and e.payload["event"] == "tool:post"
    ]
    assert children and children[-1].payload["status"] == "succeeded"
    assert "Plain dict marker" in children[-1].payload["source"]


def test_recipe_catalog_is_names_only_bounded_and_not_active_sessions(tmp_path):
    root = tmp_path / "recipes"
    root.mkdir()
    candidate = root / "review.yaml"
    candidate.write_text("not even valid YAML: [")
    (root / "linked.yaml").symlink_to(candidate)
    (root / "not-a-recipe.txt").write_text("ignore")
    hidden = root / "one/two/three"
    hidden.mkdir(parents=True)
    (hidden / "hidden.yaml").write_text("out of depth")
    result = recipe_files(SimpleNamespace(recipe_roots=[str(root), str(root)]))
    assert [r["recipe_file"] for r in result["rows"]] == [str(candidate)]
    assert result["rows"][0]["status"] == "file candidate"
    assert "not active sessions" in result["scope"] and result["partial"]
    assert "not been validated" in result["rows"][0]["detail"]
    for n in range(105):
        (root / f"candidate-{n}.yml").touch()
    result = recipe_files(SimpleNamespace(recipe_roots=[str(root)]))
    assert len(result["rows"]) == 100 and result["partial"]


async def test_closed_host_has_no_shortcuts_and_cannot_break_outcome_drain(host):
    await host.close()
    assert skill_commands(host.session) == []


async def test_cached_shortcuts_refresh_after_turn_without_extra_execution(prepared, tmp_path):
    from test_navigation import bridge_for

    bridge, events = await bridge_for(prepared, tmp_path / "state", tmp_path)

    class Discovery:
        def get_shortcuts(self):
            return {"memory": {}, "bad/name": {}, "unsafe\nline": {}, "a" * 81: {}}

        async def discover(self):
            raise AssertionError("Catalog must never cause source discovery")

    try:
        host = bridge.host
        host.session.coordinator.register_capability("skills_discovery", Discovery())
        assert skill_commands(host.session) == ["memory"]
        assert host.submit("Compute one digest")[0]
        await host.task
        await asyncio.sleep(0.02)
        updates = [e for e in events if e["type"] == "commands"]
        assert updates and updates[-1]["commands"] == ["memory"]
        assert updates[-1]["session_id"] == host.session_id
        assert host.session.coordinator.get("tools")["fixture_probe"].calls == 1
    finally:
        await bridge.close()

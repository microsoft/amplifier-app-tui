import copy
import json
from pathlib import Path

import pytest
from test_navigation import bridge_for

from amplifier_tui.recovery import context_transfer, public_history


def test_public_history_repairs_only_explicit_unknown_outcomes():
    messages = [
        {"role": "assistant", "content": "", "tool_calls": [{"id": "a"}, {"id": "b"}]},
        {"role": "tool", "tool_call_id": "a", "content": "verified completed"},
    ]
    original = copy.deepcopy(messages)
    with pytest.raises(ValueError, match="Unfinished"):
        context_transfer(messages, "source")
    repaired, missing = public_history(messages, repair=True)
    assert messages == original and missing == ["b"]
    assert repaired[1] == messages[1]
    assert "UNKNOWN" in repaired[2]["content"]
    assert public_history(repaired)[1] == []
    with pytest.raises(ValueError, match="Unpaired"):
        public_history([messages[1]], repair=True)
    with pytest.raises(ValueError, match="duplicate"):
        public_history([messages[0], messages[0]], repair=True)


async def test_context_fork_preserves_original_and_requires_explicit_send(prepared, tmp_path):
    bridge, events = await bridge_for(prepared, tmp_path, tmp_path)
    source = bridge.host
    overlay = tmp_path / "overlay.yaml"
    import amplifier_tui
    from amplifier_tui.composition import SourceMap, prepare

    fixtures = Path(amplifier_tui.__file__).parent / "fixtures"
    workspace = Path(__file__).resolve().parents[2]
    sources = SourceMap(
        {
            f"https://github.com/microsoft/amplifier-module-{name}": str(
                workspace / f"amplifier-module-{name}"
            )
            for name in ("loop-streaming", "context-simple")
        }
    )
    overlay.write_text(
        f"bundle:\n  name: explicit-test-overlay\nproviders:\n  - module: provider-fixture\n    source: {fixtures / 'provider-fixture'}\n    config:\n      vendor: another-fixture-vendor\n"
    )

    async def reopen(candidate, spec):
        value, report = await prepare(
            str(fixtures / "bundle.yaml"), spec["overlays"], tmp_path, sources, install_deps=False
        )
        await candidate.open(value, report, tmp_path)

    bridge.open_launch = reopen
    try:
        source.submit("Remember this before conversion")
        await source.task
        checkpoint = (source.store.path / "checkpoint.json").read_bytes()
        request = {
            "op": "switch",
            "target": "new",
            "session_id": source.session_id,
            "conversion_overlay": str(overlay),
            "draft": "keep this",
            "request_id": "fork",
        }
        assert not bridge.command(request)[0]
        request["confirm_conversion"] = True
        assert bridge.command(request)[0]
        await bridge.switch_task
        target = bridge.host
        assert target is not source, events
        assert target.store.draft == "keep this"
        assert target.store.metadata["launch"]["overlays"][-1] == str(overlay)
        assert (source.store.path / "checkpoint.json").read_bytes() == checkpoint
        captured = json.loads((target.store.path / "imported-context.json").read_text())
        assert "Remember this before conversion" in str(captured["messages"])
        provider = target.session.coordinator.get("providers")["fixture"]
        assert provider.get_info().id == "another-fixture-vendor"
        assert provider.calls == []
        assert target.submit("Continue in new composition")[0]
        await target.task
        assert "Remember this before conversion" in str(provider.calls[0].messages)
    finally:
        await bridge.close()


async def test_conversion_failure_keeps_source_and_draft(prepared, tmp_path):
    bridge, _ = await bridge_for(prepared, tmp_path, tmp_path)
    original = bridge.host
    try:
        assert bridge.command(
            {
                "op": "switch",
                "target": "new",
                "session_id": original.session_id,
                "conversion_overlay": "missing.yaml",
                "confirm_conversion": True,
                "draft": "retained",
                "request_id": "missing",
            }
        )[0]
        await bridge.switch_task
        assert bridge.host is original and original.ready
        assert original.store.draft == "retained"
    finally:
        await bridge.close()

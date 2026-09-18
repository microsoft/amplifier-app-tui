"""Scoped post-rc4 compatibility gates; no credentials or arbitrary recovery claims."""

import base64
import copy
import hashlib
import json
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from test_navigation import bridge_for
from test_workspace_review import git

from amplifier_tui.events import Event
from amplifier_tui.file_input import clipboard_image
from amplifier_tui.onboarding import provider_overlay, setup_provider
from amplifier_tui.workspace_review import ToolEvidence

ROOT = Path(__file__).resolve().parents[1]


async def test_prior_versions_survive_resume_without_reading_or_executing(prepared, tmp_path):
    git(tmp_path, "init")
    file = tmp_path / "source.py"
    file.write_text("new source")
    digest = hashlib.sha256(file.read_bytes()).hexdigest()
    bridge, _ = await bridge_for(prepared, tmp_path / "state", tmp_path)
    try:
        source = bridge.host.session_id
        bridge.host.emit(
            "change.observed",
            "edit",
            **{
                "agent": "coder",
                "source_session": "child",
                "tool_call_id": "edit",
                "changed": ["source.py"],
                "after": {"files": {"source.py": digest}},
                "overlapping_tools": False,
            },
        )
        # A canonical completed turn is needed for ordinary exact resume.
        assert bridge.host.submit("Remember source evidence")[0]
        await bridge.host.task
        for target in ("new", source):
            assert bridge.command(
                {
                    "op": "switch",
                    "target": target,
                    "draft": "",
                    "session_id": bridge.host.session_id,
                    "request_id": f"switch-{target}",
                }
            )[0]
            await bridge.switch_task
        host = bridge.host
        assert host.tool_evidence.versions["source.py"]["historical"]
        assert not host.session.coordinator.get("providers")["fixture"].calls
        command = {
            "tool_name": "bash",
            "tool_call_id": "check",
            "tool_input": {"command": "pytest"},
        }
        await host.tool_evidence.observe(
            "tool:pre", command, session=source, turn="new", agent="reviewer"
        )
        result = await host.tool_evidence.observe(
            "tool:post", command, session=source, turn="new", agent="reviewer"
        )
        assert result["matching_prior_changes"][0]["historical"]
        file.write_text("external edit")
        await host.tool_evidence.observe(
            "tool:pre", command, session=source, turn="later", agent="reviewer"
        )
        result = await host.tool_evidence.observe(
            "tool:post", command, session=source, turn="later", agent="reviewer"
        )
        assert not result["matching_prior_changes"]
    finally:
        await bridge.close()


def test_replayed_evidence_is_bounded_and_invalidates_unavailable_versions(tmp_path):
    payload = {"changed": ["a"], "after": {"files": {"a": "a" * 64}}}
    first = Event("root", 1, "turn", "change.observed", "edit", payload)
    second = Event(
        "root",
        2,
        "turn",
        "change.observed",
        "lost",
        {"changed": ["a"], "after": {"files": {"a": "unavailable"}}},
    )
    assert not ToolEvidence(tmp_path, [first, second]).versions
    observer = ToolEvidence(tmp_path)
    for index in range(300):
        path = f"source-{index}"
        observer.remember({"changed": [path], "after": {"files": {path: "a" * 64}}}, "turn")
    assert len(observer.versions) == 256


async def test_model_metadata_reports_limits_not_remaining_context(prepared, tmp_path):
    bridge, _ = await bridge_for(prepared, tmp_path, tmp_path)
    try:
        provider = bridge.host.session.coordinator.get("providers")["fixture"]

        async def models():
            return [
                SimpleNamespace(
                    id="reported-model",
                    context_window=100000,
                    max_output_tokens=8000,
                    capabilities=["vision", "tools", "private-field"],
                ),
                {"id": "invalid-limits", "context_window": True, "max_output_tokens": 2**99},
            ]

        provider.list_models = models
        result = await bridge.host.controls.discover_models()
        assert result["rows"][0]["limits"] == {"context_window": 100000, "max_output_tokens": 8000}
        assert result["rows"][0]["capabilities"] == ["vision", "tools"]
        assert result["rows"][1]["limits"] == {}
        assert "not the current request budget" in result["scope"]
        assert "private-field" not in json.dumps(result) and not provider.calls

        def synchronous_models():
            return [SimpleNamespace(id="synchronous-model")]

        provider.list_models = synchronous_models
        synchronous = await bridge.host.controls.discover_models()
        assert synchronous["rows"][0]["model"] == "synchronous-model"
    finally:
        await bridge.close()


@pytest.mark.parametrize(
    "kind,mime", [("JPEG", "image/jpeg"), ("WEBP", "image/webp"), ("GIF", "image/gif")]
)
@pytest.mark.parametrize("backend", ["wl-paste", "xclip"])
async def test_linux_clipboard_fallback_preserves_actual_bytes(
    tmp_path, monkeypatch, kind, mime, backend
):
    image = tmp_path / "sample"
    Image.new("RGB", (12, 12), "blue").save(image, format=kind)
    raw = image.read_bytes()
    utility = tmp_path / backend
    utility.write_text(
        f"#!{sys.executable}\nimport sys\nif {mime!r} not in sys.argv: sys.exit(1)\nsys.stdout.buffer.write({raw!r})\n"
    )
    utility.chmod(0o700)
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.setenv("WAYLAND_DISPLAY" if backend == "wl-paste" else "DISPLAY", "fixture")
    value = await clipboard_image()
    assert value["media_type"] == mime and base64.b64decode(value["data"]) == raw


def test_named_credential_reference_never_reads_its_value(monkeypatch):
    monkeypatch.setenv("TEAM_MODEL_KEY", "private-value-sentinel")
    value = provider_overlay("anthropic", "explicit-model", "TEAM_MODEL_KEY")
    assert value["providers"][0]["config"]["api_key"] == "${TEAM_MODEL_KEY}"
    assert "private-value-sentinel" not in json.dumps(value)
    for invalid in ("", "sk-ant-value", "${KEY}", "KEY=value", "a b", "a" * 65):
        with pytest.raises(ValueError, match="NAME"):
            provider_overlay("anthropic", "model", invalid)


@pytest.mark.parametrize("suffix", [".json", ".YAML", ".YML", ""])
def test_setup_rejects_unloadable_suffix_before_writing(tmp_path, monkeypatch, suffix):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    target = tmp_path / f"overlay{suffix}"
    answers = iter(["anthropic", "model", str(target)])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    with pytest.raises(ValueError, match=".yaml"):
        setup_provider()
    assert not target.exists()


async def test_clipboard_refuses_wrong_successful_representation(tmp_path, monkeypatch):
    image = tmp_path / "jpeg"
    Image.new("RGB", (4, 4), "blue").save(image, format="JPEG")
    utility = tmp_path / "wl-paste"
    utility.write_text(
        f"#!{sys.executable}\nimport sys\nsys.stdout.buffer.write({image.read_bytes()!r})\n"
    )
    utility.chmod(0o700)
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setenv("WAYLAND_DISPLAY", "fixture")
    with pytest.raises(ValueError, match="differ from the requested"):
        await clipboard_image()


def test_prepared_policy_comparison_fails_closed_and_never_claims_latency():
    capture = runpy.run_path(str(ROOT / "scripts/capture_runtime_policy.py"))["policy"]
    compare = runpy.run_path(str(ROOT / "scripts/compare_runtime_policy.py"))["compare"]
    policy = capture({"tools": [{"module": "one"}, {"module": "two"}]}, "fixture")
    cli = {"kind": "cli", "core_version": "test", "policy": policy}
    tui = {**copy.deepcopy(cli), "kind": "tui"}
    result = compare(cli, tui)
    assert result["prepared_fields_match"] and result["latency_verdict"] == "NOT ESTABLISHED"
    tui["policy"]["tools"].reverse()
    assert not compare(cli, tui)["prepared_fields_match"]
    del tui["policy"]["instruction_sha256"]
    with pytest.raises(ValueError, match="schema"):
        compare(cli, tui)

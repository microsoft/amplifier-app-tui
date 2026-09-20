"""Direction checks have negative fixtures; a green shape check is not a product verdict."""

import copy
import json
import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHECK = runpy.run_path(str(ROOT / "scripts/check_direction.py"))


def test_prepared_policy_capture_redacts_credentials_and_detects_changes():
    capture = runpy.run_path(str(ROOT / "scripts/capture_runtime_policy.py"))["policy"]
    plan = {
        "providers": [
            {"module": "provider-fixture", "config": {"api_key": "secret-one", "model": "first"}}
        ]
    }
    first = capture(plan, "synthetic instruction")
    plan["providers"][0]["config"]["api_key"] = "secret-two"
    assert capture(plan, "synthetic instruction") == first
    plan["providers"][0]["config"]["model"] = "second"
    assert capture(plan, "synthetic instruction") != first
    assert "secret" not in json.dumps(first) and "synthetic instruction" not in json.dumps(first)


def test_current_direction_and_work_references():
    report = CHECK["check_repository"](ROOT)
    assert report["formal_verdicts_generated"] is False
    assert len(report["work_items"]) >= 2
    assert report["method_source_integrity"].startswith("not checked")


@pytest.mark.parametrize("state", ["DRAFT", "RATIFIED 2026-09-12", "LOCKED 2026-09-12"])
def test_states_are_not_frozen_to_draft(state):
    text = (ROOT / "contracts/session.v1.md").read_text().replace("(DRAFT)", f"({state})", 1)
    result = CHECK["check_document"](text, "example")
    assert result["state"] == state.split()[0]
    # Syntax acceptance is not evidence of a steward's word or locking conditions.


@pytest.mark.parametrize(
    "change, reason",
    [
        (lambda text: text.replace("(DRAFT)", "(RATIFIED)", 1), "date"),
        (lambda text: text.replace("(DRAFT)", "(DRAFT RATIFIED)", 1), "heading"),
        (lambda text: text.replace("## What it is", "## Other section", 1), "section order"),
        (lambda text: text.replace("Broken:", "Something:", 1), "observable failure"),
        (lambda text: text.replace("2. **", "1. **", 1), "promise identity"),
        (lambda text: text.replace("```", "", 2), "artifact"),
        (lambda text: text + "\n" * 101, "line budget"),
    ],
)
def test_malformed_contracts_are_rejected(change, reason):
    text = (ROOT / "contracts/session.v1.md").read_text()
    with pytest.raises(ValueError, match=reason):
        CHECK["check_document"](change(text), "invalid")


def test_non_contiguous_promise_numbers_are_valid():
    text = (ROOT / "contracts/continuity.v1.md").read_text()
    promises = CHECK["check_document"](text, "current")["promises"]
    retired, replacement = promises[-1], promises[-1] + 4
    text = text.replace(f"{retired}. **", f"{replacement}. **", 1)
    assert CHECK["check_document"](text, "retired-number")["promises"] == [
        *promises[:-1],
        replacement,
    ]


def test_vision_signs_need_person_and_number():
    text = (ROOT / "docs/VISION.md").read_text()
    text = text.replace(
        "- A developer types a 3-line correction", "- Someone types a multiline correction"
    )
    with pytest.raises(ValueError, match="person and number"):
        CHECK["check_document"](text, "vision", vision=True)


@pytest.mark.parametrize("source", ["session.v1:999", "nonexistent.v1:1", "convenience"])
def test_untraceable_work_is_rejected(source):
    contracts = {"session.v1": {"promises": [1, 2, 3]}}
    text = f"| UI-01 | {source} | gap | test fails on loss | Not started |"
    with pytest.raises(ValueError):
        CHECK["check_plan"](text, contracts)


def test_duplicate_work_identity_is_rejected():
    row = "| UI-01 | session.v1:1 | gap | printed test rejects loss | Not started |"
    with pytest.raises(ValueError, match="Duplicate"):
        CHECK["check_plan"](row + "\n" + row, {"session.v1": {"promises": [1]}})


def test_missing_links_are_rejected(tmp_path):
    (tmp_path / "README.md").write_text("[missing](notes/missing.md)")
    with pytest.raises(ValueError, match="missing link"):
        CHECK["check_links"](tmp_path)


def test_source_budget_includes_frontend_languages_not_generated_dependencies(tmp_path):
    for name in (
        "src/a.py",
        "frontends/rust/src/main.rs",
        "frontends/ts/app.tsx",
        "frontends/ts/node_modules/vendor/index.ts",
        "frontends/rust/target/generated.rs",
    ):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    assert len(CHECK["source_files"](tmp_path)) == 3


def test_local_method_archive_matches_pin_when_available():
    receipt = json.loads((ROOT / "notes/method-source.json").read_text())
    archive = ROOT / receipt["archive_filename"]
    if not archive.exists():
        pytest.skip("Private source archive is deliberately not distributed")
    CHECK["verify_archive"](archive, receipt)
    altered = copy.deepcopy(receipt)
    altered["commit"] = "0" * 40
    with pytest.raises(ValueError, match="commit differs"):
        CHECK["verify_archive"](archive, altered)


def test_private_archive_is_ignored_and_excluded_from_packages():
    import subprocess
    import tomllib

    name = json.loads((ROOT / "notes/method-source.json").read_text())["archive_filename"]
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert "**/*.zip" in config["tool"]["hatch"]["build"]["exclude"]
    if (ROOT / ".git").exists():
        assert subprocess.run(["git", "check-ignore", "-q", name], cwd=ROOT).returncode == 0

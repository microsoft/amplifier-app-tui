"""Real public seams and bounded evidence; no private runtime state reconstruction."""

import asyncio
import hashlib
import json
import shlex
import sys

import pytest
from test_navigation import bridge_for
from test_workspace_review import git

from amplifier_tui.inspection import Inspection
from amplifier_tui.workspace_review import ToolEvidence, junit_observation, junit_target


async def test_nested_interrupted_adoption_does_not_execute_ancestors(
    prepared, tmp_path, monkeypatch
):
    from amplifier_tui import composition

    bridge, _ = await bridge_for(prepared, tmp_path, tmp_path)
    host = bridge.host
    create = composition.create_owned_session
    parent_entered = asyncio.Event()

    async def owned(*args, **kwargs):
        session = await create(*args, **kwargs)
        if kwargs.get("session_id") != "captured-parent":
            return session

        class Parent:
            def __getattr__(self, name):
                return getattr(session, name)

            async def execute(self, instruction):
                parent_entered.set()
                await asyncio.Future()

        return Parent()

    monkeypatch.setattr(composition, "create_owned_session", owned)
    parent_task = asyncio.create_task(
        host.children.spawn("self", "parent", host.session, {}, sub_session_id="captured-parent")
    )
    child_task = None
    try:
        await asyncio.wait_for(parent_entered.wait(), 5)
        parent = host.children.active["captured-parent"]
        child_task = asyncio.create_task(
            host.children.spawn("self", "child", parent, {}, sub_session_id="captured-nested")
        )
        async with asyncio.timeout(5):
            while not host.children.active.get("captured-nested"):
                await asyncio.sleep(0.001)
        child_task.cancel()
        await asyncio.gather(child_task, return_exceptions=True)
        parent_task.cancel()
        await asyncio.gather(parent_task, return_exceptions=True)
        source = host.store.path / "children"
        originals = {path: path.read_bytes() for path in source.glob("*.json")}
        row = originals[source / "captured-nested.json"]
        request = dict(
            op="recover_child",
            session_id=host.session_id,
            source=host.session_id,
            child="captured-nested",
            sha256=hashlib.sha256(row).hexdigest(),
            text="Compute once",
            confirm=True,
        )
        # Cyclic/missing ancestry cannot authorize execution.
        ancestor = source / "captured-parent.json"
        value = json.loads(originals[ancestor])
        value["parent"] = "captured-nested"
        ancestor.write_text(json.dumps(value))
        assert not bridge.command(request)[0]
        value["parent"] = "missing-ancestor"
        ancestor.write_text(json.dumps(value))
        assert not bridge.command(request)[0]
        ancestor.write_bytes(originals[ancestor])
        assert bridge.command(request)[0]
        await host.task
        adopted = [r for r in host.children.records.values() if r["metadata"].get("recovery")]
        assert len(adopted) == 1 and adopted[0]["status"] == "completed"
        assert adopted[0]["parent"] == host.session_id
        assert adopted[0]["metadata"]["recovery"]["reparented"]
        assert len(adopted[0]["metadata"]["recovery"]["ancestry"]) == 1
        assert all(path.read_bytes() == raw for path, raw in originals.items())
        assert host.children.records["captured-parent"]["status"] == "interrupted"
    finally:
        for task in (child_task, parent_task):
            if task:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        await bridge.close()


async def test_actual_pytest_report_is_versioned_not_semantic_coverage(tmp_path):
    git(tmp_path, "init")
    (tmp_path / "test_sample.py").write_text(
        "def test_pass(): assert True\ndef test_fail(): assert False\n"
    )
    observer = ToolEvidence(tmp_path)
    command = [sys.executable, "-m", "pytest", "-q", "test_sample.py", "--junitxml=report.xml"]
    data = {
        "tool_name": "bash",
        "tool_call_id": "check",
        "tool_input": {"command": shlex.join(command)},
    }
    await observer.observe("tool:pre", data, session="root", turn="first", agent="root")
    process = await asyncio.create_subprocess_exec(
        *command, cwd=tmp_path, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
    )
    await process.communicate()
    result = await observer.observe(
        "tool:post",
        {**data, "result": {"success": False, "output": {"returncode": process.returncode}}},
        session="root",
        turn="first",
        agent="root",
    )
    assert result["returncode"] == 1
    assert result["test_report"]["counts"] == {
        "tests": 2,
        "passed": 1,
        "failed": 1,
        "errors": 0,
        "skipped": 0,
    }
    assert (
        result["test_report"]["sha256"]
        == hashlib.sha256((tmp_path / "report.xml").read_bytes()).hexdigest()
    )
    await observer.observe("tool:pre", data, session="root", turn="stale", agent="root")
    stale = await observer.observe("tool:post", data, session="root", turn="stale", agent="root")
    assert "not attributed" in stale["test_report"]["status"]
    assert "counts" not in stale["test_report"]


@pytest.mark.parametrize(
    "command",
    [
        "echo pytest --junitxml=report.xml",
        "pytest --junitxml=../report.xml",
        "pytest --junitxml=/tmp/report.xml",
        "pytest --junitxml=report.xml; echo x",
        "pytest --junitxml=a --junitxml=b",
    ],
)
def test_report_target_refuses_ambiguous_shell_or_path(command):
    assert junit_target(command) is None


@pytest.mark.parametrize(
    "xml",
    [
        "<!DOCTYPE test><testsuites/>",
        "<testsuite><testcase>",
        "<testsuite tests='100'/>",
        "<not-junit/>",
    ],
)
def test_invalid_junit_never_claims_test_counts(tmp_path, xml):
    (tmp_path / "report.xml").write_text(xml)
    assert "counts" not in junit_observation(tmp_path, "report.xml", {"status": "absent"})


async def test_budget_capture_is_numeric_dispatch_evidence_not_private_context(host):
    data = {
        "provider": "fixture",
        "model": "explicit-model",
        "max_tokens": True,
        "raw": {
            "max_output_tokens": 8000,
            "thinking": {"budget_tokens": 2000},
            "authorization": "must-not-copy",
            "messages": ["private content"],
        },
    }
    await host._observe("llm:request", data)
    rows = host.inspection.catalog(host, "context")["rows"]
    row = next(row for row in rows if row.get("event") == "llm:request")
    detail = json.loads(row["detail"])["request_budget"]
    assert detail["max_output_tokens"] == 8000 and detail["thinking_budget"] == 2000
    assert "max_tokens" not in detail
    assert "must-not-copy" not in row["detail"] and "private content" not in row["detail"]
    assert not host.session.coordinator.get("providers")["fixture"].calls
    assert not host.inspection.capture_next
    assert set(Inspection.request_budget({"max_tokens": float("inf")})) == {"scope"}

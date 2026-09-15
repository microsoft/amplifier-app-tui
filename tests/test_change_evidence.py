import hashlib

from test_workspace_review import git

from amplifier_tui.workspace_review import ToolEvidence


async def test_file_versions_agent_and_call_are_correlated(tmp_path):
    file = tmp_path / "source.py"
    file.write_text("before\n")
    observer = ToolEvidence(tmp_path)
    data = {
        "tool_name": "edit_file",
        "tool_call_id": "call-1",
        "tool_input": {"file_path": str(file)},
    }
    assert (
        await observer.observe("tool:pre", data, session="child-1", turn="turn", agent="coder")
        is None
    )
    file.write_text("after\n")
    row = await observer.observe(
        "tool:post",
        {**data, "result": {"success": True}},
        session="child-1",
        turn="turn",
        agent="coder",
    )
    assert row["source_session"] == "child-1" and row["agent"] == "coder"
    assert row["tool_call_id"] == "call-1" and row["changed"] == ["source.py"]
    assert row["before"]["files"]["source.py"] == hashlib.sha256(b"before\n").hexdigest()
    assert row["after"]["files"]["source.py"] == hashlib.sha256(b"after\n").hexdigest()
    assert "external writers" in row["status"] and row["tool_success"] is True
    assert not observer.pending


async def test_command_versions_and_overlap_do_not_invent_test_verdict(tmp_path):
    git(tmp_path, "init")
    (tmp_path / "source.py").write_text("unchanged")
    observer = ToolEvidence(tmp_path)
    command = {
        "tool_name": "bash",
        "tool_call_id": "test-1",
        "tool_input": {"command": "test command"},
    }
    other = {
        "tool_name": "write_file",
        "tool_call_id": "write-1",
        "tool_input": {"path": "source.py"},
    }
    await observer.observe("tool:pre", command, session="root", turn="turn", agent="root")
    await observer.observe("tool:pre", other, session="child", turn="turn", agent="coder")
    row = await observer.observe(
        "tool:post",
        {**command, "result": {"success": False}},
        session="root",
        turn="turn",
        agent="root",
    )
    assert row["before"]["sha256"] == row["after"]["sha256"]
    assert row["command"] == "test command" and row["tool_success"] is False
    assert row["overlapping_tools"] and not row["changed"]
    assert "test-coverage" in row["scope"]


async def test_missing_unsafe_large_and_unpaired_sources_are_explicit(tmp_path):
    observer = ToolEvidence(tmp_path)
    data = {"tool_name": "write_file", "tool_call_id": "create", "tool_input": {"path": "new.txt"}}
    await observer.observe("tool:pre", data, session="root", turn="turn", agent="root")
    (tmp_path / "new.txt").write_text("new")
    row = await observer.observe("tool:post", data, session="root", turn="turn", agent="root")
    assert row["before"]["files"] == {"new.txt": "absent"}
    assert row["changed"] == ["new.txt"]
    assert (
        await observer.observe("tool:post", data, session="root", turn="other", agent="root")
        is None
    )
    (tmp_path / "large").write_bytes(b"x" * 65537)
    for name in ("../outside", "large"):
        row = await observer.snapshot("edit_file", {"path": name})
        assert row["partial"] and row["files"][name] == "unavailable"


async def test_command_links_only_matching_prior_agent_versions(tmp_path):
    git(tmp_path, "init")
    file = tmp_path / "source.py"
    file.write_text("old")
    observer = ToolEvidence(tmp_path)
    edit = {"tool_name": "edit_file", "tool_call_id": "edit", "tool_input": {"path": "source.py"}}
    await observer.observe("tool:pre", edit, session="child", turn="one", agent="coder")
    file.write_text("new")
    await observer.observe("tool:post", edit, session="child", turn="one", agent="coder")
    command = {"tool_name": "bash", "tool_call_id": "test", "tool_input": {"command": "pytest"}}
    for changed in (False, True):
        await observer.observe("tool:pre", command, session="root", turn="two", agent="tester")
        if changed:
            file.write_text("concurrent edit")
        result = await observer.observe(
            "tool:post",
            {**command, "result": {"success": True, "output": {"returncode": 0}}},
            session="root",
            turn="two",
            agent="tester",
        )
        assert bool(result["matching_prior_changes"]) is not changed
        assert result["returncode"] == 0
        if not changed:
            prior = result["matching_prior_changes"][0]
            assert prior["agent"] == "coder" and prior["tool_call_id"] == "edit"
            assert prior["sha256"] == hashlib.sha256(b"new").hexdigest()
        else:
            assert result["source_stability"] == "changed during command"


async def test_missing_post_keeps_pre_effect_evidence_once(tmp_path):
    observer = ToolEvidence(tmp_path)
    data = {"tool_name": "write_file", "tool_call_id": "lost", "tool_input": {"path": "file"}}
    await observer.observe("tool:pre", data, session="child", turn="turn", agent="coder")
    (row,) = observer.interrupted()
    assert row["before"]["files"] == {"file": "absent"}
    assert row["after"] is None and row["tool_success"] is None
    assert "unknown" in row["status"] and not observer.interrupted()

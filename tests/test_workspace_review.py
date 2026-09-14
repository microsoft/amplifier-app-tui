"""Real temporary Git repositories; inspection may not mutate or run repo helpers."""

import asyncio
import subprocess

import pytest
from test_navigation import bridge_for

from amplifier_tui.workspace_review import GitReview


def git(root, *args):
    return subprocess.check_output(
        ["git", "-c", "user.name=TUI test", "-c", "user.email=tui-test@example.invalid", *args],
        cwd=root,
        stderr=subprocess.DEVNULL,
    )


@pytest.fixture
def repository(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init")
    (root / "file.txt").write_text("base\n")
    git(root, "add", "file.txt")
    git(root, "commit", "-m", "fixture base")
    (root / "file.txt").write_text("staged\n")
    git(root, "add", "file.txt")
    (root / "file.txt").write_text("working\n")
    (root / "untracked.txt").write_text("private untracked content")
    return root


async def test_staged_worktree_untracked_and_no_mutation(repository):
    before_index = (repository / ".git/index").read_bytes()
    before_head = git(repository, "rev-parse", "HEAD")
    review = GitReview(repository)
    snapshot = await review.refresh()
    assert {r["scope"] for r in snapshot["rows"]} == {"staged", "unstaged", "untracked"}
    for row in snapshot["rows"]:
        result = await review.diff(row["id"], snapshot["token"])
        if row["scope"] == "staged":
            assert "-base" in result["text"] and "+staged" in result["text"]
            assert result["base"].startswith("HEAD → index")
        elif row["scope"] == "unstaged":
            assert "-staged" in result["text"] and "+working" in result["text"]
        else:
            assert "private untracked" not in result["text"] and "not read" in result["text"]
    assert (repository / ".git/index").read_bytes() == before_index
    assert git(repository, "rev-parse", "HEAD") == before_head
    assert not (repository / ".git/index.lock").exists()


async def test_nested_cwd_literal_paths_unborn_and_binary(tmp_path):
    git(tmp_path, "init")
    (tmp_path / "nested").mkdir()
    name = "nested/:(glob)*\nodd.txt"
    (tmp_path / name).write_text("literal path\n")
    (tmp_path / "binary").write_bytes(b"\0\1\2")
    git(tmp_path, "--literal-pathspecs", "add", "--", name, "binary")
    review = GitReview(tmp_path / "nested")
    snapshot = await review.refresh()
    assert len(snapshot["rows"]) == 2
    for row in snapshot["rows"]:
        result = await review.diff(row["id"], snapshot["token"])
        assert (
            "literal path" in result["text"]
            if row["path"] == name
            else "Binary files" in result["text"]
        )


async def test_rename_and_status_race_are_disclosed(repository):
    git(repository, "mv", "file.txt", "renamed.txt")
    review = GitReview(repository)
    snapshot = await review.refresh()
    row = next(r for r in snapshot["rows"] if r["scope"] == "staged")
    result = await review.diff(row["id"], snapshot["token"])
    assert "not an atomic snapshot" in result["notice"]
    (repository / "another-untracked").write_text("changed")
    with pytest.raises(ValueError, match="changed"):
        await review.diff(row["id"], snapshot["token"])


async def test_external_filters_diff_and_fsmonitor_cannot_execute(repository):
    # A deliberately observable configured helper. Ordinary git diff/status could
    # invoke this filter; the review must explicitly disable it before either.
    marker = repository / "helper-ran"
    command = f"touch '{marker}'"
    for key in (
        "filter.test.clean",
        "filter.test.process",
        "diff.test.command",
        "diff.test.textconv",
        "core.fsmonitor",
    ):
        git(repository, "config", key, command)
    git(repository, "config", "filter.test.required", "true")
    (repository / ".gitattributes").write_text("*.txt filter=test diff=test\n")
    review = GitReview(repository)
    snapshot = await review.refresh()
    for row in snapshot["rows"]:
        await review.diff(row["id"], snapshot["token"])
    assert not marker.exists()


async def test_oversized_diff_fails_without_partial_success(repository, monkeypatch):
    review = GitReview(repository)
    snapshot = await review.refresh()
    row = next(r for r in snapshot["rows"] if r["scope"] == "unstaged")
    (repository / "file.txt").write_text("large line" * 10000)
    monkeypatch.setattr("amplifier_tui.workspace_review.LIMIT", 500)
    with pytest.raises(ValueError, match="exceeds"):
        await review.diff(row["id"], snapshot["token"])


async def test_review_is_local_session_scoped_and_context_free(prepared, tmp_path, repository):
    bridge, events = await bridge_for(prepared, tmp_path / "state", repository)
    try:
        assert not bridge.command(
            {"op": "workspace_changes", "request_id": "stale", "session_id": "stale"}
        )[0]
        assert bridge.command(
            {"op": "workspace_changes", "request_id": "read", "session_id": bridge.host.session_id}
        )[0]
        await bridge.review_task
        result = next(e for e in events if e["type"] == "workspace_changes")
        assert result["rows"] and "error" not in result
        assert bridge.host.session.coordinator.get("providers")["fixture"].calls == []
        assert await bridge.host.session.coordinator.get("context").get_messages() == []
        assert not bridge.command({"op": "workspace_changes", "request_id": "missing-identity"})[0]
    finally:
        await bridge.close()


async def test_cancel_and_timeout_reap_git(repository, monkeypatch):
    review = GitReview(repository)
    real_create = asyncio.create_subprocess_exec
    processes = []

    async def slow(*args, **kwargs):
        process = await real_create("sleep", "30", **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", slow)
    task = asyncio.create_task(review.refresh())
    while not processes:
        await asyncio.sleep(0.005)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert processes[0].returncode is not None


async def test_not_a_repository_explains_unavailability(tmp_path):
    with pytest.raises(ValueError, match="not a repository"):
        await GitReview(tmp_path).refresh()


async def test_non_utf8_path_is_display_only_but_diff_target_stays_exact(repository):
    import json
    import os

    path = os.fsdecode(b"bad-\xff.txt")
    (repository / path).write_text("exact file content\n")
    git(repository, "add", "--", path)
    review = GitReview(repository)
    snapshot = await review.refresh()
    json.dumps(snapshot, ensure_ascii=False).encode("utf-8")
    row = next(r for r in snapshot["rows"] if r["path"].startswith("bad-"))
    result = await review.diff(row["id"], snapshot["token"])
    assert "exact file content" in result["text"]
    json.dumps(result, ensure_ascii=False).encode("utf-8")


def test_local_git_reads_do_not_consume_execution_admission():
    from amplifier_tui.frontend_bridge import Admission

    admission = Admission()
    for i in range(4100):
        reply = admission.apply(
            {"version": 1, "request_id": str(i), "op": "workspace_changes"},
            lambda request: (True, "local read"),
        )
        assert reply["accepted"]
    assert not admission.replies

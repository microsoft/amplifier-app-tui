"""Conflict proposals against real Git indexes; no fixture-as-product claims."""

import json
import os

import pytest
from test_navigation import bridge_for
from test_workspace_review import git

from amplifier_tui.workspace_review import GitReview


@pytest.fixture
def conflict(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init")
    (root / "file.txt").write_text("base\n")
    git(root, "add", ".")
    git(root, "commit", "-m", "base")
    # Construct an unmerged index without relying on branch names or merge helpers.
    import subprocess

    base = git(root, "rev-parse", "HEAD:file.txt").strip().decode()
    subprocess.run(
        ["git", "update-index", "--index-info"],
        cwd=root,
        input=(
            f"0 {'0' * 40}\tfile.txt\n"
            + "".join(f"100644 {base} {stage}\tfile.txt\n" for stage in (1, 2, 3))
        ).encode(),
        check=True,
    )
    (root / "file.txt").write_text("<<<<<<< ours\nours\n=======\ntheirs\n>>>>>>> theirs\n")
    return root


async def captured(root):
    review = GitReview(root)
    listing = await review.refresh()
    row = next(r for r in listing["rows"] if r["scope"] == "conflict")
    return review, await review.prepare_edit(row["id"], listing["token"])


async def test_capture_then_apply_preserves_backup_index_and_mode(conflict, tmp_path):
    path = conflict / "file.txt"
    path.chmod(0o755)
    before = path.read_bytes()
    index = (conflict / ".git/index").read_bytes()
    review, proposal = await captured(conflict)
    assert path.read_bytes() == before
    result = await review.apply_edit(proposal["id"], "resolved 🙂\n", tmp_path / "backups")
    assert path.read_text() == "resolved 🙂\n"
    assert path.stat().st_mode & 0o777 == 0o755
    assert (conflict / ".git/index").read_bytes() == index
    assert json.loads(open(result["backup"]).read())["text"].encode() == before
    assert os.stat(result["backup"]).st_mode & 0o777 == 0o600
    assert not list(conflict.glob(".amplifier-review-*.tmp"))
    with pytest.raises(ValueError, match="expired"):
        await review.apply_edit(proposal["id"], "retry", tmp_path / "backups")


@pytest.mark.parametrize("change", ["content", "symlink", "hardlink", "status"])
async def test_stale_or_unsafe_target_refuses_without_loss(conflict, tmp_path, change):
    review, proposal = await captured(conflict)
    path = conflict / "file.txt"
    if change == "content":
        path.write_text("new human work\n")
    elif change == "symlink":
        path.unlink()
        (tmp_path / "outside").write_text("outside\n")
        path.symlink_to(tmp_path / "outside")
    elif change == "hardlink":
        os.link(path, tmp_path / "linked")
    else:
        (conflict / "other").write_text("new status")
    before = path.read_bytes()
    with pytest.raises((ValueError, OSError)):
        await review.apply_edit(proposal["id"], "proposal", tmp_path / "backups")
    assert path.read_bytes() == before
    assert not list(conflict.glob(".amplifier-review-*.tmp"))


async def test_backup_failure_and_mid_write_race_leave_newer_source(
    conflict, tmp_path, monkeypatch
):
    from amplifier_tui import conversations

    review, proposal = await captured(conflict)
    original = conversations.atomic_json
    path = conflict / "file.txt"

    def failed(*args):
        raise OSError("injected backup failure")

    monkeypatch.setattr(conversations, "atomic_json", failed)
    with pytest.raises(OSError, match="backup failure"):
        await review.apply_edit(proposal["id"], "candidate", tmp_path / "backup")
    assert path.read_text() == proposal["text"]

    def concurrent(*args):
        original(*args)
        path.write_text("concurrent human work")

    monkeypatch.setattr(conversations, "atomic_json", concurrent)
    with pytest.raises(ValueError, match="changed before"):
        await review.apply_edit(proposal["id"], "candidate", tmp_path / "backup")
    assert path.read_text() == "concurrent human work"
    assert not list(conflict.glob(".amplifier-review-*.tmp"))


async def test_confirmation_scope_and_no_provider_call(prepared, tmp_path, conflict):
    bridge, events = await bridge_for(prepared, tmp_path / "state", conflict)
    try:

        def command(op, **payload):
            return bridge.command(
                {"op": op, "request_id": op, "session_id": bridge.host.session_id, **payload}
            )

        assert command("workspace_changes")[0]
        await bridge.review_task
        listing = next(e for e in events if e["type"] == "workspace_changes")
        row = next(r for r in listing["rows"] if r["scope"] == "conflict")
        assert command("workspace_edit_prepare", id=row["id"], token=listing["token"])[0]
        await bridge.review_task
        proposal = next(e for e in events if e["type"] == "workspace_edit_prepare")
        assert not command("workspace_edit_apply", id=proposal["id"], text="resolved")[0]
        assert command(
            "workspace_edit_apply", id=proposal["id"], text="resolved", confirm_write=True
        )[0]
        assert not command("submit", text="racing submission")[0]
        await bridge.review_task
        assert "error" not in events[-1]
        assert (conflict / "file.txt").read_text() == "resolved"
        assert bridge.host.session.coordinator.get("providers")["fixture"].calls == []
        assert await bridge.host.session.coordinator.get("context").get_messages() == []
    finally:
        await bridge.close()


@pytest.mark.skipif(os.environ.get("TUI_TEST_CANDIDATES") != "1", reason="Build native client")
def test_native_conflict_proposal_confirmation_preserves_composer(conflict, tmp_path):
    import sys
    from pathlib import Path

    from interaction_probe import capture
    from questions_probe import wait_ready
    from terminal_probe import Probe
    from test_daily_terminal import action, dismiss
    from test_reading_terminal import draft_is

    root = Path(__file__).resolve().parents[1]
    before = (conflict / "file.txt").read_text()
    index = (conflict / ".git/index").read_bytes()
    probe = Probe(
        [
            sys.executable,
            str(root / "scripts/run.py"),
            "--fixture",
            "--no-install",
            "--cwd",
            str(conflict),
            "--state-dir",
            str(tmp_path / "state"),
        ],
        cols=160,
    )
    try:
        wait_ready(probe)
        probe.send(b"Keep my main draft")
        action(probe, "Workspace changes", "Workspace changes · observed")
        probe.send(b"conflict\r")
        probe.wait("Workspace diff · read-only")
        probe.send(b"Prepare conflict edit\r")
        probe.wait("Conflict file · original captured")
        assert (conflict / "file.txt").read_text() == before
        probe.send(b"\r")
        probe.wait("Edit conflict proposal")
        probe.send(b"human edit\r")
        probe.wait("Apply conflict proposal?")
        probe.wait("human edit")
        assert (conflict / "file.txt").read_text() == before
        capture(probe, "conflict-proposal-confirmation")
        probe.send(b"\r")
        probe.wait("replacement completed, index unchanged")
        assert (conflict / "file.txt").read_text() == before + "human edit"
        assert (conflict / ".git/index").read_bytes() == index
        capture(probe, "conflict-proposal-applied")
        dismiss(probe, "replacement completed, index unchanged")
        draft_is(probe, "Keep my main draft")
        journal = next((tmp_path / "state/conversations").glob("*/events.jsonl"))
        assert not any(
            json.loads(line)["kind"] == "turn.accepted" for line in journal.read_text().splitlines()
        )
    finally:
        probe.close()

"""Native terminal ownership flows with an isolated home and deterministic modules."""

import asyncio
import json
import os
import shlex
import sys
import uuid
from pathlib import Path

import pytest
from amplifier_foundation.session import (
    ReadyToRelease,
    SessionBusyError,
    SharedSessionStore,
    register_release_handler,
    request_release,
)
from test_shared_ownership import native as native

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from interaction_probe import action, capture  # noqa: E402
from terminal_probe import Probe  # noqa: E402

pytestmark = pytest.mark.skipif(
    os.environ.get("TUI_TEST_CANDIDATES") != "1", reason="Build native client"
)


@pytest.mark.parametrize("size", [(175, 50), (40, 20)])
async def test_native_readonly_takeover_park_and_fresh_send(native, tmp_path, size):
    launch, identity, history, messages = native
    home, cwd = Path(launch["cli_home"]), Path(launch["cwd"])
    bundle = ROOT / "src/amplifier_tui/fixtures/bundle.yaml"
    metadata = history.load_metadata()
    history.save_metadata({**metadata, "bundle": bundle.as_uri()})
    (home / "settings.yaml").write_text(
        json.dumps(
            {
                "bundle": {"active": bundle.as_uri()},
                "sources": {
                    "modules": {
                        name: str(ROOT.parent / f"amplifier-module-{name}")
                        for name in ("loop-streaming", "context-simple")
                    }
                },
                "updates": {"auto_prompt": False},
            }
        )
    )
    before = history.transcript_path.read_bytes()
    held = SharedSessionStore(cwd, identity).acquire(app="amplifier-cli")

    async def release(request):
        request.report_progress("persisting")
        return ReadyToRelease()

    registration = await register_release_handler(held, prepare_release=release)
    editor_release = tmp_path / "editor-release"
    editor_script = tmp_path / "editor.py"
    editor_script.write_text(
        "import pathlib,time\n"
        "print('External editor fixture waiting', flush=True)\n"
        f"while not pathlib.Path({str(editor_release)!r}).exists(): time.sleep(0.05)\n"
    )
    # Exercise the real native frontend and host entrypoint with only the idle
    # interval accelerated. Clock-controlled host tests pin the 300-second default.
    host_command = [
        sys.executable,
        "-c",
        "from amplifier_tui.host import SharedRuntimeBridge; "
        "SharedRuntimeBridge.idle_seconds = 3; "
        "from amplifier_tui.__main__ import main; main()",
        "--bridge",
        "--settings-policy",
        "cli",
        "--cli-home",
        str(home),
        "--cwd",
        str(cwd),
        "--state-dir",
        str(tmp_path / "tui"),
        "--no-install",
        "--resume",
        identity,
    ]
    p = Probe(
        [
            str(ROOT / "frontends/ratatui/target/release/amplifier-ratatui"),
            "--host-json",
            json.dumps(host_command),
        ],
        cwd=cwd,
        env={
            "AMPLIFIER_HOME": str(home),
            "VISUAL": f"{shlex.quote(sys.executable)} {shlex.quote(str(editor_script))}",
        },
        cols=size[0],
        rows=size[1],
        guard_terminal_modes=True,
    )
    try:
        await asyncio.to_thread(p.wait, "[Continue here]", 60)
        p.send(b"Unsent takeover draft\r")
        await asyncio.to_thread(p.wait, "Choose Continue here")
        assert history.transcript_path.read_bytes() == before
        capture(p, f"handoff-readonly-{size[0]}")
        await asyncio.to_thread(action, p, "Continue here", "Continue here; Send explicitly")
        await asyncio.to_thread(p.wait, "Unsent takeover draft")
        assert not held.active
        assert history.transcript_path.read_bytes() == before
        # Ask this actual TUI process to yield through Foundation's socket.
        store = SharedSessionStore(cwd, identity)
        try:
            unexpected = store.acquire(app="probe")
        except Exception as busy:
            owner = busy.owner
        else:
            unexpected.release()
            raise AssertionError("TUI did not acquire ownership")
        result = await request_release(
            store,
            expected_owner=owner,
            request_id=uuid.uuid4().hex,
            requester_app="synthetic-web",
            timeout=5,
        )
        assert result.status == "released"
        await asyncio.to_thread(p.wait, "[Continue here]")
        await asyncio.to_thread(p.wait, "Unsent takeover draft")
        assert history.transcript_path.read_bytes() == before
        capture(p, f"handoff-yielded-{size[0]}")
        await asyncio.to_thread(action, p, "Continue here", "Continue here; Send explicitly")
        await asyncio.to_thread(action, p, "Interact —", "Interact ·")
        # More than one complete idle interval, with no submitted work: keyboard
        # navigation, bracketed paste, focus return, mouse scroll and resize all
        # keep ownership alive without changing the canonical conversation.
        for event in (
            b"\x1b[D",
            b"\x1b[200~x\x1b[201~\x7f",
            b"\x1b[I",
            b"\x1b[<64;4;4M",
            None,
            b"\x1b[C",
        ):
            if event is None:
                p.resize(size[0] - 1, size[1])
            else:
                p.send(event)
            await asyncio.sleep(1.1)
            await asyncio.to_thread(p.read)
            try:
                unexpected = store.acquire(app="synthetic-observer")
            except SessionBusyError:
                pass
            else:
                unexpected.release()
                raise AssertionError("User activity did not retain ownership")
            assert history.transcript_path.read_bytes() == before
        capture(p, f"handoff-user-active-{size[0]}")
        await asyncio.to_thread(
            action, p, "Edit in external editor", "External editor fixture waiting"
        )
        await asyncio.sleep(4.2)  # Longer than the accelerated automatic idle interval.
        try:
            unexpected = store.acquire(app="synthetic-observer")
        except SessionBusyError:
            pass
        else:
            unexpected.release()
            raise AssertionError("External editor did not retain ownership")
        editor_release.touch()
        await asyncio.to_thread(p.wait, "Editor returned")
        p.send(b"\x1b")  # Return to native copy mode; keep the unsent draft.
        p.resize(*size)
        await asyncio.to_thread(p.wait, "session released while idle", 10)
        capture(p, f"handoff-parked-{size[0]}")
        external = store.acquire(app="synthetic-web")
        try:
            history.save_messages(
                messages
                + [
                    {"role": "user", "content": "External saved input"},
                    {"role": "assistant", "content": "External saved answer"},
                ]
            )
        finally:
            external.release()
        p.send(b"\r")  # Only this explicit Send may execute the retained draft.
        await asyncio.to_thread(p.wait, "Fixture round trip complete", 60)
        await asyncio.to_thread(p.wait_idle, 60)
        contents = history.load_messages()
        assert sum(m.get("content") == "Unsent takeover draft" for m in contents) == 1
        assert any(m.get("content") == "External saved answer" for m in contents)
        capture(p, f"handoff-continued-{size[0]}")
        assert "panicked" not in p.raw.decode(errors="replace")
    finally:
        editor_release.touch()  # Never strand the owned editor subprocess on failure.
        await asyncio.to_thread(p.close)
        assert b"\x1b[?1004h" in p.raw and b"\x1b[?1004l" in p.raw
        await registration.close()
        held.release()

"""Real PTY comparison using the workspace terminal-tester's capture implementation.

No screenshot timing is used as a latency measurement: that module intentionally
settles for 500 ms. Synthetic screenshots are local evidence, not product success.
"""

import argparse
import asyncio
import codecs
import json
import os
import select
import shlex
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
sys.path.insert(
    0, str(WORKSPACE / "amplifier-bundle-terminal-tester/modules/tool-terminal-inspector")
)
from amplifier_module_tool_terminal_inspector.session_manager import (  # noqa: E402
    PTYSession,
    SessionManager,
)


def read_utf8(self, timeout=0.01, max_reads=10):
    """Local observer adapter: preserve UTF-8 split across PTY read boundaries.

    Upstream's per-chunk decode(errors='replace') can manufacture replacement
    characters. Do not modify that independent checkout for our experiment.
    """
    if not hasattr(self, "_candidate_decoder"):
        self._candidate_decoder = codecs.getincrementaldecoder("utf-8")("replace")
    result = bytearray()
    for _ in range(max_reads):
        if not select.select([self.fd], [], [], timeout if not result else 0)[0]:
            break
        try:
            data = os.read(self.fd, 65536)
        except OSError:
            break
        if not data:
            break
        result.extend(data)
        self.stream.feed(self._candidate_decoder.decode(data))
    return bytes(result)


PTYSession._read_output = read_utf8


def render_visible_cursor(self, *args, **kwargs):
    # Local observer adapter: upstream uses a regular font even for bold and
    # omits italic/underline. Keep reference-font limitations with each image.
    from terminal_raster import render_terminal

    return render_terminal(self, *args, **kwargs)


PTYSession._render_image = render_visible_cursor


def manifest(session, status):
    path = WORKSPACE / "WORKSPACE-MANIFEST.json"
    data = json.loads(path.read_text()) if path.exists() else {"version": 1, "resources": []}
    identity = f"candidate-pty-{session.pid}"
    now = datetime.now(timezone.utc).isoformat()
    entry = next((r for r in data["resources"] if r["id"] == identity), None)
    if entry is None:
        entry = {
            "kind": "pty",
            "id": identity,
            "pid": session.pid,
            "note": "Isolated frontend comparison",
            "created_at": now,
            "teardown": f"kill -TERM {session.pid}",
        }
        data["resources"].append(entry)
    entry["status"] = status
    if status == "reaped":
        entry["reaped_at"] = now
    path.write_text(json.dumps(data, indent=2) + "\n")


async def wait_text(session, needle, timeout=10, absent=False):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        session._read_output(timeout=0.01, max_reads=10)
        if (needle in "\n".join(session.screen.display)) != absent:
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"Missing {needle!r}\n" + "\n".join(session.screen.display))


async def run(frontend, quick=False):
    evidence = ROOT / ".evidence/captures"
    manager = SessionManager(base_dir=evidence)
    command = shlex.join(
        [
            "env",
            "-u",
            "NO_COLOR",
            "COLORTERM=truecolor",
            sys.executable,
            str(ROOT / "scripts/compare.py"),
            frontend,
        ]
    )
    session = await manager.spawn("exec " + command, mode="pty", cols=120, rows=40)
    manifest(session, "active")
    captures = []

    async def capture(name):
        # The upstream PNG helper enumerates buffer.values(). After resize pyte
        # can insert rows out of order; restore numeric row order before capture.
        ordered = session.screen.buffer.copy()
        ordered.clear()
        for row in range(session.rows):
            ordered[row] = session.screen.buffer[row]
        session.screen.buffer = ordered
        snap = await session.screenshot()
        filename = f"{frontend}-{name}"
        (evidence / f"{filename}.txt").write_text(snap["text"])
        if snap["image_path"]:
            shutil.copyfile(snap["image_path"], evidence / f"{filename}.png")
        captures.append(filename)

    try:
        await wait_text(session, "Waiting for your decision")
        await capture("work-120x40")
        for cols in [160, 200]:
            session.resize(40, cols)
            await wait_text(session, "─" * cols)
            await capture(f"work-{cols}x40")
            assert session.screen.display[33][cols - 4] == "╮"
            assert session.screen.display[26][cols - 4] == "╮"
        session.resize(40, 120)
        await wait_text(session, "Enter send")
        if not quick:
            # Busy submit cannot destroy the supplied draft.
            os.write(session.fd, b"\r")
            await wait_text(session, "Busy")
            await wait_text(session, "Also check that permanent failures")
            await session.send(b"\x19", wait_ms=0)  # Allow c18; creates failed evidence.
            await wait_text(session, "simulated test failed")
            await session.send(b"\x05", wait_ms=0)
            await wait_text(session, "assert attempts")
            await capture("failed-evidence")
            await session.send(b"\x1b", wait_ms=0)
            await wait_text(session, "Evidence ·", absent=True)
            await session.send(b"\x1bOQ", wait_ms=0)  # F2
            await wait_text(session, "Focused regression tests")
            await capture("review")
            await session.send(b"\x1bOR", wait_ms=0)  # F3
            await wait_text(session, "Not available")
            await capture("system")
            await session.send(b"\x1bOP", wait_ms=0)  # F1
            await session.send(b"\r", wait_ms=0)
            await wait_text(session, "Working")
            await session.send(
                "\x1b[200~Keep the API stable.\nCheck permanent failures. 界 é 🦀\x1b[201~".encode(),
                wait_ms=0,
            )
            await wait_text(session, "Completed")
            await wait_text(session, "Check permanent failures.")
            await capture("streamed-draft")
            for cols, rows in [(80, 24), (60, 20), (120, 40)]:
                session.resize(rows, cols)
                await wait_text(session, "Enter send")
                await capture(f"resized-{cols}x{rows}")
            await wait_text(session, "Check permanent failures.")
        await session.send(b"\x11", wait_ms=0)
        deadline = time.monotonic() + 4
        while session.is_alive() and time.monotonic() < deadline:
            session._read_output(timeout=0.01, max_reads=10)
            await asyncio.sleep(0.01)
        # is_alive can report a zombie alive until close() reaps; independently
        # inspect waitpid without mistaking an uncollected child for a leak.
        pid, status = os.waitpid(session.pid, os.WNOHANG)
        if pid == 0:
            raise AssertionError("Quit did not terminate within deadline")
        assert os.waitstatus_to_exitcode(status) == 0
        print(json.dumps({"frontend": frontend, "captures": captures, "quit": "exit 0"}))
    finally:
        await manager.close_all()
        manifest(session, "reaped")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "frontend", choices=["ratatui", "opentui", "both"], default="both", nargs="?"
    )
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()
    for frontend in ["ratatui", "opentui"] if args.frontend == "both" else [args.frontend]:
        asyncio.run(run(frontend, args.quick))


if __name__ == "__main__":
    main()

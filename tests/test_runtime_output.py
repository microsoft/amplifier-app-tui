"""Private legacy-output compatibility; synthetic data, actual process descriptors."""

import asyncio
import json
import sys
from pathlib import Path

import pytest

from amplifier_tui.frontend_bridge import RuntimeOutput
from amplifier_tui.host import RuntimeBridge, SessionHost

ROOT = Path(__file__).resolve().parents[1]

# Real fixture host/modules plus an ordinary hook that writes to legacy streams.
# No model/provider service or personal account is used.
PROGRAM = r"""
import asyncio,logging,os,sys,time
from rich.console import Console
from amplifier_core import HookResult
from amplifier_tui.host import SessionHost
from amplifier_tui.__main__ import main
original = SessionHost.open
async def noisy_open(self,*args,**kwargs):
 print('BOOT-DIAGNOSTIC',flush=True)
 os.write(2,b'\x1b[31mNATIVE-DIAGNOSTIC\x1b[0m\n')
 await original(self,*args,**kwargs)
 async def diagnostic_hook(event,data):
  print('HOOK-DIAGNOSTIC',flush=True)
  Console(force_terminal=True).print('[cyan]RICH-DIAGNOSTIC[/cyan]')
  logging.warning('LOG-DIAGNOSTIC')
  child=await asyncio.create_subprocess_exec(sys.executable,'-c',
   "import os;os.write(1,b'SUBPROCESS-DIAGNOSTIC\\n')")
  await child.wait()
  # These are invented values, including the split-write sensitive line.
  os.write(2,b'Authorization: Bear')
  os.write(2,b'er fixture-auth-value\n')
  os.write(1,b'\x1b]52;c;fixture-clipboard\x07AFTER-OSC\n')
  return HookResult()
 self.session.coordinator.hooks.register('tool:pre',diagnostic_hook,priority=2)
SessionHost.open=noisy_open
main()
"""


def command(tmp_path):
    return [
        sys.executable,
        "-u",
        "-c",
        PROGRAM,
        "--bridge",
        "--fixture",
        "--no-install",
        "--state-dir",
        str(tmp_path / "state"),
        "--cwd",
        str(tmp_path),
        "--sources",
        str(ROOT.parent / "tui-sources.json"),
    ]


def test_split_escape_controls_credentials_and_utf8_are_not_terminal_input(monkeypatch):
    monkeypatch.setenv("FIXTURE_API_KEY", "invented-environment-value")
    sink = RuntimeOutput()
    monkeypatch.setenv("FIXTURE_LATE_TOKEN", "invented-late-value")
    raw = (
        "\x1b[31mReadable café\x1b[0m\n"
        "\x1b]52;c;not-a-clipboard\nmore-hidden\x1b\\after OSC\n"
        "\x1bPprivate-dcs\x1b\\after DCS\n"
        "\x9dprivate-c1\x9cafter C1\n"
        "Authorization: Bearer fixture-auth-value\n"
        "api_key='fixture-key-value'\n"
        "opaque invented-environment-value\n"
        "opaque invented-late-value\n"
        '"token": "fixture-token-value"\n'
        "-----BEGIN PRIVATE KEY-----\nfixture-pem-body\n-----END PRIVATE KEY-----\n"
        "Downloading https://fixture.invalid/private?key=value next\n"
        "Safe \u202eordinary text\n"
    ).encode()
    for byte in raw:
        sink.feed(bytes([byte]))
    text = json.dumps(sink.catalog(), ensure_ascii=False)
    for expected in ("Readable café", "after OSC", "after DCS", "after C1", "Safe ordinary"):
        assert expected in text
    for absent in (
        "not-a-clipboard",
        "more-hidden",
        "private-dcs",
        "private-c1",
        "fixture-auth-value",
        "fixture-key-value",
        "fixture-token-value",
        "invented-environment-value",
        "invented-late-value",
        "fixture-pem-body",
        "fixture.invalid",
        "\u202e",
    ):
        assert absent not in text
    assert "endpoint omitted" in text and "sensitive diagnostic line omitted" in text


def test_ring_and_line_bounds_disclose_omission_without_retaining_prefixes():
    sink = RuntimeOutput()
    sink.feed(b"x" * (sink.MAX_LINE * 4))
    assert not sink.line and sink.oversize
    sink.feed(b"END-OF-LONG-LINE\n")
    assert not sink.catalog()["rows"] and sink.catalog()["partial"]
    for i in range(512):
        sink.feed(f"row {i}\r".encode())
    view = sink.catalog()
    assert len(view["rows"]) == sink.MAX_ROWS
    assert view["rows"][0]["label"] == "row 511"
    assert sink.omitted == 1 + 512 - sink.MAX_ROWS
    sink.feed(("界" * 4096 + "\n").encode() * 128)
    assert sink.bytes <= sink.MAX_BYTES
    assert "END-OF-LONG-LINE" not in str(sink.catalog())
    assert sink.catalog()["partial"]


def test_no_partial_line_exposure_and_unsupported_capture_is_explicit(tmp_path):
    sink = RuntimeOutput()
    sink.feed(b"partial")
    assert not sink.catalog()["rows"]
    sink.feed(b" line\n")
    assert sink.catalog()["rows"][0]["label"] == "partial line"
    host = SessionHost()
    records = []
    bridge = RuntimeBridge(host, None, records.append, True, tmp_path)
    request = {"op": "inspect", "category": "runtime_output", "session_id": host.session_id}
    assert bridge.command(request)[0]
    assert records[-1]["partial"] and "unavailable" in records[-1]["scope"]
    bridge.runtime_output = sink
    assert not bridge.command({**request, "session_id": "other"})[0]
    assert bridge.command(request)[0]
    assert records[-1]["rows"][0]["label"] == "partial line"
    assert host.sequence == 0 and not host.inspection.rows


async def test_actual_host_captures_hook_streams_without_protocol_or_history_pollution(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("AMPLIFIER_TUI_CHILD_CONCURRENCY", "2")
    process = await asyncio.create_subprocess_exec(
        *command(tmp_path),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    records = []

    async def until(predicate):
        try:
            async with asyncio.timeout(20):
                while line := await process.stdout.readline():
                    record = json.loads(line)
                    records.append(record)
                    if predicate(record):
                        return record
        except TimeoutError:
            raise AssertionError(
                [(r.get("type"), r.get("status"), r.get("lines")) for r in records]
            ) from None
        raise AssertionError("Fixture host closed before requested observation")

    def send(op, **kwargs):
        process.stdin.write((json.dumps({"version": 1, "op": op, **kwargs}) + "\n").encode())

    try:
        snapshot = await until(lambda r: r.get("type") == "snapshot")
        identity = snapshot["session_id"]
        await until(lambda r: r.get("type") == "state" and r.get("ready"))
        system = next(r for r in records if r.get("type") == "system")
        assert any("2 active per parent" in line for line in system["lines"])
        assert not any("depth 3" in line for line in system["lines"])
        send("submit", text="Exercise the fixture tool", request_id="one", session_id=identity)
        await until(
            lambda r: r.get("type") == "state" and r.get("status", "").startswith("Completed")
        )

        # Reader runs independently; wait for its count-only publication, not a guessed sleep.
        def captured(r):
            return r.get("type") == "runtime_output_status" and r.get("lines", 0) >= 8

        if not any(captured(r) for r in records):
            await until(captured)
        send("inspect", category="runtime_output", request_id="two", session_id=identity)
        view = await until(lambda r: r.get("type") == "inspection")
        shown = json.dumps(view)
        for expected in (
            "BOOT-DIAGNOSTIC",
            "NATIVE-DIAGNOSTIC",
            "HOOK-DIAGNOSTIC",
            "RICH-DIAGNOSTIC",
            "LOG-DIAGNOSTIC",
            "SUBPROCESS-DIAGNOSTIC",
            "AFTER-OSC",
        ):
            assert expected in shown
        assert "fixture-auth-value" not in shown and "fixture-clipboard" not in shown
        assert "BOOT-DIAGNOSTIC" not in json.dumps([r for r in records if r is not view])
        # Process-wide diagnostic scope survives switching without pretending attribution.
        assert "switched conversations" in view["scope"]
        send("switch", target="new", draft="", request_id="three", session_id=identity)
        switched = await until(lambda r: r.get("type") == "snapshot" and r.get("reset"))
        assert switched["session_id"] != identity
        await until(lambda r: r.get("type") == "state" and r.get("ready"))
        send(
            "inspect",
            category="runtime_output",
            request_id="four",
            session_id=switched["session_id"],
        )
        switched_view = await until(lambda r: r.get("type") == "inspection")
        assert "HOOK-DIAGNOSTIC" in json.dumps(switched_view)
        send("shutdown")
        await asyncio.wait_for(process.wait(), 5)
        assert process.returncode == 0, (await process.stderr.read()).decode()
        assert await process.stderr.read() == b""
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
    journal = "".join(
        p.read_text() for p in (tmp_path / "state/conversations").glob("*/events.jsonl")
    )
    assert "DIAGNOSTIC" not in journal and "fixture-auth-value" not in journal
    assert '"status": "completed"' in journal


@pytest.mark.parametrize("broken", [False, True])
async def test_descriptor_capture_drains_flood_during_blocking_loop_and_restores_fds(broken):
    program = r"""
import os,time,json,sys
from amplifier_tui.frontend_bridge import RuntimeOutput
with RuntimeOutput() as sink:
 if sys.argv[1]=='broken':
  def fail(data): raise ValueError('controlled decoder failure')
  sink.feed=fail
 for i in range(20000): os.write(2, b'bounded diagnostic flood\n')
 # Publication is read-only and bounded even while the ordinary event loop is blocked.
 deadline=time.monotonic()+3
 while sink.summary()['lines'] < 20000 and not sink.failed and time.monotonic()<deadline: time.sleep(.005)
 sink.protocol.write((json.dumps(sink.summary())+'\n').encode())
os.write(1,b'RESTORED-STDOUT\n')
os.write(2,b'RESTORED-STDERR\n')
assert not sink.thread.is_alive()
"""
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-u",
        "-c",
        program,
        "broken" if broken else "normal",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), 10)
        assert process.returncode == 0, stderr.decode()
        summary, restored = stdout.decode().splitlines()
        assert json.loads(summary) == (
            {"lines": 0, "omitted": 0, "failed": True}
            if broken
            else {"lines": 20000, "omitted": 20000 - 128, "failed": False}
        )
        assert restored == "RESTORED-STDOUT" and stderr == b"RESTORED-STDERR\n"
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()

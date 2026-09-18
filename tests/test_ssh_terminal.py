"""Opt-in real loopback SSH transport; not a physical mobile/remote desktop claim."""

import fcntl
import getpass
import json
import os
import shlex
import shutil
import signal
import socket
import struct
import subprocess
import sys
import termios
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from benchmark_candidates import wait_edit  # noqa: E402
from interaction_probe import capture  # noqa: E402
from questions_probe import wait_ready  # noqa: E402
from terminal_probe import Probe  # noqa: E402

pytestmark = pytest.mark.skipif(
    os.environ.get("TUI_TEST_SSH") != "1"
    or sys.platform != "linux"
    or not all(shutil.which(name) for name in ("sshd", "ssh", "ssh-keygen")),
    reason="Explicit loopback-SSH gate needs OpenSSH server/client and native build",
)


def record_server(pid, status):
    path = ROOT.parent / "WORKSPACE-MANIFEST.json"
    data = json.loads(path.read_text()) if path.exists() else {"version": 1, "resources": []}
    identity = f"tui-loopback-sshd-{pid}"
    entry = next((row for row in data["resources"] if row["id"] == identity), None)
    now = datetime.now(timezone.utc).isoformat()
    if entry is None:
        entry = {
            "kind": "ssh-test-server",
            "id": identity,
            "pid": pid,
            "created_at": now,
            "note": "Owned loopback-only SSH fixture; temporary keys, no system configuration",
            "teardown": "Owned test joins listener and tracked descendants in finally; verify process identity before any manual cleanup",
        }
        data["resources"].append(entry)
    entry["status"] = status
    if status == "reaped":
        entry["reaped_at"] = now
    path.write_text(json.dumps(data, indent=2) + "\n")


def process_identity(pid):
    try:
        # After the parenthesized command: state, ppid, pgrp, ..., starttime.
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return int(fields[1]), fields[19]
    except (OSError, ValueError, IndexError):
        return None


def reap_server(server):
    # Descendants can own separate SSH tty process groups. Capture identity while
    # the listener still owns them; never reuse a bare PID as delayed authority.
    rows = {}
    for path in Path("/proc").iterdir():
        if path.name.isdecimal() and (value := process_identity(int(path.name))):
            rows[int(path.name)] = value
    owned = {server.pid: rows.get(server.pid)}
    changed = True
    while changed:
        changed = False
        for pid, value in rows.items():
            if pid not in owned and value[0] in owned:
                owned[pid] = value
                changed = True
    for sig in (signal.SIGTERM, signal.SIGKILL):
        for pid, identity in reversed(list(owned.items())):
            current = process_identity(pid)
            if identity and current and current[1] == identity[1]:
                try:
                    os.kill(pid, sig)
                except ProcessLookupError:
                    pass
        try:
            server.wait(timeout=5)
            break
        except subprocess.TimeoutExpired:
            continue
    server.wait(timeout=5)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        living = []
        for pid, identity in owned.items():
            current = process_identity(pid)
            if identity and current and current[1] == identity[1]:
                living.append(pid)
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        if not living:
            record_server(server.pid, "reaped")
            return
        time.sleep(0.02)
    raise AssertionError("Owned SSH descendants have not been reaped")


def resize_remote(probe, tty_path, cols, rows):
    probe.resize(cols, rows)
    deadline = time.monotonic() + 5
    # The local observer grid can resize before SSH sends the window-change
    # request. Verify the remote tty, then require a new native input repaint.
    with open(tty_path.read_text(), "rb", buffering=0) as remote_tty:
        while time.monotonic() < deadline:
            actual = fcntl.ioctl(remote_tty, termios.TIOCGWINSZ, b"\0" * 8)
            if struct.unpack("HHHH", actual)[:2] == (rows, cols):
                break
            probe.read(0.02)
        else:
            raise AssertionError("SSH did not propagate the remote terminal size")
    probe.send(b"~")
    wait_edit(probe, "with pasted text~")
    probe.send(b"\x7f")
    probe.wait("with pasted text~", absent=True)
    wait_edit(probe, "with pasted text")


@pytest.mark.parametrize("cols,rows", [(175, 50), (40, 20)])
def test_real_ssh_paste_resize_resume_and_terminal_restore(tmp_path, cols, rows):
    user = getpass.getuser()
    assert all(ch.isalnum() or ch in "_-" for ch in user)
    for name in ("host", "client"):
        subprocess.run(
            [
                "ssh-keygen",
                "-q",
                "-t",
                "ed25519",
                "-N",
                "",
                "-C",
                "tui-fixture",
                "-f",
                str(tmp_path / name),
            ],
            check=True,
            capture_output=True,
        )
    with socket.socket() as available:
        available.bind(("127.0.0.1", 0))
        port = available.getsockname()[1]
    state = tmp_path / "state"
    command = [
        sys.executable,
        str(ROOT / "scripts/run.py"),
        "--state-dir",
        str(state),
        "--fixture",
        "--sources",
        str(ROOT.parent / "tui-sources.json"),
        "--no-install",
    ]
    # Remote guard proves the native app restores the remote tty, independently
    # of the local SSH client restoring its own terminal.
    tty_path = tmp_path / "remote-tty"
    guard = (
        "import os,pathlib,subprocess,sys,termios; before=termios.tcgetattr(0); "
        f"pathlib.Path({str(tty_path)!r}).write_text(os.ttyname(0)); "
        "r=subprocess.run(sys.argv[1:]); "
        "assert termios.tcgetattr(0)==before,'remote terminal not restored'; sys.exit(r.returncode)"
    )
    remote = tmp_path / "remote.py"
    remote.write_text(
        "import os,subprocess,sys\n"
        f"os.chdir({str(tmp_path)!r})\n"
        f"os.environ['AMPLIFIER_HOME']={str(tmp_path / 'home')!r}\n"
        "os.environ['PYTHONDONTWRITEBYTECODE']='1'\n"
        f"command={command!r}\n"
        f"saved=list(__import__('pathlib').Path({str(state)!r}).glob('conversations/*/metadata.json'))\n"
        "if saved:\n"
        "    command.remove('--fixture')\n"
        "    start=command.index('--sources'); del command[start:start+2]\n"
        "    command += ['--resume',__import__('json').loads(saved[0].read_text())['id']]\n"
        f"sys.exit(subprocess.run([{sys.executable!r},'-I','-c',{guard!r},*command]).returncode)\n"
    )
    config = tmp_path / "sshd_config"
    # OpenSSH rejects the shared /tmp ancestor even with this private 0700
    # test directory. Only this disposable daemon relaxes that ownership walk;
    # the exact generated public key and strict client host-key check still apply.
    assert tmp_path.stat().st_mode & 0o077 == 0
    config.write_text(
        f"Port {port}\nListenAddress 127.0.0.1\nHostKey {tmp_path / 'host'}\n"
        f"PidFile {tmp_path / 'sshd.pid'}\nAuthorizedKeysFile {tmp_path / 'client.pub'}\n"
        "PasswordAuthentication no\nKbdInteractiveAuthentication no\nUsePAM no\n"
        "StrictModes no\n"
        "AuthenticationMethods publickey\nDisableForwarding yes\nPermitRootLogin no\n"
        f"AllowUsers {user}\nLogLevel VERBOSE\n"
        f"ForceCommand {shlex.join([sys.executable, '-I', str(remote)])}\n"
    )
    known = tmp_path / "known_hosts"
    known.write_text(f"[127.0.0.1]:{port} " + (tmp_path / "host.pub").read_text())
    with (tmp_path / "sshd.log").open("wb") as log:
        server = subprocess.Popen(
            [shutil.which("sshd"), "-D", "-e", "-f", str(config)],
            stdout=log,
            stderr=log,
            start_new_session=True,
        )
        try:
            record_server(server.pid, "active")
            for resumed in (False, True):
                p = Probe(
                    [
                        "ssh",
                        "-F",
                        "/dev/null",
                        "-tt",
                        "-p",
                        str(port),
                        "-i",
                        str(tmp_path / "client"),
                        "-o",
                        "BatchMode=yes",
                        "-o",
                        "IdentitiesOnly=yes",
                        "-o",
                        "StrictHostKeyChecking=yes",
                        "-o",
                        f"UserKnownHostsFile={known}",
                        "-o",
                        "GlobalKnownHostsFile=/dev/null",
                        "-o",
                        "ConnectionAttempts=3",
                        "-o",
                        "ConnectTimeout=5",
                        f"{user}@127.0.0.1",
                    ],
                    cwd=tmp_path,
                    cols=cols,
                    rows=rows,
                    guard_terminal_modes=True,
                )
                try:
                    wait_ready(p, timeout=15)
                    metadata = next(state.glob("conversations/*/metadata.json"))
                    journal = metadata.parent / "events.jsonl"

                    def events():
                        return [json.loads(line) for line in journal.read_text().splitlines()]

                    assert sum(e["kind"] == "turn.accepted" for e in events()) == int(resumed)
                    p.send(b"\x1b[200~Compute a digest\nwith pasted text\x1b[201~")
                    wait_edit(p, "with pasted text")
                    capture(p, f"ssh-{cols}-{'resume' if resumed else 'first'}-before-resize")
                    resize_remote(p, tty_path, 60, 24)
                    resize_remote(p, tty_path, cols, rows)
                    assert sum(e["kind"] == "turn.accepted" for e in events()) == int(resumed)
                    capture(p, f"ssh-{cols}-{'resume' if resumed else 'first'}-draft")
                    before_send = len(events())
                    p.send(b"\r")
                    deadline = time.monotonic() + 30
                    while time.monotonic() < deadline:
                        p.read()
                        ended = [e for e in events() if e["kind"] == "turn.ended"]
                        if len(ended) == int(resumed) + 1:
                            assert ended[-1]["payload"]["status"] == "completed"
                            break
                    else:
                        raise AssertionError("SSH fixture turn did not complete")
                    assert any(
                        e["kind"] == "tool.updated" and e["payload"].get("status") == "succeeded"
                        for e in events()[before_send:]
                    )
                finally:
                    p.close()
        finally:
            reap_server(server)

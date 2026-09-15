"""The cross-platform observer checks restoration without silently repairing it."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from terminal_probe import Probe  # noqa: E402


@pytest.mark.parametrize("restore,exit_code", [(True, 0), (False, 0), (True, 7)])
def test_controlling_session_guard_preserves_failure(restore, exit_code):
    code = (
        "import os, sys, termios, tty; "
        "original = termios.tcgetattr(0); tty.setraw(0); "
        "os.write(1, b'guard ready'); os.read(0, 1); "
        + ("termios.tcsetattr(0, termios.TCSANOW, original); " if restore else "")
        + f"sys.exit({exit_code})"
    )
    probe = Probe([sys.executable, "-I", "-c", code], guard_terminal_modes=True)
    try:
        probe.wait("guard ready")
    except BaseException:
        probe.close()
        raise
    if restore and not exit_code:
        probe.close()
    else:
        with pytest.raises(AssertionError):
            probe.close()

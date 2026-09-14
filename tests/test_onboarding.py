"""Local diagnostics must not turn setup inspection into execution or private-data export."""

import json
import sys

import pytest

from amplifier_tui import launcher


@pytest.fixture
def local_install(tmp_path, monkeypatch):
    binary = tmp_path / "native"
    binary.write_text("not executed")
    binary.chmod(0o700)
    monkeypatch.setattr(launcher, "executable", lambda workspace=None: binary)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("AMPLIFIER_TUI_STATE_DIR", str(tmp_path / "state"))
    return binary


def inspect(args, capsys, code):
    with pytest.raises(SystemExit) as exited:
        launcher.arguments(args)
    assert exited.value.code == code
    return capsys.readouterr().out


def test_guide_requires_no_binary_key_or_state(local_install, tmp_path, capsys):
    local_install.unlink()
    text = inspect(["--getting-started"], capsys, 0)
    assert "NOT an AI assistant" in text and "Queue = a later turn" in text
    assert not (tmp_path / "state").exists()


def test_missing_default_key_is_actionable(local_install, tmp_path, capsys):
    text = inspect(["--check"], capsys, 1)
    assert "[ERROR] provider" in text and "--fixture" in text
    assert not (tmp_path / "state").exists()


@pytest.mark.parametrize(
    "options", [["--fixture"], ["--overlay", "never-read.yaml"], ["--bundle", "never-loaded"]]
)
def test_custom_compositions_are_not_forced_to_use_anthropic(local_install, capsys, options):
    text = inspect(["--check", *options], capsys, 0)
    assert "[INFO] provider" in text


def test_report_is_allowlisted_not_a_redacted_environment_dump(
    local_install, tmp_path, monkeypatch, capsys
):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "private-key-sentinel")
    monkeypatch.setenv("SECRET_UNRELATED", "another-private-sentinel")
    monkeypatch.setenv("TERM", "private-terminal-sentinel")
    text = inspect(["--support-report"], capsys, 0)
    report = json.loads(text)
    assert report["schema"] == 1 and report["frontend"] == "ratatui"
    assert str(tmp_path) not in text and "sentinel" not in text
    assert "NOT checked" in text
    assert not (tmp_path / "state").exists()


def test_nonexecutable_binary_is_failure_in_doctor_and_check(local_install, capsys):
    local_install.chmod(0o600)
    assert "[ERROR] native" in inspect(["--check", "--fixture"], capsys, 1)
    assert not json.loads(inspect(["--doctor"], capsys, 1))["native_available"]


def test_blocked_state_and_missing_cwd_do_not_create_paths(local_install, tmp_path, capsys):
    blocker = tmp_path / "file"
    blocker.write_text("unchanged")
    text = inspect(
        [
            "--check",
            "--fixture",
            "--state-dir",
            str(blocker / "child"),
            "--cwd",
            str(tmp_path / "missing"),
        ],
        capsys,
        1,
    )
    assert "[ERROR] storage" in text and "[ERROR] workspace" in text
    assert blocker.read_text() == "unchanged"
    assert not (tmp_path / "missing").exists()


@pytest.mark.parametrize("operation", ["--resume", "--recover", "--export", "--list-sessions"])
def test_check_refuses_saved_conversation_operations(local_install, tmp_path, capsys, operation):
    inspect(["--check", operation], capsys, 2)
    assert not (tmp_path / "state").exists()


@pytest.mark.parametrize("operation", ["--fixture", "--recover", "--resume"])
def test_piped_native_launch_explains_without_spawning(
    local_install, tmp_path, monkeypatch, capsys, operation
):
    monkeypatch.setattr(sys, "argv", ["amplifier-tui", operation])
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    with pytest.raises(SystemExit) as exited:
        launcher.main()
    assert exited.value.code == 2
    assert "interactive terminal" in capsys.readouterr().err
    assert not (tmp_path / "state").exists()


def test_guidance_does_not_import_runtime(local_install, monkeypatch, capsys):
    # A module loader tripwire complements the no-directory-write assertions.
    import builtins

    original = builtins.__import__

    def guarded(name, *args, **kwargs):
        assert not name.startswith(("amplifier_core", "amplifier_foundation"))
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    inspect(["--check", "--fixture"], capsys, 0)

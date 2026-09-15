"""The optional development command must select this checkout, not a stale wheel."""

import os
import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def launcher(tmp_path, monkeypatch):
    main = runpy.run_path(str(ROOT / "scripts/dev-launch"))["main"]
    monkeypatch.setitem(main.__globals__, "ROOT", tmp_path)
    python = tmp_path / ".venv/bin/python"
    python.parent.mkdir(parents=True)
    python.touch(mode=0o700)
    monkeypatch.setattr(main.__globals__["sys"].stdin, "isatty", lambda: True)
    monkeypatch.setattr(main.__globals__["sys"].stdout, "isatty", lambda: True)
    return main


@pytest.mark.parametrize("args", [["--doctor"], ["--version"], ["--check"], ["--getting-started"]])
def test_information_skips_build_and_forwards_to_workspace(launcher, tmp_path, monkeypatch, args):
    def build(*a, **kw):
        pytest.fail("Informational invocation must not build")

    def execute(path, argv, env):
        assert path == str(tmp_path / ".venv/bin/python")
        assert argv == [path, str(tmp_path / "scripts/run.py"), *args]
        assert env["PYTHONPATH"].split(os.pathsep)[0] == str(tmp_path / "src")
        assert env["PYTHONDONTWRITEBYTECODE"] == "1"
        raise SystemExit(0)

    monkeypatch.setattr(launcher.__globals__["subprocess"], "run", build)
    monkeypatch.setattr(launcher.__globals__["os"], "execve", execute)
    before = Path.cwd()
    with pytest.raises(SystemExit, match="0"):
        launcher(args)
    assert Path.cwd() == before


def test_native_build_failure_does_not_run_stale_binary(launcher, tmp_path, monkeypatch):
    def build(argv, **kw):
        assert "--locked" in argv and "--release" in argv
        assert kw["env"]["CARGO_TARGET_DIR"] == str(tmp_path / "frontends/ratatui/target")
        return SimpleNamespace(returncode=7)

    monkeypatch.setattr(launcher.__globals__["subprocess"], "run", build)
    monkeypatch.setattr(
        launcher.__globals__["os"], "execve", lambda *a: pytest.fail("stale launch")
    )
    assert launcher([]) == 7


def test_missing_environment_is_actionable(launcher, tmp_path, capsys):
    (tmp_path / ".venv/bin/python").unlink()
    assert launcher(["--version"]) == 1
    assert "uv sync --inexact" in capsys.readouterr().err

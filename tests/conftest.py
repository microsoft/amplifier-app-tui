import os
from pathlib import Path

import pytest
import pytest_asyncio

import amplifier_tui
from amplifier_tui.composition import SourceMap, prepare
from amplifier_tui.host import SessionHost


@pytest.fixture(autouse=True)
def shared_state_home(tmp_path, monkeypatch):
    # The production shared lock is independent of AMPLIFIER_HOME. Tests must
    # never allocate owner records beneath the person's real platform state root.
    monkeypatch.setenv("AMPLIFIER_SESSION_STATE_HOME", str(tmp_path / "shared-owners"))


@pytest_asyncio.fixture
async def prepared(tmp_path, monkeypatch):
    # Offline tests use explicit source checkout locations, never user caches.
    workspace = Path(
        os.environ.get("AMPLIFIER_TUI_SOURCE_ROOT", Path(__file__).resolve().parents[2])
    )
    paths = {
        f"https://github.com/microsoft/{name}": str(workspace / name)
        for name in ("amplifier-module-loop-streaming", "amplifier-module-context-simple")
    }
    for value in paths.values():
        assert Path(value).is_dir(), "Run the source bootstrap documented in README.md"
    monkeypatch.setenv("AMPLIFIER_HOME", str(tmp_path / "foundation"))
    fixture = Path(amplifier_tui.__file__).parent / "fixtures" / "bundle.yaml"
    value, report = await prepare(str(fixture), [], tmp_path, SourceMap(paths), install_deps=False)
    report["required_tools"] = ["fixture_probe"]
    return value, report


@pytest_asyncio.fixture
async def host(prepared, tmp_path):
    host = SessionHost()
    await host.open(*prepared, tmp_path)
    yield host
    await host.close()

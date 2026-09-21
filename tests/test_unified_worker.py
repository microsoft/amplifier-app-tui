"""Connected adapter with the real Unified worker and credential-free fixture provider."""
import asyncio
import os
import sys
from pathlib import Path

import pytest
from aiohttp import web
from test_unified_client import attach, request

pytestmark = pytest.mark.skipif(os.environ.get('TUI_TEST_REAL_WORKER') != '1', reason='Needs Unified worker dependencies')


async def test_real_worker_detach_reconnect_and_stop(tmp_path, monkeypatch):
    server = pytest.importorskip('amplifier_web.server')
    for key, directory in [('AMPLIFIER_HOME', 'amplifier'), ('AMPLIFIER_WEB_HOME', 'home'),
                           ('AMPLIFIER_UNIFIED_IMPORT_HOME', 'legacy'), ('AMPLIFIER_SESSION_STATE_HOME', 'owners')]:
        monkeypatch.setenv(key, str(tmp_path / directory))
    provider = tmp_path / 'provider' / 'amplifier_module_provider_fixture'
    provider.mkdir(parents=True)
    gate = tmp_path / 'gate'
    provider.joinpath('__init__.py').write_text(f'GATE = {str(gate)!r}\n' + '''import asyncio
from pathlib import Path
from amplifier_core import ProviderInfo
from amplifier_core.message_models import ChatResponse, TextBlock
class Provider:
    name = 'fixture'
    def get_info(self): return ProviderInfo(id='fixture', display_name='Fixture', defaults={'model':'fixture'})
    async def list_models(self): return []
    def parse_tool_calls(self, response): return []
    async def complete(self, request, **kwargs):
        Path(GATE + '.called').touch()
        try:
            while not Path(GATE).exists(): await asyncio.sleep(.02)
        except asyncio.CancelledError:
            Path(GATE + '.cancelled').touch()
            raise
        return ChatResponse(content=[TextBlock(text='Real worker fixture completed')])
async def mount(coordinator, config=None): await coordinator.mount('providers', Provider(), name='fixture')
''')
    source_root = Path(os.environ['AMPLIFIER_TUI_SOURCE_ROOT'])
    context = source_root / 'amplifier-module-context-simple'
    bundle = tmp_path / 'fixture.md'
    bundle.write_text(f'''---
bundle:
  name: connected-worker-fixture
  version: 0.0.1
session:
  orchestrator:
    module: loop-live
  context:
    module: context-simple
    source: {context}
providers:
  - module: provider-fixture
    source: {provider.parent}
---
Use the fixture response.
''')
    app = await server.create_app(tmp_path / 'app', workspace=tmp_path, voice=False,
                                  background_updates=False, preload_providers=False)
    service = app['service']
    service.runtime.command = [sys.executable, str(Path(server.__file__).parent / 'runtime_worker.py')]
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 0)
    await site.start()
    url = f'http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}'
    clients = []

    async def wait(predicate):
        async with asyncio.timeout(60):
            while not predicate():
                if service._session().get('error'):
                    raise AssertionError(service._session()['error'])
                await asyncio.sleep(.03)

    try:
        await service.dispatch('session.create', {'bundle': str(bundle), 'title': 'Real worker'})
        sid = service._session()['id']
        a, _ = await attach(tmp_path / 'a', app, url, sid, 'terminal-a')
        b, _ = await attach(tmp_path / 'b', app, url, sid, 'terminal-b')
        clients += [a, b]
        assert (await a.dispatch(request(a, 'submit', text='Fixture task')))[0]
        await wait(lambda: gate.with_suffix('.called').exists())
        await a.close()
        assert sid in service.runtime.workers
        gate.touch()
        await wait(lambda: any(m.get('text') == 'Real worker fixture completed' for m in b.session.get('messages', [])))
        await wait(lambda: b.session['status'] == 'idle')
        restored, _ = await attach(tmp_path / 'a', app, url, client='terminal-a')
        clients.append(restored)
        assert restored.selected == sid
        assert sum(m.get('text') == 'Fixture task' for m in restored.session['messages']) == 1
        gate.unlink()
        gate.with_suffix('.called').unlink()
        assert (await restored.dispatch(request(restored, 'submit', text='Fixture stop task')))[0]
        await wait(lambda: gate.with_suffix('.called').exists())
        assert (await b.dispatch(request(b, 'stop')))[0]
        await wait(lambda: b.session['status'] == 'stopped')
        assert gate.with_suffix('.cancelled').exists()
    finally:
        for client in clients:
            await client.close()
        await runner.cleanup()

"""Private browser/installed-terminal qualification host; never production routes."""
import asyncio
import json
import os
import signal
import sys
import tempfile
from pathlib import Path

import amplifier_web
from aiohttp import web

ROOT = Path(__file__).resolve().parents[2]
# Reuse Unified's explicit synthetic-provider UI fixture from its source checkout.
sys.path.insert(0, str(Path(amplifier_web.__file__).resolve().parents[1] / 'tests/fixtures'))
sys.path.insert(0, str(ROOT / 'scripts'))
import live_clients_ui_server as fixture  # noqa: E402
from terminal_probe import Probe  # noqa: E402


async def main(home):
    stopped = asyncio.Event()
    asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, stopped.set)
    os.environ['AMPLIFIER_SESSION_STATE_HOME'] = str(home / 'owners')
    app = await fixture.fixture.main(home)
    service = app['service']
    sid = service.state['selectedSessionId']
    token = home / 'token'
    token.write_text(app['control_token'])
    token.chmod(0o600)
    probe = None

    async def inspect(request):
        return web.json_response({'session': sid, 'sent': service.runtime.sent,
                                  'terminal': probe.text if probe else '', 'stopped': service.runtime.stopped})

    async def input_text(request):
        data = await request.json()
        probe.send(data['text'].encode())
        return web.json_response({'ok': True})

    async def finish(request):
        await service.runtime.finish()
        return web.json_response({'ok': True})

    app.router.add_get('/fixture', inspect)
    app.router.add_post('/fixture/input', input_text)
    app.router.add_post('/fixture/finish', finish)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 0)
    await site.start()
    url = f'http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}'
    app['allowed_origins'] = app['allowed_origins'] | {url}
    command = [os.environ['TUI_CONNECTED_EXECUTABLE'], '--server', url, '--token-file', str(token),
               '--session', sid, '--state-dir', str(home / 'client'), '--client', 'terminal-browser-proof']
    probe = Probe(command, 120, 40, guard_terminal_modes=True)
    print(json.dumps({'url': url}), flush=True)
    try:
        while not stopped.is_set():
            probe.read(0)
            await asyncio.sleep(.01)
    finally:
        await asyncio.to_thread(probe.close)
        await runner.cleanup()


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='amplifier-connected-browser-') as directory:
        asyncio.run(main(Path(directory)))

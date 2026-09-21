"""Actual native entrypoint against Unified HTTP/SSE; provider is a labelled fixture."""
import asyncio
import os
import sys
from pathlib import Path

import pytest
from test_unified_client import server as server  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from terminal_probe import Probe  # noqa: E402

pytestmark = pytest.mark.skipif(os.environ.get('TUI_TEST_CANDIDATES') != '1', reason='Build native client')


async def displayed(probes, predicate, timeout=10):
    async with asyncio.timeout(timeout):
        while True:
            for probe in probes:
                probe.read(0)
                assert probe.process.poll() is None, probe.text
            if predicate():
                return
            await asyncio.sleep(.01)


@pytest.mark.parametrize('size', [(120, 40), (40, 20)])
async def test_installed_entrypoint_two_views_send_stream_draft_and_detach(server, tmp_path, size):
    app, url = server
    service = app['service']
    await service.dispatch('session.create', {'title': 'Connected terminal'})
    sid = service._session()['id']
    token_file = tmp_path / 'control-token'
    token_file.write_text(app['control_token'])
    token_file.chmod(0o600)
    executable = os.environ.get('TUI_CONNECTED_EXECUTABLE')
    command = [executable] if executable else [sys.executable, '-m', 'amplifier_tui.launcher']
    common = [*command, '--server', url, '--token-file', str(token_file), '--session', sid]
    a = Probe([*common, '--state-dir', str(tmp_path / 'a'), '--client', 'a'], *size, guard_terminal_modes=True,
              env={'PYTHONPATH': ''} if executable else None)
    b = Probe([*common, '--state-dir', str(tmp_path / 'b'), '--client', 'b'], *size, guard_terminal_modes=True,
              env={'PYTHONPATH': ''} if executable else None)
    try:
        await displayed([a, b], lambda: all('UNIFIED' in p.text for p in (a, b)))
        b.send(b'Private second draft')
        a.send(b'Input from terminal\r')
        await displayed([a, b], lambda: len(service.runtime.sent) == 1)
        await displayed([a, b], lambda: 'Private second draft' in b.text)
        identity = service.runtime.sent[0][2]
        await service.on_runtime_event('assistant.message', {'sessionId': sid, 'inputId': identity, 'text': 'Shared terminal response'})
        await service.on_runtime_event('runtime.status', {'sessionId': sid, 'status': 'idle'})
        await displayed([a, b], lambda: all('Shared terminal response' in p.text for p in (a, b)) and 'Private second draft' in b.text)
        assert 'Private second draft' in b.text
        assert b'Input from terminal' in a.raw and b'Input from terminal' in b.raw
        # Terminal captures are private development artifacts, never published receipts.
        for label, probe in [('a', a), ('b', b)]:
            (tmp_path / f'{label}-screen.txt').write_text(probe.text)
        a.send(b'\x11')
        await asyncio.sleep(.05)
        assert not service.runtime.stopped
    finally:
        # The service event loop must remain responsive while the bridge closes.
        await asyncio.gather(asyncio.to_thread(a.close), asyncio.to_thread(b.close))
    assert not service.runtime.stopped


@pytest.mark.parametrize('size', [(120, 40), (40, 20)])
async def test_failed_worker_is_explained_in_the_native_conversation(server, tmp_path, size):
    app, url = server
    service = app['service']
    await service.dispatch('session.create', {'title': 'Failure fixture'})
    sid = service._session()['id']
    attempts = []

    async def fail_send(session, text, input_id, emit):
        attempts.append(input_id)
        raise RuntimeError('Fixture mount failure')

    service.runtime.send = fail_send
    token = tmp_path / 'token'
    token.write_text(app['control_token'])
    token.chmod(0o600)
    executable = os.environ.get('TUI_CONNECTED_EXECUTABLE')
    launcher = [executable] if executable else [sys.executable, '-m', 'amplifier_tui.launcher']
    command = [*launcher, '--server', url,
               '--token-file', str(token), '--session', sid, '--state-dir', str(tmp_path / 'client')]
    probe = Probe(command, *size, guard_terminal_modes=True,
              env={'PYTHONPATH': ''} if executable else None)
    try:
        await displayed([probe], lambda: 'UNIFIED' in probe.text and 'loading' not in probe.text)
        probe.send(b'Fixture request\r')
        await displayed([probe], lambda: 'worker is unavailable' in ' '.join(probe.text.split()))
        assert len(attempts) == 1
        assert 'ValueError' not in probe.text
        assert 'Mode: loading' not in probe.text
        (tmp_path / 'failure-screen.txt').write_text(probe.text)
        probe.send(b'/deliveries\r')
        await displayed([probe], lambda: 'Delivery: unknown' in ' '.join(probe.text.split()))
        # Wait for the complete menu frame before paging its short detail pane.
        await displayed([probe], lambda: 'Copy retained input' in probe.text and 'Esc' in probe.text)
        if 'Retained input:' not in probe.text:
            probe.send(b'\x1b[6~')
            await displayed([probe], lambda: 'Retained input:' in probe.text)
        assert 'local_request' not in probe.text
        assert len(attempts) == 1
        (tmp_path / 'delivery-screen.txt').write_text(probe.text)
    finally:
        await asyncio.to_thread(probe.close)
    assert len(attempts) == 1 and service.runtime.stopped == []

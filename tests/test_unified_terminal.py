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


@pytest.mark.parametrize('size', [(120, 40), (40, 20)])
@pytest.mark.parametrize('selection', ['picker', 'prefix', 'full'])
async def test_unified_launcher_resumes_native_cli_history(server, tmp_path, size, selection):
    import uuid

    from test_connected_resume import native_chat

    app, url = server
    workspace = tmp_path / 'project'
    native = str(uuid.uuid4())
    host, directory = await native_chat(app['service'], workspace, native, 'Resume fixture')
    await native_chat(app['service'], tmp_path / 'other', str(uuid.uuid4()), 'EXCLUDED other directory')
    before = {p.name: p.read_bytes() for p in directory.iterdir() if p.is_file()}
    token = tmp_path / 'token'
    token.write_text(app['control_token'])
    token.chmod(0o600)
    command = [sys.executable, '-m', 'amplifier_web.cli', 'tui', '--server', url,
               '--token-file', str(token), '--state-dir', str(tmp_path / 'client'),
               '--client', 'resume-probe', '--resume']
    if selection != 'picker':
        command += [native[:8] if selection == 'prefix' else native]
    probe = Probe(command, *size, cwd=workspace, guard_terminal_modes=True,
                  env={'AMPLIFIER_TERMINAL_HOME': str(tmp_path / 'managed')})
    try:
        if selection == 'picker':
            await displayed([probe], lambda: 'Resume fixture' in probe.text)
            assert 'EXCLUDED' not in probe.text
            assert not app['service'].runtime.sent
            # Escape dismisses the startup picker; the same in-app picker can reopen it.
            probe.send(b'\x1b')
            await displayed([probe], lambda: 'Saved conversations' not in probe.text)
            probe.send(b'/resume\r')
            await displayed([probe], lambda: 'Resume fixture' in probe.text)
            probe.send(b'Resume fixture\r')
        await displayed([probe], lambda: 'NATIVE saved answer' in probe.text)
        assert 'Startup failed' not in probe.text
        import json
        state = json.loads((tmp_path / 'client/connections/resume-probe.json').read_text())
        assert state['session'] == host
        assert not app['service'].runtime.sent
        (tmp_path / f'resume-{selection}-{size[0]}-screen.txt').write_text(probe.text)
    finally:
        await asyncio.to_thread(probe.close)
    assert {p.name: p.read_bytes() for p in directory.iterdir() if p.is_file()} == before


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
    common = [*command, '--server', url, '--token-file', str(token_file), '--workspace', str(tmp_path), '--session', sid]
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
               '--token-file', str(token), '--workspace', str(tmp_path), '--session', sid, '--state-dir', str(tmp_path / 'client')]
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


@pytest.mark.parametrize('size', [(120, 40), (40, 20)])
async def test_native_resume_interleaves_retained_tools_without_execution(server, tmp_path, size):
    app, url = server
    service = app['service']
    await service.dispatch('session.create', {'title': 'History order fixture'})
    session = service._session()
    session['messages'] = [
        {'id': 'u1', 'role': 'user', 'text': 'ORDER request one', 'createdAt': 10},
        {'id': 'a1', 'role': 'assistant', 'text': 'ORDER answer one', 'createdAt': 20},
        {'id': 'u2', 'role': 'user', 'text': 'ORDER request two', 'createdAt': 30},
        {'id': 'a2', 'role': 'assistant', 'text': 'ORDER answer two', 'createdAt': 40},
    ]
    session['execution'] = {'turns': [], 'nodes': [
        {'id': 't2', 'turnId': 'turn2', 'kind': 'tool', 'label': 'ORDER tool two', 'phase': 'done', 'startedAt': 35},
        {'id': 't1', 'turnId': 'turn1', 'kind': 'tool', 'label': 'ORDER tool one', 'phase': 'done', 'startedAt': 15},
    ]}
    token = tmp_path / 'token'
    token.write_text(app['control_token'])
    token.chmod(0o600)
    executable = os.environ.get('TUI_CONNECTED_EXECUTABLE')
    launcher = [executable] if executable else [sys.executable, '-m', 'amplifier_tui.launcher']
    probe = Probe([*launcher, '--server', url, '--token-file', str(token),
                   '--workspace', str(tmp_path), '--session', session['id'], '--state-dir', str(tmp_path / 'client')],
                  *size, guard_terminal_modes=True, env={'PYTHONPATH': ''} if executable else None)
    try:
        await displayed([probe], lambda: 'ORDER answer two' in probe.text and 'UNIFIED' in probe.text)
        markers = ['ORDER request one', 'ORDER tool one', 'ORDER answer one',
                   'ORDER request two', 'ORDER tool two', 'ORDER answer two']
        # Retained native rows may be above a narrow viewport; PTY bytes retain
        # their emission order independently of the observer's current screen.
        raw = bytes(probe.raw)
        positions = [raw.index(marker.encode()) for marker in markers]
        assert positions == sorted(positions)
        assert all(raw.count(marker.encode()) == 1 for marker in markers)
        assert not service.runtime.sent
        (tmp_path / 'ordered-history-screen.txt').write_text(probe.text)
    finally:
        await asyncio.to_thread(probe.close)
    assert not service.runtime.sent and not service.runtime.stopped

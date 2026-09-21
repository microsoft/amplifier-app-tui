"""Real Unified HTTP/SSE + terminal adapter; execution here is a labelled fixture."""
import asyncio
import sys
import uuid

import pytest
from aiohttp import web

from amplifier_tui.client_state import ClientState
from amplifier_tui.unified_client import UnifiedBridge
from amplifier_tui.unified_projection import project
from amplifier_tui.unified_transport import Transport, validate_url


class FixtureRuntime:
    def __init__(self):
        self.sent, self.stopped = [], []
        self.emit = None

    async def start(self, session, emit):
        self.emit = emit

    async def send(self, session, text, input_id, emit):
        self.sent.append((session['id'], text, input_id))
        self.emit = emit
        await emit('assistant.delta', {'sessionId': session['id'], 'text': 'Fixture partial'})

    async def stop(self, sid):
        self.stopped.append(sid)

    async def close(self):
        pass


@pytest.fixture
async def server(tmp_path, monkeypatch):
    create_app = pytest.importorskip('amplifier_web.server').create_app
    monkeypatch.setenv('AMPLIFIER_HOME', str(tmp_path / 'foundation'))
    runtime = FixtureRuntime()
    app = await create_app(tmp_path / 'server', workspace=tmp_path, runtime=runtime,
                           voice=False, background_updates=False, preload_providers=False)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 0)
    await site.start()
    url = f"http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}"
    yield app, url
    await runner.cleanup()


async def until(predicate):
    async with asyncio.timeout(5):
        while not predicate():
            await asyncio.sleep(.02)


async def attach(tmp_path, app, url, sid=None, client=None):
    state = ClientState(tmp_path, url, client)
    transport = Transport(url, app['control_token'], state.identity)
    events = []
    bridge = UnifiedBridge(events.append, transport, state, session=sid)
    await bridge.open()
    return bridge, events


def request(bridge, op, **args):
    return {'version': 1, 'request_id': str(uuid.uuid4()), 'session_id': bridge.selected or '',
            'op': op, **args}


async def test_two_clients_follow_same_conversation_without_losing_drafts(server, tmp_path):
    app, url = server
    service = app['service']
    created = await service.dispatch('session.create', {'title': 'Shared'})
    sid = created['state']['selectedSessionId']
    a, ae = await attach(tmp_path / 'a', app, url, sid)
    b, be = await attach(tmp_path / 'b', app, url, sid)
    try:
        await a.dispatch(request(a, 'draft', text='First private draft'))
        await b.dispatch(request(b, 'draft', text='Second private draft'))
        accepted, reason = await a.dispatch(request(a, 'submit', text='Fixture instruction'))
        assert accepted, reason
        await until(lambda: b.session.get('streaming') == 'Fixture partial')
        assert len(app['service'].runtime.sent) == 1
        assert a.store.data['drafts'][sid] == 'First private draft'
        assert b.store.data['drafts'][sid] == 'Second private draft'
        assert any(event['type'] == 'input_pending' for event in ae)
        partial_id = next(item['id'] for item in b.items() if item['kind'] == 'assistant')
        input_id = service.runtime.sent[0][2]
        await service.on_runtime_event('assistant.message', {'sessionId': sid, 'inputId': input_id, 'text': 'Fixture partial complete'})
        await service.on_runtime_event('runtime.status', {'sessionId': sid, 'status': 'idle'})
        await until(lambda: any(item['text'] == 'Fixture partial complete' for item in b.items()))
        finals = [item for item in b.items() if item['kind'] == 'assistant']
        assert len(finals) == 1 and finals[0]['id'] == partial_id
        assert len({item['id'] for item in b.items()}) == len(b.items())
        await a.close()
        assert service.runtime.stopped == []
        await b.dispatch(request(b, 'rename', text='Renamed from terminal'))
        assert service._session(sid)['title'] == 'Renamed from terminal'
    finally:
        await a.close()
        await b.close()


async def test_creation_does_not_need_local_runtime_and_input_is_sent_once(server, tmp_path):
    app, url = server
    bridge, events = await attach(tmp_path, app, url)
    try:
        assert not bridge.selected and app['service'].state['sessions'] == []
        accepted, reason = await bridge.dispatch(request(bridge, 'submit', text='New task'))
        assert accepted, reason
        assert bridge.selected and len(app['service'].runtime.sent) == 1
        assert app['service'].runtime.sent[0][0] == bridge.selected
        assert [e for e in events if e['type'] == 'input_pending']
    finally:
        await bridge.close()


async def test_unknown_delivery_keeps_identity_and_exact_retry_does_not_repeat(server, tmp_path):
    app, url = server
    created = await app['service'].dispatch('session.create', {})
    sid = created['state']['selectedSessionId']
    bridge, _ = await attach(tmp_path, app, url, sid, 'recoverable')
    bridge.pump.cancel()
    await asyncio.gather(bridge.pump, return_exceptions=True)
    original = bridge.transport.command

    async def lose_reply(*args, **kwargs):
        await original(*args, **kwargs)
        raise ConnectionError('Lost after acceptance')

    bridge.transport.command = lose_reply
    try:
        accepted, _ = await bridge.dispatch(request(bridge, 'submit', text='Once only'))
        assert not accepted
        identity, row = next(iter(bridge.store.data['outbox'].items()))
        assert row['status'] == 'unknown'
        bridge.transport.command = original
        accepted, reason = await bridge.dispatch(request(bridge, 'retry_delivery', id=identity))
        assert accepted, reason
        assert len(app['service'].runtime.sent) == 1
        await bridge.close()
        recovered, _ = await attach(tmp_path, app, url, client='recoverable')
        try:
            assert recovered.selected == sid
            assert len(app['service'].runtime.sent) == 1
        finally:
            await recovered.close()
    finally:
        await bridge.close()


async def test_explicit_targets_survive_navigation_and_detach(server, tmp_path):
    app, url = server
    ids = []
    for name in ['A', 'B']:
        reply = await app['service'].dispatch('session.create', {'title': name})
        ids.append(reply['state']['selectedSessionId'])
    bridge, _ = await attach(tmp_path, app, url, ids[0])
    stale = request(bridge, 'submit', text='Wrong target')
    try:
        await bridge.dispatch(request(bridge, 'switch', target=ids[1], draft='Unsent A'))
        assert not (await bridge.dispatch(stale))[0]
        assert not app['service'].runtime.sent
        assert bridge.store.data['drafts'][ids[0]] == 'Unsent A'
        # Revisions from another conversation never replace this one.
        with pytest.raises(ValueError, match='different conversation'):
            bridge.reconcile({'protocolVersion': 1, 'hostInstanceId': 'host', 'revision': 9,
                              'session': {'id': ids[0]}})
        await bridge.dispatch(request(bridge, 'stop'))
        assert app['service'].runtime.stopped == [ids[1]]
    finally:
        await bridge.close()


def test_projection_keeps_user_and_assistant_distinct_and_preserves_partial_identity():
    session = {'id': 's', 'messages': [{'id': 'm', 'role': 'user', 'inputId': 'x', 'text': 'hi'},
               {'id': 'n', 'role': 'assistant', 'inputId': 'x', 'streamId': 'r', 'text': 'hello'}]}
    rows = project(session, {})
    assert [r['id'] for r in rows] == ['input:x', 'stream:r']
    assert len({r['id'] for r in rows}) == 2


def test_private_state_locks_independent_views_and_retains_unknown_intent(tmp_path):
    first = ClientState(tmp_path, 'http://localhost:8941', 'one')
    try:
        with pytest.raises(ValueError, match='already open'):
            ClientState(tmp_path, 'http://localhost:8941', 'one')
        first.data['outbox']['request'] = {'status': 'sending', 'text': 'retained'}
        first.save()
        assert first.path.stat().st_mode & 0o777 == 0o600
    finally:
        first.close()
    recovered = ClientState(tmp_path, 'http://localhost:8941', 'one')
    assert recovered.data['outbox']['request']['status'] == 'unknown'
    recovered.close()
    with pytest.raises(ValueError, match='incompatible'):
        ClientState(tmp_path, 'https://different.example', 'one')


@pytest.mark.parametrize('url', ['http://remote.example', 'https://user:pass@example.org',
                                'https://example.org/?token=x', 'file:///tmp/service'])
def test_unsafe_connection_addresses_are_refused(url):
    with pytest.raises(ValueError):
        validate_url(url)


def test_connected_imports_do_not_load_execution_dependencies():
    import subprocess
    result = subprocess.run([sys.executable, '-c',
        'import amplifier_tui.connected,sys; print(" ".join(sys.modules))'], capture_output=True, text=True, check=True)
    assert not any(name in result.stdout for name in ('amplifier_core', 'amplifier_foundation',
                                                     'amplifier_app_cli', 'amplifier_tui.host'))


async def test_stop_remains_available_while_send_reply_is_delayed(server, tmp_path):
    app, url = server
    created = await app['service'].dispatch('session.create', {})
    sid = created['state']['selectedSessionId']
    bridge, _ = await attach(tmp_path, app, url, sid)
    original = bridge.transport.command
    held, release = asyncio.Event(), asyncio.Event()

    async def delayed(identity, action, args, command_id):
        response = await original(identity, action, args, command_id)
        if action == 'conversation.send':
            held.set()
            await release.wait()
        return response

    bridge.transport.command = delayed
    task = asyncio.create_task(bridge.dispatch(request(bridge, 'submit', text='Hold reply')))
    try:
        await asyncio.wait_for(held.wait(), 3)
        accepted, reason = await asyncio.wait_for(bridge.dispatch(request(bridge, 'stop')), 3)
        assert accepted, reason
        await until(lambda: app['service'].runtime.stopped == [sid])
    finally:
        release.set()
        await task
        await bridge.close()


async def test_history_pages_are_bounded_and_do_not_start_work(server, tmp_path):
    app, url = server
    await app['service'].dispatch('session.create', {})
    session = app['service']._session()
    session['messages'] = [{'id': str(i), 'role': 'user', 'text': f'History {i}'} for i in range(250)]
    bridge, events = await attach(tmp_path, app, url, session['id'])
    try:
        for offset, first, last in [(0, 150, 249), (100, 50, 149), (200, 0, 49)]:
            assert (await bridge.dispatch(request(bridge, 'history_page', offset=offset)))[0]
            page = next(row for row in reversed(events) if row['type'] == 'history_page')
            assert page['items'][0]['text'] == f'History {first}'
            assert page['items'][-1]['text'] == f'History {last}'
            assert len(page['items']) <= 100
        assert not app['service'].runtime.sent
        assert len(bridge.items()) == 100
    finally:
        await bridge.close()


async def test_lost_creation_reply_recovers_same_session_and_sends_only_once(server, tmp_path):
    app, url = server
    bridge, _ = await attach(tmp_path, app, url, client='create-recovery')
    original = bridge.transport.command
    lost = False

    async def lose_create(identity, action, args, command_id):
        nonlocal lost
        result = await original(identity, action, args, command_id)
        if action == 'session.create' and not lost:
            lost = True
            raise ConnectionError('Creation acknowledgement lost')
        return result

    bridge.transport.command = lose_create
    try:
        assert not (await bridge.dispatch(request(bridge, 'submit', text='Create once')))[0]
        assert len(app['service'].state['sessions']) == 1
        identity = next(iter(bridge.store.data['outbox']))
        await bridge.close()
        recovered, _ = await attach(tmp_path, app, url, client='create-recovery')
        try:
            assert not app['service'].runtime.sent  # Reopening never submits.
            accepted, reason = await recovered.dispatch(request(recovered, 'retry_delivery', id=identity))
            assert accepted, reason
            assert len(app['service'].state['sessions']) == 1
            assert len(app['service'].runtime.sent) == 1
        finally:
            await recovered.close()
    finally:
        await bridge.close()


async def test_generated_names_and_custom_renames_are_shared(server, tmp_path):
    app, url = server
    service = app['service']
    await service.dispatch('session.create', {})
    sid = service._session()['id']
    bridge, events = await attach(tmp_path, app, url, sid)
    try:
        await service.on_runtime_event('session.naming', {'sessionId': sid, 'name': 'Generated project title'})
        await until(lambda: bridge.session['title'] == 'Generated project title')
        assert (await bridge.dispatch(request(bridge, 'rename', text='My permanent title')))[0]
        await service.on_runtime_event('session.naming', {'sessionId': sid, 'name': 'Late generated suggestion'})
        assert (await bridge.transport.snapshot(sid))['session']['title'] == 'My permanent title'
        await until(lambda: any(e.get('title') == 'My permanent title' for e in events))
    finally:
        await bridge.close()

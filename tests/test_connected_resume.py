"""Command-line return uses the host's real native catalog without replay."""
import json
import uuid

import pytest
from test_unified_client import request
from test_unified_client import server as server  # noqa: F401

from amplifier_tui.client_state import ClientState
from amplifier_tui.connected import parser
from amplifier_tui.unified_client import UnifiedBridge
from amplifier_tui.unified_transport import Transport


def test_resume_parser_distinguishes_picker_id_and_ordinary_launch(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert parser().parse_args([]).resume is None
    assert parser().parse_args(['--resume']).resume == ''
    assert parser().parse_args(['--resume', 'abc']).resume == 'abc'
    assert parser().parse_args(['--resume']).workspace == str(tmp_path.resolve())
    for args in (['--session'], ['--resume', '--new'], ['--session', 'a', '--resume']):
        with pytest.raises(SystemExit):
            parser().parse_args(args)


async def native_chat(service, workspace, identity, title='Native resume fixture'):
    from amplifier_web.session_files import amplifier_home, project_slug

    workspace.mkdir(parents=True, exist_ok=True)
    directory = amplifier_home() / 'projects' / project_slug(workspace) / 'sessions' / identity
    directory.mkdir(parents=True)
    (directory / 'metadata.json').write_text(json.dumps({
        'session_id': identity, 'working_dir': str(workspace), 'name': title,
        'bundle': 'bundle:fixture', 'created': '2026-01-01T12:00:00Z', 'turn_count': 1,
    }))
    (directory / 'transcript.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in [
        {'role': 'user', 'content': 'NATIVE saved question'},
        {'role': 'assistant', 'content': 'NATIVE saved answer'},
    ]))
    await service.history.refresh()
    row = next(row for row in service.state['sessions']
               if row.get('nativeIdentity') == identity and row.get('workspace') == str(workspace))
    return row['id'], directory


@pytest.mark.parametrize('selector', ['native', 'native-prefix', 'host', 'host-prefix', 'latest'])
@pytest.mark.parametrize('duplicate_native', [False, True])
async def test_native_id_and_prefix_resume_same_history(server, tmp_path, selector, duplicate_native):
    app, url = server
    service = app['service']
    native = str(uuid.uuid4())
    workspace = tmp_path / 'project'
    if duplicate_native:
        # Current hosts expose unique native IDs directly. Reused native IDs in
        # different directories retain distinct host IDs and still need lookup.
        await native_chat(service, tmp_path / 'other-project', native, 'Other directory')
    host, directory = await native_chat(service, workspace, native)
    if duplicate_native:
        assert host != native
    before = {p.name: p.read_bytes() for p in directory.iterdir() if p.is_file()}
    value = {'native': native, 'native-prefix': native[:8], 'host': host,
             'host-prefix': host[:8], 'latest': 'latest'}[selector]
    state = ClientState(tmp_path / 'client', url)
    bridge = UnifiedBridge(lambda _: None, Transport(url, app['control_token'], state.identity),
                           state, session=value, workspace=str(workspace))
    try:
        await bridge.open()
        assert bridge.selected == host
        assert state.data['session'] == host
        assert [item['text'] for item in bridge.items() if item['kind'] in {'user', 'assistant'}] == [
            'NATIVE saved question', 'NATIVE saved answer']
        assert service.runtime.sent == []
        assert len(service.state['sessions']) == 1 + duplicate_native
    finally:
        await bridge.close()
    assert {p.name: p.read_bytes() for p in directory.iterdir() if p.is_file()} == before


async def test_picker_starts_empty_preserves_recovered_drafts_and_uses_directory(server, tmp_path):
    app, url = server
    workspace = tmp_path / 'project'
    local, _ = await native_chat(app['service'], workspace, str(uuid.uuid4()))
    other, _ = await native_chat(app['service'], tmp_path / 'other', str(uuid.uuid4()), 'Other directory')
    state = ClientState(tmp_path / 'client', url)
    state.data.update(session=other, drafts={other: 'Keep other draft', '': 'Keep composer draft'})
    state.save()
    events = []
    bridge = UnifiedBridge(events.append, Transport(url, app['control_token'], state.identity),
                           state, workspace=str(workspace), resume_picker=True)
    try:
        await bridge.open()
        assert bridge.selected is None
        snapshot = next(e for e in events if e['type'] == 'snapshot')
        assert snapshot['resume_picker'] is True and snapshot['draft'] == 'Keep composer draft'
        await bridge.dispatch(request(bridge, 'conversations'))
        assert [row['id'] for row in events[-1]['sessions']] == [local]
        await bridge.dispatch(request(bridge, 'switch', target=local, draft='Keep composer draft'))
        assert bridge.selected == local
        assert [e['resume_picker'] for e in events if e['type'] == 'snapshot'] == [True, False]
        assert state.data['drafts'][other] == 'Keep other draft'
        assert state.data['drafts'][''] == 'Keep composer draft'
        assert app['service'].runtime.sent == []
    finally:
        await bridge.close()


async def test_failed_lookup_preserves_current_selection_and_never_escapes_directory(server, tmp_path):
    app, url = server
    workspace = tmp_path / 'project'
    local, _ = await native_chat(app['service'], workspace, 'abcd1111-1111-4111-8111-111111111111')
    await native_chat(app['service'], workspace, 'abcd2222-2222-4222-8222-222222222222')
    other_native = str(uuid.uuid4())
    other, _ = await native_chat(app['service'], tmp_path / 'other', other_native)
    state = ClientState(tmp_path / 'client', url)
    bridge = UnifiedBridge(lambda _: None, Transport(url, app['control_token'], state.identity),
                           state, session=local, workspace=str(workspace))
    try:
        await bridge.open()
        state.draft(local, 'Unsent work')
        for value, message in [('abcd', 'ambiguous'), ('missing', 'No matching'),
                               (other, 'No matching'), (other_native, 'No matching')]:
            with pytest.raises(ValueError, match=message):
                await bridge.select(value)
            assert bridge.selected == state.data['session'] == local
            assert state.data['drafts'][local] == 'Unsent work'
        assert app['service'].runtime.sent == []
    finally:
        await bridge.close()


async def test_prefix_resolution_checks_all_pages_and_deduplicates_aliases():
    transport = Transport('http://localhost:8941', 'unused', 'fixture')
    pages = {0: {'items': [{'id': 'host-a', 'nativeIdentity': 'abcd-one',
                           'runtimeSessionId': 'abcd-one', 'workspace': '/project'}], 'nextOffset': 100},
             100: {'items': [{'id': 'host-b', 'nativeIdentity': 'abcd-two',
                             'workspace': '/project'}], 'nextOffset': None}}
    calls = []

    async def sessions(*, offset, workspace):
        calls.append((offset, workspace))
        return pages[offset]

    transport.sessions = sessions
    with pytest.raises(ValueError, match='ambiguous'):
        await transport.resolve_session('abcd', workspace='/project')
    assert calls == [(0, '/project'), (100, '/project')]
    assert await transport.resolve_session('abcd-one', workspace='/project') == 'host-a'
    assert await transport.resolve_session('abcd-t', workspace='/project') == 'host-b'
    with pytest.raises(ValueError, match='No matching'):
        await transport.resolve_session('host-a', workspace='/other')
    pages[100]['nextOffset'] = 0
    with pytest.raises(ValueError, match='paging'):
        await transport.resolve_session('missing', workspace='/project')

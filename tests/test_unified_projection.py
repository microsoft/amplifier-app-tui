"""Synthetic retained history: ordering only, never a runtime execution fixture."""
import copy

from amplifier_tui.unified_projection import project


def history():
    return {'id': 's', 'messages': [
        {'id': 'u1', 'role': 'user', 'inputId': 't1', 'text': 'First request', 'createdAt': 10},
        {'id': 'a1', 'role': 'assistant', 'text': 'First answer', 'createdAt': 20},
        {'id': 'u2', 'role': 'user', 'inputId': 't2', 'text': 'Second request', 'createdAt': 30},
        {'id': 'a2', 'role': 'assistant', 'streamId': 'response', 'text': 'Second answer', 'createdAt': 40},
    ], 'execution': {'turns': [
        {'id': 't1', 'anchorMessageId': 'u1'}, {'id': 't2', 'anchorMessageId': 'u2'},
    ], 'nodes': [
        {'id': 'second', 'kind': 'tool', 'turnId': 't2', 'startedAt': 35, 'phase': 'done'},
        {'id': 'first', 'kind': 'tool', 'turnId': 't1', 'startedAt': 15, 'phase': 'done'},
    ]}}


def ids(rows):
    return [row['id'] for row in rows]


def test_retained_tools_interleave_without_mutating_saved_history():
    session = history()
    saved = copy.deepcopy(session)
    assert ids(project(session, {})) == ['input:t1', 'execution:first', 'message:a1',
                                          'input:t2', 'execution:second', 'stream:response']
    assert session == saved


def test_live_tool_and_final_response_keep_order_and_identity():
    session = history()
    final = session['messages'].pop()
    session.update(streaming='Second', streamingId='response')
    session['execution']['nodes'][0]['phase'] = 'running'
    partial = project(session, {})
    assert ids(partial)[-2:] == ['execution:second', 'stream:response']
    session['execution']['nodes'][0]['phase'] = 'done'
    session['messages'].append(final)
    session.pop('streaming')
    assert ids(project(session, {})) == ids(partial)


def test_undated_turns_use_identity_and_explicit_node_anchor_wins():
    session = history()
    for message in session['messages']:
        message['timestampKnown'] = False
    session['execution']['nodes'][0].update(anchorMessageId='a1')
    assert ids(project(session, {})) == ['input:t1', 'execution:first', 'message:a1',
                                          'execution:second', 'input:t2', 'stream:response']
    session['execution']['turns'] = [{'id': 't1', 'inputId': 't1'}]
    assert ids(project(session, {}))[1] == 'execution:first'


def test_clock_changes_do_not_sort_canonical_messages_or_hide_unknown_activity():
    session = history()
    session['messages'][1]['createdAt'] = 5
    session['execution']['nodes'].append({'id': 'unknown', 'kind': 'tool', 'phase': 'error'})
    result = project(session, {})
    assert ids(result)[:2] == ['unpositioned-activity', 'execution:unknown']
    assert [row['text'] for row in result if row['kind'] in {'user', 'assistant'}] == [
        'First request', 'First answer', 'Second request', 'Second answer']
    assert next(row for row in result if row['id'] == 'execution:unknown')['status'] == 'error'


def test_worker_artifact_and_parallel_tools_keep_recorded_start_order():
    session = history()
    session['execution']['nodes'] += [
        {'id': 'parallel-later', 'kind': 'tool', 'startedAt': 18},
        {'id': 'parallel-earlier', 'kind': 'tool', 'startedAt': 16},
    ]
    session['workers'] = [{'id': 'w', 'startedAt': 17, 'status': 'completed'}]
    session['artifacts'] = [{'id': 'file', 'createdAt': 19}]
    assert ids(project(session, {}))[:7] == ['input:t1', 'execution:first', 'execution:parallel-earlier',
        'worker:w', 'execution:parallel-later', 'artifact:file', 'message:a1']


def test_history_excludes_live_delivery_and_does_not_duplicate_accepted_input():
    session = history()
    outbox = {'t2': {'session': 's', 'action': 'conversation.send', 'status': 'unknown', 'args': {'text': 'Second request'}}}
    session['error'] = 'Failed'
    result = project(session, outbox)
    assert ids(result).count('input:t2') == 1
    assert ids(result)[-2:] == ['delivery:t2', 'session-error:s']
    assert not any(row['id'].startswith(('delivery:', 'session-error:')) for row in project(session, outbox, live=False))

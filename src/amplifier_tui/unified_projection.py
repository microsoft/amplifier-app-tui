"""Identified display projection of Unified snapshots; no model context or execution."""
import json
import math
from bisect import bisect_right


def _time(value):
    return value if type(value) in (int, float) and math.isfinite(value) else None


def _history(session):
    """Merge observations into message gaps without reordering canonical messages.

    Explicit host anchors win. For older hosts, recorded start times position an
    observation; a turn's identified input anchors activity with no usable clock.
    Unpositioned records stay in a labelled group before the transcript, never
    masquerading as work performed after the latest answer.
    """
    messages = session.get('messages', [])
    positions = {row['id']: index + 1 for index, row in enumerate(messages)}
    inputs = {row['inputId']: index + 1 for index, row in enumerate(messages)
              if row.get('inputId') and row.get('role') == 'user'}
    times = sorted((row['createdAt'], index + 1) for index, row in enumerate(messages)
                   if row.get('timestampKnown') is not False and _time(row.get('createdAt')) is not None)
    # Canonical message order remains authoritative even with a clock correction.
    clock, gaps, latest = [], [], 0
    for at, gap in times:
        latest = max(latest, gap)
        clock.append(at)
        gaps.append(latest)
    turns = {row['id']: row for row in session.get('execution', {}).get('turns', [])}
    buckets, unpositioned = {}, []

    def place(row, item):
        turn = turns.get(row.get('turnId'), {})
        if 'anchorMessageId' in row:
            anchor = row['anchorMessageId']
            gap = positions.get(anchor) if anchor else 0
        else:
            at = _time(row.get('startedAt'))
            if at is None:
                at = _time(row.get('createdAt'))
            index = bisect_right(clock, at) - 1 if at is not None else -1
            gap = gaps[index] if index >= 0 else (0 if at is not None and clock else None)
            if gap is None:
                if 'anchorMessageId' in turn:
                    anchor = turn['anchorMessageId']
                    gap = positions.get(anchor) if anchor else 0
                else:
                    gap = (positions.get(turn.get('messageId')) or positions.get(turn.get('userMessageId'))
                           or inputs.get(turn.get('inputId')) or inputs.get(turn.get('id')))
        if gap is None:
            unpositioned.append(item)
        else:
            buckets.setdefault(gap, []).append((row, item))

    for node in session.get('execution', {}).get('nodes', []):
        if node.get('kind') == 'tool':
            place(node, {'id': 'execution:' + node['id'], 'kind': 'tool',
                         'text': node.get('label') or node.get('summary') or 'Tool',
                         'status': node.get('phase', 'unknown'),
                         'detail': json.dumps(node, ensure_ascii=False)})
    for worker in session.get('workers', []):
        place(worker, {'id': 'worker:' + worker['id'], 'kind': 'tool',
                       'text': worker.get('title') or worker.get('instruction') or worker.get('name', 'Worker'),
                       'status': worker.get('status', 'unknown'),
                       'detail': json.dumps(worker, ensure_ascii=False)})
    for artifact in session.get('artifacts', []):
        place(artifact, {'id': 'artifact:' + artifact['id'], 'kind': 'notice',
                         'text': artifact.get('title') or artifact.get('name') or 'Artifact',
                         'status': '', 'detail': json.dumps(artifact, ensure_ascii=False)})

    def activity(gap):
        rows = buckets.get(gap, [])
        # Unknown timestamps retain source order. Known ones order concurrent
        # observations by start, not by when their completion update arrived.
        ordered = iter(sorted((pair for pair in rows if _time(pair[0].get('startedAt', pair[0].get('createdAt'))) is not None),
                              key=lambda pair: pair[0].get('startedAt', pair[0].get('createdAt'))))
        return [next(ordered)[1] if _time(row.get('startedAt', row.get('createdAt'))) is not None else item for row, item in rows]

    items = []
    if unpositioned:
        items.append({'id': 'unpositioned-activity', 'kind': 'notice',
                      'text': 'Activity · position unavailable', 'status': '', 'detail': ''})
        items.extend(unpositioned)
    items.extend(activity(0))
    for index, message in enumerate(messages):
        command = message.get('inputId')
        identity = ('input:' + command if command and message.get('role') == 'user' else
                    'stream:' + message['streamId'] if message.get('streamId') else
                    'message:' + message['id'])
        items.append({'id': identity, 'kind': message.get('role', 'notice'), 'text': message.get('text', ''),
                      'status': 'interrupted' if message.get('partial') else '',
                      'detail': json.dumps(message, ensure_ascii=False)})
        items.extend(activity(index + 1))
    return items


def project(session, outbox, *, live=True):
    items = _history(session)
    if not live:
        return items
    delivered = {message.get('inputId') for message in session.get('messages', []) if message.get('role') == 'user'}
    for command, row in outbox.items():
        if (row.get('session') != session.get('id') or row.get('action') != 'conversation.send'
                or row.get('status') == 'edited'):
            continue
        if command not in delivered:
            items.append({'id': 'input:' + command, 'kind': 'user',
                          'text': row['args']['text'], 'status': '', 'detail': ''})
        if row['status'] in {'sending', 'unknown', 'failed'}:
            items.append({'id': 'delivery:' + command, 'kind': 'notice',
                          'text': {'sending': 'Sending…', 'unknown': 'Delivery unknown · /deliveries to inspect or retry the same request',
                                   'failed': 'Not accepted · /deliveries to retry or edit'}[row['status']],
                          'status': row['status'], 'detail': row.get('error', '')})
    if session.get('streaming') and session.get('streamingId'):
        items.append({'id': 'stream:' + session['streamingId'], 'kind': 'assistant',
                      'text': session['streaming'], 'status': 'running', 'detail': ''})
    elif session.get('streaming'):
        items.append({'id': 'legacy-stream', 'kind': 'notice', 'text': 'Receiving response…',
                      'status': 'running', 'detail': 'This host lacks stable partial-response identities; the final response will appear here.'})
    if session.get('error'):
        items.append({'id': 'session-error:' + str(session.get('id', '')),
                      'kind': 'notice', 'text': session['error'],
                      'status': 'failed', 'detail': ''})
    return items

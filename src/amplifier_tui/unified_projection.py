"""Identified display projection of Unified snapshots; no model context or execution."""
import json


def project(session, outbox):
    items, delivered = [], set()
    for message in session.get('messages', []):
        command = message.get('inputId')
        if command and message.get('role') == 'user':
            delivered.add(command)
        identity = ('input:' + command if command and message.get('role') == 'user' else
                    'stream:' + message['streamId'] if message.get('streamId') else
                    'message:' + message['id'])
        role = message.get('role', 'notice')
        status = 'interrupted' if message.get('partial') else ''
        items.append({'id': identity, 'kind': role, 'text': message.get('text', ''),
                      'status': status, 'detail': json.dumps(message, ensure_ascii=False)})
    if session.get('streaming') and session.get('streamingId'):
        items.append({'id': 'stream:' + session['streamingId'], 'kind': 'assistant',
                      'text': session['streaming'], 'status': 'running', 'detail': ''})
    elif session.get('streaming'):
        items.append({'id': 'legacy-stream', 'kind': 'notice', 'text': 'Receiving response…',
                      'status': 'running', 'detail': 'This host lacks stable partial-response identities; the final response will appear here.'})
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
    if session.get('error'):
        items.append({'id': 'session-error:' + str(session.get('id', '')),
                      'kind': 'notice', 'text': session['error'],
                      'status': 'failed', 'detail': ''})
    for node in session.get('execution', {}).get('nodes', []):
        if node.get('kind') != 'tool':
            continue
        items.append({'id': 'execution:' + node['id'], 'kind': 'tool',
                      'text': node.get('label') or node.get('summary') or 'Tool',
                      'status': node.get('phase', 'unknown'),
                      'detail': json.dumps(node, ensure_ascii=False)})
    for worker in session.get('workers', []):
        items.append({'id': 'worker:' + worker['id'], 'kind': 'tool',
                      'text': worker.get('title') or worker.get('instruction') or worker.get('name', 'Worker'),
                      'status': worker.get('status', 'unknown'),
                      'detail': json.dumps(worker, ensure_ascii=False)})
    for artifact in session.get('artifacts', []):
        items.append({'id': 'artifact:' + artifact['id'], 'kind': 'notice',
                      'text': artifact.get('title') or artifact.get('name') or 'Artifact',
                      'status': '', 'detail': json.dumps(artifact, ensure_ascii=False)})
    return items

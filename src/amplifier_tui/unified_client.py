"""Connected backend for the existing Ratatui protocol. Unified owns all execution."""
from __future__ import annotations

import asyncio
import uuid

from .unified_projection import project
from .unified_transport import Rejected


class UnifiedBridge:
    async_stop = True

    def __init__(self, emit, transport, state, *, session=None, workspace=None, resume_picker=False):
        self.emit, self.transport, self.store = emit, transport, state
        self.selected = None if resume_picker else session or state.data.get('session')
        self.resume_picker = resume_picker
        self.workspace = workspace
        self.session = {}
        self.actions = set()
        self.pump = None
        self.tasks = set()
        self.online = False
        self.generation = 0
        self.revision = -1
        self.instance = None
        self.opened = False
        self.deleted = False
        self.switch_lock = asyncio.Lock()
        self.submission_lock = asyncio.Lock()
        self.retired_instances = set()

    def send(self, kind, **fields):
        self.emit({'type': kind, 'session_id': self.selected or '', **fields})

    def later(self, coroutine):
        task = asyncio.create_task(coroutine)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task

    async def open(self):
        await self.transport.open()
        self.actions = await self.transport.actions()
        self.online = True
        if self.selected:
            await self.select(self.selected)
        else:
            self.session = {'id': None, 'messages': []}
            self.initial()
        self.opened = True

    def initial(self, preserve_draft=False):
        self.send('snapshot', reset=not preserve_draft, connected=True, ready=True, navigation=True,
                  resume_picker=self.resume_picker,
                  durable=bool(self.selected), mode='UNIFIED', title=self.session.get('title') or 'Amplifier',
                  context=self.transport.url + ' · ' + (self.session.get('workspace') or self.workspace or 'Host workspace'),
                  draft=self.store.data['drafts'].get(self.selected or '', ''), items=self.items(),
                  system=['Connected to ' + self.transport.url,
                          'Exit detaches; work continues on Unified.',
                          'Recover this view with --client ' + self.store.identity,
                          'Unsupported standalone controls are not sent to a model.'])
        self.resume_picker = False
        self.send('system', lines=['Host: ' + self.transport.url,
                  'Client: ' + self.store.identity,
                  'Stop uses Unified cancellation; graceful/force stages are not negotiated.',
                  'Use /deliveries to inspect uncertain input. Rich artifacts open in the web client.'],
                  commands=['/new', '/resume', '/rename', '/stop', '/deliveries'], steer=False)
        # The connected protocol does not negotiate standalone mode controls.
        self.send('mode_status', supported=False)
        self.publish()

    def items(self):
        return project(self.session, self.store.data['outbox'])[-100:]

    def publish(self):
        self.send('remote_items', items=self.items(), title=self.session.get('title', 'Amplifier'))
        status = self.session.get('status', 'ready')
        ownership = self.session.get('ownership', {})
        blocked = ownership.get('status') in {'blocked', 'yielded', 'yielding', 'taking-over', 'yield-failed'}
        # Clear an earlier ownership block after the server reports acquisition.
        if blocked or getattr(self, '_blocked', False):
            self.send('ownership', status='blocked' if blocked else 'owned',
                      message=('In use by ' + ownership.get('source', 'another application')
                               + ' · Continue here requests takeover') if blocked else 'Connected')
        self._blocked = blocked
        pending = next((row for row in self.session.get('approvals', [])
                        if row.get('status') == 'pending'), None)
        approval = ({'id': pending['id'], 'prompt': pending.get('prompt', 'Approval requested'),
                     'options': ['allow', 'deny']} if pending else None)
        self.send('state', ready=self.online and not blocked and not self.deleted, busy=status in {'working', 'starting', 'stopping'},
                  status=('Disconnected · reconnecting; no input resent' if not self.online else
                          'Choose a conversation or send to start one' if not self.selected else
                          'Unified · ' + status), approval=approval,
                  cancellation='remote' if status == 'stopping' else '', turn_id=self.session.get('id', ''))

    def connection(self, online):
        if self.online != online:
            self.online = online
            self.publish()

    def reconcile(self, snapshot):
        if snapshot.get('protocolVersion') != 1:
            raise ValueError('Unsupported session snapshot version')
        if snapshot.get('deleted'):
            self.deleted = True
            self.send('state', ready=False, busy=False, status='Conversation removed on the host', approval=None)
            return
        session = snapshot.get('session')
        if not isinstance(session, dict) or session.get('id') != self.selected:
            raise ValueError('Snapshot targets a different conversation')
        instance, revision = snapshot.get('hostInstanceId'), snapshot.get('revision')
        if not isinstance(instance, str) or type(revision) is not int:
            raise ValueError('Missing snapshot identity/revision')
        if instance in self.retired_instances:
            return
        if instance == self.instance and revision < self.revision:
            return
        if self.instance and self.instance != instance:
            self.retired_instances.add(self.instance)
        self.instance, self.revision, self.session = instance, revision, session
        changed = False
        for message in session.get('messages', []):
            identity = message.get('inputId')
            if identity in self.store.data['outbox'] and message.get('delivery', {}).get('status') == 'accepted':
                del self.store.data['outbox'][identity]
                changed = True
        if changed:
            self.store.save()
        self.publish()

    async def watch(self, identity, generation):
        try:
            async for snapshot in self.transport.snapshots(identity, self.connection):
                if generation != self.generation:
                    return
                self.reconcile(snapshot)
        except (Rejected, ValueError, OSError) as exc:
            if generation == self.generation:
                self.online = False
                self.send('state', ready=False, busy=False, approval=None,
                          status=f'Connection unavailable: {exc}; no work resent')

    async def select(self, identity, *, preserve_draft=False):
        identity = await self.transport.resolve_session(identity, workspace=self.workspace)
        snapshot = await self.transport.snapshot(identity)
        if self.pump:
            self.pump.cancel()
            await asyncio.gather(self.pump, return_exceptions=True)
        self.generation += 1
        self.selected = identity
        self.deleted = False
        self.instance, self.revision = None, -1
        self.session = snapshot['session']
        self.store.data['session'] = identity
        self.store.save()
        self.online = True
        self.initial(preserve_draft=preserve_draft)
        self.reconcile(snapshot)
        self.pump = asyncio.create_task(self.watch(identity, self.generation))
        if 'session.warm' in self.actions:
            self.later(self.warm(identity))

    async def warm(self, identity):
        try:
            await self.transport.command(identity, 'session.warm', {}, str(uuid.uuid4()))
        except (Rejected, ValueError, OSError):
            pass  # Preparation is advisory; ordinary send/ownership status remains authoritative.

    async def dispatch(self, request):
        op = request.get('op')
        target = request.get('session_id') or None
        if target != self.selected:
            return False, 'This control belongs to another conversation; nothing sent'
        if op in {'draft', 'editor_draft'}:
            self.store.draft(target, request.get('text', ''))
            return True, 'Draft saved locally'
        if op == 'deliveries':
            self.send('deliveries', entries=[{'id': key, **row} for key, row in self.store.data['outbox'].items()
                                             if row.get('session') == target])
            return True, 'Pending delivery; exact retry only'
        if op == 'edit_delivery':
            row = self.store.data['outbox'].get(request.get('id'))
            if not row or row.get('session') != target or row['status'] != 'failed':
                return False, 'Only definitively rejected input can be edited; unknown input is retained'
            self.send('delivery_draft', text=row['args'].get('text', ''))
            row['status'] = 'edited'
            self.store.draft(target, row['args'].get('text', ''))
            self.store.save()
            self.publish()
            return True, 'Unsent text copied to composer; nothing submitted'
        if not self.online:
            return False, 'Disconnected; draft retained. Wait for reconnect before sending'
        if op == 'conversations':
            page = await self.transport.sessions(offset=request.get('offset', 0), workspace=self.workspace)
            query = request.get('query', '').casefold()
            rows = [{'id': row['id'], 'title': row.get('title', 'Untitled'), 'cwd': row.get('workspace', ''),
                     'status': row.get('status', '')} for row in page['items']
                    if not query or query in ' '.join(str(row.get(key) or '') for key in
                        ('title', 'id', 'nativeIdentity', 'runtimeSessionId')).casefold()]
            self.send('conversations', request_id=request['request_id'], sessions=rows,
                      offset=request.get('offset', 0), next_offset=page.get('nextOffset'),
                      truncated=page.get('nextOffset') is not None, query=request.get('query', ''),
                      partial=bool(query and page.get('nextOffset')),
                      scope='Unified host conversations · title/ID search on this page; host paths')
            return True, 'Conversations loaded'
        if op == 'switch':
            async with self.switch_lock:
                if target != self.selected:
                    return False, 'Selection changed; nothing opened'
                self.store.draft(target, request.get('draft', ''))
                if request.get('target') == 'new':
                    self.selected = None
                    self.deleted = False
                    self.session = {'id': None, 'messages': []}
                    self.store.data['session'] = None
                    self.store.save()
                    self.generation += 1
                    if self.pump:
                        self.pump.cancel()
                        await asyncio.gather(self.pump, return_exceptions=True)
                    self.initial()
                else:
                    await self.select(request['target'])
            self.send('switch_result', request_id=request['request_id'], ok=True)
            return True, 'Conversation opened'
        if op == 'inspect':
            self.send('inspection', request_id=request['request_id'], category=request.get('category'),
                      rows=[], partial=True, scope='Inspect full runtime details in the Unified web client; no local runtime is mounted.')
            return True, 'Host inspection boundary'
        if op == 'history_page':
            offset = request.get('offset', 0)
            if type(offset) is not int or not 0 <= offset <= 1000000:
                return False, 'Invalid history offset'
            try:
                async with asyncio.timeout(15):
                    while len(project(self.session, {}, live=False)) < offset + 100 and self.session.get('sharedHistoryOffset', 0):
                        before = self.session['sharedHistoryOffset']
                        await self.transport.command(target, 'session.history', {'before': before, 'limit': 100}, str(uuid.uuid4()))
                        while self.selected == target and self.session.get('sharedHistoryOffset') == before:
                            self.reconcile(await self.transport.snapshot(target))
                            if self.session.get('historyError'):
                                raise ValueError(self.session['historyError'])
                            await asyncio.sleep(.05)
                if target != self.selected:
                    return False, 'Selection changed; earlier history was not opened'
                history = project(self.session, {}, live=False)
                end = max(0, len(history) - offset)
                start = max(0, end - 100)
                remaining = self.session.get('sharedHistoryOffset', 0)
                rows = history[start:end]
                self.send('history_page', request_id=request['request_id'], items=rows, offset=offset,
                          next_offset=offset + 100 if start or remaining else None,
                          previous_offset=max(0, offset - 100) if offset else None,
                          start=remaining + start + 1 if rows else 0, end=remaining + end,
                          total=remaining + len(history), scope='Host timeline; read only; earlier activity depends on host retention')
                return True, 'History loaded'
            except (OSError, ValueError, Rejected, TimeoutError) as exc:
                self.send('history_page', request_id=request['request_id'], error=str(exc) or 'History is still unavailable; retry explicitly')
                return False, 'Earlier history unavailable; current conversation retained'
        if op == 'cancel_switch':
            return False, 'Opening completes independently; choose another conversation afterwards'
        if self.deleted:
            return False, 'Conversation removed; use New or Resume to choose another'
        if op not in {'submit', 'stop', 'decision', 'rename', 'continue_here', 'retry_delivery'}:
            return False, 'This standalone control is not supported by the connected client; use Unified web controls'
        async with self.submission_lock if op == 'submit' and target is None else _Unlocked():
            if op == 'submit' and target != self.selected:
                return False, 'Selection changed; text retained, nothing sent'
            # Capture the request target, never the possibly newer selected conversation.
            if op == 'retry_delivery':
                identity = request.get('id')
                row = self.store.data['outbox'].get(identity)
                if not row or row.get('session') != target or row['status'] not in {'unknown', 'failed'}:
                    return False, 'Delivery changed; inspect it again'
            else:
                action, args = {
                    'submit': ('conversation.send', {'text': request.get('text', '')}),
                    'stop': ('conversation.stop', {}),
                    'decision': ('approval.respond', {'id': request.get('approval_id'), 'decision': request.get('option')}),
                    'rename': ('session.rename', {'title': request.get('title', request.get('text', ''))}),
                    'continue_here': ('session.takeover', {}),
                }[op]
                if action not in self.actions:
                    return False, 'This host does not offer that action'
                if op == 'submit' and not args['text'].strip():
                    return False, 'Write a message first'
                if request.get('image_id'):
                    return False, 'Connected image upload is not available; use the web client'
                identity = str(uuid.uuid4())
                row = {'session': target, 'action': action, 'args': args, 'status': 'sending',
                       'local_request': request['request_id'], 'generation': self.generation}
                if target is None:
                    if op != 'submit':
                        return False, 'Select a conversation first'
                    row['create_id'] = str(uuid.uuid4())
                self.store.data['outbox'][identity] = row
            return await self.deliver(identity, row)

    async def deliver(self, identity, row):
        row['status'] = 'sending'
        self.store.save()  # Durable intent before the first request, including session creation.
        self.publish()
        if row['action'] == 'conversation.send' and row.get('generation') == self.generation:
            self.send('input_pending', request_id=row.get('local_request'), text=row['args']['text'])
            if self.store.data['drafts'].get(row['session'] or '') == row['args']['text']:
                self.store.draft(row['session'], '')
        acknowledged = False
        try:
            if row['session'] is None:
                created = await self.transport.command(None, 'session.create',
                    {'workspace': self.workspace} if self.workspace else {}, row['create_id'])
                state = created.get('state', {})
                new_id = created.get('result', {}).get('sessionId') or state.get('selectedSessionId')
                if not new_id:
                    raise ValueError('Creation outcome unknown; retain this request for exact retry')
                row['session'] = new_id
                self.store.save()
                if self.selected is None and row.get('generation') == self.generation:
                    self.store.data['drafts'][new_id] = self.store.data['drafts'].pop('', '')
                    await self.select(new_id, preserve_draft=True)
            result = await self.transport.command(row['session'], row['action'], row['args'], identity)
            uncertain = result.get('delivery') == 'unknown'
            acknowledged = not uncertain
            # A concurrent snapshot may already have acknowledged and removed this entry.
            if identity in self.store.data['outbox']:
                row['status'] = 'unknown' if uncertain else 'accepted'
                if uncertain:
                    row['error'] = 'Unified saved this request, but execution is unconfirmed.'
                else:
                    row.pop('error', None)
                if row['action'] != 'conversation.send':
                    del self.store.data['outbox'][identity]
                self.store.save()
            if result.get('session', {}).get('id') == self.selected:
                self.reconcile(result)
            if uncertain and identity in self.store.data['outbox']:
                self.publish()
                return False, 'Execution unconfirmed · /deliveries retains the original request'
            return True, 'Accepted by Unified; execution outcome is separate'
        except Rejected as exc:
            if identity not in self.store.data['outbox']:
                return True, 'Acceptance confirmed by the conversation stream'
            row['status'] = 'failed' if 400 <= exc.status < 500 and exc.status != 408 else 'unknown'
            row['error'] = str(exc)
            self.store.save()
            self.publish()
            await self.refresh_delivery(row)
            if identity not in self.store.data['outbox']:
                return True, 'Acceptance confirmed by the conversation'
            self.publish()
            return False, str(exc) + ' · /deliveries retains this request'
        except (OSError, ValueError, TimeoutError) as exc:
            if identity not in self.store.data['outbox']:
                return True, 'Acceptance confirmed by the conversation stream'
            if acknowledged:
                self.publish()
                return True, 'Accepted by Unified; live view could not refresh'
            row['status'], row['error'] = 'unknown', (
                'The response could not be verified.' if isinstance(exc, ValueError)
                else 'The connection ended before delivery was confirmed.')
            self.store.save()
            self.publish()
            await self.refresh_delivery(row)
            if identity not in self.store.data['outbox']:
                return True, 'Acceptance confirmed by the conversation'
            self.publish()
            return False, 'Delivery unknown · /deliveries for exact retry; nothing resent automatically'

    async def refresh_delivery(self, row):
        identity, generation = self.selected, self.generation
        if not identity or row['session'] != identity:
            return
        try:
            async with asyncio.timeout(5):
                snapshot = await self.transport.snapshot(identity)
            if identity == self.selected and generation == self.generation:
                self.reconcile(snapshot)
        except (OSError, ValueError, Rejected, TimeoutError):
            pass  # Failed observation cannot authorize another command.

    async def close(self):
        if self.pump:
            self.pump.cancel()
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, *([self.pump] if self.pump else []), return_exceptions=True)
        await self.transport.close()
        self.store.close()  # Never sends Stop or releases the host's execution lock.


class _Unlocked:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

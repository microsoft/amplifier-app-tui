"""Private client intent only; never a transcript, credentials or execution lock."""
from __future__ import annotations

import fcntl
import json
import os
import re
import tempfile
import uuid
from pathlib import Path


class ClientState:
    def __init__(self, root, url, identity=None):
        self.identity = identity or str(uuid.uuid4())
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}', self.identity):
            raise ValueError('Client ID must contain 1–100 letters, digits, underscores or hyphens')
        directory = Path(root).expanduser() / 'connections'
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = directory / (self.identity + '.json')
        lock_path = directory / (self.identity + '.lock')
        self.lock = os.fdopen(os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600), 'a+')
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.lock.close()
            raise ValueError('That client is already open; omit --client for an independent view') from None
        self.data = {'version': 1, 'url': url, 'session': None, 'drafts': {}, 'outbox': {}}
        try:
            if self.path.exists():
                with os.fdopen(os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW)) as stream:
                    data = json.load(stream)
                if (data.get('version') != 1 or data.get('url') != url
                        or not isinstance(data.get('drafts'), dict)
                        or not isinstance(data.get('outbox'), dict)):
                    raise ValueError('Client recovery state is incompatible; original retained')
                self.data = data
                for row in self.data['outbox'].values():
                    if row['status'] == 'sending':
                        row['status'] = 'unknown'
            self.save()
        except BaseException:
            self.close()
            raise

    def save(self):
        fd, temporary = tempfile.mkstemp(prefix='.client-', dir=self.path.parent)
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump(self.data, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def draft(self, session, text):
        self.data['drafts'][session or ''] = text
        self.save()

    def close(self):
        if not self.lock.closed:
            self.lock.close()

"""Unified v1 transport. Reconnection reads state; mutations never retry themselves."""
from __future__ import annotations

import asyncio
import json
import ssl
from urllib.parse import quote, urlencode, urlsplit

import aiohttp

MAX_FRAME = 32 * 1024 * 1024


class Rejected(RuntimeError):
    def __init__(self, status, data):
        self.status, self.data = status, data
        super().__init__(data.get('error', f'Unified returned HTTP {status}'))


def validate_url(value):
    parts = urlsplit(value)
    if (parts.scheme not in {'http', 'https'} or not parts.hostname or parts.username
            or parts.password or parts.query or parts.fragment or parts.path not in {'', '/'}):
        raise ValueError('Use a host URL without credentials, path, query or fragment')
    if parts.scheme == 'http' and parts.hostname not in {'localhost', '127.0.0.1', '::1'}:
        raise ValueError('Remote connections require HTTPS; use --ca-file for a private CA')
    return value.rstrip('/')


class Transport:
    def __init__(self, url, token, client_id, *, ca_file=None):
        self.url = validate_url(url)
        self.token, self.client_id = token, client_id
        self.ssl = ssl.create_default_context(cafile=str(ca_file)) if ca_file else None
        self.http = None
        self.attached = None

    async def open(self):
        self.http = aiohttp.ClientSession(headers={
            'Authorization': 'Bearer ' + self.token, 'X-Amplifier-Client': self.client_id})
        try:
            self.attached = await self.request('POST', '/api/clients/attach', {
                'clientId': self.client_id, 'kind': 'tui', 'protocolVersion': 1})
            if self.attached.get('protocolVersion') != 1:
                raise ValueError('Unsupported Unified protocol; no work sent')
        except BaseException:
            await self.close()
            raise
        return self.attached

    async def close(self):
        if self.http:
            await self.http.close()

    async def request(self, method, path, data=None):
        try:
            return await self._request(method, path, data)
        except aiohttp.ClientError as exc:
            # Never include authenticated request headers in diagnostics.
            raise OSError(type(exc).__name__) from None

    async def _request(self, method, path, data=None):
        async with self.http.request(method, self.url + path, json=data, ssl=self.ssl,
                allow_redirects=False, timeout=aiohttp.ClientTimeout(total=60)) as reply:
            # Bound reading even when a peer omits or misstates Content-Length.
            body = bytearray()
            async for chunk in reply.content.iter_chunked(65536):
                body.extend(chunk)
                if len(body) > MAX_FRAME:
                    raise ValueError('Unified response exceeded the client size limit')
            try:
                result = json.loads(body)
            except (ValueError, UnicodeDecodeError):
                if reply.status >= 400:
                    # Proxies and unhandled host exceptions can return text/HTML.
                    # Preserve HTTP evidence without displaying an arbitrary body.
                    raise Rejected(reply.status, {'error':
                        f'Unified could not complete the request (HTTP {reply.status}). '
                        'Check the conversation status before retrying.'}) from None
                raise ValueError(f'Unified returned an invalid response (HTTP {reply.status})') from None
            if not isinstance(result, dict):
                raise ValueError('Unified response must be an object')
            if reply.status != 200 or result.get('accepted') is False:
                raise Rejected(reply.status, result)
            return result

    async def actions(self):
        # Unlike other endpoints this returns a JSON array.
        async with self.http.get(self.url + '/api/actions', ssl=self.ssl,
                allow_redirects=False, timeout=aiohttp.ClientTimeout(total=30)) as reply:
            if reply.status != 200:
                raise Rejected(reply.status, {'error': 'Cannot discover Unified actions'})
            body = bytearray()
            async for chunk in reply.content.iter_chunked(65536):
                body.extend(chunk)
                if len(body) > MAX_FRAME:
                    raise ValueError('Unified action catalog exceeded the client size limit')
            data = json.loads(body)
            if not isinstance(data, list):
                raise ValueError('Unified action catalog must be an array')
            return {row['name'] for row in data if isinstance(row, dict) and 'name' in row}

    async def sessions(self, *, offset=0, workspace=None):
        query = {'offset': offset, 'limit': 100}
        if workspace:
            query['workspace'] = workspace
        return await self.request('GET', '/api/sessions?' + urlencode(query))

    async def snapshot(self, identity):
        return await self.request('GET', '/api/sessions/' + quote(identity, safe=''))

    async def command(self, identity, action, args, command_id):
        path = ('/api/sessions/' + quote(identity, safe='') + '/commands'
                if identity else '/api/actions')
        return await self.request('POST', path, {'id': command_id, 'action': action, 'args': args})

    async def snapshots(self, identity, connection):
        path = '/api/sessions/' + quote(identity, safe='') + '/events'
        delay = .25
        while True:
            try:
                async with self.http.get(self.url + path, ssl=self.ssl, allow_redirects=False,
                        timeout=aiohttp.ClientTimeout(total=None, sock_read=45)) as reply:
                    if reply.status != 200:
                        raise Rejected(reply.status, {'error': 'Session stream unavailable'})
                    buffer, event, lines, size = bytearray(), '', [], 0
                    async for chunk in reply.content.iter_chunked(65536):
                        buffer.extend(chunk)
                        if len(buffer) + size > MAX_FRAME:
                            raise ValueError('Unified stream exceeded the client size limit')
                        while b'\n' in buffer:
                            raw, _, buffer = buffer.partition(b'\n')
                            line = raw.decode('utf-8').rstrip('\r')
                            if line.startswith('event:'):
                                event = line[6:].strip()
                            elif line.startswith('data:'):
                                lines.append(line[5:].lstrip())
                                size += len(raw)
                            elif not line:
                                if event == 'snapshot' and lines:
                                    data = json.loads('\n'.join(lines))
                                    connection(True)
                                    delay = .25
                                    yield data
                                    if data.get('deleted'):
                                        return
                                event, lines, size = '', [], 0
                    connection(False)
            except aiohttp.ClientSSLError:
                raise ValueError('Server TLS verification failed; check the trusted CA') from None
            except (aiohttp.ClientConnectionError, aiohttp.ClientPayloadError, TimeoutError):
                connection(False)
            await asyncio.sleep(delay)
            delay = min(5, delay * 2)

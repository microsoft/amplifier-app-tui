"""Launch the optional terminal client of an existing Amplifier Unified service."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from .client_state import ClientState
from .unified_client import UnifiedBridge
from .unified_transport import Transport, validate_url


def parser():
    result = argparse.ArgumentParser(description=__doc__, epilog='Use amplifier-tui --standalone with the standalone extra for a local execution host.')
    result.add_argument('--server', default=os.environ.get('AMPLIFIER_UNIFIED_URL', 'http://127.0.0.1:8941'),
                        help='Unified 0.19.5+ URL; remote hosts require HTTPS')
    result.add_argument('--token-file', type=Path, help='Private control-token file (never a token argument)')
    result.add_argument('--ca-file', type=Path, help='Trusted CA certificate for a private HTTPS host')
    result.add_argument('--client', help='Recover a previous client ID; omit for an independent terminal')
    result.add_argument('--state-dir', type=Path, default=Path(os.environ.get('AMPLIFIER_TUI_STATE_DIR',
                        str(Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'amplifier-tui'))))
    selection = result.add_mutually_exclusive_group()
    selection.add_argument('--session', '--resume', dest='session', help='Host conversation ID, or latest')
    selection.add_argument('--new', action='store_true', help='Start an empty composer without creating work yet')
    result.add_argument('--workspace', help='Workspace path on the server; not this terminal filesystem')
    result.add_argument('--list-sessions', action='store_true', help='List host conversations without running work')
    result.add_argument('--bridge', action='store_true', help=argparse.SUPPRESS)
    result.add_argument('--version', action='version', version='amplifier-tui · Unified connected client')
    return result


def credential(args):
    token = os.environ.get('AMPLIFIER_UNIFIED_TOKEN', '')
    path = args.token_file
    if not path and not token:
        from urllib.parse import urlsplit
        if urlsplit(args.server).hostname in {'localhost', '127.0.0.1', '::1'}:
            home = Path(os.environ.get('AMPLIFIER_WEB_HOME') or os.environ.get('AMPLIFIER_WEB_DATA_DIR') or Path.home() / '.amplifier-unified')
            path = home / 'config/auth/control-token'
    if path:
        token = path.expanduser().read_text().strip()
    if not token or '\n' in token or '\r' in token:
        raise ValueError('Provide --token-file or AMPLIFIER_UNIFIED_TOKEN for this host')
    return token


async def run(args):
    token = credential(args)
    store = ClientState(args.state_dir, args.server, args.client)
    transport = Transport(args.server, token, store.identity, ca_file=args.ca_file)
    try:
        if args.new:
            store.data['session'] = None
            store.save()
        if args.list_sessions or args.session == 'latest':
            await transport.open()
            offset = 0
            while True:
                page = await transport.sessions(offset=offset, workspace=args.workspace)
                if args.session == 'latest':
                    if not page['items']:
                        raise ValueError('No conversation exists in this host scope')
                    args.session = page['items'][0]['id']
                    break
                for row in page['items']:
                    print(f"{row['id']}  {row.get('title', 'Untitled')}  {row.get('workspace', '')}")
                offset = page.get('nextOffset')
                if offset is None:
                    return
            await transport.close()
        from .frontend_bridge import serve
        await serve(lambda emit: UnifiedBridge(emit, transport, store, session=args.session,
                                               workspace=args.workspace))
    finally:
        await transport.close()
        store.close()


def main(argv=None, workspace=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    options = parser()
    args = options.parse_args(arguments)
    try:
        args.server = validate_url(args.server)
        credential(args)  # Fail before handing terminal ownership to the renderer.
    except (OSError, ValueError) as exc:
        options.error(str(exc))
    if args.bridge or args.list_sessions:
        try:
            asyncio.run(run(args))
        except (OSError, ValueError, RuntimeError) as exc:
            options.error(str(exc))
        return
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        options.error('Use an interactive terminal, or --list-sessions for a read-only listing')
    from .launcher import executable
    binary = executable(workspace)
    if not binary.is_file():
        # Editable development installs use their explicitly built native frontend.
        binary = Path(__file__).resolve().parents[2] / 'frontends/ratatui/target/release/amplifier-ratatui'
    if not binary.is_file() or not os.access(binary, os.X_OK):
        options.error('Native frontend missing; install a platform wheel or build frontends/ratatui with Cargo')
    host = [sys.executable, '-m', 'amplifier_tui.connected', '--bridge', *arguments]
    os.execv(str(binary), [str(binary), '--host-json', json.dumps(host)])


if __name__ == '__main__':
    main()

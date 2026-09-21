# Amplifier TUI

The optional native terminal client for **Amplifier Unified**. Keep a terminal,
web tabs and other terminals open on the same conversation: they follow the same
host-owned work, while each view keeps its own selection and private draft.
Ratatui preserves terminal selection and scrollback; output remains after exit.

The [0.4.0rc1 prerelease](https://github.com/microsoft/amplifier-app-tui/releases/tag/v0.4.0rc1)
contains connected mode; 0.3 release wheels contain the standalone product. See [acceptance evidence](notes/ACCEPTANCE.md) for exactly
what has been tested. Contracts remain DRAFT, not a full cross-client parity claim.

The canonical repository is **microsoft/amplifier-app-tui**. Published branches,
tags and release assets retain their original contents. Earlier issue and pull
request discussion remains in the [original repository](https://github.com/bkrabach/amplifier-app-tui).

## Install

Use Python 3.11+, uv and access to this repository. Source installation also needs
Git, Rust/Cargo and a C linker. No compiler is needed when launching an installed
platform wheel. Native builds support macOS and Linux; Windows uses WSL2. Authenticate through your usual Git credential helper, never a
credential in the repository URL.

```sh
uv tool install --no-sources git+https://github.com/microsoft/amplifier-app-tui
amplifier-tui --server http://127.0.0.1:8941
```

With the corresponding Unified optional-install change, install its `tui` extra
and launch `amplifier-unified tui`. That launcher uses the local service's configured
port, token file and app-owned CA. It connects to an existing service; it does not
start a second host. Reinstall without the extra to omit the terminal client.

A simpler Terminal app installation experience is being designed in Unified's
[distribution proposal](https://github.com/microsoft/amplifier-unified/blob/main/docs/clients/terminal-installation.md).
Desktop installers, web installation controls and device pairing are proposed,
not features of the current release.

The client itself requires only its HTTP transport dependencies. Foundation, Core,
CLI policy and provider SDKs stay on the Unified host. The existing local execution
host is available explicitly through the `standalone` extra and `--standalone`;
see [standalone instructions](docs/STANDALONE.md).

## Connect and resume

Unified 0.19.5+ provides the v1 connection contract. Stable partial-response display
requires the paired streaming-identity change; an earlier host shows a receiving
indicator until the final answer rather than guessing response identity.

```sh
amplifier-tui --list-sessions
amplifier-tui --session HOST_CONVERSATION_ID
amplifier-tui --session latest --workspace /path/on/the/host
amplifier-tui --new
amplifier-tui --server https://host.example:8443 --token-file /private/host-token --ca-file /private/host-ca.crt
```

`AMPLIFIER_UNIFIED_URL` supplies a default server. Loopback connections discover
`config/auth/control-token` under `AMPLIFIER_WEB_HOME`, `AMPLIFIER_WEB_DATA_DIR` or
`~/.amplifier-unified`. Otherwise provide a private token file or
`AMPLIFIER_UNIFIED_TOKEN`. Remote hosts require verified HTTPS; no insecure switch
is provided. Tokens are never saved in client state or passed as argument values.
The host control token grants host control, not a per-conversation permission scope.

Each launch creates an independent client ID, displayed in System. Use
`--client ID` to recover that terminal's selection, drafts and uncertain requests.
Only one local process may use that ID at once. Private client state defaults to
`$XDG_DATA_HOME/amplifier-tui` (or `~/.local/share/amplifier-tui`); override with
`--state-dir`. This stores local intent, never canonical session history.

## Work in the terminal

- Enter sends; Alt+Enter adds a newline. Paste never sends. The composer clears
  once the local request is retained and a provisional message appears.
- Actions or `/resume` opens the host conversation picker. New opens an empty
  composer; the host creates a conversation on the first Send. Workspace paths
  refer to the host, even when the terminal is on another device.
- `/rename`, permission decisions and Stop use the host's shared actions. Stop
  requests cancellation; it does not undo effects. Graceful/force stages are not
  negotiated by this connected version.
- Continue here requests cooperative takeover if a standalone CLI owns the
  execution lock. It does not send the draft. Other attached clients observe it.
- Earlier history displays read-only pages of up to 100 messages. Conversation
  search filters titles/IDs in the current catalogue page and discloses that limit.
- `/deliveries` exposes uncertain requests for deliberate exact retry. Reconnect
  never submits again. A definitively rejected message can be copied back for
  editing; an unknown request retains its original identity and content.
- Ctrl-Q or Quit detaches. Host work continues, including with no viewers.

Tool and delegated-work status is projected from host evidence; unknown outcomes
stay unknown. Rich artifacts, configuration editing, attachments, queue/steer,
voice and full canvas interaction remain web-client capabilities in this first
connected version. Unavailable standalone commands are refused explicitly.

## Develop and verify

```sh
uv sync --inexact --no-sources --extra standalone
uv run --no-sync python scripts/bootstrap_sources.py --workspace /path/to/source-workspace
cargo build --locked --release --manifest-path frontends/ratatui/Cargo.toml
AMPLIFIER_TUI_SOURCE_ROOT=/path/to/source-workspace uv run --no-sync pytest -q
uv run --no-sync ruff check .
uv run --no-sync python scripts/check_direction.py
```

The standalone extra is needed by the retained host tests, not by connected users.
Install a sibling Unified checkout into the isolated development environment to
run HTTP/SSE integration tests. See [verification guide](SMOKE_TESTS.md),
[client boundary](notes/CONNECTED-CLIENT.md) and [engine boundary](notes/ENGINE-BOUNDARY.md).
Textual and OpenTUI remain comparison harnesses; Ratatui is the product renderer.
No fixture is evidence of paid-provider or physical-device qualification.

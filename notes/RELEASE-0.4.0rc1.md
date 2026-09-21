# Amplifier TUI 0.4.0rc1

The native terminal interface now connects to an existing Amplifier Unified
service by default. Multiple terminals and web clients can share conversations
while retaining independent selection and drafts. Closing the TUI detaches;
work continues on the host.

The connected client supports browsing and creating conversations, streaming
responses, earlier history, rename, approvals, Stop, cooperative takeover and
explicit retry after uncertain delivery. Unified owns execution and canonical
history. Shared automatic naming preserves custom names.

## Install and connect

Download the wheel matching your OS and architecture, then install it with
`uv tool install --no-sources ./<wheel>.whl`. Native wheels need no Cargo at
installation. Source installation builds the renderer and requires Rust and a
C linker. Connect to Unified 0.19.5 or newer:

```sh
amplifier-tui --server https://your-host:8443 --token-file /private/control-token --ca-file /private/ca.crt
```

The paired Unified release also offers its optional `[tui]` extra and
`amplifier-unified tui`, using the host's configured local port and credentials.
Never place token contents in command arguments. Each launch gets a distinct
client identity; use `--client` explicitly to recover its selection and draft.

Previous standalone execution remains available by installing the wheel with
`[standalone]` and launching `amplifier-tui --standalone`. Existing standalone
history is preserved; it is not imported into a second client-owned store.

## Evidence and scope

This early-access release includes qualified macOS ARM64 and Linux ARM64 wheels
with source fingerprints and install receipts. The filenames specify their
actual build platform; Linux is not a manylinux or musl portability claim.
Intel and other platforms may build from source but have no new binary
qualification in this release. Windows uses WSL2.

Both published architectures pass installation without Cargo, real native PTY
checks, retained-history upgrade from 0.3.0rc6, and standalone fixture scripting.
Connected terminal/web tests verify shared input and results, independent drafts,
detach/reconnect, and explicit Stop. Providers in these checks are deterministic
fixtures; no paid-provider or physical-terminal certification is claimed.

Voice, uploads, rich canvas, full settings editing and queue/steer remain web
controls. The retained standalone suite has six environment failures reproduced
on unchanged main, detailed in [ACCEPTANCE](ACCEPTANCE.md). Contracts remain
DRAFT; this candidate does not claim complete client parity or ratification.

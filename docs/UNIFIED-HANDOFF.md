# Shared-session handoff for the Amplifier Unified team

Start from this repository's **main**. Read [VISION](VISION.md),
[contracts](../contracts/), [ENGINE-BOUNDARY](../notes/ENGINE-BOUNDARY.md),
[PLAN](../notes/PLAN.md) and [ACCEPTANCE](../notes/ACCEPTANCE.md).
The plan owns remaining work; acceptance distinguishes fixtures, actual entrypoints
and released artifacts. Dependency commits are pinned in `pyproject.toml`/`uv.lock`.

## What the TUI now owns

The Python host composes Foundation/core and the selected bundles/modules; the
Ratatui frontend consumes identified events and sends controls. No kernel fork or
mandatory orchestrator replacement was introduced.

- Every live session uses Foundation's native history API and the CLI project/session
  layout. Transcript/metadata are authoritative; CI events enrich Activity/accounting.
  `.tui` retains drafts and local control/admission receipts, not a second conversation.
- Busy sessions open read-only. **Continue here** requests cooperative release from
  the observed acquisition; it still must acquire the lock and reload before execution.
  Merely opening/focusing history or taking over never sends the draft.
- Incoming release closes admission, holds follow-ups, finishes current calls and
  descendants, saves and disposes modules before Foundation unlocks. Save/cleanup
  failures retain ownership; requester timeout never cancels the owner's cleanup.
- After five minutes without runtime work or observed user activity, the runtime
  retires while the terminal view survives. Local editing/inspection renew the timer;
  background polling does not. External editing prevents automatic parking. Native
  terminal/tmux-owned copy/scroll events are outside the app's activity visibility.
  The next explicit mutation reacquires and remounts current saved configuration/history.
  This is not a warm, permanently mounted worker. Old callbacks retain old handles.
- Native terminal history remains copyable and immutable. Resume renders the latest
  100 items; Earlier history pages older content without trimming model context.

## Where to work

| Boundary | Entry point |
| --- | --- |
| Ownership/view lifecycle | `SharedRuntimeBridge` in `src/amplifier_tui/host.py` |
| Graceful preparation and final cleanup | `SessionHost.prepare_release`, `close` |
| Canonical history and read-only stores | `SharedConversationStore` in `conversations.py` |
| Async request identity/admission | `Admission.apply_async` and `serve` in `frontend_bridge.py` |
| Switching conversations | `WorkspaceBridge` in `navigation.py` |
| CLI policy/home/cwd integration | `cli_compat.py`, `composition.py`, `__main__.py` |
| Provider/local controls, modes, descendants | `runtime_controls.py`, `modes.py`, `children.py` |
| Ownership notices and Continue here | `frontends/ratatui/src/{main,chrome,interaction}.rs` |

Use Foundation's existing `SharedSessionStore`, `register_release_handler` and
`request_release`; do not create a TUI-specific lock, event database or takeover bus.
See [Foundation handoff](https://github.com/microsoft/amplifier-foundation/blob/main/docs/SESSION_HANDOFF.md).
All participants must use the same coordination root as well as the same history.
Foundation #399 fixes inherited listener cleanup after fork; the CLI and TUI must
carry compatible exact Foundation pins. A listener file existing is insufficient:
the post-fork regression requires an actual authenticated release exchange.

## Next work, in order

1. **LIVE-03: optional upstream live-runtime adapter.** Preserve independent loop/context
   choices. Verify generation provenance, background descendants and activation-bound
   callbacks. First Ctrl-C must finish current calls throughout the tree; second Ctrl-C
   is force stop. Do not wire an immediate-cancel `live.stop` to graceful Stop.
   The host exposes `session.durable_checkpoint` for supporting loops after ordered
   tool-result append; the checkpoint does not claim an unfinished turn is complete.
2. **LIVE-04: bounded read-only observation.** Follow external native revisions without
   acquiring execution, replaying work, rereading full logs on paint, duplicating costs,
   reprinting committed terminal history or losing draft/selection. Current refresh is
   on reacquisition/reopen, not continuous attachment to another worker.
3. **Portable controls and recovery.** Foundation's
   [proposal overview](https://github.com/microsoft/amplifier-foundation/blob/main/docs/PORTABLE_SESSION_CONTROLS.md)
   and three contracts are on main but remain DRAFT. They do not implement common
   pins/modes/goals, queue/steering, transferable approvals or crash recovery. Choose
   adapters/profiles deliberately; unknown metadata preservation is not conformance.
4. **Detach/reattach only as an explicit topology.** The release socket is not an event
   subscription or live control channel. Keeping work alive after a frontend exits
   requires an independently owned host and a separate lifecycle/control protocol.

## Resume-control pitfall

An automatically created, ready provider-control receipt with revision zero, no
provider and no changes is not a user override. A changed mount fingerprint must not
freeze that empty receipt to old configuration. The TUI refreshes only this exact
pristine shape for native shared sessions. Explicit choices, unknown fields and
pending transitions still fail closed; no control file is deleted to make resume pass.
The reported user session has not been independently identified; the regression is
reproduced with synthetic native history and changed provider configuration.

## Verification and sharp edges

Use disposable homes and synthetic history; never start a personal conversation as a
test. Follow [SMOKE_TESTS](../SMOKE_TESTS.md), including native PTYs serially:

```sh
uv sync --inexact --no-sources
cargo build --release --locked --manifest-path frontends/ratatui/Cargo.toml
PYTHONDONTWRITEBYTECODE=1 uv run --no-sync pytest -q
TUI_TEST_CANDIDATES=1 uv run --no-sync pytest -q tests/test_handoff_terminal.py
uv run --no-sync python scripts/shared_session_probe.py
```

`tests/test_shared_handoff.py` uses real Foundation locks/sockets and TUI mounts;
CLI/Unified lifecycle adapters use synthetic collaborator sessions. The optional
Unified case requires an isolated environment with Unified and loop-live installed.
It is not a full web-runtime or paid-provider test. Native PTYs cover 175×50 and
40×20; captures are private reference-font reconstructions, not user screenshots.

Persist uncertainty before effects; a free lock does not prove remote work stopped.
Native files are atomic individually, not a transcript/metadata transaction. Older
nonparticipants are not fenced. Pending controls and private module state cannot be
reconstructed from only transcript and CI events. No full interoperability, generic
crash recovery or new release-wheel claim should exceed ACCEPTANCE's evidence.

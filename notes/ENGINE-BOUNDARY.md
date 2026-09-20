# Engine and persistence boundaries

## Ownership

The Python host composes real Foundation/core sessions and exposes identified events
and controls. The Rust/Ratatui frontend owns terminal rendering and editing, never
runtime imports or execution policy. The thin kernel is unchanged. Bundles and
independent orchestrator/context/provider/tool/hook modules own their behavior.
CLI helpers are pinned application policy, not a kernel API.

## Canonical conversation storage

Every live session uses Foundation SessionHistoryStore transcript/metadata semantics under the
selected Amplifier home's project/session directory. Normal launch reads the CLI's
global/project/local/session settings. Explicit isolated policy chooses its own home
but uses the same session format. Directory-local discovery never falls back to a
retired live TUI journal. Deterministic fixture journals are test harnesses only.

The `.tui` sidecar owns drafts, held input and native control/admission receipts, not
observation history. Its compact execution receipt never contains messages or gates
native resume on an event-journal sequence. Every open rebuilds the in-memory display
from canonical messages; configured CI/log receipts enrich ordinary Activity.
Native transcript/metadata reads stream through Foundation without import-size quotas.
Display previews and initial replay have separate bounds, never execution quotas.
Preserve names, unknown canonical metadata and JSON provider continuation fields.
Foundation validates native primary/backup files; invalid history never becomes empty.
Never replay providers, tools,
approvals or held work while reconstructing history.

Canonical messages have both core `tool/arguments` and provider `function` tool-call
envelopes. Display projections handle both. Persisted injected reminders stay in
model context but use the CLI's display-only exclusion rules for transcript/recall.
Read-only discovery must not import CLI's eager key/bootstrap initialization.
Set the runtime's home and cwd before importing CLI helpers; do not retarget those
process globals while another session is live.

CLI public transcripts exclude system/developer messages. Persistent context modules
own their private messages and may refuse set_messages after loading their files.
Compare native JSON public readback (ignoring only documented internal sequencing)
before attempting restoration; never hide lost provider fields through sanitization. Preserve existing
private context when public history already agrees. Unsupported readback refuses.

## Ownership and uncertainty

TUI acquires Foundation SharedSessionStore ownership before loading a writable
session and retains the original HeldSession through runtime/child cleanup. Cooperating
CLI and web hosts use the same canonical working-directory/session key and state
root (`AMPLIFIER_SESSION_STATE_HOME`, otherwise Foundation's platform default).
The view is independent of that acquisition. Busy opens read canonical history
without mounting modules; explicit Continue here uses Foundation's release protocol.
Receipts never grant ownership: reacquire and reread canonical history and current
launch policy before mounting. Never retarget a changed acquisition automatically.
Outbound handoff closes admission, holds follow-ups, gracefully drains current work,
saves and disposes modules before Foundation unlocks. Save/cleanup failure keeps
ownership. A settled 15-second idle interval uses the same conservative disposal
path; next explicit mutation remounts instead of reusing callbacks from the old host.
The terminal and unsent draft survive. Partial source revisions remain read-only.
The optional session.durable_checkpoint capability persists ordered public context
when a supporting loop calls it; it is not evidence that an unfinished turn completed.
Never derive a different lock root from the client's Amplifier home. Busy ownership
refuses execution; a stale callback cannot borrow a later acquisition. Native writes
and release stay synchronous on the host event loop; check() alone is not a generic
thread-safe save transaction. Do not call HeldSession.write(): native files own history.
Secure canonical revision stamps detect stale writes without rereading whole files.
Older/noncooperating writers and remote effects are not fenced by this local POSIX lock.
This does not implement live-loop attachment, a persistent daemon, event-only recovery
or portable control semantics. External changes refresh on reacquisition; automatic
observer tailing and private module activation fencing need separate verification.

Before Foundation's two-file save, mark the sidecar uncertain. Ready follows successful
canonical validation. Incomplete pairing,
corrupt metadata, unfinished admission receipts and stale writes refuse continuation. Shared
crash recovery is not implemented; retain the original and export for inspection.
No prior effect becomes undone merely because a session stopped.

Archive/restore changes only TUI visibility metadata under shared ownership, never the CLI
transcript or CLI deletion policy. Imported historical reference and adopted public
context are explicit new-identity operations, not substitutes for ordinary Resume.

## Runtime controls

First Stop signals graceful cancellation through active descendants; current calls
finish and parents await their children. Second Stop requests force cancellation.
Own finalization until cleanup and canonical capture settle. Valid drained state is
resumable; uncertain effects are never disguised as completion or replayed.

Questions and approvals correlate to their originating request and execution owner.
Cancellation clears pending decisions without granting permission. Process children
preserve approval transport, nested delegation and cancellation; unavailable worker
state cannot imply safe continuation. Display retention is not an execution quota.

Queue, steering and task replacement are different admissions. Stop holds the queue.
A correction accepted by the UI is not evidence that a module consumed it. Provider,
mode, goal and component controls retain their actual capability and enforcement
scope; native control sidecars are not yet a common CLI control format. The proposed
Foundation controls/intent/recovery contracts are not implemented or ratified. Mere
preservation of unknown metadata does not make another client enforce its meaning.
An automatically created, ready provider receipt with revision zero, no selection
and no changes is not an override. Only that exact pristine native-session shape
may refresh after composition changes; explicit, unknown or pending controls must
not be cleared or rebound just to make resume succeed.

## Presentation and accounting

One renderer owns the terminal. Module stdout/stderr is bounded, redacted private
diagnostic material, never terminal escape instructions or invented tool outcomes.
Structured child events stay under their observed parent, not timing-guessed roots.

The primary terminal screen retains committed output for terminal/tmux copy and
scrollback. Inspection temporarily owns an alternate view without replacing retained
history. Startup archives rows above its observed cursor, not unused screen space.
Temporary live padding is cleared by owned line before scrolling; never use a full
screen history purge to repair geometry. Bounded cursor probes replay input bytes;
missing geometry preserves uncertain rows via a conservative bottom-row fallback.
Rendering consumes source text; display wrapping never changes copied source.
Structural Markdown prefixes preserve wrapped list and quote scope; copied source
is unchanged. Parser-decoded controls are sanitized too. Conservative links retain
nonredundant destinations; capabilities are recorded in [MARKDOWN-GAPS](MARKDOWN-GAPS.md).

Call usage uses observed identity, reported values and parent attribution; no
estimates of in-flight generation. Resume reads bounded canonical event logs and
explicit descendant ownership, reconciling native observations by kernel receipt
identity, never equal amounts or nearby timestamps. Historical totals seed Session,
not Turn. Foundation normalizes optional CI capture (including configured relocation);
the root events log is a fallback only when CI is absent, never a second summed source.
The host owns bounded descriptor-relative no-follow opens; a narrow read-only Path
adapter supplies its opened stream to the shared reader until that API accepts streams.
On-demand shared Activity is an in-memory snapshot, not a live file-polling mechanism.
Historical observations/accounting are derived from shared sources in memory; only
local intent/admission receipts remain sidecars. Inspection keeps canonical source
bytes read-only. Missing, conflicting, bounded or uncorrelated evidence stays partial.
Full private-control interchange remains in [PLAN](PLAN.md).

## Verification and publication

[SMOKE_TESTS](../SMOKE_TESTS.md) owns runnable gates;
[ACCEPTANCE](ACCEPTANCE.md) records current evidence and limitations.
Fixtures use owned homes and no paid providers. Run PTY/service tests serially and
track/reap external resources. Source installs and released wheels are distinct:
a published release does not acquire later checkout changes.

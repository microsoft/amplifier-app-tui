# Engine and persistence boundaries

## Ownership

The Python host composes real Foundation/core sessions and exposes identified events
and controls. The Rust/Ratatui frontend owns terminal rendering and editing, never
runtime imports or execution policy. The thin kernel is unchanged. Bundles and
independent orchestrator/context/provider/tool/hook modules own their behavior.
CLI helpers are pinned application policy, not a kernel API.

## Canonical conversation storage

Every live session uses CLI SessionStore transcript/metadata semantics under the
selected Amplifier home's project/session directory. Normal launch reads the CLI's
global/project/local/session settings. Explicit isolated policy chooses its own home
but uses the same session format. Directory-local discovery never falls back to a
retired live TUI journal. Deterministic fixture journals are test harnesses only.

The `.tui` sidecar owns observation history, drafts, held input and native controls.
Its checkpoint stores a canonical digest and admission state, not another authoritative
message history. If CLI history advances while TUI is closed, validate the completed
journal, retain its observations and rebuild the display from canonical messages.
Preserve names and unknown canonical metadata. Never replay providers, tools,
approvals or held work while reconstructing history.

Canonical messages have both core `tool/arguments` and provider `function` tool-call
envelopes. Display projections handle both. Persisted injected reminders stay in
model context but use the CLI's display-only exclusion rules for transcript/recall.
Read-only discovery must not import CLI's eager key/bootstrap initialization.
Set the runtime's home and cwd before importing CLI helpers; do not retarget those
process globals while another session is live.

CLI public transcripts exclude system/developer messages. Persistent context modules
own their private messages and may refuse set_messages after loading their files.
Compare sanitized public readback before attempting restoration; preserve existing
private context when public history already agrees. Unsupported readback refuses.

## Ownership and uncertainty

TUI holds an exclusive sidecar lock and checks the canonical digest before admission
and save. The current CLI does not honor that lifetime lock. Sequential switching is
supported; concurrent editing is not. A digest check is not a cross-process
transaction or a guarantee against a noncooperating writer racing after the check.

Before the CLI's two-file save, mark the sidecar uncertain. Ready follows successful
canonical validation and durable observation checkpointing. Incomplete pairing,
corrupt metadata, uncertain journals and stale writes refuse continuation. Shared
crash recovery is not implemented; retain the original and export for inspection.
No prior effect becomes undone merely because a session stopped.

Archive/restore changes only TUI visibility metadata under its lock, never the CLI
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
scope; native control sidecars are not yet a common CLI control format.

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
not Turn; detailed receipts live in the Activity sidecar. Canonical source bytes are
read-only. Missing, conflicting, bounded or uncorrelated evidence stays partial.
Full private-control interchange remains in [PLAN](PLAN.md).

## Verification and publication

[SMOKE_TESTS](../SMOKE_TESTS.md) owns runnable gates;
[ACCEPTANCE](ACCEPTANCE.md) records current evidence and limitations.
Fixtures use owned homes and no paid providers. Run PTY/service tests serially and
track/reap external resources. Source installs and released wheels are distinct:
a published release does not acquire later checkout changes.

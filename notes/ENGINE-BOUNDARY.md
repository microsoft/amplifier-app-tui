# Engine boundary: first-slice record and reopened decision

## Local newcomer guidance

The launcher offers offline guidance and local prerequisite checks before saved-state
lookup or module loading. Checks never create a probe file, validate a key, fetch sources
or mount a bundle. A custom composition's provider requirements stay unknown; a default
key's presence is not authentication evidence. State writability is an access precheck,
not a successful write, quota guarantee or race-free admission decision. Support JSON is
constructed from allowlisted fixed messages/statuses, not a redacted environment/config
dump; doctor remains a separate path-bearing private diagnostic. Neither reads transcripts.
Native Help is client-local text, preserving the composer and requiring no host operation.

## Installed product and overload ownership

The installed entrypoint launches the packaged Ratatui binary with the same Python bridge.
Hatch compiles locked Cargo sources at wheel-build time and assigns a platform tag; it
does not download an unrelated executable or silently fall back to Textual. Workspace
launch is a thin adapter selecting workspace source/state defaults. Installed launch uses
remote bundle sources, packaged overlays and separate XDG data; module dependency activation
targets the app interpreter, not the shared CLI. Version/doctor and System name the runtime.
Existing local-source conversations still require their recorded paths; no migration is inferred.

Source delivery now retains at most 4096 events / 8 MiB serialized payload, before the
separate 1024-record transport queue. The journal is written first. Overflow fails the
connection, stops current admission/execution and leaves an uncertain checkpoint; no
automatic retry or reconnect is implied. Queue consumption releases its byte budget.
Headless and retained-harness readers also fail explicitly. A switched conversation shares
the connection's failure signal only after successful preparation/commit. This bounds pending
delivery, not all context/transcript memory or arbitrary module tasks. Module initialization
still lacks a public pre-initialize ownership seam; cancellation-time hook warnings remain.

Turn-end source summaries count root and child tool-call outcomes, not text confidence or
the parent's aggregate child card. A failed command does not turn a completed agent loop
into a failed loop, and a completed loop does not certify tests, task acceptance or production
readiness. Child pre/post observations fold by call identity. Detailed source stays inspectable.

## Daily-work adapters

`Inspection` indexes identified source observations, not model summaries. It retains at most
256 identities with 16 KiB detail excerpts; read-only catalogs cap at 100 rows / 1 MiB. Root
tool results remain in canonical evidence; child tool/text observations are explicitly bounded.
Child observers report source IDs and waiting states through the host journal, with no widget
imports. The native view requests a snapshot and discards late replies after dismissal/switch.
Context diagnostics consume public usage/compaction events without invoking the context
manager's request-building path (which could compact). Missing measurements stay unavailable.

`local_drafts` stores private atomic/fsynced editor copies outside canonical context/admission.
Original conversation/request scopes survive explicit historical recovery, but carry no
delivery authority. Corrupt records are retained and reported, never overwritten as empty.
The client autosaves after a 250 ms pause and before leaving the editor; recent unflushed
input is not crash-durable. Answer/correction copies can outlive their submitted request.

Completed direct-child continuation is lazy and explicit through the public resume capability.
It validates the saved parent/root fingerprint, completed status, inherited mode and recreated
mount-plan fingerprint before execution. Only reconstructible default-routed definitions are
supported across restart. A running receipt is persisted before effects so the old completed
receipt cannot authorize replay after a crash. Nested/custom-routed/interrupted children and
old receipts fail closed. Initialization still uses Foundation's public factory; its earlier
partial-initialization ownership gap remains. This is not recipe-process recovery.

Text input reads one descriptor-relative workspace file with no symlink traversal, a 64 KiB
bound and before/after metadata check. Preview owns captured bytes and digest. Insertion adds
literal text to the existing draft; it does not alter context or reread at submission. The
string-only orchestrator seam does not advertise image attachments. External editing is an
explicit idle-only user command, on a temporary alternate screen with raw mode suspended;
the primary transcript survives and failure retains the original draft.

Sections below record preceding waves; this section supersedes their editor/child limitations.

Independent replacement checks exercise upstream `loop-basic` and `context-persistent`,
in all four combinations with the original streaming/simple modules. Persistent context
inherits simple's compaction but has independently packaged file ownership. It ignores
`set_messages` when its own file was loaded; the host and child adapter now read back
restored canonical history and refuse mismatches before admission. Only simple's documented
internal `_seq` restamping is excluded from equality. The gate supplies an isolated explicit
transcript path. Default shared-home paths, per-child storage allocation, arbitrary private
context state and migration are not certified; the default composition is unchanged.

The first-slice decisions below remain an accurate account of the existing code, not
requirements for its successor. The [direction amendment](DIRECTION-REVIEW.md) reopens
frontend, host and transport selection. Textual is no longer the target frontend.
The interaction wave uses Ratatui as the working client and `scripts/run.py` as an
explicit real-work launcher. OpenTUI remains the historical comparison body. The host
now projects queued approval requests and optional public skills discovery; widgets
still do not import modules or manufacture execution policy. This is not final selection.
Ratatui and OpenTUI compete against [presentation](../contracts/presentation.v1.md) and
[performance](../contracts/performance.v1.md), not against the convenience of this code.

The reading/return wave adds host-owned `ConversationStore`: append-only identified
observations, atomic canonical-context checkpoints, separate draft text and a Linux
single-writer lock. `get_messages` / `set_messages` are the context module's public
portable-history seam. Reopening projects observations and restores messages; only a
new submission executes. Module initialization still runs its normal mount lifecycle.
The effective mount-plan digest guards configuration changes without persisting provider
configs; it is not a frozen copy of module code or dynamically resolved prompt files.
Only completed checkpoints resume. Interrupted/failed/unknown work and journal/checkpoint
disagreement fail closed; repair policy, durable queueing and arbitrary module-private
state are not implemented. Draft autosaves do not consume the execution-admission ledger.

The navigation wave adds `WorkspaceBridge`, an app-side adapter, not a new orchestrator.
Idle-only switching saves the source draft, prepares one candidate via the normal
composition callback, then replaces the source after readiness. A failed candidate or
cancelled preparation closes its acquired handle/store and leaves the source available.
Only one candidate initializes at once; the existing partial-initialization ownership
gap still applies. Mount-time candidate approvals are denied, not retargeted to the
source UI. The final source-cleanup/commit phase is not cancellable from the client;
an exceptional cleanup failure is an error, not a claimed rollback.
The working client includes conversation identity on requests; stale identities are
rejected, and identity-less clients cannot issue controls after switching. Snapshot
replacement explicitly clears conversation-specific view state. Local asynchronous
lookups carry request/conversation identity; the client also checks draft/cursor and
discards dismissed or edited requests. File discovery is capped and off the event loop,
with no file-content reads, recursion or model/tool execution. Read-only lookups, like
draft autosaves, do not consume the bounded execution-admission ledger.

A bidirectional child-process boundary is now implemented as an opt-in experiment, not
a selected production architecture. It keeps the existing host's execution authority,
adds correlated admission, and routes direct module fd 1 writes away from protocol output.
Both candidates have real fixture/PTY and live-provider evidence through it; see the
[review packet](TERMINAL-REVIEW.md). Slow-reader durability and ownership before partial
initialization returns remain open. The old headless command still runs one prompt and
denies approvals; that old command is not the persistent server.
A long-lived child process, in-process bridge, or replacement host is admissible if it
meets [session](../contracts/session.v1.md) and [ecosystem](../contracts/ecosystem.v1.md).
Replacing runtime parts is permitted; introducing interface policy into the thin kernel
or silently dropping bundle/module obligations is not. Existing components are useful
starting points, not protected investments. See [the work plan](PLAN.md).

## Native terminal ownership

The working Ratatui client uses the normal screen for conversation output, not
`ratatui::init()`'s alternate-screen default. `native::Journal` projects stable source
blocks and final items once, with separate live pending content. Finalization consumes
only the remaining source suffix. Real revisions are labelled rather than silently
rewriting terminal history. Native rows are a presentation artifact, not model context.
The live region contains mode, ordinary controls, draft and current activity; idle height
is ten rows. Unfinished Markdown is held in an eight-row live preview; complete source
remains available through Transcript inspection. Incomplete fences/tables are not frozen
into prematurely final Markdown. This is not arbitrary streaming-source rewrite support.

Review/System, menus, editors and source inspection use a temporary alternate screen;
return restores primary output and commits newly observed work, not a second transcript.
Normal mouse input belongs to terminal selection; inspection enables mouse controls.
Queue/steer/approval/question operations retain the same host identities and policy.
No kernel, provider, orchestrator, context or runtime transport changes are required.

The client manages a fixed Ratatui live viewport: the library's default inline resize
clears the screen on narrowing. Native history must not be cleared on resize. Growth
also accounts for tmux pulling history onto the screen without moving its reported
cursor. Cleanup flushes pending source, removes live chrome and restores only owned
terminal modes. Exit retention is separately tested from saved-conversation recovery.
Initial historical replay projects the latest 1,000 items with a disclosure; the complete
source remains in the client/store and new output is unaffected. The 100,000-item stress
scene demonstrated that dumping invisible historical backlog on exit exceeded the
four-second cleanup gate. Emission yields after 128 queued rows and prepares up to 32 dirty items per frame;
retained items are not all laid out again per key. A single Markdown block is still
parsed as a unit. Native history capacity remains terminal-owned, not silently configured.

## Follow-up admission and local organization (runtime)

`Followups` is an app-owned admission adapter attached to the current `WorkspaceBridge`
host. It does not execute tools or construct model requests: release uses `SessionHost.submit`
and the selected orchestrator/context unchanged. Queue capability is enabled only for
the store-backed bridge, not the historical Textual/headless host or simulated scene.
The native Send label becomes Queue while an identified runtime turn is active; the
protocol still sends a distinct operation. Queue admission is acknowledged only after
an atomic/fsynced private record (maximum 20 entries, 65536 characters each).

Release marks one entry dispatched before turn admission and correlates its `input_id`
in the ordinary turn journal. The next release waits for the task, terminal outcome and
checkpoint, not a rendered completion event. Stop/failure, switching and reopening hold
the queue. Edit pauses waiting work and validates its identity/state again at the host;
already admitted work rejects edit/remove. Completed admissions leave the pending list
but retain their text, identity and outcome in the journal. There is no automatic retry.

There is deliberately no cross-file transaction claim: a crash between marking dispatch
and admission can leave an uncertain record. That record blocks release, and recovery
is not implemented. A queued draft may still be visible if the process dies before its
acknowledged editor-clear autosave, but returning never resubmits it. Active interrupted
conversations remain subject to the existing completed-checkpoint-only resume gate.

Rename edits only local metadata under the conversation lock. Search/jump and reply
copy use retained identified source in the client, never provider/tool calls. Search
scans at most 16 MiB recent source / 200 matches per explicit query; reply catalogs cap
at 100 blocks and preview 12000 characters. Message clipboard copy rejects blocks over
1 MiB rather than silently truncating. These are local UI bounds, not CLI parity evidence.

## Historical first-slice decision

The newer runtime-control adapter is described below; the historical capability gaps
in this section are not the current shipped scope.

Decision: use Foundation PreparedBundle and an in-process conversation controller.
The controller owns admission, IDs and terminal outcomes; the selected orchestrator
owns provider requests, tool execution, context updates and cancellation boundaries.
No kernel changes and no copied CLI engine. Terminal and JSONL clients share this controller.

## Source facts

Inspected current source on 2026-09-12, with exact pins in sources.lock.json.
`amplifier-agent` at fa33a2099bf748c0e4553c0b74eafe1077fb9326:

- `engine.py:Engine.boot` accepts a PreparedBundle override (its test-only docstring
  conflicts with the public integration guide recommending it for embedders).
- `Engine.dispatch` implements initialize, submit, shutdown only. Shutdown marks a flag;
  it does not itself stop an active runtime. No steer/cancel operation is implemented there.
- `_runtime.py:make_turn_handler` creates a kernel session per turn and restores disk
  messages only when its closed-over is_resumed flag is true. Session ID alone is insufficient.
- Runtime preparation mutates the mount plan, injects vendored skills/modes, rewrites
  recipe/logging paths, and may set MCP environment variables.
- Importing `amplifier_agent_lib` unconditionally overwrites AMPLIFIER_HOME. This is
  unsuitable for importing into this host alongside independently configured Foundation.
- Child overlays are hydrated from source_path entries; Foundation-composed named agents
  require a different resolution path. Prepared-bundle injection alone does not prove parity.
- Persistence repairs orphan tools on resume; incremental tool saves differ from final saves.
  Error/cancel paths are not equivalent to a fully durable conversation controller.

CLI source at 772bdb42f135fa310e217d6634dd727039d2d840 supplies settings precedence,
provider instances, tool policies, CLI expertise, modes, skills, routing, wayfinder,
prompt-tail instructions, child context policy and recovery. These are product policies.
`runtime/config.py`, `session_runner.py`, `session_spawner.py`, and `AGENTS.md` were
inspected; this host does not claim to reproduce their full behavior.

Foundation's `BundleRegistry(include_source_resolver=...)`, `Bundle.prepare(...)`,
and `PreparedBundle.create_session(...)` provide the necessary host-neutral seams.
The selected loop registers session.steer, but its queue accepts strings without
request IDs and clears at turn start. This slice does not advertise correlated steering.
Its orchestrator:complete status distinguishes success, incomplete, error, cancelled
and budget_exhausted. A normal execute return alone cannot prove successful work.

## Choices implemented in the first slice

- Explicit bundle, ordered overlays, working directory, state directory and source map.
  No implicit CLI settings import or credential-file migration. Provider modules resolve
  their own credentials; examples use environment references. Changes take effect on launch.
- Keep selected loop/context and policy hooks. Exclude known terminal writers explicitly
  in the interactive composition policy; report exclusions. Unknown modules remain generic.
- Textual 8.2.8 supplies asyncio integration, a multiline TextArea, alternate-screen
  lifecycle and a test Pilot. Enter inserts text; Ctrl+S submits. This deliberate keymap
  makes multiline paste text, and permits editing during runtime work.
- Start in-process; no invented RPC or daemon promise. Optional controls remain unavailable
  until their semantics can be represented faithfully. Future engine adapters use the same seam.
- A configured module can write outside host state or print directly. This is not an OS
  sandbox or a promise that arbitrary Python extensions obey the display contract.

Framework references: [workers](https://textual.textualize.io/guide/workers/),
[testing](https://textual.textualize.io/guide/testing/),
[TextArea](https://textual.textualize.io/widgets/text_area/).

## Integration findings from the slice

Foundation prepares sources but does not perform CLI environment expansion. Expansion
of root module configs is host policy; prompts and deferred child configs remain intact.
The core can log optional mount failures and continue. PreparedBundle has no factory or
pre-initialize observer injection; this host temporarily watches the pinned initializer's
warning logger and refuses readiness on a warning. This fallback is process-scoped and
supports one initializing conversation at a time, not multiplexed sessions. Replace it
with a public initialization observer/session-factory seam when available. The core's
module:load_failed event is useful only if an observer is registered before loading starts.

If create_session raises/cancels before returning its session, the host cannot acquire
that partially initialized session to clean it. Normal close and post-initialize rejection
are tested. Fatal mid-initialize extension failures remain a known cleanup gap; do not claim
arbitrary module lifecycle conformance. Copying Foundation's private prompt/resolver setup
or globally monkeypatching AmplifierSession would create a worse maintenance boundary.

Readiness reports actual exported tool names, not PreparedBundle.module_exports hints:
the inspected hint attributes glob to filesystem, while this revision mounts it from search.
Stream block identity is scoped to provider request index and turn. The released core lacks
HEAD's newer correlation helper, so the host does not pretend those source changes were tested.
Terminal logging is captured by Textual; the headless CLI redirects Python stdout to stderr.
Modules writing directly to file descriptor 1 can still bypass it and are not conformance-tested.

## Correlated corrections and conversation-provider selection

`RuntimeControls` consumes public coordinator capabilities; no kernel or upstream module
changes are made. `session.steer` receives a unique correction/turn envelope containing
the user's original text. Admission is fsynced before calling the module. The host gates
on the first provider request because the selected loop clears its queue at turn start.
Only a matching root `orchestrator:steering_injected` observation marks insertion applied.
Pending corrections finish unconfirmed on Stop/failure or absent evidence, never as an
automatic follow-up. The loop's final-generation edge can continue the same turn to
consume steering. Applied means context insertion, not obedience, task success or undo.
The editor retains the target turn even if it ends while the person types. Retained
correction items and a local catalog preserve source/status separately from sent turns.

`conversation.provider_pin` supplies discovery/current/pin/unpin and compatibility policy.
The host permits changes only while idle and pauses queued work first. It does not mutate
provider configuration, unmount providers, override vendor guards, or change other routing.
The selection is saved in a separate private atomic `controls.json`, marked pending before
the synchronous module mutation and ready afterward. Failed final persistence disables
admission; pending/corrupt/missing required records refuse resume. Reopening restores the
pin before readiness, without provider or tool calls. This is not a cross-file transaction
or recovery procedure. The record retains up to 1000 identified changes, with the latest
100 inspectable/copyable in the UI. Module-private state outside these explicit controls
is still not generally restored. `provider:resolve` observations record actual top-level
selection and its basis separately from the requested pin or provider-reported catalog.

Foundation uses provider `id` for composition while the kernel uses `instance_id` for
mounting. The composition adapter normalizes these public names on loaded roots and
explicit overlays, rejects disagreeing names, and reports that policy in System detail.
Recursive includes are already composed by Foundation; their authors must use `id` so
distinct instances are not collapsed before reaching this adapter. The example overlay
authors both keys. Normal single-instance launches and their selection policy are unchanged.

Native dialogs with a lost acknowledgement keep their text available for explicit copy
and dismissal. Neither action resends the control or changes the main composer. This
is connection-loss handling, not crash-durable dialog storage or transparent reconnection.

## Structured questions and local workspace review

The independently installable `modules/tool-user-input` uses only kernel contracts and
the public coordinator capability `user.questions`. Its normal `request_user_input`
tool call still passes through orchestrator tool hooks; a policy denial prevents the
question. The capability is an async callable `(questions, *, session_id, timeout)`.
The active root or one of its active children may ask. Non-interactive hosts return unavailable without
waiting; active child requests use root-owned identified routing. The host validates 1–3 uniquely identified
questions, up to 6 choices each, and limits pending groups/turn count/wait duration.
No selected default or permission answer is inferred.

The native client stores answers locally, independently of the main composer and
approval UI. Explicit submission includes group/turn/session identity and all question
IDs. Admission validates offered labels or free text and records/fsyncs the exact outcome
before resolving the waiting tool. Persistence failure disables admission and delivers
no answer. Cancellation, timeout and Stop produce distinct no-answer outcomes. The tool
result enters canonical context normally; completed resume projects outcomes without
re-asking. Local unanswered editor state is not durable across crashes. The launcher
adds a declared overlay before explicit overlays; `--no-questions` opts out. Saved
composition is never silently amended. Another tool with the same exported name causes
an explicit mount failure rather than replacement.

`GitReview` is an app-owned, asynchronous read-only observer, not an Amplifier tool or
execution authority. Requests/results carry conversation and request identity; opaque
row IDs map to observed literal paths. Dismissal and switching discard stale responses.
Reads do not consume the execution-admission ledger or enter model context. Each Git
process has a timeout/output bound and is reaped on cancellation. Status is bounded to
500 rows and labelled as partial at the limit; output/decoded diff is capped at 1 MiB.
Staged compares HEAD (or the empty base) to index; unstaged compares index to working
tree. Untracked names are not opened; conflicts are labelled without an invented diff.
Index locks/optional writes, fsmonitor, hooks, external diff, textconv and configured
clean/process filters are disabled. This last step matters: Git can run a clean filter
even in a read-only status/diff command. Tests install observable helpers to catch that.
Submodule contents and ignored paths are omitted. Invalid UTF-8 has a lossy display but
selection retains the exact path internally. Status/HEAD changes invalidate selections;
unchanged porcelain status cannot prove contents stayed unchanged, so every comparison
explicitly disclaims atomicity and agent attribution. No stage/revert/commit or test
execution is present in this view.

## Structured reading, source snapshots and hunk navigation

Table layout, code-block discovery and coloured diff inspection are frontend projections;
they add no host operation or module policy. The existing Markdown parser feeds styled
cells to width-aware layout. Adequate width keeps aligned columns; narrow width emits
labelled fields per row. Both retain source separately and use the existing lazy per-item
layout invalidation. Reflow must combine line and span styles, not discard line colour.

Code discovery scans up to 16 MiB of recent assistant source and returns at most 100
blocks. Each immutable snapshot records source message ID, block ordinal, language hint
and parsed code content. That content excludes CommonMark fence/container indentation;
it is not a byte-for-byte copy of the surrounding Markdown. Preview is bounded to 12000
characters and copy to 1 MiB. Shared snapshot references keep menu redraws from copying
every code body. Updating a source item cannot retarget an already-open copy action.

Diff hunk choices similarly own the observed Git result by shared reference. They never
issue a fresh Git read or imply a patch was applied. Hunk scanning stops at 100 entries
and at file boundaries; the full diff remains accessible when the catalog is partial.
Copying an individual hunk explicitly labels the result as an excerpt, not a complete
patch. Generic menu detail caches compare source/width/style and reflow only when those
change, preserving coloured wrapped lines without reparsing the full diff on each key.
These snapshots are local view state, not new canonical context or durable executions.

## Session repairs: children, modes and historical recovery

`Children` owns public Foundation `PreparedBundle.create_session` lifecycles and registers
the existing `session.spawn` / `session.resume` capabilities. Agent overlays compose with
the parent's bundle; provider preference resolution remains Foundation policy. Root and
child contexts/identities are separate. Child approvals and structured questions route to
the root's identified controls, and Stop requests child cancellation. Child tasks remain
under host lifetime ownership: detached delegate tasks are drained before root
checkpoint/close, rather than allowed to write into a closed journal. Known terminal hooks
remain excluded and app-local logging/recipe paths cannot be redirected by agent overlays.
Tool/hook inheritance consumes module IDs (`inherit_tools` / `exclude_tools` and hook
equivalents); this host applies exclusions to explicit agent contributions too. Limits are
4 active / 32 retained children and 3 nested levels. Child resume retains canonical context
within the open root, not across process restart. Explicit subprocess isolation is refused.
Private child receipts retain observed mounts, context and outcome, not provider config.

`Modes` adapts the composed mode tool, discovery and hook events. Assistant tool calls
still traverse normal tool-pre policy. Warn/confirm requests become explicit approvals;
denial does not arm an automatic retry. An authorized call temporarily uses an auto-gated
tool instance without changing the mounted configuration; original transition/allow-clear
checks and runtime-overlay hooks still execute. Native human choices require explicit
Apply but are not assistant tool calls: feeding them through the assistant allowlist would
trap the user inside explore mode, which excludes the mode tool. Pending mode writes and
activation-failed events fail closed. Resume validates the discovered definition digest
and restores policy before admitting work. Children reactivate the parent's active mode.

`recovery` reads at most 16 MiB of validated identified journal data through the shared
non-executing projection, including partial assistant streams. Export requires no runtime.
Explicit recovery acquires the original's lock, validates policy records, and creates a
new conversation with historical reference context plus the saved draft. Original bytes
and queued admissions remain untouched. No orphan tool calls enter the new canonical
context and nothing executes until a new user submission. This is not faithful restoration
of interrupted canonical context or arbitrary module-private state, and is never rollback.

Native drag selection freezes a bounded rendered snapshot (20,000 lines / 2 MiB) around
the starting viewport. Wheel/edge autoscroll moves within that snapshot, extending the
selection without retargeting it to new output. Resize clears selection. Explicit copy
uses OSC52. Historically, `Native scrollback` left the alternate screen and disabled mouse capture,
then writes at most 2 MiB of sanitized retained transcript source to the primary screen.
The existing host event pump keeps draining; no new execution or clipboard write occurs.
Enter/Esc restores the alternate screen, mouse capture and untouched editor. Bracketed
paste is ignored in this view. Terminal/tmux scrollback limits apply; configuration is
never altered. That explicit snapshot handoff was insufficient and is replaced by the
default native ownership described above; this paragraph records the prior implementation.
Whole-conversation export remains the independent file path for retained history.

## Everyday navigation and control visibility

Bare launcher `--resume` uses a stdlib terminal chooser before composition is mounted.
Cancellation is read-only. Explicit `latest`/ID bypasses the chooser; recovery needs its
own confirmation and retains the original. The in-app picker still uses identified
asynchronous lookup and the existing prepare/commit/cancel switching boundary.

`input_history.recall` reads only matching resolved-cwd journals in this app's state
directory. It excludes the current session, scans bounded tails (16 MiB total / 1 MiB
per journal) and returns up to 1000 submissions / 2 MiB plus a partial flag. Catalog
activity orders sessions because legacy events have no timestamps. It never mutates
checkpoints or model context. An asynchronous `input_history` message carries the root
identity; stale replies are ignored and frontend prefix merging waits until active
recall finishes, preserving its index and original draft/cursor.

`mode_status` projects observed mode policy separately from runtime labels and menus.
Root readiness supplies the initial/restored state; the mode adapter reports state after
completed persistence. Child-prefixed mode events cannot replace the root badge. Visible
Resume/Pending/Steer/Modes controls reuse existing identified operations: queue means a
later turn; steering targets the active turn. Widgets acquire no new execution authority.

# Engine boundary: first-slice record and reopened decision

## Explicit session and tool operations (2026-09-17)

Context clear is confirmed user intent, not a model tool. It holds pending input,
writes a private bounded pre-clear context/goal backup, marks local controls pending,
calls the mounted context's public `clear`, verifies empty canonical readback, clears
the active goal and checkpoints under the same identity. History and effects remain.
A no-op, failed or cancelled mutation cannot become a ready checkpoint. Persistent
modules may truncate their own transcript; the app backup precedes that call.

Turn branches use Foundation's CLI turn boundaries and strict orphan-tool handling,
then the existing public-context transfer/readback path under a new identity. The
source stays open until the candidate is ready. They are not private-state forks:
new launch configuration applies, while old pins/modes/goals/controls/queues do not
transfer. Unsupported context modules refuse rather than synthesizing success.
JSON export serializes the displayed projection with source identity and sequence,
including explicit partial-stream markers. It omits raw session-ready composition
and is neither canonical context nor a resumable session. Input journal remains
bounded at 16 MiB; rendered output is bounded at 32 MiB, created mode 0600.

Manual tool invocation is a host operation, not a provider instruction. The app uses
kernel pre/post hook processing (including denial, changed input and ask_user), normal
tool approval, cancellation registration and the same delegate dispatch identity.
It does not call a root provider or emit prompt-complete naming triggers. Tools and
their hooks/children can still use providers or external services; no free/safe-tool
claim follows from bypassing the root model. Ephemeral next-LLM injections have no
implicit continuation to trigger. Module result status and observed outcome remain
separate; post-hook result modifications are used in the displayed returned value.
The existing owned-execution boundary now also shields/drains host operations; forced
unverified operation cancellation marks uncertainty rather than abandoning execution
and claiming safe resume. No orchestration policy moves into the kernel.

## Existing CLI host parity (2026-09-17)

The `/config` read path reuses Foundation's loaded `SessionConfigurator`, as the
pinned CLI does, while rendering an allowlisted metadata subset: names, enablement,
module IDs, origin bundle names and introduction kind. It never serializes arbitrary
configuration, source URLs or instruction bodies. Agent rows describe definitions,
not spawned sessions; context entries are not token occupancy. Lists are bounded to
32 rows per category, with exact-name lookup for omitted items. Tab uses the CLI's
cached snapshot; it does not query modules on keystrokes. Read-only inspection must
not write shared policy or enter model context.

Configuration changes use that pinned adapter for tool/provider/context/agent/behavior
toggles, with explicit mode, last-provider and pinned-provider guards. Check actual
post-operation state before recording success; partial/no-op transitions retain a
pending control record and refuse execution/resume. Behavior hooks remain unchanged.
An app guard rejects spawning a disabled root agent even from a previously copied
definition map. Existing children are unaffected; new children inherit current context
and definitions, not root-only tool/provider toggles. Scalar `set` edits metadata only;
it does not remount modules. Values are omitted from diff/inspection, and obvious
credential paths refuse in favor of provider-owned setup.

Version-2 local controls retain the complete supported configuration policy; v1 tool
records migrate without reinterpreting current shared settings as old session policy.
CLI-composed configurator defaults apply to new conversations and are immediately
retained locally when nonempty. Resuming always uses the conversation's own state;
saving shared policy must not invalidate the conversation that saved it. Module-plan
fingerprints still guard changed composition. Shared saves require an exact explicit
scope and confirmation, hold the CLI's per-scope lock, validate YAML before its
permissive reader, and use its atomic writer/credential normalization. Isolated
launches never fall back to a user's home. The original preparation/settings attributes
are app-private and omitted from reports/kernel mount plans.

The dedicated bridge process reserves its protocol descriptor before runtime imports
and captures descriptors 1/2 into a separately drained pipe. Legacy Python/Rich/logging,
native writes and inherited subprocess output therefore cannot paint the terminal or
pollute JSONL. A thread maintains at most 128 lines / 256 KiB; oversized logical lines
are omitted, incomplete lines wait for a newline, and decoder failures keep draining
while marking capture unavailable. Count-only notices are throttled to twice a second;
text crosses the boundary only on explicit Actions → Runtime output inspection.

This is private process-scoped diagnostic text, not conversation evidence: startup and
switched sessions share the process tail, child/tool/severity ownership is not inferred,
and no diagnostic enters journals, exports or canonical context. Stateful terminal-
control stripping covers split ANSI/OSC/DCS; recognizable credential lines, current
secret-shaped environment values, PEM blocks and endpoints are omitted. Arbitrary
private prose cannot be reliably scrubbed, so inspection/copying carries a review warning.
Module-owned logs are independent. The adapter does not emulate Rich interactive input,
interpret raw logs as pipeline state, or promise complete/crash-durable diagnostics.

Child admission is separate from observation retention. Each parent has its own
capacity semaphore (default eight; `AMPLIFIER_TUI_CHILD_CONCURRENCY=1..64`). Waiting
children publish identified capacity status. A parent retains its slot while nested
work uses a different semaphore; ancestors cannot consume their descendants' slots.
The host no longer imposes a total nesting ceiling. It registers the delegate's actual
`self_delegation_depth`, not ancestry depth; the module still enforces self-delegation
policy. This is not removal of module safety rules.

Stop wakes admission waiters without starting their calls. Graceful waiters return
cancelled results, allowing the caller to join already-running siblings; propagating
CancelledError there would incorrectly abort the parent. Force Stop retains immediate
cancellation semantics. Cancelling an unadmitted continuation leaves its previously
completed durable receipt untouched.

Durable hosts keep the most recent 32 completed context/preparation payloads resident;
older completed work reloads through the existing validated receipt/parent/composition
path on explicit continuation. Small ancestry, labels and accounting remain indexed
in memory; this is not a claim of constant total session memory. Hosts without durable
storage cannot evict their only canonical context. Compact progress retains recent
and live summaries (32 normally, up to 64 live), states omissions, and totals every
owned child, including hidden errors/costs/calls. Original Activity records remain
separate from the bounded preview. No execution quota is derived from history size.
Explicit subprocess execution uses the same parent-owned composition, admission,
observations and receipts. A fresh interpreter mounts the selected runtime; an
inherited local socket carries bounded JSON RPC, independently of raw stdout/stderr.
Approvals, questions and nested spawns return to the owning host. No pickle, network
listener, temporary credential-bearing config, or implicit in-process fallback is used.
The parent forwards kernel cancellation and owns process-group reaping; killed or lost
workers leave uncertain receipts, never successful continuation claims. This is process
isolation, not an operating-system sandbox. Transport belongs in frontend_bridge and
session construction in composition; this adds no source file or second domain.
The same child setup installs modes, canonical context and tool invocation correlation
in either interpreter. The parent keeps provider preference resolution; remote catalog
queries return through the child provider, not an unrelated root instance. Frames are
limited to 16 MiB with 128 pending requests per direction. Foundation's pinned child
environment allowlist is reused; modules still receive their declared configuration.
The control descriptor is non-inheritable by tools. An owner-loss watchdog terminates
the app-created process group even while a module blocks its event loop. This does not
promise confinement of independently daemonized processes or arbitrary native code.
EOF, oversized evidence, failed canonical capture and forced kill never manufacture a
successful receipt. Socket reset during shutdown is expected transport loss, not a
reason to abandon joining the process. Independent module policies remain untouched.

Child routing uses the pinned CLI's preference coercion, model-role normalization,
Foundation promotion and resolution diagnostics. Current explicit preferences win;
otherwise the saved chain wins over agent defaults. The model-role declaration also
travels to the child configuration for ecosystem routing hooks. Ordered preferences
remain durable; hot resumes re-resolve them against the current provider catalog.
Unresolved choices warn through the identified child display and retain the CLI's
configured-priority fallback, not a fabricated successful routing claim.

An unrouted plan fingerprint verifies non-routing composition independently of the
selected model. The in-memory baseline never enters receipts (it may contain provider
configuration). Saved hashes/routing/modes have a consistency digest, not local-file
authentication. Legacy receipts first reconstruct their original exact mount hash;
they do not gain permission by dropping provider fields from that hash. A cancelled
admission restores the earlier in-memory row and leaves its durable receipt unchanged.
Current parent mode and the child's own approved mode are tracked separately: a child
changing its own mode does not mean that its inherited parent policy changed.

Finalization marks interrupted children resumable only after execution is owned/drained,
cleanup succeeds, and the canonical messages pass the same tool-pair validation used
for interrupted roots. Unowned execution, failed cleanup/capture, incomplete legacy
receipts and missing tool outcomes remain unavailable for same-identity continuation.
No result is synthesized on this path; explicit public recovery is separate. Context
readback must match before the new instruction executes, including persistent stores.
No ancestor is started implicitly, and two continuations cannot claim one active child.

LocalCommands reuses the pinned CLI's pure repeated-reason detector and threshold
policy. A tripped goal clears the orchestrator's existing session-state seam; it
does not replace the loop or claim goal success. The pending control record stays
pending until execution drains and context checkpoints. The loop can finish one
already-admitted continuation, matching the CLI backstop's bounded overshoot.
Explicitly setting/clearing a goal resets the detector; returning never starts work.

Command argument discovery uses the CLI's cached CompletionSnapshot and pure engine,
refreshed at startup and turn/control completion, never on Tab. Identified replies
are discarded after draft, cursor or session changes. Unsupported live configuration
verbs are filtered rather than advertised. Provider diagnostics address every mounted
instance (or one explicit name), retain per-provider timeouts/model bounds, and never
change conversation routing. Standalone validation is explicitly requested and billed
by the provider; catalog discovery itself is not proof of access.

The host declares boolean `approval.interactive` before root/child module mounting.
It describes transport, not consent. Computer-use's upstream hook prefers that
capability, preserving legacy TTY fallback only when absent; explicit false or invalid
values fail closed. Normal ask_user/deny/defaults and actual decision ownership remain
unchanged. The workspace source override exercises the patched upstream module without
rewriting declared mount policy; published installs need that upstream change delivered.

Explicit launcher subcommands and the `cli` prefix replace the process with the pinned
CLI before importing runtime policy. Cwd, environment, literal argv, stdio, home guards
and CLI session storage remain CLI-owned. This supplies existing administration and
scripting without another mutation implementation; it is not native TUI private-state
resume, a new dashboard, or automatic execution of commands typed into a model prompt.

## Cancellation ownership and resume (2026-09-17)

Cancelling a Rust-backed Session.execute awaiter is not proof that its Python
orchestrator callback has stopped. The app mounts an ExecutionOwner around the
selected orchestrator through the public coordinator API, retaining the selected
module's execution policy and kernel lifecycle dispatch. After a short immediate-
cancellation drain allowance, **forced** Stop cancels that owned task and joins execution before capturing
context. Repeated caller cancellation cannot abandon cleanup. If actual task
ownership is unavailable, forced awaiter cancellation is explicitly uncertain and
blocks further admission; uncooperative modules still need process-level shutdown.
Exact-type module capability checks unwrap the adapter; no policy moves into core.

Interactive first Stop requests the public token's graceful state, without cancelling
execution waits or starting an escalation timer. Second Stop requests immediate
cancellation synchronously. Child tokens register with their actual parent after
mounting and unregister only after owned cleanup; late registration inherits the
parent's state. A child still mounting when graceful Stop arrives never starts its
first model call. Public tool-pre denial plus the existing invocation adapter prevent
new tools returned by an in-flight model from starting, including the race through
asynchronous pre-policy. Already-entered calls keep their real results. New approval
requests deny while stopping, and pending human waits close without invented answers.

A gracefully stopped child returns its partial result with cancelled outcome metadata.
It must not raise CancelledError into a still-draining delegate: that exception can
cancel sibling waits and implicitly escalate the whole tree. Forced cancellation keeps
that exception path and joins detached children. Root finalization awaits graceful
descendants without cancelling them; force can interrupt that drain but never abandons
the checkpoint owner. Interrupted turns do not run successful-prompt naming hooks.
Explicit idle mode/local controls reset both cancellation stages and the public
token before admission; stale force intent must not disable a later control's Stop.
The public loops still own model/tool sequencing; tests cover both independently
selected loops and contexts, not arbitrary non-cooperative modules.

Turn outcome and checkpoint safety are different facts. A drained interrupted turn
remains interrupted, but complete, valid public tool pairing can support normal
resume. Missing outcomes are never synthesized on that path. Closed admission does
not erase the underlying healthy state before its final checkpoint. Canonical
capture precedes turn.ended, with no await between that event and its checkpoint.
Contiguous idle display-only observations advance the existing checkpoint without
changing its safety status or crossing an execution/admission gap.

Old uncertain checkpoints are not silently promoted. Explicit recovery creates a
new identity, retaining exact validated public messages only when a terminal
checkpoint is followed by display-only notices; otherwise historical reference
recovery applies. Original bytes, uncertain effects and child evidence remain.
Large checkpoint status previews read a bounded writer-header hint; opening still
validates the full journal/context. A preview is never execution authorization.

Native Ctrl-C Press during work advances the Stop stage and stays; it neither quits
nor clears the draft. Selection copy comes first. Repeat/Release cannot escalate or
quit; Caps Lock works. Idle Ctrl-C opens a separate default-No confirmation without
discarding an underlying modal or draft. Enter on No, Escape, another Ctrl-C and pasted
text never authorize exit. SIGINT uses the same policy; SIGTERM and explicit Ctrl-Q
remain shutdown. Typed stage state survives progress/approval updates, and the live
meter retains elapsed/accounting while explaining force escalation at narrow widths.

Cancellation presentation keeps the existing stage semantics: negative-state colour
is not a new failure outcome. Native active-child clocks extrapolate only elapsed
wall time from identified running observations; repeated sibling snapshots preserve
their anchors. Final reported durations remain authoritative. These clocks live only
in the renderer, freeze on disconnection/ending, and never modify source, usage or
the journal. Interact invalidates only a requested live item's second-level layout;
long turn durations keep visible seconds rather than appearing frozen for a minute.

## Startup transport ownership (2026-09-17)

A wall-clock timeout around an asyncio pipe drain measures both terminal blockage
and host event-loop starvation. Synchronous bundle preparation can therefore abort
a healthy reader while a resumed snapshot is still draining. The pipe writer owns
nonblocking writes and an inactivity deadline on a separate, explicitly joined
thread; runtime preparation, module policy and controls remain on their existing
owner. The bounded queue contains encoded immutable records, not shared mutable
runtime objects. Shutdown stops polling and joins the writer; no abandoned blocking
write or silent retry. A failed transport cannot continue to advertise startup or
durable draft storage. This repairs existing session/presentation obligations; it
does not grant readiness before mounting or alter saved context.

## Directory-local return and usage adjacency (2026-09-17)

CLI source `f0ba88398043f6b012d151360397893e46cd5d52` uses
`project_utils.get_project_slug()` over `Path.cwd().resolve()`;
`SessionStore` chooses that project's store, and `commands/session.py`'s interactive
resume and ID lookup use it. This is exact directory identity, not a Git-root or
recursive parent match. The TUI keeps its existing store format, filtering metadata
by resolved absolute cwd before search, checkpoint previews, paging and latest/ID
resolution. The launcher captures its effective cwd; the bridge pins its opening
cwd across New/Resume. Selection rechecks scope before recovery writes or mounting.
Scoped search preserves other directories' derived cache rows, with a connection-local
SQL selection applied before the result budget; simultaneous windows cannot evict
each other's index merely by searching. Global refresh still prunes absent sources.
Unknown/malformed directory identities never become local matches. Explicit export
and internal global inspection remain separate, without relocating saved sessions.

Activity separators are deferred until the following visible item is known: usage
joins activity, while assistant responses retain their blank. Native immutable
history, the live tail and temporary inspection share the rule; no cursor deletion
or repaint of already-committed transcript is required.

## Readable ongoing work (2026-09-17)

Codex source at `2f8603f07547247e698748884542ba60a157621c`, particularly
`codex-rs/tui/src/bottom_pane/textarea/wrapping.rs` and textarea visual navigation,
uses source-indexed semantic breaks and grapheme-safe fallback, not inserted newlines.
Its hanging whitespace/cursor sentinels are custom behavior. Our pinned TextArea
already offers WordOrGlyph with source-based editing; select it rather than fork an
editor. The bounded chrome height counter must match that editor's Unicode word and
grapheme ranges, including tabs and long-word fragments. This is the same intent,
not a claim of identical separator/insertion-point behavior to Codex.

The native projection condenses each root usage record to one width-safe row,
prioritizing model and cost. Exact reported source remains expandable and in Activity;
no costs or token totals are recomputed. Todo rendering recognizes successful public
create/list snapshots or count-validated update arguments (the actual module returns
counts, not the updated list). At most 256 entries are recognized; other envelopes,
errors and truncated results use generic evidence. Cards show reported task state,
not a task-acceptance verdict, with a checklist in Interact. Each task preview is
bounded to 1,024 characters with explicit disclosure and exact Activity evidence.
Child ownership and
saved/native history remain unchanged; old cards are observations, not a sticky plan.

Foreground model phases are deduplicated transient host observations from request,
stream-block and retry events. Child/naming events cannot replace them; turn ending
clears them, and client identity/active-turn checks reject stale frames. Tools animate
only while observed running, at paint time over the mutable projection (not cached
layouts or committed rows). Human waits, idle and disconnection remain static.

## Agent task titles (2026-09-17)

Foundation's delegate can prepend inherited history before its `[YOUR TASK]`
boundary. Locate the final paired parent-end/task delimiter in a bounded suffix
before clipping the task excerpt; old headings and nested history are not the job.
Missing/out-of-bounds delimiters produce an unavailable title, never a history guess.
The original effective instruction still goes unchanged to the child and Activity.

The child adapter derives one bounded display title per execution from an explicit
instruction heading or the opening task clause. It removes only leading boilerplate;
negation and exact execution instructions remain unchanged. This is an excerpt, not
a semantic summary or a policy claim. No provider call, delegate schema extension,
module or kernel change is involved. Titles persist with child metadata and observed
progress, refresh on explicit continuation and remain distinct from role and activity.
Native/Interact rows prioritize warnings, title and identity before optional telemetry;
narrow layouts use the stable agent ordinal. Activity preserves source instructions,
heading/excerpt provenance and titled breadcrumbs in hot and saved projections. Keep
the small title metadata when large tool output is bounded, including final updates.
Older observations without titles retain their previous preview; no history migration.

## Ecosystem session naming (2026-09-16)

As in app-cli, the app emits `prompt:complete` after successful root execution; the
kernel and orchestrator do not own this event. Configured `hooks-session-naming`
retains trigger, model-routing and title policy. Its module-owned metadata sidecar
prevents a late whole-file write from replacing app admission/composition metadata.
Observed generated titles merge into the app store; explicit user names always win.
Purpose-tagged naming calls are visible background work with session-only usage,
never foreground streams or turn costs. Idle utility observations advance only the
saved journal sequence, preserving canonical context and uncertain/ready admission.
The app does not generate an alternative title when the hook is absent or defers.

## Continuous work and usage (2026-09-16)

App preparation emits named startup phases; neither renderer nor kernel loads bundles.
The existing host/children adapters observe each provider dispatch/response, normalize
reported cache aliases and retain attributed usage messages. Cache writes add to input;
cache reads are already included in input. Foundation's Decimal cost accumulator remains
the arithmetic authority. Per-call journal identities deduplicate restoration; missing
cost and earlier unmetered history remain explicit. No pricing estimates or billing API.
Exact parent-call progress enriches presentation without replacing tool arguments/results.
The bridge publishes a constant-size `turn_metrics` projection on turn/usage events;
the ledger remains the sole accounting owner. The native client advances elapsed
time locally from the host's monotonic turn clock, rejects stale session/turn frames,
and repaints quiet active work without emitting history. The local shimmer uses an
80ms tick only during work/background phases, painting a brighter band through the
label while measures stay muted. Waiting/reduced-motion clocks tick once per second;
idle emits no animation frames. A disconnected runtime stops the local ticks and
live indicators; its separate outcome-uncertain warning remains. New turns
select empty turn accounting before their first report while retaining session costs.
No provider polling, guessed token generation or timer journal records are required.
The native journal commits chronological stable output and uses available viewport space
for remaining mutable content. Explicit Interact is a temporary reflowed projection over
the same source, with inline previews and recursive Activity links; it does not rewrite
primary history, execute tools or change the default terminal mouse owner.

The native palette follows muxplex brand.conf/tokens.css at reference `f88898e`:
base `#0D1117`, raised surface `#1A1F2B`, words `#F0F6FF`, secondary `#8E95A3`,
border `#2A3040`, cyan `#00D9F5`, activity amber `#F1A640`, error `#F85149`.
Use the raised surface, not the almost-identical tile base, for visible user/input
separation. Syntect selectors map to these semantic colours rather than importing
an unrelated theme. Light mode uses brand neutrals and darker accessible accents;
terminal/NO_COLOR remain colour-owned by the terminal. Image pixels are source data,
not UI colour roles. Shimmer blends activity amber toward conversation ink locally.

The supported filesystem adapter exposes ephemeral provider-request guidance for
user-owned `/allowed-dirs`/`/denied-dirs` recovery. A directory-policy refusal is not
an absent directory; mkdir cannot grant access. This guidance does not change tool
configuration, add paths, lift deny precedence or bypass a refusal with shell tools.
Actual policy mutation remains an explicit local command with root-session scope.

## Recursive activity projection (2026-09-16)

The invocation wrapper also retains only a bounded authoritative completion status;
post-hook result bodies remain the sole content source. If truncation destroys a
serialized envelope, the adapter can label the observed invocation outcome without
recovering redacted text. Valid post-hook errors override that fallback. Child call
usage and warnings enrich exact parent summaries; their source events remain journalled
and drillable, rather than becoming independent root notices. No execution/cost cap
or module policy is silently imposed by this projection.

Delegate summaries describe the current execution, including only descendants linked
to that execution. Resuming a child must not add its earlier nested work to a new task's
summary; the session accounting ledger still retains every call. Missing historical
summary fields remain unavailable, never fabricated zero counts or warning-free claims.

Child display proxies emit explicit child/tool-owned Activity observations, including
mount-time messages when no child session handle exists yet. Hook warning/error counts
remain distinct from tool failures. Invocation and public-block IDs include the child's
execution identity because a provider may reuse call IDs or restart request counters
after resume. Parent progress checks both parent identity and its current execution;
late obsolete children cannot update that parent's new work. Forked-skill labels use
explicit module metadata and do not alter the skill's instructions or permissions.

The existing children adapter observes task-keyed tool dispatch at the actual tool
invocation, propagating a scoped ContextVar through delegate/recipe tasks and restoring
it in `finally`. The streaming loop's optional dispatch map is an app compatibility
seam, not a new kernel contract. Unsupported/immutable tools still execute; missing
correlation stays unavailable. Tool instances, schemas, permissions and result policy
remain owned by their modules. Root and child observers emit stable call identities.
Instance-bound guards remain the invocation target, even when a different class method
exists; class replacement is followed only for an originally class-bound implementation.
Rust hook callbacks can use separate Python tasks, so setting scope in a pre-hook is
insufficient; the actual parallel/nested integration test caught that false assumption.

Inspection owns a bounded read-only hot index, stable first-observed sibling order,
explicit parent-call links and descendant status counts. Saved Activity pages read the
public event journal in a worker, not on the input loop: at most 100 siblings per page,
with a 1 MiB response budget and bounded source excerpts. Scans stop at 64 MiB, 10,000
identities or two seconds and disclose incomplete results. Switching conversations
invalidates pending replies. Public emitted blocks are not private-context reconstruction.
The private journal retains full evidence; Markdown export includes model-call usage.
Native committed rows remain terminal-owned; interactive drill-down uses the existing
temporary inspection screen and never replays operations.

## Scoped CLI controls and service evidence (2026-09-16)

`LocalCommands` in the existing runtime-controls adapter owns app admissions and a
separate fail-closed control record. The pinned streaming loop still owns goal
evaluation/continuation; Foundation owns tool mount changes; the inspected filesystem
module owns actual write/edit enforcement. These root controls do not change child,
bash, routing or shared settings policy. Modes retain the module tool's transitions
and cannot silently restore a locally disabled tool. Ordinary turns without an active
goal do not add control-record writes. No new kernel/module protocol is required.

Provider login invokes a mounted asynchronous public method with transient wire-only
instructions. It shares host task/Stop ownership, never stores auth prompt text in the
journal, and never copies credential files. Synchronous or mount-time terminal login
remains outside this supported path. Actual browser authorization needs its human.
Structured CLI adoption uses the existing public-history validator and target readback,
with new identity/source digest; original policy/private state cannot be reconstructed
from a transcript and are not advertised as canonical same-session resume.

Memory and intelligence checks use upstream modules against disposable destinations.
The UI can inspect bounded public forwarding diagnostics for its root session, but
neither an empty diagnostic file nor an HTTP success proves remote indexing. Raw URLs,
error detail and secrets stay out of the projected diagnostics. Personal service health
and policy-equivalent performance require separate evidence, not favorable assumptions.

## Everyday CLI workflow seams (2026-09-16)

Generic result normalization belongs to app presentation, after module policy hooks;
bounded recognized envelopes improve status/preview without rewriting original evidence.
Skill menus consume cached module discovery and refresh after a turn, while actual
invocation retains pinned CLI argument semantics and module-owned loading/fork behavior.
No memory-specific dispatcher is introduced. Recipe file browsing is names-only local
app policy; an explicitly documented ephemeral hook reminds the model that `list` means
active runs. This changes request policy, not the thin kernel or recipe engine. Neither
file selection nor inserted skill text is an execution admission. Tests use actual
modules and controlled state; personal-service delivery remains a separate gate.

## Configured CLI compatibility (2026-09-15, development)

`cli_compat.py` is an app-layer adapter over pinned CLI policy helpers, not kernel
policy. Ordinary new launches select CLI settings; explicit bundle/preset/overlay
launches retain isolated policy unless explicitly opted in. Saved launch policy and
CLI home are restored; cross-policy/home/cwd switching needs a new process. The host
process adopts the CLI workspace before module imports, and the pinned CLI bootstrap
loads its own keys.env with ambient-variable precedence without rewriting it. Global,
project and local settings are captured once for preparation; malformed settings fail
closed. Provider identities, module/source overrides, routing, permissions, default
CLI behaviors and configured app behaviors flow through the pinned merge semantics.
Explicit TUI overlays are later-wins. Behavior load failure is fatal, unlike CLI's
optional behavior omission. Source activation happens after configuration merging.

Terminal-print hooks are replaced by identified projections. CLI-policy launches
retain configured logging/recipe/context-intelligence destinations; isolated policy
retains app-local storage. Existing credentials remain module-owned; terminal-driven
login is not implemented behind the composer. Configured hooks can have startup
effects. No private user configuration or conversation is a test fixture.

Public tool outcomes, child result excerpts, source/severity messages, retry/throttle,
thinking blocks, effective context-budget events and reported root usage get bounded
inline projections. Exact tool evidence remains separately inspectable. Missing cost
or occupancy is unknown, not zero. No provider pricing tables or private meters.

CLI history discovery reads bounded exact-directory metadata. Confirmed import captures
text using descriptor-relative no-follow reads, checks stability, preserves the source
and opens a NEW conversation without model calls/tool replay. Canonical CLI state,
credentials and private modules do not migrate. `/skill` uses pinned CLI prompt semantics;
unsupported slash commands refuse locally. These are named compatibility boundaries,
not proof that every CLI command or configured service works.

## rc5 scoped recovery and evidence

Nested interrupted public-context adoption validates at most two captured ancestors
back to the source root, using bounded no-symlink receipt reads and unchanged root
fingerprints. It refuses cycles, missing parents and active nested ancestry. The
new execution is deliberately parented to the current root; exact child effective
policy still must match, so a parent-specific composition is not silently replaced.
Original children and ancestors never execute or change during adoption. Same-identity
nested continuation keeps its existing active-parent requirement.

Recipe inspection explains the runner's public outcome, including unsafe-resume
refusals; it does not implement a second checkpoint interpreter. JUnit evidence reads
only an explicit simple pytest command's workspace-relative report, bounded to the
existing 64 KiB safe snapshot. New/changed valid reports expose counted case outcomes
and a digest beside command/source evidence; unchanged or unavailable reports cannot
be attributed. Counts do not establish coverage, truth of assertions or authorship.

Request-budget observations allowlist provider-dispatch numeric limits only, including
already-exposed raw numeric fields; they never enable raw logging or copy credentials,
messages or private context meters. Missing effective budgets remain unknown. The
thinking reservation may be part of output, not an additional amount to sum.
Pastes bypass the ordinary 250 ms typing debounce through the same bounded transport;
this narrows the persistence window, not a guarantee for unacknowledged keystrokes.

## Post-rc4 compatibility boundaries

Legacy persistent receipts without relocation fingerprints can be adopted only when
their full recorded mount fingerprint matches the newly reconstructed plan using the
original app-owned transcript location. Execution still uses a fresh new-ID store;
the compatibility check never loads or overwrites the original transcript. Missing
policy evidence and changed/private/nested requirements remain explicit refusals.

Correction reuse is a native-only confirmed copy into an empty idle composer without
attachments. It neither resends the original control nor changes its status. The
eventual Send is a separate normal admission, so the person must review uncertain
earlier effects. Bounded change observations restore prior-version provenance on
resume; new command boundaries must still match the saved digest. This is historical
source correlation, not proof a command tested a file or exclusive attribution.

Model discovery adds allowlisted advertised limits/capabilities from the public model
catalog. It never reads private token meters, constructs context or infers remaining
capacity. Linux clipboard acquisition tries PNG, JPEG, WebP then GIF representations
under one deadline, with no conversion; an available but invalid/mismatched image
fails rather than falling through. macOS still requests original PNG data only.

## Confirmed local review and child finalization

Git inspection remains read-only. An explicitly selected unmerged path can separately
capture a regular UTF-8 proposal of at most 64 KiB. Only confirmed Apply writes, while
the root is idle and its queue held. The host rechecks status and source digest, walks
descriptor-relative without symlinks, refuses hard links, backs up original bytes, then
rechecks inode/metadata before replacing through a same-directory temporary file. Index
and HEAD are untouched. The proposal is consumed before replacement: ambiguous fsync or
transport outcomes cannot authorize an automatic retry. Unrelated applications do not
share a lock, so this detects stale versions but is not an external-writer CAS guarantee.
Backups describe attempted replacement, not certified success; the operation result
separately reports observed completion. Opening/editing the proposal never sends context.

Child finalization now has one shielded owner for public-context capture, cleanup and
durable receipt. Repeated caller cancellation is reported after that owner drains, with
interrupted rather than completed continuation state. This is independent of the
Rust/Python coroutine scheduling warning: third-party callbacks remain unchanged.
Explicit historical recovery also copies bounded public child-message excerpts and
source hashes into the recovery evidence, not executable children or canonical history.
Its inspection is copy-only; arbitrary private state and unfinished recipe effects stay
unknown. Static GIF/WebP keeps original bytes with explicit animation refusal; macOS
clipboard acquisition requests PNG data only, without implicit TIFF conversion.

## Next input slice: semantic references

References use explicit workspace-relative `path:line` / `path:start-end` selection,
capturing a regular UTF-8 file once with no symlink traversal. Confirmation discloses
the path, one-based inclusive range, full-source digest and selected-content digest.
They share the existing once-only attachment admission record with images, so a mixed
set has one identity and one durable claim, not two partially consumed drafts. Existing
`image`/`images` storage and transport keys remain backward compatible; entries declare
their media type. Public metadata omits original bytes. References use public text
context blocks with explicit provenance; only actual image entries require vision.
No code is executed and no path is reread at Send, queue dispatch or resume. Text recall
does not attach references. Four combined attachments and existing storage budgets apply.

## Indexed discovery, media and reference migration

Search uses a derived 0600 SQLite trigram cache, not rewritten journals. Incremental
refresh reads up to 16 MiB / one second; query work has a cooperative SQLite progress
deadline. Oversized/invalid/incomplete records and budget exhaustion remain partial.
Replacement/truncation invalidates cached rows; corrupt caches are preserved before
rebuilding. Content matching precedes 100-result paging. Timestamped admissions order
directory recall globally; legacy timestamps are unknown, never synthesized on reopening.
Snapshot replacement waits for active recall to finish and retains later submissions.

Image drafts hold at most four immutable 2 MiB PNG/JPEG snapshots. Pillow makes a bounded
32×16 coarse thumbnail (16 megapixels / 8192 per-side input limit); original bytes, not
the preview, enter the public image blocks. Queue image storage is capped at 16 MiB;
claiming draft ownership precedes queue persistence, and dispatched rows never auto-retry.
Local clipboard acquisition is explicit, bounded and process-group-owned, supporting
only available Wayland/wl-paste or X11/xclip. No inferred SSH clipboard access or OSC52 read.

Stored-context inspection reads public messages while idle, with bounded excerpts and
image bytes omitted. Provider llm:request summaries are separate dispatch observations;
raw wire payloads never enter the host's journal through this observer. An explicit
one-shot diagnostic can retain a bounded, in-memory projection of the next root
`llm:request.raw` if the selected provider exposes it. It never enables provider raw
logging, rebuilds context or calls a model. Missing payloads remain unavailable; headers,
media bytes, unknown top-level fields and oversize content are omitted. Provider-side
redaction and projection mean this is not exact network serialization, delivery proof,
future context, or an occupancy meter. Explicit clear, re-arm and reopening discard it.
Module-authored logging policy is independent and may already persist that source event.
Standalone confirmed provider probes pause the queue and cannot become transcript turns.
Text import creates a new composition with a hashed historical reference, not executable
tool messages or module-private state. Recovery also retains a typed source-event ledger.
Completed children may retain bounded JSON orchestrator overrides across guarded reopen;
root/effective fingerprints, active parent, routing and inherited-mode checks still apply.

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

Native control writes use eight queued records plus one in flight, at most one MiB each;
the UI never waits for a host to drain its pipe. Queue failure disconnects without
retry and leaves unacknowledged intent uncertain. The native client owns a separate
Unix process group for its host. Exit requests cooperative shutdown, then terminates
that group after three seconds and reports forced termination after restoring the
terminal, allowing up to 500 ms to confirm direct-child reaping; missing confirmation
is explicit rather than another unlimited wait. This covers inherited-group descendants, not detached groups or remote
effects, and does not certify module cleanup or fix callback cancellation warnings.

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
Instruction sources use `mentions:resolved` observations registered before initialization,
not a full request reconstruction. Advisory model discovery runs only after an explicit
UI confirmation through public mounted `list_models`; copy does not select. Provider
exceptions disclose only their type, not possibly credential-bearing exception messages.

Saved-message discovery now uses the incremental private index described above; the
earlier tail scan is superseded. Metadata discovery still enumerates the local catalog
(64 KiB maximum per metadata file). Oversized canonical checkpoints are validated on
opening, not fully loaded for menu discovery. Matches are excerpts with event sequence,
never imported context. Both startup and in-app pickers can search indexed content;
record limits and unfinished refreshes remain disclosed partial results.

`local_drafts` stores private atomic/fsynced editor copies outside canonical context/admission.
Original conversation/request scopes survive explicit historical recovery, but carry no
delivery authority. Corrupt records are retained and reported, never overwritten as empty.
The client autosaves after a 250 ms pause and before leaving the editor; recent unflushed
input is not crash-durable. Answer/correction and other dialog copies can outlive their
submitted request. Queue-edit copies retain the original queue identity; search, rename
and file-selector copies retain their dialog kind. Recovery is copy-only, never activation.

Completed child continuation is lazy and explicit through the public resume capability.
It validates the saved parent/root fingerprint, completed status, inherited mode and recreated
mount-plan fingerprint before execution. Recorded provider preferences reconstruct through
Foundation's public resolution API; changed resolutions refuse. Nested continuation needs
its actual parent active and never starts ancestors implicitly. A running receipt is persisted
before effects so the old completed receipt cannot authorize replay after a crash. Interrupted
children and unsupported/old receipts fail closed. Persistent-context child paths are scoped
under the root conversation and child identity, before fingerprinting. Real v2 recipe-tool
failure/reopen/resume tests separately verify completed-step skipping, not arbitrary process recovery.

Root and child startup now use `create_owned_session`: acquire the public kernel session
before awaiting initialization, mount Foundation's public resolver/deduplicator/capabilities,
initialize, resolve pending context, and install the public system-prompt factory. On any
startup exception/cancellation, drain acquired-handle cleanup even through repeated cancellation.
Factory equivalence is tested against Foundation. No private lifecycle monkeypatch or UI policy
was added to the kernel. Third-party cleanup that never returns and cancellation-time hook
coroutine warnings remain unresolved, distinct from owning the partially initialized handle.

Root finalization is not a second execution: repeated Stop is idempotent, and a first Stop
after execution has already ended cannot cancel its checkpoint. Close rejects admission,
joins in-progress startup/turn work, and owns one shielded cleanup task shared by all callers.
Cancelling a close waiter is reported only after cleanup drains; cleanup failure remains
observable on later close requests, without automatic retry or releasing an owned store early.
Startup's exception path detaches before joining close to avoid a startup/close wait cycle.
This does not impose a timeout on uncooperative modules or fix Rust/Python callback warnings.
Close during finalization can conservatively retain an uncertain checkpoint; it never upgrades
interrupted work to resumable success merely because cleanup finished.
Explicit mode operations reset the same task-state flags on admission and enter finalization
before checkpointing; a previous completed conversation turn cannot make a new mode operation
immune to Stop. An interrupted mode transition still fails closed rather than claiming rollback.

Text input reads one descriptor-relative workspace file with no symlink traversal, a 64 KiB
bound and before/after metadata check. Preview owns captured bytes and digest. Insertion adds
literal text to the existing draft; it does not alter context or reread at submission. The
image path captures one PNG/JPEG of at most 2 MiB into a private atomic admission record.
All mounted providers must advertise vision. Metadata-only UI preview confirms frozen bytes;
explicit idle submission marks dispatch before adding a public image block to canonical context,
then calls the ordinary string-prompt orchestrator. No implicit reread, queue conversion, retry,
clipboard image acquisition or thumbnail decoding. Dispatch is not proof of provider receipt.
Historical recovery leaves image records in the original conversation. External editing is an
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
Only one candidate initializes at once; the acquired session is cleaned even if its
initialization fails. Mount-time candidate approvals are denied, not retargeted to the
source UI. The final source-cleanup/commit phase is not cancellable from the client;
an exceptional cleanup failure is an error, not a claimed rollback.
History recall finishes before the target's ready snapshot is published. Snapshot and
switch-result publication have no intervening await; the native footer keeps "Opening"
until the matching switch result. This prevents a Ready display while input is still
blocked waiting for directory history. Early Enter is never deferred or silently replayed.
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
The live region contains mode, contextual controls, draft and current activity. Ordinary
wide idle chrome is five rows plus one empty separator/cursor-anchor row: mode heading,
one open input row, separation, actions and status. The editor
glyph-wraps and grows to six visible rows; controls wrap at narrow widths. Queue/Steer/Stop
appear during work; the current mode remains above the input. No side border or prompt
character is painted alongside any draft row, including in inspection. Native emission,
live content, composer and inspection share the full terminal width with no outer gutter;
Markdown indentation and dialog-internal spacing remain content structure. Ordinary live
headers omit renderer/runtime branding; fixture/simulated labels remain explicit.
Readiness reads simply Ready; errors and tool-outcome qualifications are not suppressed.
The bounded conversation title remains visible when it fits, including after rename.
Work/Review/System are available through Actions and existing keys, without a permanent tab row.
Unfinished Markdown is held in an eight-row live preview; complete source
remains available through Transcript inspection. Incomplete fences/tables are not frozen
into prematurely final Markdown. This is not arbitrary streaming-source rewrite support.

Review/System, menus, editors and source inspection use a temporary alternate screen;
return restores primary output and commits newly observed work, not a second transcript.
If inspection was resized, return/exit queries the restored primary cursor before
clearing; the old live height is not an anchor and can otherwise erase short replies.
Unchanged-size return/exit issues no extra query.
Normal mouse input belongs to terminal selection; inspection enables mouse controls.
Queue/steer/approval/question operations retain the same host identities and policy.
No kernel, provider, orchestrator, context or runtime transport changes are required.

The client manages a fixed Ratatui live viewport: the library's default inline resize
clears the screen on narrowing. Native history must not be cleared on resize. Growth
also accounts for tmux pulling history onto the screen without moving its reported
cursor, only on height growth with an unmoved anchor. The cursor parks on an empty live
separator, not a wide composer border: tmux can map a border's cursor onto its wrapped
continuation after narrowing, leaking that first border row into history. A focused real
tmux regression counts composer headings as well as retained transcript/shell markers.
Resize does not sleep or purge/replay history. Cleanup flushes pending source, removes live chrome and restores only owned
terminal modes. Exit retention is separately tested from saved-conversation recovery.
Startup preserves the preceding whole screen with primary-screen CRLF scrolling, then
starts a fresh page. It needs no cursor query or startup CPR timeout. The transcript
starts at the top and the composer stays bottom-aligned; the live viewport owns the
intervening space until output fills it. Blank space keeps the terminal background.
Exit removes that live space and places the shell immediately after emitted output.
Full-pane previews retain the transcript; footer-only crops can omit short conversations.
Erase owned rows individually: tmux can archive a provisional full-height frame when
ED starts at row zero. This is not transcript replay or a history purge.
A Unix resize cursor-position probe now has a 100 ms deadline, then scrolls a fresh page
using CRLF; it never emits a scrollback purge. The single input owner reads at most 64 KiB
and replays every byte through public `crossterm::event::buffer_input`, including Unicode,
paste and partial responses. After a silent probe it does not issue another query, avoiding
late-response attribution. Normal responding terminals take no timeout. This uses the
[Codex Crossterm fork API](https://github.com/openai-oss-forks/crossterm/blob/45fecb9508105988f42fe6ff0441783ed3717f92/src/event.rs),
pinned to `45fecb9508105988f42fe6ff0441783ed3717f92`; no event reader may race the probe.
Linux PTY/tmux evidence does not establish behavior on every terminal or a character-exact
resize anchor. A response-shaped literal spanning an already buffered paste remains an edge to probe.

Readiness is an explicit additive `ready` field in real-host snapshots/state, not text
matching. The provisional editor accepts input but does not admit or defer a submission;
Enter before readiness retains the draft. Older v1 scene snapshots without this field
remain compatible. Startup failures leave the editor usable. When typing races a restored
draft, the current editor/selection/undo stays intact and the original becomes a scoped
`startup` entry under Saved local drafts. Requests that could replace it carry the backup;
the host persists that copy before saving/submitting/queuing/switching. Corrupt/full storage
rejects the mutation and retains the original. Backup retries are idempotent, not retries
of execution. Recovery never inserts text into canonical model context automatically.
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
and admission can leave an uncertain record. That record blocks release until explicit idle
acknowledgement marks it dismissed, preserving its identity/text and holding the queue.
This is uncertainty resolution, not proof of non-execution or retry. A queued draft may still be visible if the process dies before its
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

Syntax colour uses pinned Syntect 5.3.0 with embedded grammars/themes and the Rust regex
backend; no user grammar files, plugins or network resolution. The documented
[line highlighter](https://docs.rs/syntect/5.3.0/syntect/easy/struct.HighlightLines.html)
retains multiline lexical state within one block. Only token foregrounds are projected
into Ratatui spans; terminal escape sequences are not generated from code. Existing
display sanitization remains separate from exact source/clipboard ownership. Unfinished
native previews remain plain, avoiding repeated parsing of growing fences.
Highlighting accepts at most 16 KiB per Markdown render, 256 lines per block and 1024 bytes
per line. Unknown/disabled/oversized/error cases retain plain source, not a truncated
highlighted excerpt. Eight source-and-language cache entries avoid reparsing on resize;
these are input/memory-work bounds, not a hard CPU deadline for a regex. Grammars initialize
lazily; the syntax stress receipt includes cold grammar use while typing.
Inspection stores the captured code separately from explanatory text, so Markdown-like
code cannot become active links/headings and copying never incorporates a preview label.

Textarea retains a scroll origin across viewport growth, even when all input now fits.
For fitting drafts the app primes the public renderer at origin zero and restores the
exact cursor/selection before painting. No draft recreation or undo-history reset occurs.
A deterministic one-row-to-three-row test complements the real tmux inspection regression.

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
equivalents); this host applies exclusions to explicit agent contributions too. The
original 4-active / 32-total / 3-depth limits are superseded by per-parent admission
and durable context retention described above. Valid completed receipts can resume
explicitly after restart when parent/composition/mode still validate. Subprocess
isolation remains refused.
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

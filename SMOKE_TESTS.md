# Verification guide

Shared-session gate: run `uv run --no-sync pytest -q tests/test_shared_sessions.py tests/test_shared_usage.py`
for actual CLI SessionStore round trips, same-ID canonical writeback, directory-local
picker/search/recall, session settings, preserved unknown metadata, no-replay startup,
changed-CLI projection rebuilding, reminder filtering, explicit branch context,
stale-write/uncertainty/symlink refusal, private export and reversible TUI visibility.
When independent loop/context packages are installed, four combinations also verify
module-owned private system history survives resume without entering the CLI's public
transcript. Missing packages explicitly skip those checks; never use shared-home
defaults for the persistent-context fixture. Accounting checks cover root/child/utility
receipts, recorded forks, repeat-resume deduplication, conflicting/missing/symlinked
logs and capture bounds. Preserve canonical bytes; earlier costs never enter a new Turn.
Run `uv run --no-sync python scripts/shared_session_probe.py` serially with other
PTY tests. It creates a fresh disposable CLI environment/home, uses actual CLI
entrypoints and default app behaviors, then resumes the same identity in native TUI
at 175×50 and 40×20. Never reuse a CLI environment claimed by another home or bypass
the CLI ownership guard. Local bundle overrides require file URIs for fragments.
Only the provider/tool are deterministic fixtures; no paid calls are authorized.
Inspect private `shared-session-*` captures and require new-turn tool outcomes,
no transcript growth before Send, unchanged root-session count and restored TTY.
The probe mounts actual hooks-logging and reconciles fixture usage across returns.
Its mixed Markdown answer exercises nested lists, loose paragraphs, quotes, headings,
code, Unicode and links; narrow screens correctly retain the opening text in history
instead of requiring both the opening prompt and the answer tail on one screen.
The probe also starts/resumes an explicit isolated composition under its owned
`--cli-home`, asserts canonical storage and rejects a parallel live journal store.
Raw probe logs/settings/transcripts are private and must never be published. This
does not certify concurrent writers, private-control equivalence or complete costs
when the source receipts are missing.

Structural reading gate: build the native frontend, then run
`TUI_TEST_CANDIDATES=1 uv run --no-sync pytest -q tests/test_structured_reading_terminal.py tests/test_reading_terminal.py tests/test_tmux_scrollback.py`.
Inspect `mixed-markdown-*` captures at 40/80/175 columns. Exact source copy and draft
preservation are independent assertions. Rust tests compare styled incremental and
completed Markdown at every character boundary and reject parser-decoded controls.

Release upgrade gate: `scripts/release_wheel.py --terminal --scripting --upgrade-from
PATH_TO_PRIOR_WHEEL` requires the published wheel's adjacent `.receipt.json`, verifies
its name/hash and scans both artifacts before installing. It seeds real fixture turns
with the prior release, reinstalls the candidate into that SAME isolated tool environment,
then resumes the original identity twice. Historical bytes must remain a journal prefix;
return must retain the unsent draft and must not add model turns or tool events before
explicit Send. Require a successful tool result from each new turn, not old history.
Installation has no Cargo on PATH. The five-platform workflow downloads rc5 and runs this gate, installed
CLI scripting/completion, and disposable macOS pasteboard checks. Old versions/artifacts
are never overwritten. These runs do not prove arbitrary private-module migration.
Keep first-install and upgrade startup observations labelled separately; neither purges
global caches or establishes cold-start performance. Publish only reviewed wheels and
allowlisted receipts from the exact candidate commit, never local diagnostic logs.

SSH transport gate: run `TUI_TEST_SSH=1 uv run --no-sync pytest -q
tests/test_ssh_terminal.py` serially with all other PTY/service/tmux tests (shared
resource bookkeeping). Linux and local OpenSSH server/client are required. The test
owns a loopback-only daemon, temporary keys and a forced synthetic fixture command;
it never edits system SSH configuration or user authorized keys. Exact public-key and
strict private host-key verification remain enabled. Only the disposable daemon's
ownership walk is relaxed because OpenSSH rejects the shared `/tmp` ancestor; the
key directory must still be private. Assert the remote tty size, not just the local
observer's grid, before judging a resize. A fresh input repaint must preserve pasted
text without submission. Both local and remote tty guards require restoration.
The lightweight observer does not implement terminal reflow; its post-resize image
can retain stale chrome. Do not call that a visual pass or repair it by clearing real
history. Use the attached tmux gate for resize/reflow and inspect pre-resize SSH paint.
Track listener/descendant process identities and verify cleanup before recording
reaped. This is actual SSH transport, not physical-phone, WAN or clipboard proof.

Entrypoint completion/housekeeping: `tests/test_entrypoint_workflows.py` verifies
archive confirmation, exact identity, original directory, single-writer refusal,
retained content and explicit restore. CLI/bash protocol checks cover native options,
actual nested commands and configured provider candidates; bash/zsh/fish sources
must leave settings/session bytes untouched. Explicitly fail key/store construction
to prove completion does not initialize them. No shell startup-file writes.
Run `scripts/release_wheel.py --terminal --scripting` for an isolated uv-installed
wheel, real native fixture start/turn/resume, actual CLI argument/stdin prompts and
text/JSON/JSON-trace output, plus installed completion. Use `--output-dir .evidence/…`
for private candidate evidence; this does not publish a release. Fixture bundle
arguments use `file://` URIs, not bare paths (which the CLI resolves as names).
`--private-failure-log NEW_PATH` retains bounded mode-0600 failure diagnostics only;
never commit/upload that file. A passing deterministic script is not paid-provider
or arbitrary module-private-state proof. Do not bypass the CLI foreign-home guard.

Session operations: `tests/test_session_workflows.py` exercises confirmed context
clear, retained backups/history/draft/held input, no-op refusal, turn-branch validation,
source preservation and projection-only JSON exports. Direct tools must exercise real
kernel denial, modified input, hook-owned and tool-owned Allow/Deny, no root-provider
or naming calls, graceful drain and force uncertainty. Run the direct-delegate tests
in both actual presets and the clear tests in both loop/context swaps. Native
`tests/test_session_workflows_terminal.py` covers default-No confirmations, retained
drafts, branches and actual direct-tool approvals at 175×50 and 40×20. Inspect private
`session-*` captures. Wait on a new turn ending plus the current idle footer, not a
retired completion label; narrow action-search selectors must fit the search field.

Configuration mutation: `tests/test_cli_controls.py` verifies actual mounts, dynamic
context, disabled-agent spawn refusal, protected providers, behavior hook retention,
metadata-only edits, no-op/partial fail-closed state, v1 migration and unchanged
conversation policy after a shared save. Scope tests use temporary CLI homes, preserve
unrelated settings and malformed YAML, and require explicit scope plus confirmation.
`test_cli_compat.py` verifies configured policy survives actual CLI preparation without
entering reports. Native controls tests exercise toggle/diff/aliases at 175×50 and
40×20; inspect private `config-changes-*` / `config-aliases-*` captures. No model turns
or actual shared-settings writes are authorized by these fixture tests.

Loaded configuration: run `tests/test_cli_controls.py` and native
`tests/test_controls_terminal.py`. The catalog must use the same loaded Foundation
inspector as the CLI, with cached completion only; it must not read source contents,
dump arbitrary config values, call providers, change shared settings or alter model
context. Distinguish available definitions from active agents, runtime tool toggles
from persistent configuration, and context entries from token occupancy. Exercise
32-item omission, exact-name access beyond that list, unavailable inspection without
exception-value disclosure and post-toggle refresh. At 175×50 and 40×20, use Actions
to insert `/config`, explicitly Send, inspect one item and preserve a subsequent
draft. Wait for a new correlated observation, not an identical row from the earlier
dashboard. Slash suggestion acceptance and command Send are separate actions; use
an explicit paste for the exact-argument path. Inspect private `config-*` captures.

Subprocess children: `tests/test_child_process.py` uses real kernel/modules in fresh
interpreters, with deterministic providers. Check explicit/configured process mode,
hot/cold continuation, environment filtering, attribution/accounting, nested local and
process children at capacity one, Allow/Deny and actual question answers, graceful
drain, emergency group termination, startup/crash failure and parent disappearance.
The private RPC test holds one handler open while controls proceed, then checks
oversized replies fail closed. A reset socket must not skip process reaping; interrupted
or lost canonical capture must not authorize continuation. Linux /proc disappearance
may surface as either ENOENT or ESRCH while reading a dying process.
Run actual delegate/recipe and inherited-mode tests in both presets, then native
`tests/test_child_process_terminal.py` at 175×50 and 40×20. Inspect private
`child-process-*` approval/complete/stopping/stopped captures: the question precedes
the full child identity, explicit Allow is still required, Stop retains the draft,
and validated drained children remain resumable. Wait for the dialog to close before
typing and for the full draft to repaint after a terminal update; a partial PTY frame
is not evidence that input was discarded. These are offline module/terminal checks,
not billed model-wire evidence or an operating-system sandbox certification.

Legacy output: `tests/test_runtime_output.py` exercises actual descriptor capture,
split controls/UTF-8, synthetic credentials, ring/line limits, a 20,000-line flood,
decoder failure, restoration and joining. The real fixture host runs an ordinary hook
using print, Rich, logging, native fd writes and inherited subprocess stdout; verify
valid protocol, unchanged tool outcome, no journal pollution and explicitly process-
scoped retention across conversation switching. These are fixtures, not a certification
of an external pipeline's interactive UI or arbitrary secret detection.
After rebuilding Ratatui, run `TUI_TEST_CANDIDATES=1` against
`tests/test_runtime_output_terminal.py` alongside controls, Activity and graceful-stop
regressions. Inspect private `runtime-output-{175,40}-{catalog,detail}` captures for
readable scope/copy warnings, no null conversation fields, unchanged draft and return
to native selection. Opening diagnostics must not submit or execute anything.
Queue regression waiters must include runnable queued work, not merely absence of an
active/dispatched task: a done callback can still be scheduled to admit the next row.
The delayed-completion fixture in `test_followups.py` exercises that boundary explicitly.

Child continuation: `tests/test_child_continuation.py` uses real fixture execution
for hot/cold routing changes, saved preference precedence, scoped fallback warnings,
cancelled admission and graceful/forced interrupted-child continuation. Tampered
receipt fields, changed tool policy and unpaired outcomes must refuse without edits
or execution; keep `tests/test_daily_replacement.py` in the gate. Run actual delegate
resume and independent child/parent mode tests in both presets. With TUI_TEST_SWAPS=1,
exercise both loops and both contexts through interrupted-child cold continuation.
Keep canonical continuation distinct from public-context adoption and never count
restored observations as execution. These deterministic runs are not provider-wire
or arbitrary module-private-state certification.

Delegation admission: `tests/test_child_admission.py` exercises forty real fixture
children, cold continuation, ten concurrent requests, graceful/forced Stop, nested
capacity and cancelled continuation receipt preservation. Run children, sustained-work,
graceful-stop and actual delegate/recipe preset regressions too. The hot-context limit
must never become a lifetime execution quota. Native sustained tests include bounded
hundred-child observations at 175×50 and 40×20: inspect `admission-*` captures, omitted
counts, full accounting/error badges and Activity access. Those terminal observations
are synthetic transport fixtures, not a hundred live model calls. Module self-depth
and parent ancestry are different; never substitute the latter for the former.

CLI host parity: run `tests/test_cli_controls.py`, `tests/test_cli_compat.py`,
`tests/test_installation.py` and the cancellation/ecosystem regressions. The goal test
uses the actual loop with a scripted evaluator, verifies mechanical stopping and
durable no-replay resume. Provider coverage includes more than eight named mounts.
Computer-use tests use the actual upstream gate/core approval with counted fixture
effects, never a personal desktop. Run that upstream repository's full offline suite
too; these checks do not certify device injection or provider wire behavior.

Build Ratatui, then run `TUI_TEST_CANDIDATES=1` against
`tests/test_navigation_terminal.py`, `tests/test_controls_terminal.py` and
`tests/test_graceful_terminal.py`. Inspect `cli-parity-arguments-*` and
`cli-parity-models-*` captures at laptop/mobile widths. Completion Enter inserts;
only subsequent explicit Send invokes the local command, not a model. Read-only
model-menu queries must not emit unrelated transcript progress after their correlated
result; command-owned progress is separate. CLI launcher tests isolate home/cwd and
exercise actual help paths; they do not prove a billed single-shot run, account login,
shell installer, or installed-wheel artifact. Keep those boundaries explicit.

Action emphasis: `test_action_terminal.py` checks actual painted action/outcome/child
badge roles, command expansion, draft retention and native/Interact round trips at
175×50, 40×20 and 32×12. Inspect `actions-*` captures. Run readable-work, sustained,
graceful-stop and real tmux scrollback regressions too. Test successful delegates
with failed/unknown children: their badges must not inherit parent success colour.
Only the state span shimmers; titles, warning badges and accounting stay steady.
NO_COLOR retains explicit outcome labels and reduced motion disables shimmer.
Expanded commands preserve syntax/source; output preview limits apply AFTER wrapping
and disclose the full-evidence route. At tiny heights, navigate visual rows to inspect
wrapped requests instead of assuming a multiword phrase fits one row. Scope colour
sampling to the intended row: a command containing `done` is not a completion badge.
Combine exact tool identity with the Request heading; an extra heading needlessly
displaces actual evidence at minimum height. Unknown ecosystem tools keep their name.
Keep standalone probe selectors aligned with the native action-first labels, without
changing OpenTUI or Activity-menu vocabulary. Assert tool success from observed events;
inspect detailed result markers through evidence, never by demanding that compact
rows leak their output bodies. Fixture-only probe runs do not exercise billed presets.

Stop presentation: `test_graceful_terminal.py` also checks red stop/hint/force/stopped
cells and advancing quiet clocks at 175×50, 40×20 and 32×12, with motion, reduced
motion and NO_COLOR. Inspect `stop-style-*` captures. Long turns retain seconds;
delegated live durations advance in native and Interact views without source/tick
events or extrapolated accounting. Repeated sibling snapshots must not reset a quiet
child's clock; completion/disconnection stops it. A tiny view may replace the meter's
bullet with an upward-history cue: sample the named state, not the bullet. Probe.read
returns on data arrival, not after its timeout: prove passage of real time by a
deadline or successive displayed seconds, never by two adjacent animation frames.

Two-stage Stop: run `test_graceful_stop.py` with `TUI_TEST_SWAPS=1` and the actual
delegate cases in `test_ecosystem_workflows.py` with `TUI_TEST_PRESETS=1`. Hold current
model/tool/stream operations open beyond the force-drain allowance; first Stop must
not cancel them or start any subsequent tool. Exercise asynchronous pre-policy and
late approvals, nested parallel siblings, and Stop while a child is mounting. Release
one branch while another stays active: no implicit force escalation or early root
checkpoint. Then exercise explicit second Stop and joined cleanup. Verify public
parent-child token propagation independently of the app's fallback child loop.
Run `test_graceful_terminal.py` plus `test_session_repairs_terminal.py` serially with
native candidates enabled. Inspect `graceful-*` captures at 175×50, 40×20 and 32×12:
elapsed/accounting, the force hint, editable draft and default-No exit choices must
remain visible together. Test repeat/release, Enter on No, Escape, repeated Ctrl-C,
bracketed paste, actual choice clicks and OS SIGINT; none implicitly confirms exit.
Force and graceful outcomes both retain validated same-identity resume without replay.
Small-screen hint/button wording must not push the timer out of the live region.
Mode fixtures must distinguish ephemeral user-role reminders from a new request.
Assert the awaited turn's terminal status: wait_for can cancel a host task that
returns an interrupted outcome, so an await returning is not proof of completion.
Explicit later mode/local commands must reset both Stop stages and the public token.

Cancellation/resume: run `test_lifecycle.py`, `test_owned_execution.py`,
`test_conversations.py`, `test_recovery.py`, `test_navigation.py`, and native
`test_session_repairs_terminal.py`. Hold an actual provider/tool callback open,
cancel repeatedly, and observe its asynchronous finalizer before checkpointing.
Stop and explicit Quit must retain valid interrupted context; resume executes
nothing until a new explicit Send. Incomplete tool pairing must still refuse normal
resume. Include a late cleanup display notice and exact checkpoint/journal sequence.
In PTY tests, Ctrl-C stops/stays with the draft retained at 175×50, 40×20 and 32×12;
Caps Lock Press works, Repeat/Release after Stop do not exit, selected text still
copies, and explicit Ctrl-Q quits. Inspect `cancel-*` captures. Resume restores
composition: do not pass `--fixture` or overlays again. Tiny native views can scroll
completed responses away; assert the saved terminal outcome, not continued visibility.
Legacy uncertainty needs a recovered copy with original hashes unchanged; complete
public context is retained, never replayed. Test checkpoint previews above 64 KiB.
Run independent loop/context swaps because cancellation wraps the public module
mount, and check module-specific capability guards through that transparent adapter.

Startup delivery: run `test_frontend_bridge.py` and the large saved-conversation
resume in `test_everyday_terminal.py`. Replay must exceed 1 MiB and overlap actual
pipe consumption with a synchronous preparation delay longer than the delivery
deadline. Prove Ready, startup edits retained, zero resumed work before explicit
Send and exactly one new fixture tool invocation afterward. A timer on the runtime
event loop cannot distinguish a slow reader from blocked preparation; the writer's
own progress clock must. Test genuinely stalled pipes, bounded records/bytes,
immutable payloads, joined shutdown and nonzero failure exits with stdin still open.
`test_flow_terminal.py` verifies Enter/editing after startup disconnect at 175×50,
40×20 and 32×12: no stale Starting/Mode: loading, no lost draft, no automatic retry.
Inspect `startup-*` captures. Observe a unique newly typed suffix, not the word
"unsent" already present in the failure warning; wrapped source need not occupy
one display row. Restore the fixture store before asserting its replay projection:
the live store's restored-event list is intentionally empty on its first launch.

Directory-local resume: compare exact resolved cwd with the CLI's project store.
Test parent/child/sibling isolation, symlink equivalence, malformed metadata, empty
scope and latest/explicit IDs; filter before paging and indexed message search.
Seed foreign matches beyond the query limit: scoped search must neither consume its
budget on those matches nor delete another directory's shared index rows.
Revalidate direct switch/recovery requests before target writes, retaining source
draft and zero provider calls. In PTY tests, restart from the intended actual cwd:
an earlier `--cwd` option does not change a later test process's launch directory.
Inspect `directory-resume-*` and `usage-spacing-*` captures. Usage joins tool/thinking
rows in both native and Interact views, but retains a blank after assistant prose;
test separately arriving committed rows, not just one buffered snapshot.

Readable-work follow-up: `test_readable_work_terminal.py` drives word-wrapped paste,
visual navigation, resize, todo/usage expansion and live tool/model-phase styling at
175×50, 40×20 and 32×12. Assert exact submitted source, not reconstructed screen text.
At minimum height use actual PageDown to read expanded source; allow its new frame
to settle before scrolling, or the observer can skip the row it meant to inspect.
Inspect `readable-*` captures. Compact usage is one row; exact numbers and timestamps
remain in its expanded record. Run `test_flow.py` for actual core phase callbacks,
deduplication and stale-host isolation, plus both-preset todo create/update/list in
`test_usage_scope_recovery.py`. Count-only updates require validated original
arguments; successful invocation must not paint every task done. Editor height must
match the actual widget after changing its wrap policy. No user session is a fixture.
When sampling waiting colours, identify the whole meter label: the ordinary footer
also says Waiting in a different, static colour. Combining both is not motion.

Brand/activity follow-up: `test_brand_terminal.py` checks actual painted cells,
quiet startup/Working shimmer, static reduced-motion/NO_COLOR, editable drafts,
Interact round trips and idle output silence at 175×50, 40×20 and 32×12. Animation
must emit small buffer diffs, never new transcript/timer records or history purges.
Close the actual host pipe during a turn: stale observations must not keep animating
as live work; the disconnection warning and editable unsent draft remain.
Inspect the captures as well as the assertions. Source images retain their pixels;
syntax styles are restricted to palette roles. Waiting for a decision stays static.
`test_usage_scope_recovery.py` uses both actual presets with a controlled provider:
long inherited history must not supply a task title, mkdir must not unlock a denied
write, and explicit allow/deny controls retain precedence across resume. Always test
the actual delegate wrapper, not only hand-authored instructions. Cumulative turn
tokens include repeated input across calls; do not replace them with last-call input.

Task titles: `test_task_titles.py` exercises explicit headings, bounded excerpts,
negation/Unicode, same-role parallel children, exact source, saved Activity and new
tasks on resumed agents. Provider-call counts must remain unchanged. Verify nested
titles independently of their parent's title. Keep display metadata through bounded
output/finalization; a multi-child call must not inherit only its first child's job.
`test_sustained_terminal.py` checks titles beside the working meter at 175×50, 40×20
and 32×12, native/Interact/expanded source (`titles-*` private captures). Tiny expanded
previews need multiple line/page movements to read the full request. Warnings take
priority over a long title; the title must never replace the original instructions.
Verify active rows and the meter together: testing either alone missed blank padding
displacing the last task at the minimum size. Drop optional live-tail padding first;
do not rewrite committed terminal history or hide an available accounting measure.

Active-turn meter: `test_flow.py` checks reported root/child totals, cache semantics,
utility-only session accounting, missing/partial costs, reset and persisted restore.
`test_flow_terminal.py` holds the native host silent while elapsed time advances at
175×50, 40×20 and 32×12; inspect the `meter-native-*` and `meter-interact-*` captures.
Keep the unsent draft through Interact, Stop and next-turn reset; reject obsolete
turn/session metric frames. Time ticks must never append journal/transcript rows.
Reserve meter space when sizing the composer; tiny decision views retain an explicit
answer action with the full question in its review dialog. Tokens sum repeated call
inputs plus outputs/cache writes, not current context occupancy; cache reads are not
added again. All money arithmetic stays in the host's Decimal ledger.

Child ownership: exercise `ChildDisplay.show_message` before session mounting finishes
and inside parallel actual tool invocations, including warning/error and thinking/usage
source names. Preserve each public notice under its child/tool and verify the saved
Activity projection too; root-only progress tests do not cover this adapter. Hook
notices and tool failures have separate counters. Resume nested work with the SAME
provider call ID and a restarted request counter: execution-qualified IDs, sibling
filters and late-observation guards must prevent stale work appearing current. Forked
skill metadata names actual execution, not just a file load; a review label is not
read-only enforcement. Keep fixture evidence separate from real skill policy.

Sustained delegated work: `test_sustained_work.py` runs four actual child sessions
with a scripted provider (80 child model calls, 228 child tools), exact per-agent
warning/accounting checks and saved-journal inspection. A separate 700-sibling
fixture verifies pagination after the hot index evicts early identities. Read saved
Activity off the event loop; disclose scan/excerpt bounds and reject stale lookup
replies after switching conversations. A bounded recent cache is not full history.
Truncation tests observe only invocation status before hooks; never retain raw output
to repair an envelope, and never let fallback success override a valid policy error.
The actual mode module must be exercised inside children, not just inherited at spawn.
`test_sustained_terminal.py` checks 175×50, 40×20 and 32×12: compact parallel summaries,
visible warnings (or disclosed above-viewport activity), initial Enter expansion,
line scrolling and paste-then-Send. Do not navigate Up to compensate for a hidden
initial selection. Await the expanded body before inspecting colour: the collapsed
summary can already contain the same words. Native history remains terminal-owned.
Preserve an anchored reader when new input is submitted; completion text can already
be above a tiny visible viewport, so await a retained end-state rather than demanding
that every completed row remain on screen. Resume a child with prior nested work:
its new delegate summary must exclude that older work without dropping ledger costs.
Historical summaries lacking counters must say unavailable, not zero or no warnings.

Provider budget compatibility: `test_flow.py` holds an awaitable provider check
pending through the actual host/core/streaming loop, verifies no generation
dispatch occurs early, then completes the first turn. Check the installed module
implementation, not just a neighboring checkout: a synchronous `request_budget`
method can return an awaitable native count. Await the result before validating;
do not disable the budget guard. The loop's own budget matrix covers immediate
and deferred decisions, rebuilds, capability loss, errors and cancellation.

Feedback follow-up: `test_flow.py` mounts the actual naming hook over a controlled
provider, checks two-turn triggering, late utility usage/checkpoint restore and a
manual rename racing generation. Do not treat `orchestrator:complete` as the app's
`prompt:complete` lifecycle. The latter must be emitted explicitly like app-cli.
The same test file holds a cooperative tool open: correction stays pending, Stop
interrupts it, and drafts survive. This does not certify uncooperative modules:
tool-search's synchronous subprocess/fallback work can block the host event loop.
`test_flow_terminal.py` checks actual painted dim thinking/user correction cells and
adjacent final usage at laptop/narrow widths. Completion is quiet Ready, not a visible
Completed banner. Run `experience_journey.py --live --feedback-only --executable
ABSOLUTE_DAILY_COMMAND --output NEW_PRIVATE_JSON` for two live turns per preset,
generated naming, attributed utility usage and resume without re-execution.
Naming can make the last provider request a utility call: request-policy assertions
must select conversation calls without disabling the hook or dropping its evidence.
Rebind transient observations on an in-app conversation switch and reject late source
callbacks; process restart alone cannot test that seam. Do not interrupt an integrated
gate with SIGINT: the runtime's handler can stop its current test turn instead of pytest.

Continuous work/accounting: `test_flow.py` exercises actual core/loop execution with
four concurrent children and synthetic provider usage, cache aliases, failed-attempt
then successful-request accounting, replay deduplication and partial/legacy totals.
`test_flow_terminal.py` drives inline expansion/collapse with real fixture runtime at
175×50, 40×20 and 32×12, native mouse return and draft retention. A labelled transport
fixture separately holds startup and a long stream for deterministic layout inspection.
Run `experience_journey.py --live --flow-only --executable ABSOLUTE_DAILY_COMMAND
--output NEW_PRIVATE_JSON` for both real presets: four parallel delegates, one recipe,
inline/recursive inspection, attributed usage and resume without execution.
Native history is immutable: only explicit interaction captures mouse input. Completed
observations behind an unfinished call stay in order; a completed replay backlog must
drain in bounded batches rather than being fully laid out on every frame. That backlog
must not hide fresh streaming output: render the unfinished suffix while replay drains.
Measure event-to-visible latency as well as typing; responsive edits alone missed this.
Each response observation has its own journal identity, not just an orchestrator iteration:
retries and parallel calls can share an iteration. Startup phases are transient wire state,
never writes beyond a checkpoint during a refused reopen. Child labels must not rely
on truncated IDs, whose prefixes may be identical. Preserve raw evidence independently.

Conversation-first Activity: `test_activity_tree.py` exercises the actual streaming
loop with two concurrent parent calls and nested children, plus unknown ancestry and
bounded public-thinking excerpts. A ContextVar set inside a Rust hook callback does
not return to the execution task: establish it at tool invocation using task-keyed
dispatch observation, and restore it in `finally`. Missing dispatch stays uncorrelated.
Preserve instance-bound execution guards: resolve a replacement class method only when
the wrapped method originally belonged to that class. The actual-runtime denial test
guards against silently bypassing an instance policy wrapper.
`test_activity_terminal.py` uses actual fixture runtime, mouse/keyboard drill-down at
175×50, 40×20 and 32×12, retained drafts and zero replay. Run real tmux tests serially.
The shared observer's `wait_idle()` requires a NEW idle transition after input; an old
Ready frame can otherwise make tests inspect unfinished attachments or quit mid-turn.
New/Resume do not execute turns: await their context identity, not a turn transition.
Provider adoption creates candidate files before initialization completes; wait for its
new identity on screen before asserting checkpoint contents, not the source's Ready footer.
Public-thinking Markdown and user/composer surfaces are projections, never source edits.
The live experience journey now also opens Activity during work and traverses actual
delegate/recipe ancestry after completion. No timing guesses or private-context reads.
Use `--activity-only` for the bounded one-root/two-child journey per preset; it does not
certify the full mode/question/queue journey. Build the release binary before PTY tests:
building only Cargo's debug target does not update the executable those tests launch.

Approachable-experience gates: `test_experience_terminal.py` covers eight grids from
32×12 through 240×65, with 175×50 the primary TOTAL viewport, and four explicit colour
treatments. Inspect the actual captures; a screenshot hash is not a usability score.
Keep terminal-default and NO_COLOR syntax plain without changing source/copy bytes.
PageDown detail steps must not exceed the visible detail height in a short menu.
The question matrix checks local choice after resize, scrollable review, retained main
draft and zero submitted answers. Initial light-theme paint must cover all owned live
rows, not just the composer. Real attached tmux tests remain the native-copy authority.

`scripts/experience_journey.py --live --executable ABSOLUTE_DAILY_COMMAND --output NEW_PRIVATE_JSON`
runs a bounded whole-workflow probe on both presets: actual delegation/v2 recipe,
mode approval, clarification, active correction, queued edit/pause/release, failed test,
source fix and new test result, information-work comparison, completed resume and child
interruption. It uses owned projects, never personal conversations/services. Eight root
and three child turns per preset on the intended path; 240 seconds per turn. Preserve
failed attempts and stop on unexpected policy decisions rather than auto-approving them.
The reusable `Journey` observer records input byte counts instead of input bodies;
observations and executable paths can still be sensitive, so step receipts remain private.
Wait for the specific prompt title to disappear after an acknowledged edit: the absence
of "Actions / choices" is not evidence that a separate edit prompt has closed. A normal
scrollback action may replace the status message after completion; assert final content
and Send availability, not a stale "Completed" label. Receipt counts remain independent.
Successful `experience_journey.py` and `cli_compat_probe.py` runs remove their temporary
private state by default; failures preserve it for diagnosis. Pass `--keep-artifacts` only
when the retained state is needed for a specific review.

Local mode commands do not create a model turn. The app exposes current module mode
as an ephemeral provider-request observation so historical mode results are not mistaken
for current policy. Test default after clear and named mode after activation through the
actual ordered provider messages across default → explore → default, not just substring
presence anywhere. Reminder deduplication can retain the original default observation
before a later Explore reminder; a successful transition advances the observation's
revision so returning to default is a new fact. Context modules may retain ephemeral reminders with metadata;
do not promise they are absent from the journal. The observation changes no permissions.
This app hook is a named request-policy difference in CLI comparisons.

The runtime benchmark includes native edit/menu/inspection/selection/return and tool-success paint, bootstrap
median intervals, and two Linux process-tree RSS snapshots including the host. Snapshots
are not peak/PSS; shared pages can be counted twice and detached/remote work is excluded.
Keep timing separate from builds, tests and provider runs; use 30 alternating pairs.
Prepared skills configuration includes absolute installed package paths: compare the
actual asset bytes before explaining that difference, without silently normalizing it.
The question tool and app-owned request guidance remain real differences. No speed-parity
claim follows from a favorable warm fixture measurement.
`scripts/benchmark_experience.py --samples 30 --output NEW_PRIVATE_JSON` separately
measures the simulated Decisions action and pending-dialog shrink/grow paint with draft
and request retained, never submitting a permission. Search the actual Decisions action;
Review decision is the normal view's button label, not that menu's search label.

Clean tool installs use `uv tool install --no-sources`: the pinned CLI dependency's
development `tool.uv.sources` follows Foundation main and conflicts with the app's exact
Foundation URL. Preserve the exact pin and resolve packaged metadata; do not float the
dependency or treat an already-populated development environment as install evidence.
Doctor's CLI-state description now distinguishes ordinary configured launches from
read-only diagnostics; check that boundary instead of the historical "not imported" label.
Candidate receipts fingerprint packaged sources and native source in dirty checkouts.
First isolated-state and resumed startup observations are not cold-cache benchmarks.

Local CLI controls: `test_cli_controls.py` uses actual core/Foundation/streaming-loop
mounts for goal caps, no-execution setup, durable restore, tool removal/remounting,
uncertain-state refusal, directory enforcement and structured CLI adoption. Do not
mistake Foundation `config_set` (a config dictionary mutation) for reconfiguration of
tools that cache policy in constructors. The root filesystem adapter updates both
supported write/edit instances and explicitly excludes bash/children from its scope.
Mode policy and local disabled tools must not silently re-enable one another.
Preset tests verify directory-policy restore and mode arguments/trailing prompts.
Authentication uses the actual ChatGPT provider wrapper with a synthetic OAuth exchange;
this is not real browser/account authorization. Verify cancellation before task startup,
no secret prompt in journal/context, no focus stealing, explicit prompt reopening and
clearing after Stop. Native captures live under `.evidence/interaction/cli-controls-*`.
`test_service_delivery.py` uses actual memory save/inject code with an explicitly owned
store (`timer=False`), plus actual intelligence fan-out and a loopback HTTP receiver.
It verifies authenticated transport, exclude-wins routing, local JSONL and HTTP 401
diagnostics. It never certifies personal services, installs timers or writes personal
memories. Receivers register in the workspace manifest and close in `finally`; run
these and PTY tests serially. Diagnostic inspection is bounded, root-session filtered,
and excludes raw URLs/error detail; absence of failures never proves remote delivery.
Optional filesystem/OAuth/memory/HTTP module cases require `TUI_TEST_PRESETS=1` and
the ecosystem dependency setup; the ordinary minimal fixture suite does not require
every optional service module. The all-enabled gate must run them without skips.
Typed mode completion is not a menu request: unsolicited completion must not reopen
the picker. Its final journal observation belongs inside the saved checkpoint sequence;
await context collection first, then emit and checkpoint synchronously before delivery.
Native exit/resume tests wait for the unique completion status, not historical mode text.
Exact slash-command names must precede fuzzy action matching: adding “filesystem”
otherwise steals `/system`. The functional launcher test covers that collision.
`cli_compat_probe.py --controls --live --output NEW_PRIVATE_PATH` adds local goal/config/
provider checks and read_file under an explicitly selected mode to both controlled
live presets, without extra model turns. It does not authorize real OAuth or personal
service probes. Keep failed and passing receipts distinct, and inspect final captures.

Everyday CLI workflow gates: `test_cli_workflow_gaps.py` covers bounded JSON/Python
literal envelopes, hostile/malformed/oversized refusal, actual root/child tool execution,
cached skill aliases and turn-end catalog refresh. Original tool evidence stays intact;
an ambiguous string is unknown, never success inferred from prose. Both preset recipe
tests distinguish active sessions from local filenames and verify app-owned ephemeral
discovery guidance reaches the actual provider request. This guidance is a named CLI
policy difference, not a kernel change or proof of equivalent requests.
Native `test_compact_terminal.py` disables cursor replies through F3, resize, F1 and F4;
it also checks skill insertion versus Send, stale-session catalogs and sticky startup
failure after Enter/late draft refusal. Ratatui `Terminal::clear()` (not its constructor)
queries the cursor even on an owned alternate screen. Clear that owned screen directly;
keep the separate bounded primary-screen resize strategy. Silent startup alone does
not test the inspection transition. The configured `cli_compat_probe.py --live` now
bills four read-only turns across both presets, including an actual discovered skill's
arguments. It also selects a recipe filename without sending or running it. Use a new
receipt filename; earlier receipts describe earlier code. Inspect the captures.

rc5 gates: `test_rc5.py` uses real nested session mounts, validates cyclic/missing
ancestry refusal and preserves original child/ancestor receipts. Nested adoption is
explicit reparenting under a new identity, not resumed ancestor execution. Actual
pytest JUnit reports retain report hashes and case counts; unchanged, invalid,
symlink/outside or shell-ambiguous reports never claim fresh test evidence. Reports
remain bounded workspace snapshots, not semantic coverage or exclusive attribution.
`test_ecosystem_workflows.py` now removes progress fields only from its own generated
recipe state and verifies the real runner refuses unsafe resume without repeating the
completed write. Native gates test Stop-and-draft confirmation/cancel and pasted-draft
persistence before ordinary debounce, with no submission. Inspect the captures.
After integration, `lifecycle_probe.py --live --adopt-persistent --nested --output PATH`
exercises a real intermediate parent, Stop/exit during the nested question, and new-root
adoption through native menus; it verifies both original receipts remain byte-identical.
Its isolated overlay explicitly clears delegate's child-tool exclusion. Foundation's
default intentionally excludes delegation from children; do not silently change that
product policy or mistake an unavailable child tool for a recovery failure.
Foundation list overlays concatenate: an empty exclusion list does not clear the
preset's list. This controlled probe uses the delegate module's falsy-null behavior;
it is not a general configuration-replacement contract.
The runtime may wrap nested cancellation as an ancestor execution failure. Require
the selected child to be interrupted and every ancestor to be interrupted/failed;
retain each observed status rather than relabelling the whole tree as interrupted.

The runtime benchmark requires `--output NEW_PRIVATE_PATH --policy-comparison RECEIPT`;
`--native-only` omits historical OpenTUI and `--pairs 30` is the full run. Run it alone,
after preparing the isolated CLI baseline. The terminal probe's historical
`alternate_screen` flag also chooses Ctrl-Q (native) versus Ctrl-D (CLI); it does not
force native alternate-screen startup. Do not switch that flag merely because the
native client now uses inline history. Keep failed diagnostic receipts distinct.
Release receipts now include source commit and tracked-source cleanliness; match them
to the tested revision and actual CI run before publishing candidate wheels.

Post-rc4 gates: `test_post_rc4.py` exercises replayed source-version provenance,
bounded model metadata, named environment references and Linux clipboard fallback.
`test_child_recovery.py` covers both legacy and current receipts with simple/persistent
contexts, same/historical roots, and altered-policy refusal. Native correction reuse
requires an empty idle composer, separate confirmation and zero new turn admissions.
Inspect both correction/model-limit captures. After the full suite, run
`scripts/lifecycle_probe.py --live --adopt-persistent --legacy-receipt --output PATH`:
it changes only its freshly generated test receipt to the legacy shape, never a user's
record, then verifies source preservation after native adoption in both presets.
Clipboard acquisition has one total three-second deadline, preserves source bytes,
and rejects a successful utility response whose format disagrees with the requested MIME.
Utility fixtures are not physical desktop or SSH clipboard proof. Provider setup must
reject non-YAML suffixes before writing; valid JSON content alone is not a loadable filename.
`compare_runtime_policy.py` exits 1 for differing prepared fields, 2 for invalid evidence;
even exit 0 does not prove request-time, credential or latency equivalence.

rc4 gates: persistent direct-child public adoption runs in `test_child_recovery.py`
with `TUI_TEST_SWAPS=1`, both same-root and historical-root paths. Preserve original
receipt and module transcript bytes; a new store must read back imported messages
exactly before execution. A module's existing-file restore policy is never bypassed.
After the integrated gate, `scripts/lifecycle_probe.py --live --adopt-persistent`
exercises the actual recovered-work menu and confirmation with both live presets.
It bills two additional child turns. Generated overlays need a recognized YAML suffix;
successful serialization alone does not establish that Foundation can load the file.
`test_change_evidence.py` links exact unchanged versions to earlier agent observations,
refuses changed versions, and retains unresolved pre-tool evidence once. Context-policy
tests distinguish configuration rows from actual usage/compaction observations; native
inspection opens the detail without sending its retained draft. Native detail checks
wait for the new menu title before asserting detail: the same text may already
be visible in the preceding selection preview. Unique table-cell resize
matching is approximate; repeated/ambiguous cells must fall back rather than guess.
`capture_runtime_policy.py` runs under the respective isolated CLI/TUI interpreter with
a fresh `--state` directory. Keep its receipts private: hashes and module IDs are not
anonymous diagnostic exports. Prepared-policy agreement alone never proves matching
runtime requests or CLI latency. Do not disable policy to obtain a favorable number.

AFK continuation: run `test_owned_execution.py`, `test_child_recovery.py`,
`test_change_evidence.py`, `test_context_transfer.py` and the expanded independent-swap
approval matrix. New native navigation cases cover provider-fork confirmation and
continuous typing autosave. Full-suite evidence precedes billed lifecycle probes.
`benchmark_history.py --terminal` now measures complete catalog/search/checkpoint-page
work and actual native Resume paint separately; neither is matched-policy CLI proof.
`release_wheel.py --output-dir PATH --terminal` keeps experimental wheels apart from
published-version artifacts. `--ci-clipboard` mutates only a disposable macOS GitHub
runner's pasteboard, tests the installed adapter against real PNG bytes, then clears it;
it refuses personal-desktop invocation. Ubuntu 22.04 is a separate CI gate, not musl proof.

Cancellation lesson: cancelling a Rust-backed execution wait immediately can outrun
Python callback scheduling. Own the wait and give the public cancellation token bounded
grace; drain ownership through repeated cancellation without suppressing warnings. This
does not impose a hard deadline on arbitrary cleanup: the native process-group deadline
remains separate. A cooperatively returned cancelled outcome is still interrupted work.
Draft lesson: debounce from the first pending edit, not the latest keystroke, or continuous
typing indefinitely postpones persistence. Terminal assertions must account for wrapped
disclosure text rather than waiting for a substring split across two physical rows.

September continuation gates: `test_conflict_review.py` uses real unmerged indexes to
test capture versus Apply, original backups, unchanged index/mode, stale content,
symlink/hard-link refusal, backup failure and a write injected after backup. Enable
native candidates for the actual proposal/confirmation/composer path; inspect its
capture and assert the proposed text is visible, not only the Apply label. External
writers remain outside a transactional lock. Never retry an ambiguous replacement.
`test_lifecycle.py` gates repeated child cancellation during context capture and cleanup;
ownership survives until the interrupted receipt is saved. Callback warnings are a
separate runtime seam, never suppressed by these tests. `test_recovery_inputs.py` covers
real interrupted-child historical recovery, original receipt preservation, no execution,
unavailable/foreign/oversized child evidence, static GIF/WebP bytes and animation refusal.
The macOS PNG clipboard parser is simulated locally; do not label it desktop verification.
Run `scripts/backlog_probe.py --live --format gif` and `--format webp` with distinct
receipt paths after the integrated suite. Each bills two controlled, tool-free turns.

`scripts/release_wheel.py --terminal` adds installed real-PTY fixture execution, Help
without submission, clean termios restoration, resume without replay and a second turn.
The observer requires pyte; run through `uv run --no-project --with pyte==0.8.2 python`.
CI requests this gate on each wheel platform. An unrun/failed job is not coverage; this
does not verify real desktops, tmux, clipboard acquisition or billed live providers.

macOS observer lesson: the first rc3 CI run reached exit but failed a post-exit slave
`tcgetattr` with ENOTTY. Darwin revokes the controlling terminal when its session leader
exits ([XNU exit implementation](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_exit.c)).
The installed gate now retains a controlling-session guard to compare the actual modes
before that revocation. It never repairs them and propagates nonzero app exits.
`test_terminal_guard.py` proves clean restoration, deliberate raw-mode leakage and
nonzero-exit handling. Default Linux performance probes keep their original topology;
do not substitute guard timings for historical renderer measurements.

Read AGENTS.md, current contracts, notes/PLAN.md and notes/ACCEPTANCE.md when entering verification. Do not use live
credentials in deterministic tests. Run from the project directory after README setup.

```sh
uv run --no-sync python scripts/check_direction.py
PYTHONDONTWRITEBYTECODE=1 uv run --no-sync pytest -q
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv build
```

The direction check validates shape, local links, language-independent source ceilings
and work-to-promise references. Its negative fixtures exercise failures too; it is not
a behavioral Converge ledger. If the private method archive is available, add `--archive`
as documented in [Converge practice](notes/CONVERGE.md). Verify distributions omit ZIPs.
Changes limited to direction/check tooling do not require new billed provider runs;
execution-path changes still owe the relevant live and integration evidence below.

Lifecycle ownership: `tests/test_lifecycle.py` gates real checkpoint/startup/cleanup awaits.
Exercise Stop twice, Stop then exit, cancellation of close waiters, natural completion while
saving, concurrent close, and cleanup failure. Assert one outcome/cleanup and no new execution.
Do not rely on sleeps to hit these races, suppress callback warnings, or call cleanup finished
while its handle is still live. Track startup separately so closing an opening host cannot
return early or wait recursively on itself. After the full suite, run
`PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python scripts/lifecycle_probe.py --live` serially:
four billed root/two child turns across both presets, completed read/resume without replay,
then Stop immediately followed by exit during a child question. Inspect private captures;
verify stopped questions, one interrupted parent/child and an uncertain checkpoint.
Mode changes also use the host's task slot: reset its finalization state for a new mode
operation and protect that operation's checkpoint. The actual-preset regressions in
`tests/test_ecosystem_workflows.py` catch stale state inherited from a completed turn.
Immediate close after submit must make zero calls into session execution, not merely
end with an interrupted status. Apply Stop before handing off to the cleanup task;
otherwise the scheduler can enter the runtime during that handoff. Keep the explicit
call counter in `test_close_before_first_execution_step_cleans_up`.

Direct Codex adoption gate: build Ratatui, then run `TUI_TEST_CANDIDATES=1` with
`tests/test_compact_terminal.py`, `tests/test_tmux_scrollback.py` and the complete native
suite. Verify a fresh primary-screen page, bottom-aligned five-row ordinary idle chrome plus an empty cursor-anchor separator,
growing/wrapped drafts, narrow controls,
visual-row history boundaries, delayed readiness preserving selection, zero implicit
submissions, and startup without any CPR request/reply, retaining typed input. Resize
queries have a 100 ms Unix deadline and replay all captured bytes through the pinned
Crossterm fork; a silent responder disables later probes. Real tmux resize must keep
both SHELL-BEFORE and each transcript marker exactly once. Inspect private `compact-*`
captures alongside actual live-preset ready/completed views. Corrupt local recovery
storage must prevent startup draft overwrite; `test_daily_replacement.py` verifies this.
Run native PTY/tmux probes serially: they share manifest bookkeeping.

Continuation gates: `tests/test_file_references.py` covers source hashes, inclusive LF
line ranges, UTF-8/CRLF, no symlink traversal, deleted-source queue dispatch, text-only
providers and atomic mixed-set admission. `tests/test_request_diagnostics.py` checks
explicit one-shot consent, bounded projection, missing provider exposure, child/probe
scope, clear and no raw host-journal writes. `tests/test_backlog_terminal.py` adds the
actual reference dialog, source-scoped dialog copies, persistent diagnostic status and
a host that deliberately never reads its pipe. The native client must remain escapable,
restore the terminal, report forced/uncertain cleanup and terminate its inherited group.
Do not use a blocking stdin write before starting an exit timeout, or call detached and
remote work reaped. Acknowledgement text can be immediately replaced by Ready: query and
show the diagnostic's real waiting/captured state, not a transient success toast.

After building/testing, run `PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python
scripts/continuation_probe.py --live --allow-private-provider-raw` serially. It makes two
billed turns across both presets with a deliberately explicit raw-provider test overlay
in private state. Queue a file/line reference, delete its source, reopen without composition
overrides, then explicitly Run; check the exact captured source digest/location/content,
controlled reply, no tool calls and no extra diagnostic turn. The overlay authorizes
module-owned raw logging only for this isolated test; never publish its logs or captures.
Inspect private `continuation-*` screenshots and publish only the allowlisted receipt.
The extra flag is not normal app behavior: diagnostics never enable provider logging.

Index regressions must include out-of-range SQLite integers, casefold-expanding text
before a match, and a measured read budget that includes source-prefix fingerprints.
The cache now uses a versioned first-record prefix of at most 4 KiB, charging those reads
to the refresh budget; old derived signatures trigger rebuilding, never journal changes.
Benchmark alone with `scripts/benchmark_history.py --output
notes/evidence/continuation-history-benchmark.json`; retain the original rc2 receipt.

Whole-backlog gates: `tests/test_backlog.py` exercises acquired-handle startup cleanup,
source observations, content paging, explicit uncertain-delivery resolution and immutable
image admission. `tests/test_backlog_terminal.py` exercises image/search controls,
non-submitting recipe review drafts and focus-preserving child-list refresh. With
`TUI_TEST_SWAPS=1`, persistent child storage/continuation is exercised with both independent
loops. With `TUI_TEST_PRESETS=1`, real v2 recipe failure/reopen/resume must skip the completed
step and retry only the explicitly requested unfinished work on both presets.

`PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python scripts/backlog_probe.py --live` makes
two billed controlled-image turns through both presets; compare exact canonical image bytes,
colour identification, zero tool calls, source inspection and private native captures.
Never use a fixture's image transport as proof of real vision capability.
`scripts/approachability_probe.py --live` adds two billed image-set turns and two confirmed
standalone provider probes across both presets. Queue two captured images, replace their
source files, close/reopen, then explicitly Run. Check exact canonical bytes, no implicit
replay, colour identification, retained draft, and unchanged checkpoint after context/probe
inspection. Resume must restore recorded cwd, never combine it with a cwd override.
`scripts/benchmark_history.py` measures synthetic incremental indexing and warm search;
keep its catalog/UI/model/CLI exclusions visible beside any reported timings.
Initial startup, not only conversation switching, must withhold advertised Ready while
directory-history loading still rejects Submit. On failed startup, release that history
guard so the actual startup failure remains visible instead of a permanent loading message.
`PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python scripts/release_wheel.py` verifies an
isolated compiler-free wheel install. `.github/workflows/release-wheels.yml` is manual,
produces private candidate artifacts and does not publish a release; unrun platforms stay unverified.
Release builds remap home/Cargo/project paths in Rust. Scan every decompressed wheel member,
including the executable, and the receipt before upload; build/install logs are withheld.
The workflow uploads only the current verified wheel and receipt. A prior wheel carried
build-home paths despite source-level checks passing: source-only scanning is insufficient.
The per-repo-conventions fresh-context review found this before publication; retain the
regression guard and independently inspect newly introduced artifact formats.
Wheel platform tags must describe the embedded executable, not Python's build tag.
A universal2 Python on macOS produced a falsely universal wheel containing a single
Rust architecture. Set an explicit macOS deployment floor and architecture, verify
the binary with `lipo`, and check both filename and installed executable in the release
gate. Same-machine installation alone cannot falsify a universal2 mislabel. See the
[packaging tag specification](https://packaging.python.org/en/latest/specifications/platform-compatibility-tags/).
Delayed history recall must not expose Ready before conversation switching accepts input;
the explicit delayed-switch native regression covers that lifecycle window.
The benchmark measures the first editable composer separately from scene readiness;
do not wait for Send, which is intentionally disabled during real startup. Its editor
observer recognizes open input and historical border styles and joins wrapped visual rows; test it with
`tests/test_benchmark_observer.py` rather than matching tokens in transcript output.

The suite uses actual bundle preparation, the released Rust-backed core, upstream
streaming orchestrator/context, independent fixture modules, Textual Pilot and Linux
PTY subprocesses. It does not replace the runtime with a mocked successful engine.
The non-completion test deliberately replaces one orchestrator's execute method to
exercise an unknown lifecycle signal; that is not a second-orchestrator conformance run.

## Live read-only action

Installed-product gate: `uv build` must produce a platform-specific wheel containing
`amplifier_tui/_bin/amplifier-ratatui` and an sdist with Cargo sources/lock/build hook.
Install into isolated `UV_TOOL_DIR` and `UV_TOOL_BIN_DIR` paths under `.state`, never
replace the steward's installed CLI. Run the installed `amplifier-tui --doctor`, then
`scripts/install_probe.py --executable /absolute/path/to/isolated/bin/amplifier-tui`.
It uses a working directory outside the source checkout, no source map, real module
downloads/installation, tool execution, the question overlay and explicit resume.
Repeat with `--live --output notes/evidence/installed-live.json` for both actual presets;
four root/two child turns are billed. Finally repeat installation from the private Git URL,
not only a local wheel, before claiming Git-installable delivery. Publication excludes
private session state, raw transcripts and the earlier git-demo branch/marker/report.
Record final source revision separately from the package version and runtime evidence.
`tests/test_installation.py` verifies remote/package configuration, credential-free local
diagnostics, tool-outcome independence and bounded source delivery. Burst the source without
a consumer: journal every observation, cap count/bytes, stop admission, retain an uncertain
checkpoint and never execute the queued initial task. Test byte-budget release on consumption.

For the structured-question/workspace wave, build Ratatui and run the native regression
suite with `TUI_TEST_CANDIDATES=1`. The actual-loop question tests cover explicit review,
stale identities, pre-tool policy denial, limits, timeout/Stop, persistence failure and
canonical resume. Temporary real Git repositories cover staged/unstaged/untracked,
unborn HEAD, nested cwd, literal/non-UTF-8 paths, binary/large diffs, helper suppression,
cancellation/reaping, unchanged index and no model/context work. Native tests exercise
choice/free text, dismissal, main-draft retention, question history and diff copy.

After tests/builds, `PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python scripts/questions_probe.py --live`
executes four billed turns across both presets: question answers and tool-free recall
after resume, plus local Git inspection without execution. Inspect its private captures.
Run benchmark separately, with no concurrent build/tests/provider activity; include the
new Rust modules in source fingerprints. This does not measure control fsync latency.

After `bootstrap_sources.py --workspace .. --all`, supply the provider credential and run:

```sh
PYTHONDONTWRITEBYTECODE=1 uv run --no-sync amplifier-tui --bundle ../amplifier-foundation/bundles/anchors --overlay examples/anthropic.yaml --sources ../tui-sources.json --require-tool read_file --headless 'Use read_file to read pyproject.toml. Report only the project name. Do not edit files, run commands, delegate, or use any other tool.'
```

Repeat for `anchors-amp-dev`. Check session.ready, a read_file result with success true,
text.delta followed by text.final for the same block identity, and completed turn. Verify
the reported hook handlers and no initialization warnings; a response alone is insufficient.
The prompt constrains this action, not the preset's permissions. Do not mistake it for a sandbox.

## Interactive checks

Code colour: run Rust tests both with `env -u NO_COLOR cargo test --release --locked
--manifest-path frontends/ratatui/Cargo.toml` and with `NO_COLOR=1`, then the native
structured-reading tests. Assert actual token foreground variation, exact clipboard
content, multiline lexical state, unknown-language/size fallback, narrow resize and
unchanged draft. Inspect `syntax-native-*` and `syntax-inspection-*` captures.
`structured_reading_probe.py --live --output notes/evidence/syntax-live.json` checks both
real presets. The renderer benchmark also records a separate 240-edit syntax stress case
with six grammars and 100 native code blocks; this is not provider latency or CLI parity.
For editor growth, exercise a narrow inspection frame before returning to a fitting
multiline composer; assert all lines, cursor, selection and undo, not only the last line.

Development command: `scripts/dev-launch` may be symlinked onto the person's PATH by
explicit request. Test diagnostic invocations without Cargo, build failure without stale
launch, argument/cwd forwarding and a real fixture turn through the resolved symlink.
Resolve that PATH command outside `uv run`: uv prepends the editable environment's own
console entrypoint, which is a different launcher. Record the external link for teardown;
never replace an existing command or use real user state for the smoke test.

Newcomer guidance: run `test_onboarding.py` and `test_onboarding_terminal.py` with the
native candidate enabled. Verify missing key/binary/cwd/state errors, no state writes or
runtime imports, custom-provider uncertainty, path-free allowlisted support output, and
non-executable doctor exit codes. Native help must preserve Unicode drafts, allow reading
the final paragraph at 40/160 columns and add zero submissions before an explicit send.
Inspect `onboarding-help-*` captures; a title-only assertion misses unreadable instructions.
Repeat guide/check/support commands and fixture execution from the installed wheel outside
the checkout. Full regression and isolated renderer timing still apply after native edits.

Daily replacement adds `test_daily_replacement.py` and `test_daily_terminal.py`: real child
execution/observations, waiting scope, completed direct-child restart, incompatible/uncertain
receipt rejection, isolated local draft recovery, bounded UTF-8 snapshots, symlink refusal,
and keyboard-only native inspection/external-editor success and failure. The editor test
asserts zero submitted turns; recovery checks original bytes and zero answer delivery.
Use `daily_probe.py` with an explicit live credential after the full suite: four billed root
and four child turns across both presets, including restart/explicit child memory recall.
Inspect `daily-*` captures; its receipt fingerprints host and renderer source. Run PTY owners
serially and the benchmark separately. No inferred Git authorship or exact context meter.
Keep action-search labels unambiguous: a new description containing "Decisions" can shadow
the ordinary decision action. Test old keyboard paths as well as new menus. Inspect evidence
must get enough vertical room for its source, and assertions must tolerate visual wrapping.
Wait for a dialog's closing frame before sending another function key: a stale Search label
can satisfy the next wait, while adjacent Escape sequences can be parsed as literal suffixes.
Child restart must permit exactly inherited parent orchestrator settings (the stock delegate
passes them), without treating arbitrary overrides as reconstructible routing.

Independent swap gate: add `amplifier-module-loop-basic` and
`amplifier-module-context-persistent` as workspace submodules, then install only into this
app's environment with `uv pip install --no-deps -e ../amplifier-module-loop-basic -e
../amplifier-module-context-persistent`. Run `TUI_TEST_SWAPS=1 PYTHONDONTWRITEBYTECODE=1
uv run --no-sync pytest -q tests/test_independent_swaps.py`. Four loop/context combinations
execute a real fixture-tool round trip, completed resume with zero provider calls, and an
explicit second turn. Tests explicitly set the persistent module's transcript path under
temporary storage: its default would use the shared Amplifier home. They characterize its
refusal to replace loaded history and verify host rejection of a mismatching module-owned
transcript. This is not all-module policy, child-persistent-context or arbitrary migration proof.
The simple module restamps internal `metadata._seq`; comparison allows only that difference,
not changed canonical content, tool identities or other metadata. Read source, not only the
persistent module README: the pinned implementation also appends messages to its own file.

Native terminal correction: `test_tmux_scrollback.py` must exercise the DEFAULT view,
not first open `/scrollback`. It checks real attached tmux selection across pages,
short Unicode replies in full-pane capture previews, inspection return, repeated
narrow/wide resizes and transcript retained after exit. Capture all history and count
markers: a still-visible footer or duplicate reply is a failure, not proof of retention.
Never clear history to repair a redraw. tmux can expose old rows on growth without moving
its reported cursor. The observer models DEC 1049 save/restore; real tmux remains the gate.
Locate the composer by its Message heading, not old border glyphs. Prior-conversation terminal
text is expected after New/Resume; assert model-context isolation from checkpoints.
The ordinary view leaves the mouse to terminal selection; injected mouse test sequences
prove action routing, not that default native view captures physical clicks.
Use `interaction_probe.py --output notes/evidence/inline-fixture.json`, then
`interaction_probe.py --live --output notes/evidence/inline-live-current.json` for this
wave's keyboard-only controls (four billed read-only turns across both presets).
Inspect `*-inline.png` as well as the decision/detail captures. Run
`benchmark_candidates.py --output notes/evidence/inline-benchmark.json` alone afterward.
The 100,000-item case must also pass cleanup, not just edit latency: initial replay
is disclosed and limited to 1,000 historical items, while full source remains inspectable.
Do not issue a new cursor-position query during unchanged-size menu/quit cleanup.
If inspection was resized, query the restored primary anchor before clearing, rather
than subtracting its old viewport height and erasing short replies. Exit observers must
keep servicing terminal queries; the existing finite resize fallback still applies.
Leave alternate screen only when owned;
redundant DEC 1049 restore can reposition the cursor into retained text.
With full-height startup, clear owned rows with EL rather than ED from row zero: tmux
may otherwise archive provisional chrome. Resize observers must wait for the pane's
actual PTY TIOCGWINSZ, not only tmux capture dimensions: grid resize can precede the ioctl
update. Wait for complete draft deletion before the next resize; a prefix match can
accept an unfinished synchronized frame. Test multiline tmux copy buffers, not only OSC52.

Everyday navigation adds `tests/test_input_history.py`, `test_everyday_terminal.py` and
`test_tmux_scrollback.py`. The last creates an isolated tmux socket/server, records it
in the workspace manifest, attaches through a PTY, copies old primary-screen history
across pages in real copy mode, verifies draft retention and reaps both resources.
Never run it concurrently with other PTY owners (manifest writes are not locked).
Capture-pane alone is not evidence of the attached copy-mode screen on tmux 3.4.
The suite also exercises bare startup-picker cancellation without state writes, cwd
recall without context import, delayed-history/draft isolation, drag wheel/edge scrolling,
visible Pending/Steer buttons and restored mode badges. Reflow assertions wait for the
new width before issuing navigation; Escape tests wait for dismissal before typing.

After the full native/preset suite and build, run
`PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python scripts/everyday_probe.py --live`.
It bills four read-only turns across both presets, checking identified steering,
queued recall, plan badge through new/resume and a native-view round trip with no extra
turn. Inspect `everyday-*` captures. Then run the benchmark alone:
`uv run --no-sync python scripts/benchmark_candidates.py --output notes/evidence/everyday-benchmark.json`.
Scene timing does not measure history-directory I/O, snapshot entry cost or matched CLI
latency. Preserve independently staged tests when reporting unrelated lint failures.

The structured-reading wave adds Rust table/code/hunk cases and
`tests/test_structured_reading_terminal.py`: actual fixture tool round trip, wide/narrow
tables, Unicode code-content copy, unchanged draft, completed resume, bounded catalog
and oversized-copy refusal. A labelled simulated source update tests that an open code
snapshot stays fixed until catalog refresh. Temporary real Git tests change the file
after observation and verify hunk navigation/copy stays with the original diff.

After tests/builds, run `PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python scripts/structured_reading_probe.py --live`
for two billed read-only turns across both presets: read_file, an actual Markdown table,
and code copy with no extra execution. Inspect `structured-*` private captures. Then run
`benchmark_candidates.py --output notes/evidence/structured-reading-benchmark.json`
separately; its scene timing is not a measurement of large-catalog discovery or Git I/O.

The runtime-control wave adds `tests/test_runtime_controls.py` and
`tests/test_controls_terminal.py`: real-loop early/stale/bounded corrections, observed
insertion, final-stream continuation, stop/failure, replay isolation, actual alternate
provider selection, vendor guards, restored pins and fail-closed control storage.
Native tests exercise multiline corrections, late-editor rejection, provider confirmation,
selection history/copy and resume. A separate simulated lost-acknowledgement transport
tests dialog copy/dismiss; it is not runtime conformance. Inspect `controls-*` captures.

Four billed turns across both presets verify two mounted Anthropic models:

```sh
PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python scripts/controls_probe.py --live
```

Each Haiku turn reads a file and receives an identified active correction. After selecting
Sonnet and restarting, a tool-free turn must recall the correction, with the provider's
observed selection naming the restored pin. Assert actual mounted instance names and
insertion events—not only the chosen label or old transcript text. Receipt:
`notes/evidence/controls-live.json`. Timing uses
`benchmark_candidates.py --output notes/evidence/controls-benchmark.json`; older receipts
remain historical. Scene timing is not control-fsync or matched CLI latency evidence.

The workflow wave adds `tests/test_followups.py` and `tests/test_workflow_terminal.py`:
actual-kernel sequential queue release, pause/edit/remove, stop/failure, duplicate
admission, uncertain dispatch, restored queues and rename/context isolation. PTYs
exercise these controls during actual fixture approvals, modal rejection/cancellation,
local search and exact OSC52 copy. The bounded-search/Markdown case is a clearly
simulated projection probe, not engine conformance. Inspect private `workflow-queue`
and `workflow-search` captures before asking for UX feedback.

Four billed read-only turns verify live queued continuation and local organization:

```sh
PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python scripts/workflow_probe.py --live
```

Each preset reads one file, then a queued tool-free memory question checks canonical
continuity and admission after the prior outcome. Rename/search/copy add no turns.
The sanitized receipt is `notes/evidence/workflow-live.json`; raw state remains private.
Use `benchmark_candidates.py --output notes/evidence/workflow-benchmark.json` for this wave.

The navigation wave adds `tests/test_navigation.py` and `tests/test_navigation_terminal.py`:
actual-kernel new/return/context/draft isolation, failed and cancelled target preparation,
target cwd and completion scope, native picker/path controls and delayed-reply rejection.
Inspect the private `navigation-conversations` / `navigation-files` PTY captures; they
can contain temporary machine paths and must not be published blindly.

For live in-app switching (four billed read-only turns):

```sh
PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python scripts/navigation_probe.py --live
```

This creates both preset conversations, then switches between them inside Ratatui.
Each performs read_file and a context-memory turn; the second prompt does not include
the marker. The new answer, source draft and restored identity are checked separately.
The sanitized receipt is `notes/evidence/navigation-live.json`. Keep older receipts as
historical evidence; benchmark with `--output notes/evidence/navigation-benchmark.json`.

The reading/return wave adds `tests/test_reading_terminal.py` and
`tests/test_conversations.py`. They check Markdown styles, three-line wheel movement
inside one long reply, stable reading during streaming, resize, boundary history,
local completion, fresh-engine context restore, zero replay operations, private files,
single-writer locks and corrupt/uncertain/configuration-mismatched rejection.
The Markdown test captures an actual simulated terminal in `.evidence/interaction`.

For live return evidence (four billed turns across both presets):

```sh
PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python scripts/reading_probe.py --live
```

Each first turn reads pyproject.toml and receives a unique marker. The new engine's
next answer must recall that marker without it appearing in the second prompt. Assert
the **new answer in identified events**, not marker text still visible in old history.
The receipt contains assertions and source hashes, not private transcripts or markers.
Use `benchmark_candidates.py --output notes/evidence/reading-benchmark.json` to keep
the earlier historical timing receipt; source changes invalidate old measurements.

The current Ratatui interaction slice additionally owes:

```sh
PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python scripts/interaction_probe.py
```

This uses real Foundation/core with fixture provider/tool modules, two turns, module
approval, visible actions and exact evidence. It writes ignored terminal images and a
sanitized receipt. Tests include a keyboard-only workflow (Tab/arrows/Enter/Escape),
menu cancellation preserving selection, pasted menu text never executing, stale focused
decisions, actual runtime option scope and queued approval requests. OpenTUI retains its
older controls; do not claim a matched visual comparison after the Ratatui interaction wave.

With explicit provider credentials, this bills four live turns across both presets:

```sh
PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python scripts/interaction_probe.py --live
```

It verifies read_file and load_skill(list=true) through the real-work launcher using
ordinary controls. These operations are read-only requests, not a sandbox. Live capture
intermediates can include machine paths and remain ignored; do not publish them blindly.
The fixture decision capture must wait for the option-list frame, not question text already
visible in the underlying card. Renderer source changes invalidate earlier timing receipts.

The new candidates have real PTY gates, separate from the legacy Textual tests:

```sh
cargo build --release --locked --manifest-path frontends/ratatui/Cargo.toml
cargo test --release --locked --manifest-path frontends/ratatui/Cargo.toml
cargo clippy --release --locked --manifest-path frontends/ratatui/Cargo.toml -- -D warnings
bun test --cwd frontends/opentui
TUI_TEST_PRESETS=1 TUI_TEST_CANDIDATES=1 PYTHONDONTWRITEBYTECODE=1 uv run --no-sync pytest -q
PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python scripts/capture_candidates.py both
```

The capture script requires the workspace's terminal-tester submodule at
fde68aa883ff64b2ee1c94a4b6afa721443ddc55. It does not install an app bundle into the
user's CLI. Its local adapter preserves incremental UTF-8, numeric row order after
resize and hidden-cursor state; upstream source is unchanged. The low-overhead probe
answers cursor-position requests and measures parsed PTY output, not screenshot delay.
All spawned test process groups are recorded and reconciled in the workspace manifest.

Width regressions are checked in actual PTY output, not just layout arithmetic:
both engines launch at 160/200 columns, resize through 60/80/160/200 columns, and
retain the draft. Ratatui's ordinary and inspection composer starts at column zero and
wraps only after the final column; its transcript and tmux copy buffer have no outer gutter.
Test exact-width lines through resize/exit to catch last-column autowrap artifacts.
OpenTUI remains the historical inset comparator. A 120-column-only capture misses fixed-width
canvases. The engines started from one design; Ratatui now carries additional interaction work.

Run candidate timing independently from build/test workloads:

```sh
PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python scripts/benchmark_candidates.py
PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python scripts/benchmark_runtime.py
```

The second script requires isolated CLI setup, never the daily shared Python environment:

```sh
uv venv .state/cli-baseline-env
uv pip install --python .state/cli-baseline-env/bin/python ../amplifier-app-cli
AMPLIFIER_HOME="$PWD/.state/cli-baseline" .state/cli-baseline-env/bin/amplifier bundle add "file://$PWD/src/amplifier_tui/fixtures" --name tui-benchmark
AMPLIFIER_HOME="$PWD/.state/cli-baseline" .state/cli-baseline-env/bin/amplifier run --bundle tui-benchmark --provider fixture --mode single 'Compute a digest'
```

Only create the isolated environment if it does not already exist. Preserve the CLI's
foreign-home guard; never set its shared-venv bypass for these measurements. Its extra
composed policies and the fixture's model-discovery warning mean this is not yet a
policy-equivalent baseline. Read the measurement scope in notes/TERMINAL-REVIEW.md.
Raw samples and sanitized receipts live under notes/evidence; capture intermediates and
all runtime state stay ignored. Verify distributions omit state, caches, node_modules,
native build output and private archives.

With explicit provider credentials, the following bills two live read-only turns:

```sh
PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python scripts/smoke_live_candidates.py
```

It exercises Ratatui/anchors and OpenTUI/anchors-amp-dev. Ordinary pytest remains
credential-free. Confirm live tool success and completion, not just an answer string.

The following verifies the existing Textual reference harness, not the selected product UI.
New frontend candidates owe the real-terminal capture protocol in
[FRONTEND-EVALUATION](notes/FRONTEND-EVALUATION.md) and matched measurements in
[PERFORMANCE](notes/PERFORMANCE.md). No unrun visual/performance gate is a pass.

Start the fixture. Type during startup, submit once, type a multiline second draft
during streaming, resize, switch views and return. Confirm text and selection remain.
PTY tests exercise bracketed paste/Send, a completed turn, startup failure, normal quit,
alternate-screen exit, bracketed-paste disable and exact termios restoration.
Pilot covers correlated approval clicks and stale button identity; host tests cover stop
before execution, during a tool and during an approval. Windows/macOS and real IME remain untested.

## Lessons that own future checks

- Indexed search must find content before the old tail window and beyond page one.
  Exercise append, truncation, corrupt cache, malformed/oversized records and Unicode
  literal queries. Partial indexing is not “no matches.” Timestamp recall needs interleaved
  sessions, current-session replacement and arrivals during an active history browse.
- Media tests compare original provider-request bytes after source files change, queue
  admission, rejection and reopen. Preview pixels must serialize identically across disk;
  thumbnail tuples versus JSON lists caused a real regression. No fixture proves vision.
- Standalone provider probes require explicit confirmation, no conversation/tools, queue
  hold and redacted failures. Observe real native confirmation/result paths; text can wrap
  between terminal rows. Stored-context inspection must not build the next request.
- Historical import must preserve its source, validate the captured digest and make zero
  provider/tool calls before an explicit new submission. It is not cross-vendor canonical
  resume. Completed-child custom settings must be retained exactly, not replaced by the
  current parent's defaults. Interrupted/private-state reconstruction remains separate.

- Git installation must be exercised from the actual private URL, outside the checkout,
  with no sibling source map. A local editable install or successful wheel build is not
  that proof. Fingerprint the installed Python/native files, not just workspace sources.
- Review existing Git history before first publication: a user test-drive commit can hold
  private receipts even when the working tree looks like a new project. Preserve the local
  branch and file bytes; publish only the explicitly reviewed application snapshot.
- Bound source delivery before the transport queue. On overflow, keep journal-first
  observations, refuse new work and test connection shutdown while stdin remains open.
  Record-count bounds alone do not constrain a single huge serialized event.
- Session repairs: `TUI_TEST_PRESETS=1 TUI_TEST_CANDIDATES=1 uv run --no-sync pytest -q`
  includes actual delegate/v2 agent recipes, mode denial/approval/restore/child inheritance,
  native mode controls, drag-copy, direct questions at 40/160 columns and historical
  recovery with original-byte/no-execution assertions. Use PYTHONDONTWRITEBYTECODE=1.
- `uv run --no-sync python scripts/session_repairs_probe.py --live` bills six parent and
  four child turns across both actual presets: read-only delegation/v2 recipe, direct
  question answering, approved mode entry and native clear after restore. Run PTY owners
  serially. Inspect private captures; retain only sanitized assertion/hash receipts.
- Native control replies need conversation identity even when they are not journal
  events. Host-only tests miss replies silently discarded by the real client.
- Dependency-declared v2 recipes need their own execution test: legacy recipe success
  is insufficient. Dependency resolution can exceed a tiny fixture-tool timeout.
- Prepared bundle/module configuration can be mutated by mounts; clone it before
  initialization so later child composition and resume fingerprints remain stable.
- Mode activation can fail through an event rather than an exception. Test this signal;
  an active-mode label alone is not enforcement evidence. Native human mode choices
  are not assistant tool calls, or an assistant allowlist can trap the human in a mode.
- Recovery must include unfinalized assistant deltas and preserve the original byte for
  byte. A flattened historical fork is not faithful interrupted canonical-context resume.
- Delegate timeouts/cancellation may detach child tasks. The host must drain its owned
  children before checkpoint/journal close. Test Stop during a child's pending question,
  not only cancellation of a directly awaited fixture child.

- Named providers cross two public vocabularies: Foundation merges `id`, core mounts
  `instance_id`. Test root/overlay composition AND actual mounts; constructing a mount
  plan by hand misses collapse during composition. Recursive include authors need `id`.
- Steering admission is not insertion. Test first-request gating, exact turn identity,
  duplicate text/request IDs, foreign events, final-stream continuation and Stop/failure.
  This loop can continue after a final answer if a correction arrives during generation.
- Provider changes retain module guards and have their own interrupted-write tests.
  Resume must restore the selected instance before work; display alone is not proof.
- A lost modal acknowledgement must leave text copyable/dismissible without permitting
  an automatic resend. Test a transport that exits without the reply, not just rejection.

- Queue release waits for the execution task AND its checkpoint, not just a painted
  outcome event. Test Stop before execution starts, failure, duplicate admission,
  failed persistence and restoration; reopening is not permission to execute.
- Pending-item edit/remove validates identity and admission state in the host. A menu
  snapshot is not authority. Rejected edits retain their editor text until cancelled.
- Search bounds must remain visible while a result is selected; per-choice details
  must not hide partial-scan warnings. Copy source bytes, not rendered Markdown cells.

- Navigation needs failure/cancellation tests before and during preparation, not just
  successful snapshot replacement. Verify candidate locks are released and stale source
  requests cannot affect the newly selected conversation.
- Conversation switching isolates undo, selection and sent-history browsing state,
  not just the visible draft. Undo in a new conversation must not restore source text.
- Completion replies must match the request, conversation, draft and cursor. Test a
  deliberately delayed response after editing; do not infer this from fast local scans.
- Picker labels must remain identifiable at real terminal widths. Put compact titles/IDs
  in the list and full directory identity in selected details, not a clipped path dump.
- A transcript screenshot is not resume evidence: assert canonical messages in a fresh
  context module and count provider/tool calls before a new explicit submission.
- Scroll one long item, not just many short ones. Assert stable visible rows while an
  unrelated stream grows; item-count offsets can pass short-message-only probes.
- Empty/truncated/missing journal records must not turn a nonempty checkpoint into a
  valid empty conversation. Validate identity, sequence and checkpoint agreement.
- Persist absolute local bundle/overlay references; tool cwd is not launcher cwd.
- A returned assistant string is not completion evidence. Assert runtime outcome separately.
- Foundation's static module-export hints can be stale. Require actual tool names explicitly.
- Failure-tolerant core initialization needs host admission policy. A missing hook is not ready.
- The PyPI core version and inspected source HEAD can differ. Record both, including peeled tag SHA.
- UI click identity must include the original widget/request, not a reused button ID.
- Test cancellation before an asyncio task starts: otherwise its finally block may never run.
- Some upstream repos track bytecode. Use PYTHONDONTWRITEBYTECODE to avoid incidental source changes.
- A smoke-test UI is not a design review. Exercise it and inspect captures before asking a specific steward question.
- A framework or transport is a replaceable implementation choice. Measure its integrated cost before freezing it.
- Contract shape and work traceability can be checked locally; draft detail is not ratification or future-service integration.
- Choice selection is local, not submission. Exercise Esc/reopen with multiple answers,
  and show enough review detail to identify every answer; an invisible second answer is
  not a useful review step. Question arrival must not take the composer's focus.
- On resume, "Ready" can appear in old assistant text before modules initialize. Live
  probes must wait for the current status row, not a whole-screen substring match.
- Repeated copy probes must count new OSC52 observations; an old "Source copied" status
  can remain visible while a later copy is still being processed.
- Reflow must preserve the combination of line and span styles. Test both plain source
  equality and actual colours; a visible plus/minus sign alone does not verify diff colour.
- Narrowing a tail-following transcript can move an earlier table header offscreen.
  Scroll to that source before asserting its narrow layout; do not confuse viewport
  position with lost table content.
- Mounted tools and successful read_file turns do not prove everyday preset viability.
  Exercise delegate and an agent-bearing recipe through session.spawn before claiming
  that coverage. A completed parent turn may contain failed tools.
- Mode gates are not necessarily approval requests: inspect the gate policy and actual
  event. A warn-policy first denial can allow a retry; a later clarification answer
  must not be confused with granting tool permission. Test the whole user-facing path.
- Question-menu tests using known labels do not prove discoverability. Check the
  unanswered transcript card and narrow-width entry point without prior menu knowledge.
  Mouse capture plus ignored drag events is not usable transcript selection/copy.
- A read-only Git command can invoke repository-configured clean/process filters.
  Disable those before both status and diff; --no-ext-diff/--no-textconv alone is insufficient.
  Use literal pathspecs and preserve opaque source identities even for lossy filename display.
## Configured CLI compatibility gate

Use synthetic global/project/local settings, never the developer's configured service
destinations or personal transcripts. `tests/test_cli_compat.py` compares the actual
pinned CLI resolver, tests settings/identity/destination preservation, and verifies
unknown-command refusal and explicit source-preserving CLI import. With
`TUI_TEST_PRESETS=1`, both presets use real CLI default behaviors plus a controlled
configured behavior/provider and execute a shell tool and delegation.

After the integrated suite, run `scripts/cli_compat_probe.py --output NEW_RECEIPT`
serially, then `--live --output NEW_RECEIPT` (four billed read-only turns, explicitly
supplied Anthropic key). Inspect `.evidence/interaction/cli-compatible-*` captures.
The probe owns its home/workspace and exercises actual menus and command refusal;
never substitute personal configured hooks for this fixture. Interactive module login
and health of personal remote services remain unverified.

For current runtime diagnostics, `capture_runtime_policy.py --settings-policy cli`
captures the compatibility adapter and default question overlay. `--cli-home` may
select only an app-owned isolated baseline home; use its owning CLI environment.
`benchmark_runtime.py --native-only --cli-compatible` measures the actual configured
native entrypoint alongside that CLI after a strict private comparison receipt exists.
Prepared differences and missing request-time equivalence still prevent a parity claim.

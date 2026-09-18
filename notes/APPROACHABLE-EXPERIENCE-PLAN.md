# Approachable daily replacement — integrated execution plan

Planning record, 2026-09-16. Not implementation evidence or a Converge verdict.
Authority: [steward direction](DIRECTION-REVIEW.md); destination: [VISION](../docs/VISION.md).
[PLAN](PLAN.md) owns work identities and promise references. This note works those
promises into design choices, scenarios and gates; it does not create a second contract.

## Outcome and scope

Make Amplifier usable for information workers learning to build with AI: people who
can describe an outcome but should not need to understand orchestrators, terminal
key chords or session internals to direct work. Expert commands remain available.
Deliver one coherent experience across first launch, conversation, execution, decisions,
review and return, rather than another collection of disconnected features.

The primary reference is approximately **175 columns by 50 rows total**, including
composer and status; roughly 45 rows were visible above them in the steward's view.
That is a review reference, not a fixed transcript budget or a physical-pixel claim.
Mobile means a narrow terminal/SSH client, not a new native mobile application.

This request plans the complete wave. No behavior is changed by this document.
Implementation should complete the locally authorized work in sequence without asking
the steward to rediscover elementary defects. Reversible design choices below are
working defaults. Account authorization, personal-service mutation and publication
remain separately gated; those gates do not block independent local work.

## Current baseline and concrete observations

- The native Ratatui frontend already provides primary-screen history, borderless
  input, menus, retained drafts, queue/correction, decisions, resume and real ecosystem
  execution. Extend it; do not restart the framework comparison or rebuild those paths.
- Existing PTY probes send real input, resize and capture rendered grids. Attached
  tmux tests verify native history/copy/exit. Live probes exercise both presets.
  Coverage is substantial but fragmented; a sequence of short probes is not a
  sustained task or proof that a newcomer understands what happened.
- Inspected live captures show raw mode dictionaries, long usage lines, public thinking
  and serialized tool results competing with short answers. This is an observed
  presentation problem; do not suppress the underlying evidence or failure states.
- `Chrome::new` wraps an action list to width; many advanced actions share one broad
  menu. Width fitting alone is not hierarchy, understandable vocabulary or discovery.
- README combines current usage with long historical frontend/release instructions.
  Current login guidance also lags the scoped async login adapter. Consolidate current
  instructions and link historical records rather than teaching contradictory paths.
- Latest development evidence is 571 integrated passes and two live presets. It is
  regression evidence for that source, not acceptance of the experience proposed here.
  Matched-policy CLI latency, physical mobile behavior and personal-service health
  remain unestablished. Use [current validation](evidence/cli-controls-validation.md).

## Design decisions to carry through every surface

1. Conversation first; one persistent composer. Work is the ordinary surface, Review
   explains changes/results, System explains configuration. Do not add a permanent
   sidebar, dashboard or fixed-width centered canvas merely because a desktop is wide.
2. Plain task language. Prefer visible labels such as "Change current task", "Next
   tasks", "Conversations", "Changes" and "Details" over requiring people to learn
   steer/queue/session vocabulary. Preserve established slash commands as aliases;
   final wording follows the baseline walkthrough, not substring-menu implementation.
3. Keep useful content at column zero. No outer gutters, repeated prompt prefixes,
   decorative side borders or line numbers in ordinary copyable prose/code/input.
   Preserve meaningful source indentation, list markers and quoted content. Separate
   role/tool labels from content so users can select the content cleanly.
4. Use vertical rhythm rather than boxes: a deliberate blank row between speaker
   turns/activity groups, compact spacing within related operations, and a clear
   composer boundary. Do not put multiple blank rows around every tiny tool event.
5. Semantic styling: primary text, secondary metadata, focus, working, needs-attention,
   failed and interrupted/unknown. Pair every state colour with words or symbols.
   Use subtle background only where it clarifies input/focus/decisions; never pad
   copyable lines with decorative spaces. Inspect dark, light, limited-colour and
   NO_COLOR rendering. Avoid animations/blinking as the only sign of activity.
6. Progressive detail without lost meaning. Show operation, meaningful target and
   actual outcome first; full arguments/results, source identity and metadata remain
   inspectable/copyable. Failures, pending decisions and unknown outcomes never vanish
   into a generic "Done" or count that requires investigation to notice.
7. Native terminal ownership is non-negotiable. Ordinary mouse selection belongs to
   the terminal/tmux, not an app-wide mouse grab. Controls have ordinary keyboard paths;
   do not advertise normal-view labels as reliably mouse-clickable. App mouse behavior
   is confined to views that explicitly own it. Mobile must not require function keys.
8. Keep history honest. Committed terminal rows cannot be collapsed/reflowed in place
   without violating retention. Summarize before emission; open detail in inspection,
   and retain full source in the conversation store/export. No clearing history to
   make a screenshot tidy. Separate native selection from exact source-copy actions.

## Responsive and accessibility matrix

Proposed test sizes, not claims about particular physical devices:

| Grid (columns × rows) | Purpose | Layout expectation |
|---|---|---|
| 175 × 50 | Primary large-laptop reference | Full-width conversation; quiet compact footer; useful context around decisions |
| 120 × 35 and 80 × 24 | Smaller laptop and split pane | Secondary metadata moves to details; controls remain readable and reachable |
| 60 × 24 and 40 × 20 | Narrow/mobile-terminal proxies | Single-column menus; wrapped questions; no function-key dependency |
| 175 × 25 | Wide but short / virtual-keyboard proxy | Composer growth cannot crowd out waiting action or a usable content region |
| 240 × 65 | Large desktop | More work visible, not extra permanent chrome; no arbitrary transcript width cap |
| 32 × 12, then below minimum | Stress and degradation | Essential safe navigation/exit at supported minimum, explicit resize fallback below it; no panic/draft loss |

At the primary size, target about five to six idle live-region rows for a one-line
draft, including required cursor/separator bookkeeping. Count actual terminal rows.
Growing drafts, attachments and pending decisions may expand deliberately; preserve a
visible cursor and content area. Reuse the existing one-to-six input-row behavior
unless measurement justifies a change. Narrow views may use an overflow menu, never
silently clip an essential action or make a hidden focused action respond to Enter.
At the minimum, safe degradation is a separate result from comfortable usability.

Capture empty, short and long answers; multiline/large pasted drafts; Markdown tables;
wide code; Unicode/combining characters; long paths; running/failed tools; multiple
children; approvals; questions; queue/correction; menus; review; resume and startup
errors. Exercise resize while each owns focus, including an on-screen-keyboard-like
height shrink. Use pairwise coverage for secondary states and all sizes for core
typing, waiting, menu, copy and resize paths; record which combinations ran.
Pixel screenshots cannot prove physical font comfort, screen-reader support, OS
selection or an actual mobile keyboard. Report those as specific human/platform gaps.

## Integrated work packages

### EXPERIENCE-01 — Baseline and interactive journey harness

Extend existing `terminal_probe.py`, `interaction_probe.py` and live/lifecycle probes;
avoid building a second test framework. Provide a reusable session driver with
observe/send/paste/resize/capture operations and a resumable step journal. It must
support exploratory observation between actions as well as repeatable scripts.

Launch the resolved daily `amplifier-tui` command outside `uv run` (which changes PATH),
with explicit app-owned state/home/workspace and controlled destinations. Also test
the clean installed executable. Record actual executable, source/binary fingerprints,
terminal size, preset, theme and fixture/live classification. Never use personal
history or configuration as a fixture. Register/reap owned PTY/tmux/receiver resources.

Baseline captures come before edits. Assertions observe current state/request IDs,
not words that can remain in old transcript text. Reuse real runtime events/checkpoints
as a second oracle after UI actions; never mutate host state to bypass the interaction.
Retain failed runs separately and turn found bugs into focused regressions.
Before each live journey, record its provider/model, finite turn/time limits and
estimated spend; stop at the declared limits instead of retrying indefinitely.
Provider usage reports are observations, not an exact billing guarantee. Run PTY/tmux
owners serially while manifest updates remain unlocked.

### EXPERIENCE-02 — Shared layout, styling and native copying

Work principally in `chrome.rs`, `native.rs`, `main.rs`, `markdown.rs` and the existing
menu renderer. Establish shared spacing, state colour and width-priority rules before
restyling individual dialogs. Reuse existing theme machinery where available; avoid
scattering new colour literals. Verify explicit light/dark/terminal-default behavior
without an unbounded terminal query. Colour fallback must not change source content.

Test native multi-page selection, tmux copy buffers, multiline composer copying,
source-code copy, brackets/paste, exact-last-column wrapping, inspection return and
exit retention. Assert no added leading gutters or repeated decoration; meaningful
source whitespace stays intact. Terminal soft-wrap behavior and OSC52 restrictions
must be disclosed rather than promised away. Keep export as the clipboard-independent
fallback. Capture actual attached copy mode, not only tmux pane text.

### EXPERIENCE-03 — Readable conversation and activity

Give user requests, assistant answers, ongoing activity and outcomes distinct readable
rhythm. Replace ordinary raw mode/config/result dumps with bounded, source-backed
summaries. Known file/shell/delegation/recipe operations can have useful projections,
but unknown tools must retain a generic useful path with errors and exact evidence.

Show public progress/thinking concisely, with available detail rather than a wall of
text. Never invent hidden reasoning, progress percentages, service health, elapsed
completion estimates or costs. Keep reported usage available without repeating long
token/provider lines through every answer. Failure/unknown counts and their next
inspection action remain visible even when the model declares success. Separate
"Response finished" from "Tests passed" and from completion of the person's task.

### EXPERIENCE-04 — Composer and task-oriented navigation

Group Actions around writing/attachments, current work, conversations, review and
configuration/help. Search aliases across groups, prioritizing exact commands; preserve
cached/local discovery with no model/network request per keystroke. Keep familiar
commands compatible. Explain unavailable actions and provide the supported alternative.

Make Enter's current purpose visible: Send when idle, queue-next-task when running;
changing active work remains a distinct deliberate action. Expose queue pause, edit,
remove and release without vocabulary guessing. Preserve text/selection/attachments
through menus, history, completion, cancellation and startup. Show the multiline-input
path in local help and test supported terminal key encodings. Paste never submits.
No rename or regroup may silently change control authority or target identity.

### EXPERIENCE-05 — Decisions, waiting, interruption and errors

Audit one state vocabulary for starting, ready, working, waiting for permission,
waiting for an answer, queued/paused, stopping, interrupted, failed and disconnected.
Reflect observed runtime state, not optimistic acknowledgements. Pair a persistent
reason with the next useful action; do not use a disappearing toast for a blocker.

Questions and permissions are separate flows. Show who asks, what is affected, actual
options and consequences. Do not pre-submit suggested choices or turn free-text assent
into blanket permission. Multiple root/child requests retain identity and waiting
counts, never steal draft focus, and remain navigable at narrow sizes. Errors lead to
copy details, retry only where safe, setup help, recovery or exit as appropriate.
Test stale responses, repeated Stop, Stop/exit, late tool results, disappearing focused
controls and uncertain saves. No queued work starts merely because Stop was pressed.

### EXPERIENCE-06 — Complete daily-work journeys

Use disposable project repositories below the workspace; persistent project source
never goes at the workspace root. An example sustained task is building a small CSV
summary utility with sample data and tests. Use synthetic content and real tools.

1. Launch, find help, select/resume deliberately and submit the task through the composer.
2. Request delegated research and an agent-bearing recipe; observe actual child work
   and step results, not just authored definitions or an empty active-run catalog.
3. Handle a real clarification and a controlled approval using visible ordinary paths.
   Deterministic runtime fixtures provide reliable race points; live runs are distinct.
4. Edit a multiline draft while work streams; add a file reference; queue another task,
   edit/pause it, and separately apply an identified correction to the current task.
5. Observe file edits and a test failure, inspect exact evidence, then explicitly ask
   for a fix and check new test evidence against the observed source version.
6. Interrupt controlled work, inspect partial effects and retain pending input paused.
   Close/reopen; use supported completed resume or explicitly acknowledged recovery,
   as the state requires. Never weaken guards to make the journey convenient.
7. Explicitly continue, inspect changes, copy a code block and multi-page conversation,
   exit, and verify terminal history and usable shell remain. Count operations before
   and after replay; neither old tools nor decisions can execute on their own.

Run the full journey on both supported presets at 175×50, using independently observed
tool/checkpoint outcomes. Use narrower regression journeys for controls/copy/return.
Also do a realistic information-work task (compare synthetic documents and produce a
decision brief) so the design is not optimized only for code/test output. Reserve an
exploratory walkthrough with no expected-label script: ask at every stage "What is
happening? What can I do? What changed?" Automation cannot certify human comprehension.

### EXPERIENCE-07 — First use, setup and documentation

Make launch in a normal working directory explain setup or present a usable composer,
not implementation branding. Task examples remain local, dismissible and unsent.
Explain model/provider, active mode, scope and missing capabilities in user language;
technical identities remain inspectable. Authentication stays provider-owned and
transient; an unavailable login method gives an actionable external path.

Test missing credentials, unavailable provider/network, bad bundle, read-only state,
failed startup and incompatible resume. A failure must retain the draft and explain
the next step. Review first-conversation, migration and support docs with current
labels. Put current install/run instructions first and move historical walkthroughs
behind explicit links without deleting their evidence. Shareable diagnostics must
remain allowlisted and distinct from private detailed logs.

### EXPERIENCE-08 — Performance that earns the claim

Follow [the existing benchmark protocol](PERFORMANCE.md). First identify remaining
prepared-policy differences, including question-tool and skills configuration, then
compare resolved request instructions/tool schemas and enforcement. Intentional UI
differences must be documented, not hidden by dropping hooks or capabilities.

Separate default-product experience from a supported matched-work experiment. If
default policies cannot be made equivalent, show the differences and keep that result
non-equivalent; a diagnostic matched configuration is not proof of default parity.
Use at least 30 alternating pairs for startup/first-visible/tool turnaround/control
response, separate cold and warm conditions, and report median/p95 plus uncertainty.
Record native plus host resources, not only the renderer process.

Keep the existing 50 ms p95 local interaction target under streaming, decisions, large
history, syntax and resizing. Measure selection/inspection/menu responsiveness too.
Profile before optimizing; preserve policy and exact evidence. Run timing alone, not
during builds, suites, screenshots or live traffic. Do not promise provider latency.

### EXPERIENCE-09 — Actual services and authentication

Prepare a separate, explicit destination/account test procedure. Existing isolated
memory and HTTP tests remain mandatory. With authorization, use one clearly synthetic
memory marker and prove save, later-session retrieval and actual request injection;
use one intelligence marker and prove accepted delivery and subsequent queryability
at the intended service. Record correlation and time bounds; 200, mounted hooks and
absence of errors do not prove indexing. Respect configured exclusions.

Do not auto-open browser authorization or write personal stores during ordinary
verification. Identify supported deletion/cleanup before external marker creation;
if no safe cleanup exists, request that choice rather than creating hidden residue.
Record externally owned test resources in the manifest and retain cleanup outcomes.
Real login requires the account owner where appropriate; expired/cancelled login must
leave input usable and codes absent from transcript, captures and published receipts.

### EXPERIENCE-10 — Installed candidate and handoff

Build an identifiable candidate from the tested source; install in isolated tool/bin
directories and run outside the checkout without sibling source maps or a compiler
for supported wheels. Exercise new/resume, local help, real tool execution, menus,
copy/exit restoration and explicit version reporting. Preserve the steward's daily
launcher and existing installed CLI. Re-test the development link separately.

Reconcile exact source versus artifact fingerprints and platform evidence. Review the
publishable source and decompressed artifacts for privacy, including a fresh-context
review when required by repository conventions. No release asset replacement or push
is implied by this planning request. Stage a release proposal; publish only when
authorized. Do not claim physical platforms merely from an OS CI job.

## Execution order and architecture guardrails

Execute as one bounded wave, with intermediate verification rather than one giant
untested patch: **baseline → shared layout/state vocabulary → activity/composer/decision
flows → sustained journeys and fixes → clean install/docs → final performance and
acceptance packet**. Service procedure can be prepared independently, but actual
account/destination checks wait for their authority. Re-run affected paths after fixes.
No delegation is required or assumed by this plan.

Keep display changes in existing Rust presentation/navigation modules. If a missing
observation requires host work, use identified app-layer events/adapters in `host.py`,
`events.py`, `inspection.py`, `runtime_controls.py` or their existing owners. Modules
still own tool/provider/context/orchestrator/hook policy; no widget imports into them,
no kernel UI policy, no second recipe engine. Preserve old stored events and command
aliases; any format change needs explicit compatibility tests and no silent migration.

The project is at its 50-production-file ceiling. Consolidate responsibly within
existing owners; if a clean implementation needs a new domain or source budget, produce
the required split proposal rather than hiding code in scripts or weakening the guard.
Keep DRAFT contract state and stable promise identities. Do not use vision as a status
report. Preserve the dirty worktree and unrelated notes; no broad staging/reset/cleanup.

## Evidence and stopping rule

Each completed item records tested revision, exact invocation, viewport/theme, fixture
versus live mode, assertions, capture references, outcome and remaining limits in an
acceptance note. Private screenshots/transcripts remain ignored; sanitized receipts
are separately reviewed. Record visual observations as findings, not screenshot hashes
masquerading as a quality score. Compare before/after at identical sizes and workloads.

Completion requires:

- Full enabled Python/native/module-swap regression gates with optional cases actually
  enabled, lint/format/direction checks and relevant platform/install gates.
- Core responsive matrix passing with no lost drafts, hidden essential decisions,
  unintended sends, contaminated source copies or erased/duplicated native history.
- Developer-inspected captures for every named surface and both live primary journeys;
  meaningful runtime receipts independent of assistant success claims.
- Performance measured on final code, with a non-regression result only for genuinely
  comparable work. An unresolved comparison remains an explicit gap, not a green badge.
- No unresolved data-loss, consent, unintended-execution, terminal-corruption or basic
  journey blocker. Lesser visual findings are individually listed with their impact.
- Clean-install evidence and privacy-reviewed release readiness, with publication and
  account/service gaps separately identified; all owned test resources reconciled.

The final handoff asks only focused human questions: Is ordinary activity readable at
your 175×50 size? Are current-task versus next-task controls obvious? Does copy/selection
behave naturally in your physical laptop/mobile client? It includes the exact journey,
captures and known limits. Human comfort and deployed-service checks cannot be inferred
from automated passes. They are not an invitation for the steward to find basic defects.

Do not manufacture a fresh generic backlog when this wave ends. Report completed work,
concrete remaining blockers and the evidence needed to resolve them. Original-identity
CLI private-state resume, arbitrary global reconfiguration, a new mobile frontend and
a new terminal framework are outside this wave unless a demonstrated blocker earns
an explicit change of scope.

# Amplifier TUI — Vision (DRAFT)

The destination is written as though already true; promises live in contracts, evidence and sequencing in notes.
Direction changes here first, with dated evidence; work follows from the remaining gap.
The adopted method and its provenance are described in [Converge practice](../notes/CONVERGE.md).
## What Amplifier TUI is

Amplifier TUI replaces the Amplifier CLI experience with a polished terminal workspace, as responsive as its CLI. Existing CLI workflows and the host services required by ecosystem bundles remain available: administration and scripting reuse CLI policy, while interactive approvals, diagnostics, completion, goal safety and child execution belong to the terminal host. People can inspect the loaded configuration without invoking a model or exposing credential values; authored definitions remain distinct from running work. A mounted bundle is not a compatibility claim; unsupported transitions are explicit, never silently weakened. Domain-specific dashboards are not prerequisites for this compatibility.
It learns from Codex's proven interaction and terminal behavior while Amplifier's ecosystem owns execution.
Information workers learning to build with AI understand and influence work without terminal expertise; Work, Review and System share one conversation and composer.
Conversation has the space; routine machinery is quiet, the composer grows with the person's words, and startup immediately welcomes editing without implicit submission while named background phases remain visible. Streaming belongs to one continuous transcript, not a small holding area; parallel delegates retain distinct task labels and bubble up their observed current activity. Child tools, warnings and accounting belong to that delegate's expandable activity, with compact counts and cost visible on its summary, not a second conversation-wide telemetry stream. Full per-call evidence remains inspectable.
Light conversation text sits on near-black; submitted words and the composer share a charcoal surface with vertical breathing room, not role labels or side borders. Equivalent accessible themes preserve that hierarchy. The normal terminal opens a full-height, edge-to-edge workspace with no outer horizontal gutters; borderless bottom input keeps selections clean and implementation branding stays quiet. Tools and public thinking occupy single-line summaries. Read-only Activity opens stable, recursively inspectable work with exact parent-call attribution, previews and source evidence; missing observations stay unknown. Native terminal history remains immutable and selectable, while the live tail alone indicates ongoing work.
The default palette follows muxplex brand: near-black conversation, raised charcoal input, cool white words, muted secondary text, cyan interaction and amber attention. Observed running tools and named model/background waits carry a gentle brighter sweep without changing copyable text or committed history; human waits, reduced-motion and colour-free treatments remain static. Todo updates show reported completion, current work and remaining steps with an expandable checklist, never treating a successful invocation as task completion. Accessible themes preserve hierarchy; source-image previews retain their own colours.
The active turn shows wall-clock elapsed time, reported call count and explicitly labelled cumulative turn usage and turn/session costs, including delegated work. Repeated context read by separate calls counts as usage, never as current context size or unreported in-flight generation. Delegated work has short, stable task titles that lead with the job, not prompt boilerplate or inherited conversation history; agent identity, current activity and exact instructions remain distinct and inspectable without extra naming calls. Action-first tool rows emphasize the operation in cyan, keep targets and accounting secondary, and distinguish amber running/unknown states from red failures. Parent completion never colours a child's warning as success. Only the live state shimmers; bounded expanded command previews preserve source and exact tool identity, and active checklist tasks stand out from completed work.
Visible actions and contextual choices make the experience usable without memorizing shortcuts.
The conversation outlives screens and engines; returning offers a picker, search and input recall scoped to the resolved launch directory, not its parents or children. Resume never silently changes the workspace.
Follow-up work has a visible waiting place; stopping never starts another task behind the person.
Ctrl-C first requests a graceful stop through the session tree, letting current model/tool calls finish and delegates resolve upward; a second press while stopping requests immediate cancellation. Both stages stay open, preserve the draft and explain progress and escalation. Stopping and stopped states use the palette's distinct red negative-state accent, not ordinary amber work or cyan interaction; elapsed time continues through quiet draining until actual completion. Ctrl-C exits only after explicit confirmation defaulting to No. A drained interruption with validated state remains resumable; unverified shutdown requires explicit recovery with the original preserved.
Corrections distinguish being accepted from reaching active work; neither implies a new turn or interrupts a running tool. Stop names that separate cancellation intent.
Conversation provider choices have a visible scope and survive returning to the same work.
Questions invite deliberate answers without granting permission; workspace review distinguishes observations from attribution and explicit version-checked edits from inspection.
People can name, find and copy work across indexed saved conversations without involving a model; incomplete indexing remains visible. Configured ecosystem naming supplies useful automatic titles without replacing a person's explicit name.
The ordinary conversation accumulates native terminal history; selection and tmux scrolling need no special view.
Exiting leaves readable work behind; a compact live composer coexists with transcript-aware terminal previews.
Export and retained conversation state remain distinct from terminal rows and never execute history.
Waiting questions offer an answer where the question is shown, including at narrow widths.
Delegation and recipes expose child progress, waiting reasons, scoped evidence and explicit continuation limits, including explicitly process-isolated agents. A process boundary preserves approvals, questions, nested delegation and two-stage cancellation; lost workers never imply safely resumable state. Display retention never becomes an execution quota; capacity waits remain cancellable and nested work cannot deadlock behind its own ancestors. Module-owned self-delegation policy remains authoritative.
The current mode stays visible; mode changes retain module enforcement and returning restores their policy.
Interrupted work remains readable and can seed an explicitly acknowledged new conversation without replay. Supported recovery continues captured public context under a new identity; private-state gaps and unknown tool effects are explicit before adoption. Change and command evidence identifies its originating agent, tool and observed source versions without claiming exclusive authorship against concurrent writers.
Markdown and syntax-coloured code stay readable without changing copied source; chronological recall, immutable attachment sets, semantic file/line references and external editing preserve unsent intent. Referenced excerpts retain their source version and location through waiting work and return, without a hidden reread.
Bundles bring instructions, tools, providers and behaviors without owning the interface.
CLI-compatible work applies the person's layered settings, named providers, app behaviors and permissions through an explicit app policy; existing conversations never acquire a different policy silently. Configured memory, notifications and intelligence destinations retain their declared scope.
Ordinary activity explains commands, files, results, provider waits and attributed warnings without requiring an inspector. Each model call identifies its session/agent, actual model and observed routing, local time, duration, tokens/cache and cost; turn/session totals retain child contributions without double-counting. Routine qualifiers do not drown out useful facts; actual gaps stay explicit. Native selection is the default; an explicit interaction mode enables inline mouse/keyboard expansion and returns to native copying without replay. Local commands never silently become model prompts; bringing CLI history across distinguishes a historical reference from executable continuation.
Module-advertised skill commands remain discoverable; browsing recipe files never masquerades as listing active runs or authorizes execution. Goals and configuration changes name their enforcement scope; authentication remains provider-owned and transient codes never become conversation history. Service delivery requires observed receipts, not mount counts.
Installation delivers an identifiable native client without a development workspace or local compiler for supported release platforms; newcomers configure providers deliberately, without silent policy migration or exposing private conversation data.
The [composition contract](../contracts/composition.v1.md) names the replaceable seams; [session](../contracts/session.v1.md), [presentation](../contracts/presentation.v1.md),
[continuity](../contracts/continuity.v1.md), [ecosystem](../contracts/ecosystem.v1.md) and [performance](../contracts/performance.v1.md) own the promises at those seams.
This project uses the Converge method; it is not the Converge service or steward's desk.
## Principles
### 1. The person's words are valuable
A half-written correction or answer is retained work, never permission to submit after recovery.
Typing does not compete with the assistant's output.
Deciding when words take effect is part of expressing intent.
The composer makes that timing understandable and wraps at word boundaries without inserting newlines; oversized words split only as needed, with cursor and selection preserved.

### 2. The ecosystem remains modular
A provider is independently replaceable.
A tool does not need to know which screen reads its result.
A context module can change how requests are assembled.
An orchestrator can change how work is executed.
The thin kernel stays a mechanism, while compatibility protects behavior rather than code.
The host and its adapters are replaceable too; preserving a slow implementation is not a goal.

### 3. Evidence determines what happened
Confident prose cannot make a failed test pass.
A partial command result remains partial.
The end of a response is an observation about a turn.
Acceptance of the requested work is a separate judgment.

### 4. Composition is inspectable
The person can see the source of the active behavior.
An authored capability and a usable capability are different facts.
System explains the difference, observed context usage and local versus remote intelligence capture.
A development preset brings expertise without implying installed services.

### 5. The conversation outlives a screen
Returning does not require reconstructing intent from terminal rows.
The person's draft and the agent's history have different owners.
Retained decisions keep their source and can be corrected.
Historical events explain previous work without initiating it again. A safely stopped child can continue explicitly under its own identity; deliberate model routing changes preserve its canonical history and non-routing policy, while uncertainty remains visible and never authorizes replay.

### 6. Control has a truthful scope
A correction names the work it changes.
A decision names the action it permits.
Stopping work does not claim to reverse its effects; repeated controls preserve final accounting and cleanup.
Delegated work makes its access and result inspectable.

### 7. One rendering owner
The terminal receives structured observations; legacy module stdout/stderr remains available as bounded, redacted private diagnostics, separate from conversation and authoritative outcomes, with uncertain ownership and capture limits explicit.
It adapts to width without turning display fragments into history.
Stable output joins the normal terminal screen; temporary inspection never replaces its retained account.
Generic content stays useful when a richer renderer is absent. Per-call usage occupies one concise model/cost-led row directly beneath activity; only an assistant response retains a separating blank before usage. Expansion retains exact accounting, routing and timing, and final turn/session totals remain distinct.
The headless client reads the same conversation boundary.
The [interaction contract](../contracts/interaction.v1.md) owns discovery, focus and rich input behavior.

### 8. The experience chooses the machinery
Plain-language actions, deliberate vertical spacing, accessible styling and fluent editing serve laptop, narrow mobile-terminal and large desktop views without sacrificing copyable text; framework defaults do not dictate interaction.
A real terminal capture, not an attractive browser picture, demonstrates the experience.
People review a stated question after the developer has exercised the ordinary controls.

### 9. Responsiveness is part of correctness
Typing stays immediate while work streams, history grows and decisions arrive.
The interface feels at least as fast as the CLI under comparable work.
Rendering and transport do not monopolize input or cancellation; process and language choices earn their place through observed results.

## What this deliberately resists
- A kernel fork containing interface policy.
- A second implementation of every ecosystem tool, or a screen that implies success from assistant confidence.
- Hidden submission of input that the person only pasted.
- Blanket undo of commands and concurrent human edits.
- Treating role descriptions as enforced access restrictions.
- Mistaking an instruction about a service for a running service.
- A private event vocabulary that every third-party tool must adopt.
- Framework loyalty, a compulsory process boundary, or speed gained by dropping evidence.
- A developer fixture passed off as a product review or a live assistant.

## How you can tell it is working

- A developer types a 3-line correction during a response and loses 0 characters.
- A returning developer restores 1 conversation with 0 repeated tool operations.
- A reviewer finds the exact result of 1 failed command within 2 interactions.
- A bundle author replaces 1 tool without editing a terminal widget.
- A developer runs both 2 named presets through the same host implementation.
- A person interrupts 1 task and sees 0 claims that interruption undid its effects.
- A developer compares 2 frontend candidates in real terminals before selecting one.
- A reviewer sees 0 unexplained departures from the agreed terminal visual reference.
- A person experiences 0 measured responsiveness regressions against the matched CLI baseline.
- A steward receives 1 explicit review question with the evidence needed to answer it.
- A developer scrolls and copies 1 long conversation in tmux without switching app modes, then exits with its transcript retained.

## Changelog

| Date | Change | Evidence |
|---|---|---|
| 2026-09-17 | Make loaded configuration inspectable without model work or credential disclosure. | Continued CLI-parity authorization; the local control previously exposed only root tools, while the CLI inspects the wider loaded composition. |
| 2026-09-17 | Preserve interactive child controls across explicit process isolation. | CLI parity audit found subprocess spawning refused; the headless runner cannot alone retain approvals, live activity or safe cancellation/continuation. |
| 2026-09-17 | Preserve legacy module output without surrendering terminal ownership. | CLI parity audit found redirected module print/Rich/log output discarded by the native client; structured messages alone do not cover existing bundles. |
| 2026-09-17 | Give actions, outcomes and subordinate evidence distinct emphasis. | Steward approved the Codex source comparison: whole-row colour obscures actions and incorrectly gives successful delegates' child errors a success accent. |
| 2026-09-17 | Distinguish cancellation visually and retain elapsed feedback through quiet draining. | Steward found muted stopping states and an apparently paused counter; negative-state colour and visible seconds clarify ongoing shutdown. |
| 2026-09-17 | Distinguish graceful tree cancellation, emergency escalation and confirmed exit. | Steward wants current calls to finish and nested delegates to resolve upward on first Ctrl-C, immediate stopping on the second, and default-No confirmation before Ctrl-C exits. |
| 2026-09-17 | Separate cancellation from quitting and resumability from turn success. | Steward's Ctrl-C exited working conversation and ordinary resume refused despite captured context; late callbacks also outlived its checkpoint. |
| 2026-09-17 | Join usage to preceding activity while separating responses. | Steward requested removal of the blank above usage except when it follows an assistant response. |
| 2026-09-17 | Scope resume discovery and selection to the launch directory. | Steward expected CLI-style directory-local resume after a parent-directory restart; a global picker offered unrelated work. |
| 2026-09-17 | Make plans and waits readable, wrap input by words and condense per-call usage. | Steward requested todo status, broader activity styling, Codex-informed wrapping and one-line within-turn reports after reviewing resumed work. |
| 2026-09-17 | Clarify cumulative usage/task sources and adopt brand activity styling. | Steward authorized usage/title fixes, then requested muxplex brand colours and a brighter animated sweep through active indicators; accessible static treatments and native copying remain requirements. |
| 2026-09-17 | Give delegated work short task-first titles. | Steward approved replacing truncated instruction openings after the clearer parallel-agent session still hid the actual jobs behind boilerplate. |
| 2026-09-16 | Make active-turn time and accounting continuously visible. | Steward requested accumulated turn time, tokens and dollars plus session dollars beside the working indicator; quiet tool waits currently hide that context. |
| 2026-09-16 | Keep sustained child telemetry with its delegate, with compact counts and complete per-call inspection. | Steward's long delegated review exposed flat usage/warning floods and unknown statuses after output truncation; steward approved the diagnosis and implementation. |
| 2026-09-16 | Clarify correction timing, automatic naming and consistent visual authorship. | Steward's follow-up found correction mistaken for interruption, missing generated names, bright expanded thinking, unboxed correction text and separated final usage totals. All user-authored conversation text shares charcoal; thinking stays distinctly secondary even when expanded, and final usage reads as one block. |
| 2026-09-16 | Require continuous streaming, visible background phases, distinct delegates and per-call accounting; make inline interaction explicit. | Steward's ordinary four-agent session exposed an eight-row clipping limit, hidden child progress, cache-token omissions and a startup readiness gap; steward approved the proposed correction and native-copy default. |
| 2026-09-16 | Specify conversation-first surfaces, compact activity and recursive observation. | Steward approved single-line tools/public thinking, charcoal input/user text, black transcript, explicit nested inspection and quiet normal completion while retaining native selection. |
| 2026-09-16 | Make task-oriented approachability and responsive visual hierarchy explicit. | Steward supplied an approximately 175-column by 50-row laptop reference, required copy-friendly spacing/styling and identified information workers learning AI-assisted coding as the audience. |
| 2026-09-16 | Clarify runtime control, authentication and delivery authority. | Steward authorized remaining CLI workflows; inspected tools cache permission configuration and module login owns credential storage. |
| 2026-09-16 | Clarify module-command and recipe discoverability. | Module notices advertised skill commands missing from the native menu; recipe session listings were confused with files. |
| 2026-09-15 | Make configured CLI compatibility and useful execution content explicit. | Steward approved the source-backed CLI gap analysis: preset success omitted app settings, remote destinations and public progress content. |
| 2026-09-15 | Clarify executable public-context recovery and tool-correlated source evidence. | Steward authorized all seven residual groups while AFK; historical excerpts alone cannot continue a child, and Git status alone cannot identify which tool observed a file version. |
| 2026-09-14 | Clarify retained file/line reference location and source version. | Steward requested the entire remaining backlog; plain insertion loses attachment identity across queue and return. |
| 2026-09-14 | Extend the destination to indexed discovery, richer retained inputs and deliberate review edits. | Steward requested all eight remaining backlog groups; bounded tail scans, one-image admission and read-only diffs leave named workflow gaps. |
| 2026-09-14 | Clarify repeated-control ownership during finalization. | Continued steward authorization; repeated Stop or exit during a stopped turn's checkpoint cancels that checkpoint in a deterministic real-runtime reproduction. |
| 2026-09-14 | Extend discovery across saved conversations and make compiler-free release installation explicit. | Steward requested the entire reviewed replacement-readiness backlog; the current picker stops at 100 records and Git installation requires local Rust tooling. |
| 2026-09-14 | Clarify source-preserving code colour. | Continued steward authorization; READ-02's monochrome code remains a visible reading gap. Unknown languages and bounded highlighting must retain readable source. |
| 2026-09-14 | Specify zero outer horizontal gutters. | Steward identified the remaining three-column side padding and explicitly requested its removal. |
| 2026-09-14 | Specify a fresh full-height starting workspace and borderless input; quiet live branding. | Steward explicitly requested full-screen appearance, terminal/tmux-friendly copying and removal of Ratatui/LIVE RUNTIME labels. Native shell/transcript retention remains required. |
| 2026-09-14 | Make content-sized chrome and non-submitting startup explicit. | Steward approved the [direct Codex study](../notes/CODEX-TERMINAL-SOURCE-STUDY.md); our fixed ten-row footer crowded ordinary replies. Native retention remains authoritative over upstream history-purging resize. |
| 2026-09-14 | Make newcomer guidance and privacy-conscious setup inspection explicit. | Steward requested approachability for others; launch help assumes developer knowledge and diagnostics provide paths without actionable checks. |
| 2026-09-13 | Specify installable native delivery and identifiable runtime. | Steward requested uv tool installation from a private Git repository; development-only launch obscures which capabilities are running. |
| 2026-09-13 | Clarify child visibility, retained local editors and context diagnostics. | Steward authorized the next daily-replacement wave; child receipts and local logging lacked an ordinary inspection path. |
| 2026-09-13 | Require ordinary native history and exit retention for the Amplifier CLI replacement, informed by Codex. | Steward rejected snapshot-only scrollback; isolated 150-line test produced zero tmux history rows and exit erased the visible transcript. |
| 2026-09-13 | Clarify resume choice, directory-scoped recall, scrollable/native selection and persistent mode visibility. | Steward could copy only one viewport, could not see the active mode, and needed explicit queue/steer discovery. |
| 2026-09-13 | Clarify ordinary copy, actionable questions, child execution, mode continuity and interrupted-work recovery. | Steward's real session exposed missing spawn, inaccessible selection/answers and a stopped conversation that could not reopen. |
| 2026-09-12 | Clarify structured reading and source-preserving code/diff inspection. | Continued steward request; current tables lose column relationships and copying code requires copying an entire reply. |
| 2026-09-12 | Clarify structured answers and read-only workspace review. | Steward requested continued implementation; questions need a tool/host seam distinct from approvals, and observed diffs are not agent-attribution evidence. |
| 2026-09-12 | Clarify active correction evidence and retained, scoped provider choices. | Steward requested continued parity work; inspected orchestrator exposes steering and conversation-provider capabilities without kernel changes. |
| 2026-09-12 | Make pending follow-ups and local conversation organization explicit. | Steward requested continued progress toward the studied Codex workflow powered by Amplifier. |
| 2026-09-12 | Make local conversation/file discovery explicit. | Steward accepted the reading/return slice and requested continued implementation; launcher-only return and missing path completion interrupt the ordinary workflow. |
| 2026-09-12 | Make reading, recall and return explicit in the experience. | Steward requested Markdown, proper scrollback, boundary-aware history, completion and conversation resume. |
| 2026-09-12 | Initial draft derived from the supplied handoff and source inspection. | User authorized first-slice implementation; new wording awaits review. |
| 2026-09-12 | Amend direction: visual fidelity, CLI-level responsiveness, replaceable host and evidence-led frontend selection; retain ecosystem boundaries. | [Direction review](../notes/DIRECTION-REVIEW.md): the first UI missed the concept, its review purpose was unclear, and the steward approved a replacement comparison. Detail remains draft. |
| 2026-09-12 | Clarify available terminal width as part of the experience. | Steward reported the comparison did not fill the terminal; both clients imposed an unexplained 112-column cap. |
| 2026-09-12 | Restore discoverable interaction alongside runtime correctness. | [Source reconciliation](../notes/INTERACTION-RECONCILIATION.md): prototype shortcuts displaced the studied interaction model; steward requested usable ecosystem execution. |

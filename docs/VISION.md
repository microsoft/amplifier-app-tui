# Amplifier TUI — Vision (DRAFT)

The destination is written as though already true; promises live in contracts, evidence and sequencing in notes.
Direction changes here first, with dated evidence; work follows from the remaining gap.
The adopted method and its provenance are described in [Converge practice](../notes/CONVERGE.md).

## What Amplifier TUI is

Amplifier TUI replaces the Amplifier CLI experience with a polished terminal workspace, as responsive as its CLI.
It learns from Codex's proven interaction and terminal behavior while Amplifier's ecosystem owns execution.
A person understands and influences work; Work, Review and System share one conversation and composer.
Conversation has the space; routine machinery is quiet and detail is available on demand.
The interface carries the agreed concept's hierarchy into terminal cells and uses the available width.
Visible actions and contextual choices make the experience usable without memorizing shortcuts.
The conversation outlives screens and engines; returning offers a picker and same-directory input recall.
Follow-up work has a visible waiting place; stopping never starts another task behind the person.
Corrections distinguish being accepted from reaching active work; neither implies a new turn.
Conversation provider choices have a visible scope and survive returning to the same work.
Questions invite deliberate answers without granting permission; workspace review distinguishes observations from attribution.
People can name, find and copy their conversation without involving a model.
The ordinary conversation accumulates native terminal history; selection and tmux scrolling need no special view.
Exiting leaves readable work behind; a compact live composer coexists with transcript-aware terminal previews.
Export and retained conversation state remain distinct from terminal rows and never execute history.
Waiting questions offer an answer where the question is shown, including at narrow widths.
Delegation and recipes expose child progress, waiting reasons, scoped evidence and explicit continuation limits.
The current mode stays visible; mode changes retain module enforcement and returning restores their policy.
Interrupted work remains readable and can seed an explicitly acknowledged new conversation without replay.
Markdown and code stay readable; history, file snapshots and external editing preserve the unsent draft.
Bundles bring instructions, tools, providers and behaviors without owning the interface.
Installation delivers an identifiable native client without a development workspace or silent policy migration; newcomers learn and diagnose setup without executing work or exposing private conversation data.
The [composition contract](../contracts/composition.v1.md) names the replaceable seams.
[Session](../contracts/session.v1.md), [presentation](../contracts/presentation.v1.md),
[continuity](../contracts/continuity.v1.md), [ecosystem](../contracts/ecosystem.v1.md) and
[performance](../contracts/performance.v1.md) own the promises at those seams.
This project uses the Converge method; it is not the Converge service or steward's desk.

## Principles

### 1. The person's words are valuable
A half-written correction or answer is retained work, never permission to submit after recovery.
Typing does not compete with the assistant's output.
Deciding when words take effect is part of expressing intent.
The composer makes that timing understandable.

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
Historical events explain previous work without initiating it again.

### 6. Control has a truthful scope
A correction names the work it changes.
A decision names the action it permits.
Stopping work does not claim to reverse its effects.
Delegated work makes its access and result inspectable.

### 7. One rendering owner
The terminal receives structured observations.
It adapts to width without turning display fragments into history.
Stable output joins the normal terminal screen; temporary inspection never replaces its retained account.
Generic content stays useful when a richer renderer is absent.
The headless client reads the same conversation boundary.
The [interaction contract](../contracts/interaction.v1.md) owns discovery, focus and rich input behavior.

### 8. The experience chooses the machinery
Visual hierarchy, legible evidence and fluent editing are product requirements; framework defaults do not dictate interaction.
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

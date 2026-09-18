# Composer and transcript Contract — v1 (DRAFT)

Proposed boundary derived from the implementation handoff; parent: [composition.v1](composition.v1.md).
## Who builds against this
The terminal builder and the person typing while work runs. The steward reviews this wording independently of implementation progress.

## What it is

```text
draft(text, selection, focus) survives view and runtime changes
identified stream block -> accumulated source -> rendered text at current width
tool(call_id) -> running | succeeded | failed | interrupted | unknown
Work: conversation + activity; Review: evidence; System: composition; persistent composer + native transcript; explicit interaction returns without replay
```

The example describes a boundary, not implementation status; [interaction](interaction.v1.md) owns action discovery, focus and richer draft behavior. Acceptance evidence lives in [the acceptance notes](../notes/ACCEPTANCE.md).

## The promises

1. **Preserve unsent text.** Startup, tab changes, execution and rejected submission preserve text and selection.
   Startup welcomes editing immediately with named preparation/restoration phases; background operations stay visible until complete. Readiness never queues an implicit send; simultaneous restored and newly typed drafts remain recoverable. Word-first soft wrapping, oversized-word fallback, visual navigation and height/resize preserve exact text, cursor and selection; display wraps never insert newlines.
   Broken: Missing characters or a moved selection violates the person's draft.
   Affected: the boundary's clients and the person relying on them.

2. **Keep paste as text.** Pasted newlines and shortcut characters never submit a message.
   Broken: A partial pasted task reaching the engine breaks the input boundary.
   Affected: the boundary's clients and the person relying on them.

3. **Project identified source.** Markdown renders retained source; tables preserve cell relationships on resize. Code inspection identifies its block and never executes it. Syntax colour preserves copied code/whitespace; unknown languages, disabled colour and highlighting limits keep readable plain content without fetching grammars. Scroll moves visual lines, holds an identified anchor and follows output only at the tail.
   The default conversation emits stable rows into native terminal history without a selection mode switch or configuration change. Initial historical replay may be bounded with visible disclosure and full-source inspection/export; new output is not silently omitted.
   Broken: Duplicate output after finalization or resize breaks the transcript.
   Affected: the boundary's clients and the person relying on them.

4. **Keep outcomes visible.** Tool failures and unknown outcomes remain visible beside assistant text. Every model call exposes attributed provider/model, observed routing/pinning, local timestamp, duration, input/cache/output/total and cost when supplied; turn/session totals include observed children without double-counting. Routine billing/occupancy disclaimers stay out of ordinary output; missing/partial values remain explicit and exact evidence inspectable. The active-turn indicator includes elapsed wall time, reported call count, explicitly labelled cumulative turn token usage, turn cost and session cost. Repeated call inputs count as usage, not current context size. Time advances during quiet tool/decision waits; new turns reset their counters while session costs survive resume. Tokens/costs advance from reported calls, never estimated in-flight generation; narrow layouts retain these measures without taking composer ownership.
   Tools and public thinking use updating inline summaries; parallel delegates lead with short, stable task titles distinct from agent identity and current observed activity, plus compact call/cost/warning totals. Titles use explicit labels or bounded task excerpts, excluding inherited conversation wrappers/history, not extra model calls; unavailable task boundaries are not guessed. Full instructions remain unchanged and inspectable, and an explicit continuation gets a title for its new task. Child telemetry stays under its observed parent, with every model-call record available in Activity rather than flooding the root conversation. Tool completion is independent of output truncation when authoritative invocation status was observed; unobserved outcomes remain unknown. Streaming uses available conversation space without a fixed-height holding area or silent clipping. Expanded public thinking renders Markdown without generating reasoning. Named work/wait/stop indicators disappear at completion; failures remain explicit. Broken: A confident answer hiding a failed action violates evidence.
   Affected: the boundary's clients and the person relying on them.

5. **Own the terminal once.** The client releases terminal resources on exit, leaving emitted transcript readable. Resizing, finalization and temporary inspection never erase or duplicate committed history.
   Ordinary startup opens a fresh full-height primary-screen workspace, moving prior shell output into native history without purging it. Missing cursor-query replies have a finite input-preserving fallback during startup, inspection and resize.
   Broken: Returning to the pre-app shell with no transcript, competing renderers, or a broken shell violates terminal ownership.
   Affected: the boundary's clients and the person relying on them.

6. **Carry the agreed design into the terminal.** Actual captures preserve deliberate vertical separation, readable hierarchy and a compact bottom-aligned composer across declared laptop, narrow and large-terminal sizes; focus and semantic states remain distinguishable without colour. Full-pane previews contain the actual transcript; a cropped footer-only preview may omit short conversations above unused space.
   Conversation, composer and inspection use every terminal column without outer horizontal gutters; input rows have no decorative side borders. Idle chrome fits the draft; mode and discoverable actions remain visible. Ordinary live views omit renderer/runtime branding; simulated and fixture execution remain clearly labelled.
   Muxplex brand supplies near-black conversation, raised charcoal input/user messages with one blank row above/below and no role labels, cool white words, muted thinking even when expanded, cyan interaction and amber attention. Stopping, its force-stop explanation and stopped/interrupted outcomes use the distinct negative-state accent. Quiet draining retains visibly advancing elapsed time until the actual ending, including reduced motion; disconnected observations never claim live progress. Final usage/totals are contiguous. Observed running tools and named model/background waits shimmer without changing text/history or monopolizing input; completed/stale observations and human waits never animate. Reduced-motion and colour-free modes disable shimmer; accessible themes preserve hierarchy and image previews retain source colours. Broken: Width caps, widget defaults, motion-only status or diagnostic floods replace the agreed design.
   Action-first summaries distinguish cyan operations/titles, muted targets/metadata, amber work/uncertainty and red negative outcomes; only the live state animates. Parent completion and child warning/error badges retain independent meaning, including without colour. Affected: the person reading the conversation and the steward evaluating the product.

7. **Reveal detail without taking over.** Routine tools collapse to concise summaries; exact evidence is expandable, copyable and independently scrollable. Workspace inspection names its repository and comparison scope, defaults to read-only, labels limits/concurrent-change uncertainty, and never attributes a diff to the agent without evidence. Separately confirmed edits validate the captured file version and refuse stale writes; test evidence names the source state actually observed. Tool-correlated change/command evidence names the originating session, call and before/after source digests; unavailable or overlapping observations remain explicit, not exclusive causal authorship or a test-acceptance verdict.
   Explicit interaction offers inline expansion and recursive Activity, preserving draft/source identity; Escape restores native mouse ownership. Parent-call links require observation, not timing guesses. Narrow views use breadcrumbs; native history remains immutable and interaction never replays execution. Per-call usage has one model/cost-led row with disclosed clipping and expandable exact fields; final totals stay separate. Usage directly follows preceding activity without a blank; after an assistant response, retain a blank. Recognized todo results show reported done/active/pending counts and a bounded task preview with an expandable checklist; failed/unrecognized results stay generic, and turn/tool completion never implies task completion. Broken: Output floods the conversation, scroll jumps away from the reader, or opening detail destroys their draft or selection.
   Expanded tools retain exact names/arguments with source-preserving command colour and bounded, disclosed output previews; active checklist tasks are emphasized over completed/pending work. Affected: people inspecting work while composing their next instruction.

8. **Give review a purpose.** A handoff states the review question, tested interactions, limitations and whether the session is simulated or live.
   Broken: A fixture launch or green test count is presented as proof of visual quality, or asks the steward to discover basic defects.
   Affected: the steward whose time the review consumes.

## Not in v1

Pixel-identical browser typography, uniform behavior across every terminal, and a particular widget framework.

## How the kit checks it

Use framework-independent terminal captures and interaction scripts; compare retained source and composer selection. Exercise actual tmux history/copy mode without `/scrollback`, exit retention, short/long capture-pane previews, resize and overlay round trips; count duplicate rows and verify terminal-mode restoration. The [visual comparison plan](../notes/FRONTEND-EVALUATION.md) applies promises 6–8 to real terminal scenes. The document check validates shape and links; runtime tests supply behavior evidence. Draft contracts do not seed formal Converge ledger rows.

## Open questions

Which terminal-specific visual adaptations need steward acceptance, and which input/selection behavior first requires an explicit terminal-support restriction?

## Changelog

| Date | Change | Evidence |
|---|---|---|
| 2026-09-17 | Clarify P6's semantic action/outcome spans and cancellation clock; P7's bounded command previews, active tasks and usage spacing. | Steward approved Codex-informed action emphasis and independent child badges after reporting muted Stop, an apparently paused clock and excessive usage gaps. |
| 2026-09-17 | Clarify P1/P6/P7 for word wrap, observed plans, compact usage and scoped activity. | Steward requested these ordinary-session improvements; presentation never changes execution policy or accounting. |
| 2026-09-17 | Clarify P4's usage/task boundaries and amend P6's brand/activity treatment. | Steward requested unambiguous cumulative usage, titles excluding inherited history, latest muxplex brand colours and animated live-label shimmer; execution and copying remain unchanged. |
| 2026-09-17 | Clarify P4's task-first delegated titles. | Steward approved replacing unhelpful instruction-prefix previews while preserving exact instructions, identities, warnings and accounting. |
| 2026-09-16 | Clarify P4's active-turn time and accounting. | Steward requested cumulative time/tokens/dollars and session cost on the working indicator, including long quiet delegated work. |
| 2026-09-16 | Clarify P4's hierarchical accounting and independent tool outcome. | Approved follow-up to sustained parallel work flooding the conversation with child usage/warnings and truncated result envelopes losing known completion status. |
| 2026-09-16 | Clarify P6's consistent authorship, thinking contrast and final usage grouping. | Steward observed unboxed corrections, expanded thinking rendered as bright responses, and an unnecessary gap before turn totals. |
| 2026-09-16 | Amend P1/P3/P4/P7 for continuous work, per-call usage and explicit inline interaction. | Approved correction of clipped parallel delegates, hidden child activity, missing cache fields and uninformative startup. Native copying stays default. |
| 2026-09-16 | Specify P4/P6/P7 compact recursive activity and conversation surfaces. | Steward approved charcoal input/user messages, muted one-line tools/thinking, working tail and read-only nested inspection without taking native scrollback ownership. |
| 2026-09-16 | Clarify P6's responsive and non-colour hierarchy. | Steward requested a comprehensive approachable UX around an approximately 175 by 50 terminal, with native copying, vertical spacing and smaller/larger views. |
| 2026-09-16 | Make P5's no-cursor-response obligation explicit during inspection. | F3 worked with the test observer's automatic cursor reply but failed in the terminal-testing module's PTY. |
| 2026-09-15 | Clarify P4's ordinary execution content. | Direct observer probes dropped budget/retry/thinking and message attribution; generic tool rows hid arguments and results. |
| 2026-09-15 | Clarify P7's source-correlated change/command evidence. | Steward requested agent/test attribution; a successful command and an unversioned diff cannot establish which source state was checked. |
| 2026-09-14 | Permit separately confirmed version-checked edits beside read-only review in P7. | Steward explicitly requested all backlog items, including conflict editing and source-attributed change/test review. Inspection itself remains non-mutating. |
| 2026-09-14 | Extend P3's code readability to source-preserving syntax colour. | READ-02 leaves every code token monochrome; steward requested continued progress. Colour is a projection, not execution or a source rewrite. |
| 2026-09-14 | Clarify P6's edge-to-edge width. | Steward requested removing the remaining three-column outer inset; content indentation and local dialog structure remain meaningful. |
| 2026-09-14 | Amend P5/P6 for full-height startup, open input and quiet live labels. | Explicit steward request supersedes cursor-anchored startup and the bottom-20-row short-preview guarantee; history retention and complete-pane previews remain mandatory. |
| 2026-09-14 | Clarify content-sized chrome, editable startup and conservative probe fallback in P1/P5/P6. | [Latest Codex source study](../notes/CODEX-TERMINAL-SOURCE-STUDY.md) and steward approval; fixed ten-row idle layout is ours, not an inline-terminal requirement. |
| 2026-09-13 | Permit disclosed bounds on initial historical replay in P3, separate from new output. | Replaying 100,000 historical items kept typing responsive but exceeded the four-second exit gate; dumping invisible backlog on quit made retention block control. |
| 2026-09-13 | Correct P3/P5/P6 to default native history, retained exit output and compact previews. | Snapshot-only test missed ordinary use; isolated tmux history stayed empty and a bottom-20-lines preview missed a short reply. |
| 2026-09-13 | Extend P3 to scrollable selection and native scrollback access. | Steward could copy one page but could not scroll during selection or use tmux history. |
| 2026-09-13 | Extend P3 to visible selection and separate source export. | Mouse capture prevented the steward from selecting transcript text. |
| 2026-09-12 | Clarify table reflow and source-specific code inspection in P3. | Current separated-cell fallback and whole-message-only copy leave ordinary reading gaps. |
| 2026-09-12 | Specify read-only workspace comparison scope in P7. | Existing tool evidence is not a consolidated view of local changes or proof of authorship. |
| 2026-09-12 | Specify Markdown and line-based anchored scroll in P3. | Steward observed whole-item scrolling and requested readable Markdown. |
| 2026-09-12 | Initial draft; no ratification claimed. | Supplied handoff and current source inspection. |
| 2026-09-12 | Add visual fidelity, quiet expandable evidence and purposeful review; remove the Textual-specific verification prescription. | [Direction review](../notes/DIRECTION-REVIEW.md): functional tests did not establish the requested experience. |
| 2026-09-12 | Clarify P6: use available width, not a fixed centered canvas. | Steward's wide-terminal review exposed a 112-column cap in both clients; the earlier capture rubric missed it. |
| 2026-09-12 | Delegate discoverability and focused interaction to interaction.v1. | [Source reconciliation](../notes/INTERACTION-RECONCILIATION.md); visual fidelity alone did not preserve the researched experience. |

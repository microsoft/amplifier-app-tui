# Composer and transcript Contract — v1 (DRAFT)

Proposed boundary derived from the implementation handoff.
Parent: [composition.v1](composition.v1.md).

## Who builds against this

The terminal builder and the person typing while work runs.
The steward reviews this wording independently of implementation progress.

## What it is

```text
draft(text, selection, focus) survives view and runtime changes
identified stream block -> accumulated source -> rendered text at current width
tool(call_id) -> running | succeeded | failed | interrupted | unknown
Work: conversation + concise expandable activity; Review: changes + evidence
System: effective composition; one persistent composer across all three
normal terminal: stable transcript rows + compact live region; temporary inspection returns without replay
```

The example describes a boundary, not a claim that every feature is implemented.
The [interaction contract](interaction.v1.md) owns action discovery, focus and richer draft behavior.
Acceptance evidence lives in [the acceptance notes](../notes/ACCEPTANCE.md).

## The promises

1. **Preserve unsent text.** Startup, tab changes, execution and rejected submission preserve text and selection.
   Startup editing never queues an implicit send on readiness; simultaneous restored and newly typed drafts remain recoverable rather than silently replacing one another.
   Broken: Missing characters or a moved selection violates the person's draft.
   Affected: the boundary's clients and the person relying on them.

2. **Keep paste as text.** Pasted newlines and shortcut characters never submit a message.
   Broken: A partial pasted task reaching the engine breaks the input boundary.
   Affected: the boundary's clients and the person relying on them.

3. **Project identified source.** Markdown renders retained source; tables preserve cell relationships on resize. Code inspection identifies its block and never executes it. Syntax colour preserves copied code/whitespace; unknown languages, disabled colour and highlighting limits keep readable plain content without fetching grammars. Scroll moves visual lines, holds an identified anchor and follows output only at the tail.
   The default conversation emits stable rows into native terminal history without a selection mode switch or configuration change. Initial historical replay may be bounded with visible disclosure and full-source inspection/export; new output is not silently omitted.
   Broken: Duplicate output after finalization or resize breaks the transcript.
   Affected: the boundary's clients and the person relying on them.

4. **Keep outcomes visible.** Tool failures and unknown outcomes remain visible beside assistant text.
   Broken: A confident answer hiding a failed action violates evidence.
   Affected: the boundary's clients and the person relying on them.

5. **Own the terminal once.** The client releases terminal resources on exit, leaving emitted transcript readable. Resizing, finalization and temporary inspection never erase or duplicate committed history.
   Ordinary startup opens a fresh full-height primary-screen workspace, moving prior shell output into native history without purging it. Missing cursor-query replies have a finite input-preserving fallback.
   Broken: Returning to the pre-app shell with no transcript, competing renderers, or a broken shell violates terminal ownership.
   Affected: the boundary's clients and the person relying on them.

6. **Carry the agreed design into the terminal.** Actual captures preserve hierarchy, palette roles and a compact bottom-aligned composer at available width. Full-pane previews contain the actual transcript; a cropped footer-only preview may omit short conversations above unused space.
   Conversation, composer and inspection use every terminal column without outer horizontal gutters; input rows have no decorative side borders. Idle chrome fits the draft; mode and discoverable actions remain visible. Ordinary live views omit renderer/runtime branding; simulated and fixture execution remain clearly labelled.
   Broken: An unexplained width cap, default widget chrome or raw diagnostic dump replaces the design without an accepted adaptation.
   Affected: the person reading the conversation and the steward evaluating the product.

7. **Reveal detail without taking over.** Routine tools collapse to concise summaries; exact evidence is expandable, copyable and independently scrollable. Workspace inspection names its repository and comparison scope, defaults to read-only, labels limits/concurrent-change uncertainty, and never attributes a diff to the agent without evidence. Separately confirmed edits validate the captured file version and refuse stale writes; test evidence names the source state actually observed. Tool-correlated change/command evidence names the originating session, call and before/after source digests; unavailable or overlapping observations remain explicit, not exclusive causal authorship or a test-acceptance verdict.
   Broken: Output floods the conversation, scroll jumps away from the reader, or opening detail destroys their draft or selection.
   Affected: people inspecting work while composing their next instruction.

8. **Give review a purpose.** A handoff states the review question, tested interactions, limitations and whether the session is simulated or live.
   Broken: A fixture launch or green test count is presented as proof of visual quality, or asks the steward to discover basic defects.
   Affected: the steward whose time the review consumes.

## Not in v1

Pixel-identical browser typography, uniform behavior across every terminal, and a particular widget framework.

## How the kit checks it

Use framework-independent terminal captures and interaction scripts; compare retained source and composer selection.
Exercise actual tmux history/copy mode without `/scrollback`, exit retention, short/long capture-pane previews, resize and overlay round trips; count duplicate rows and verify terminal-mode restoration.
The [visual comparison plan](../notes/FRONTEND-EVALUATION.md) applies promises 6–8 to real terminal scenes.
The document check validates shape and links; runtime tests supply behavior evidence. Draft contracts do not seed formal Converge ledger rows.

## Open questions

Which terminal-specific visual adaptations need the steward's acceptance against the reference?
Which input/selection behavior first requires an explicit terminal-support restriction?

## Changelog

| Date | Change | Evidence |
|---|---|---|
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

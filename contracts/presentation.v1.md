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
   Lists keep hanging indentation through wrapping, nested blocks and continuation paragraphs; quotes retain their prefix and headings use typography and spacing, not displayed Markdown delimiters. Literal hashes in escaped text/code remain literal. Tight lists stay compact, distinct blocks keep separation, and streaming/final projections agree. Links suppress only redundant destinations unless usable hyperlinks preserve access; source remains copyable. Stable rows enter native terminal history without a selection-mode switch. Resume shows the latest 100 historical items with explicit read-only older/newer pages and disclosed preview bounds; canonical context remains complete and new output is not silently omitted. Connected history interleaves observed activity with canonical messages using recorded positions; missing placement is disclosed. Initial return, live updates and older pages use the same identified timeline. Inspection never reprints committed native history. Empty/hidden projections have no selectable rows; stale anchors resolve to visible rows without losing the draft.
   Broken: Duplicate output after finalization or resize breaks the transcript.
   Affected: the boundary's clients and the person relying on them.

4. **Keep outcomes visible.** Tool failures and unknown outcomes remain visible beside assistant text. Every model call exposes attributed provider/model, observed routing/pinning, local timestamp, duration, input/cache/output/total and cost when supplied; turn/session totals include observed children without double-counting. Routine billing/occupancy disclaimers stay out of ordinary output; missing/partial values remain explicit and exact evidence inspectable. The active-turn indicator includes elapsed wall time, reported call count, explicitly labelled cumulative turn token usage, turn cost and session cost. Repeated call inputs count as usage, not current context size. Time advances during quiet tool/decision waits; new turns reset their counters while session costs survive resume. Tokens/costs advance from reported calls, never estimated in-flight generation; narrow layouts retain these measures without taking composer ownership.
   Shared return imports attributable historical accounting receipts without replay or source-log edits. Duplicate observations count once; missing, ambiguous, corrupt or bounded-out evidence cannot silently become a complete total. Historical costs belong to the session, not the next turn. A current resume summary distinguishes reconciled session accounting from totals captured at historical turn boundaries; it never rewrites those receipts. Foundation's scoped reader supplies optional CI activity with configured relocation and exact message/tool association, never timestamp guesses. Canonical resume is independent of activity scanning; live observations reach the view without log polling.
   Tools and public thinking use updating inline summaries; parallel delegates lead with short, stable task titles distinct from agent identity and current observed activity, plus compact call/cost/warning totals. Titles use explicit labels or bounded task excerpts, excluding inherited conversation wrappers/history, not extra model calls; unavailable task boundaries are not guessed. Full instructions remain unchanged and inspectable, and an explicit continuation gets a title for its new task. Child telemetry stays under its observed parent, with every model-call record available in Activity rather than flooding the root conversation. Tool completion is independent of output truncation when authoritative invocation status was observed; unobserved outcomes remain unknown. Streaming uses available conversation space without a fixed-height holding area or silent clipping. Expanded public thinking renders Markdown without generating reasoning. Named work/wait/stop indicators disappear at completion; failures remain explicit. Broken: A confident answer hiding a failed action violates evidence.
   Affected: the boundary's clients and the person relying on them.

5. **Own the terminal once.** The client releases terminal resources on exit, leaving emitted transcript readable. Resizing, finalization and temporary inspection never erase or duplicate committed history.
   Ordinary startup opens a full-height primary-screen workspace, moving only rows above the observed launch cursor into native history without purging them. Unused rows below it and temporary live padding never become an artificial page of scrollback. Missing cursor-query replies have a finite input-preserving fallback during startup, inspection and resize; uncertain geometry never authorizes erasing prior output.
   Broken: Returning to the pre-app shell with no transcript, competing renderers, or a broken shell violates terminal ownership.
   Affected: the boundary's clients and the person relying on them.

6. **Carry the agreed design into the terminal.** Actual captures preserve deliberate vertical separation, readable hierarchy and a compact bottom-aligned composer across declared laptop, narrow and large-terminal sizes; focus and semantic states remain distinguishable without colour. Full-pane previews contain the actual transcript; a cropped footer-only preview may omit short conversations above unused space.
   Conversation, composer and inspection use every terminal column without outer horizontal gutters; input rows have no decorative side borders. Headings use accent contrast as well as typography; major headings retain underlining even with colour disabled or an indistinct bold font. Expanded thinking keeps its secondary colour. Idle chrome fits the draft; mode and discoverable actions remain visible. Ordinary live views omit renderer/runtime branding; simulated and fixture execution remain clearly labelled.
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

# Discoverable interaction Contract — v1 (DRAFT)

Restores user-facing obligations from the supplied Codex/Amplifier studies and concept. Parent: [presentation.v1](presentation.v1.md); execution authority stays in [session.v1](session.v1.md).
## Who builds against this

People learning the interface, composer/action builders, and host capability adapters. The steward approves direction separately from ratifying this detailed wording.

## What it is

```text
visible action / searchable menu -> focused choice -> explicit activation
draft -> submit | queue | steer (distinct, capability-backed intentions)
decision(request_id, offered options) -> focused answer to that same request
questions(request_id, question_ids) -> local answers -> review -> explicit submit
completion / history preview -> accept locally | cancel back to original draft
```

This describes the destination, not a claim that every interaction is implemented. [Reconciliation](../notes/INTERACTION-RECONCILIATION.md) records source and adoption decisions.

## The promises

1. **Make ordinary actions discoverable.** Send, queue management, active correction, provider selection, stop, decisions, evidence, conversation naming/search/copy and navigation have visible, keyboard-focusable paths with task-oriented labels understandable without terminal expertise; shortcuts are optional accelerators.
   Resume offers a paged picker and bounded content search only across conversations in the resolved launch directory, excluding parents/children and malformed directory identities before search or paging. Latest/explicit-ID selection and in-app switching enforce the same scope; no matches never falls back globally. Scope and partial results are disclosed without importing context. Configured names never override explicit user names. Queue-next-turn, correction at the runtime's next input boundary and Stop cancellation remain distinct; the current mode stays visible.
   Visible Interact and Activity entries offer inline expansion and recursive previews/evidence with equivalent click/keyboard paths; Escape restores native copying and the draft. Mouse ownership is explicitly labelled; normal terminal selection remains default. Inspection never submits or retries. Broken: A person needs a memorized Ctrl chord to complete the ordinary workflow, or a displayed action cannot be reached by keyboard.
   Affected: new users and people who cannot use a mouse.

2. **Give focus one owner.** Menu, decision and editor input have explicit precedence; Escape dismisses local interaction without sending or losing a draft. Ctrl-C during active work requests the next Stop stage in session.v1:6 without clearing the draft; selected-text copying retains precedence. A Ctrl-C exit requires explicit confirmation defaulting to No; Enter on that default, Escape and repeated Ctrl-C never exit. Key-repeat events cannot escalate or exit; explicit Quit remains available.
   Broken: Enter both chooses an action and submits text, or arriving activity steals a keystroke intended for the composer.
   Affected: people writing corrections while tools and decisions arrive.

3. **Preserve rich input intent.** Up/Down recall history only at editor line boundaries and restore the draft on return; supported references retain meaning, and text recall never invents missing attachments.
   Recall includes same-directory submissions without importing model context. Explicit snapshots disclose path, selected line range and digest before attachment or insertion; reference text retains source identity through queue/resume, while images require compatible providers. Captured bytes never become a path reread or silent conversion. External editing returns to an unsent draft and preserves it on failure.
   Broken: A draft submits corrupted references or missing queued attachments; timestamps recall out of order, legacy ordering is undisclosed, or clipboard acquisition implicitly submits.
   Affected: people assembling and recalling instructions; durable retention belongs to continuity.v1.

4. **Keep completion local until accepted.** Tab completes eligible queries before moving focus; bounded workspace-path suggestions read names, not contents, preserve neighbors, and discard stale replies after editing, dismissal or conversation changes.
   Broken: Opening, filtering or dismissing a menu sends a model request or rewrites unrelated draft content.
   Affected: people discovering commands or completing references without executing them.

5. **Make decisions scoped and stable.** Show the runtime's actual options and action; focus and answers retain the original request identity, including when another request arrives or resolves.
   Broken: Fixed yes/no controls invent scope, a later request replaces the focused question, or stale activation answers a new request.
   Affected: the person granting permission and modules waiting for an answer.

6. **Explain usable capabilities.** Actions and catalogs distinguish available controls, mounted tools and authored definitions; configuration inspection uses loaded metadata, names omissions, never calls a model or exposes credential values. Mutations identify session versus saved scope, verify their outcome, and distinguish staged metadata from live module changes; shared saves require explicit scope and confirmation. Unsupported intentions have reasons, never simulated success.
   Slash commands resolve locally or explain unsupported semantics without a model request; discovered user-invocable skill shortcuts remain available after lazy discovery, and insertion stays distinct from execution. Recipe files, active runs and historical activity are separate catalogs. Getting-started/task help is local, dismissible and draft-preserving; opening instructions never executes examples. Goals disclose continuation limits; configuration names the actual affected mounts. Explicit provider login uses module-owned storage, cancellable ownership and transient UI-only prompts; unsupported authentication refuses without copying credentials.
   Broken: A menu advertises working delegation from agent definitions alone, or a demo scene is the unexplained default for real work.
   Affected: people choosing bundles, tools, skills and modes.

7. **Verify the ordinary path on real execution.** Acceptance includes discoverable navigation, an actual module/tool round trip, evidence inspection and a second turn without shortcut-only controls.
   Broken: Scene screenshots or mount counts are presented as proof that the ecosystem workflow works.
   Affected: the steward deciding whether the implementation is viable.

8. **Answer questions deliberately.** Structured questions offer choice or free text, retain their request/question identity, and require explicit submission after review. Dismissal keeps local answers while the request is live; cancellation, timeout and Stop never invent an answer. Questions neither grant permissions nor steal composer focus.
   A waiting question has a directly actionable, width-safe entry point; answering does not require knowing hidden menu names.
   Broken: Selecting a suggested choice silently submits, an answer reaches a different request, or a question masquerades as approval.
   Affected: people clarifying work and modules consuming their answers.

## Not in v1

A mandated Codex keymap, a new runtime permission vocabulary, or a claim of complete CLI policy parity. Queue, steer, resume and delegation are enabled only with their session/ecosystem obligations.

## How the kit checks it

Use actual PTY keyboard and mouse input, including menus during streaming and stale decisions.
Compare sent requests with the preserved draft and original option/request identities.
Exercise both ecosystem presets separately from simulations and deterministic provider fixtures.
Record missing rich-input/continuity behavior as gaps, not implicit acceptance.

## Open questions

Which reference/attachment types should the first rich composer support? Which CLI discovery and provider-selection policies should be adopted for ordinary startup?

## Changelog

| Date | Change | Evidence |
|---|---|---|
| 2026-09-17 | Clarify P6's read-only loaded-configuration boundary. | Continued CLI-parity authorization; inspection must distinguish definitions from running work without exposing configuration values or silently applying mutations. |
| 2026-09-17 | Give P2 staged Ctrl-C stop-and-stay and default-No exit confirmation. | Steward used Ctrl-C to cancel work and lost resumability, then requested graceful/force stages and explicit confirmation before exit; idle draft-clearing is not adopted. |
| 2026-09-17 | Scope P1's resume picker, search and selection to the launch directory. | Steward requested the CLI's directory-local return behavior; global discovery could offer a different workspace. |
| 2026-09-16 | Clarify P1's correction timing and ecosystem naming. | Steward expected Change task to interrupt grep and found first-message titles instead of CLI-style automatic names. |
| 2026-09-16 | Clarify P1's explicit inline mouse/keyboard interaction and native-copy return. | Steward approved trying inline expansion while retaining native copying by default. |
| 2026-09-16 | Extend P1's visible read-only Activity path. | Steward requested nested click expansion with equivalent keyboard access; ordinary terminal history must remain selectable. |
| 2026-09-16 | Clarify P1's task-oriented audience. | Steward prioritizes information workers learning AI-assisted coding over shortcut-first terminal experts; ordinary controls must explain intent. |
| 2026-09-16 | Specify P6's control and authentication scope. | CLI goal/configuration and provider login are separate operations, not ordinary prompts; cached tool policy cannot be changed by editing a settings label. |
| 2026-09-16 | Clarify P6's command and recipe discovery boundaries. | Native slash choices omitted module-advertised skills; zero active recipe sessions was mistaken for no recipe files. |
| 2026-09-15 | Clarify P6's deterministic command boundary. | CLI commands fell through the native dispatcher into ordinary model submission. |
| 2026-09-14 | Specify P3's file/location reference identity across queue and resume. | Steward authorized the remaining backlog; plain insertion loses location semantics and image-only admission unnecessarily requires vision. |
| 2026-09-14 | Extend P3 to chronological recall and durable attachment/reference sets. | Steward authorized the entire remaining backlog; current recall groups sessions by activity and image admission supports one idle-only file. |
| 2026-09-14 | Extend P3 to capability-backed immutable image input. | Steward requested the full backlog; string-only submission cannot carry image bytes, while the public context/provider formats support image blocks. |
| 2026-09-14 | Extend P1 to paged saved-work discovery and source content search. | Steward authorized all reviewed backlog items; title-only filtering of the first 100 records cannot locate older work. |
| 2026-09-14 | Clarify P6's local newcomer guidance. | Steward requested approachability beyond the development workspace; terse shortcut hints do not explain ordinary tasks. |
| 2026-09-13 | Define P3's explicit text snapshots and external editing. | Steward authorized composer work; the current string-only runtime seam does not establish image attachment support. |
| 2026-09-13 | Clarify P1/P3's picker, mode indicator, queue/steer distinction and directory recall. | Steward's ordinary workflow exposed hidden controls and session-only recall. |
| 2026-09-13 | Clarify P8's discoverable entry point. | The steward saw a question but could not find how to answer; known-label tests missed this. |
| 2026-09-12 | Add P8 for structured questions separate from approvals. | Continue the steward's parity request through an independent tool and host capability. |
| 2026-09-12 | Include correction and scoped provider selection in P1. | Continue the steward's ordinary-control parity request through actual module capabilities. |
| 2026-09-12 | Extend P1 to waiting work and local conversation organization. | Steward requested continued implementation toward the researched Codex experience. |
| 2026-09-12 | Specify bounded filename discovery and stale-result rejection in P4. | Extend accepted completion behavior without implied attachments or execution. |
| 2026-09-12 | Specify boundary-aware history and Tab precedence in P3–4. | Steward requested familiar editor/history/completion behavior. |
| 2026-09-12 | Draft discoverability, focus, rich input and functional workflow obligations. | [Reconciliation](../notes/INTERACTION-RECONCILIATION.md); steward rejected shortcut-first interaction and requested ecosystem viability. |

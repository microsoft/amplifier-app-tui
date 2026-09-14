# Discoverable interaction Contract — v1 (DRAFT)

Restores user-facing obligations from the supplied Codex/Amplifier studies and concept.
Parent: [presentation.v1](presentation.v1.md); execution authority stays in [session.v1](session.v1.md).

## Who builds against this

People learning the interface, composer/action builders, and host capability adapters.
The steward approves direction separately from ratifying this detailed wording.

## What it is

```text
visible action / searchable menu -> focused choice -> explicit activation
draft -> submit | queue | steer (distinct, capability-backed intentions)
decision(request_id, offered options) -> focused answer to that same request
questions(request_id, question_ids) -> local answers -> review -> explicit submit
completion / history preview -> accept locally | cancel back to original draft
```

This describes the destination, not a claim that every interaction is implemented.
[Reconciliation](../notes/INTERACTION-RECONCILIATION.md) records source and adoption decisions.

## The promises

1. **Make ordinary actions discoverable.** Send, queue management, active correction, provider selection, stop, decisions, evidence, conversation naming/search/copy and navigation have visible, keyboard-focusable paths; shortcuts are optional accelerators.
   Resume without an explicit identity offers a picker. Queue-next-turn and steer-current-turn are distinguishable beside the composer; the active mode remains visible outside menus.
   Broken: A person needs a memorized Ctrl chord to complete the ordinary workflow, or a displayed action cannot be reached by keyboard.
   Affected: new users and people who cannot use a mouse.

2. **Give focus one owner.** Menu, decision and editor input have explicit precedence; Escape dismisses local interaction without sending or losing a draft.
   Broken: Enter both chooses an action and submits text, or arriving activity steals a keystroke intended for the composer.
   Affected: people writing corrections while tools and decisions arrive.

3. **Preserve rich input intent.** Up/Down recall history only at editor line boundaries and restore the draft on return; supported references retain meaning, and text recall never invents missing attachments.
   Recall includes same-directory submissions without importing model context. Explicit text-file snapshots disclose path/digest and preview before insertion; external editing returns to an unsent draft and preserves it on failure. Unsupported media are refused, not silently converted.
   Broken: A visually intact draft submits a corrupted reference or missing attachment, or cancelled history recall destroys the original draft.
   Affected: people assembling and recalling instructions; durable retention belongs to continuity.v1.

4. **Keep completion local until accepted.** Tab completes eligible queries before moving focus; bounded workspace-path suggestions read names, not contents, preserve neighbors, and discard stale replies after editing, dismissal or conversation changes.
   Broken: Opening, filtering or dismissing a menu sends a model request or rewrites unrelated draft content.
   Affected: people discovering commands or completing references without executing them.

5. **Make decisions scoped and stable.** Show the runtime's actual options and action; focus and answers retain the original request identity, including when another request arrives or resolves.
   Broken: Fixed yes/no controls invent scope, a later request replaces the focused question, or stale activation answers a new request.
   Affected: the person granting permission and modules waiting for an answer.

6. **Explain usable capabilities.** Actions and catalogs distinguish available controls, mounted tools and authored definitions; unsupported intentions have reasons, never simulated success.
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

A mandated Codex keymap, a new runtime permission vocabulary, or a claim of complete CLI policy parity.
Queue, steer, resume and delegation are enabled only with their session/ecosystem obligations.

## How the kit checks it

Use actual PTY keyboard and mouse input, including menus during streaming and stale decisions.
Compare sent requests with the preserved draft and original option/request identities.
Exercise both ecosystem presets separately from simulations and deterministic provider fixtures.
Record missing rich-input/continuity behavior as gaps, not implicit acceptance.

## Open questions

Which reference/attachment types should the first rich composer support?
Which CLI discovery and provider-selection policies should be adopted for ordinary startup?

## Changelog

| Date | Change | Evidence |
|---|---|---|
| 2026-09-13 | Define P3's explicit text snapshots and external editing. | Steward authorized composer work; the current string-only runtime seam does not establish image attachment support. |
| 2026-09-13 | Clarify P1/P3's picker, mode indicator, queue/steer distinction and directory recall. | Steward's ordinary workflow exposed hidden controls and session-only recall. |
| 2026-09-13 | Clarify P8's discoverable entry point. | The steward saw a question but could not find how to answer; known-label tests missed this. |
| 2026-09-12 | Add P8 for structured questions separate from approvals. | Continue the steward's parity request through an independent tool and host capability. |
| 2026-09-12 | Include correction and scoped provider selection in P1. | Continue the steward's ordinary-control parity request through actual module capabilities. |
| 2026-09-12 | Extend P1 to waiting work and local conversation organization. | Steward requested continued implementation toward the researched Codex experience. |
| 2026-09-12 | Specify bounded filename discovery and stale-result rejection in P4. | Extend accepted completion behavior without implied attachments or execution. |
| 2026-09-12 | Specify boundary-aware history and Tab precedence in P3–4. | Steward requested familiar editor/history/completion behavior. |
| 2026-09-12 | Draft discoverability, focus, rich input and functional workflow obligations. | [Reconciliation](../notes/INTERACTION-RECONCILIATION.md); steward rejected shortcut-first interaction and requested ecosystem viability. |

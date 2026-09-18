# Return and retained intent Contract — v1 (DRAFT)

Proposed boundary derived from the implementation handoff.
Parent: [composition.v1](composition.v1.md).

## Who builds against this

The conversation store, host and returning person, independent of frontend or process topology.
The steward reviews this wording independently of implementation progress.

## What it is

```text
save -> conversation identity + cwd + composition + admitted history + draft
restore -> historical view
explicit new submission -> new execution
decision -> provenance + correction history
```

The example describes a boundary, not a claim that every feature is implemented.
Acceptance evidence lives in [the acceptance notes](../notes/ACCEPTANCE.md).

## The promises

1. **Retain identity.** Resume restores conversation, working directory, composition identity, explicit conversation-provider selection and canonical context before accepting work; incompatible or uncertain checkpoints or control state refuse execution explicitly. A drained interrupted turn with validated canonical state can resume under the same identity without claiming completion or replaying work; unverified execution or missing tool outcomes still require explicit recovery.
   Explicit child continuation verifies its parent, reconstructed non-routing composition and inherited mode; completed or drained interrupted canonical state may continue, while uncertain state refuses. Explicit routing changes follow CLI preference precedence, retain identity and expose unresolved fallback; inspection never starts work. Nested continuation requires its actual parent active and never starts ancestors implicitly.
   Broken: Resuming into an unintended directory breaks the returning person's task.
   Affected: the boundary's clients and the person relying on them.

2. **Retain intent.** Drafts and queued inputs survive closing with their admission state; explicit conversation switching saves the source draft, and failed target preparation preserves the current conversation.
   Unsent answer/correction and other dialog editors retain source identities separately from canonical context; recovery offers inspection/copy, never automatic delivery or retargeting. The interface discloses the autosave interval and does not claim unflushed keystrokes are crash-durable.
   Broken: An unsent input becoming submitted on return violates intent.
   Affected: the boundary's clients and the person relying on them.

3. **Replay only observations.** History reconstruction never invokes a tool, provider or approval.
   Explicit CLI-session discovery/import preserves source bytes and distinguishes historical reference from supported executable adoption; neither silently replays tools or changes the original session's policy. Structured public adoption validates tool pairing and exact context readback under a new identity; it never claims original private-state continuation.
   Broken: A repeated external effect during replay violates recovery.
   Affected: the boundary's clients and the person relying on them.

4. **Keep decisions attributable.** Retained decisions name their source and preserve later corrections.
   Broken: An invented or stale summary treated as user instruction violates provenance.
   Affected: the boundary's clients and the person relying on them.

5. **Separate stopping and undo.** Interruption records partial effects without claiming rollback. Explicit adoption of a captured nested child may reparent its public context to the current root only after validating complete recorded ancestry and unchanged effective policy; it never executes ancestors or implies continuation of their private state.
   An uncertain session remains inspectable/exportable. Explicit recovery creates a new identity with disclosed historical context, keeps the original intact and never replays unfinished tools or releases queued work. Supported structured recovery preserves observed tool identities, labels absent outcomes unknown and requires acknowledgement; unavailable module-private state is never invented. An explicitly adopted public-context child continuation uses a new identity and new instruction, retains verified completed tool results, and marks missing outcomes unknown without executing their calls. Unsupported private-state requirements refuse before execution. A supported persistent context is adopted only into a fresh isolated store with exact public-message readback; relocation is explicit and never overwrites the original module transcript.
   Broken: A cancelled operation presented as undone misstates workspace state.
   Affected: the boundary's clients and the person relying on them.

## Not in v1

A promise that arbitrary remote tools can be interrupted or that every process survives host exit.

## How the kit checks it

Close and reopen with drafts, pending input and partial work; count backend operations during replay.
The document check validates shape and links; runtime tests supply behavior evidence.
Draft contracts do not seed formal Converge ledger rows.

## Open questions

Which durable admission record separates accepted, applied and uncertain input after a boundary failure?
How does a replacement context manager preserve canonical history independently of request compaction?

## Changelog

| Date | Change | Evidence |
|---|---|---|
| 2026-09-17 | Distinguish P1's safe root/child interruption from uncertain persistence and permit explicit routing-aware child continuation. | The CLI parity audit identifies refusals based solely on child outcome or changed routing; execution ownership, canonical validation and non-routing policy must decide resumability. |
| 2026-09-15 | Clarify P3's cross-application continuity. | Steward approved CLI migration work; a separate TUI catalog and text import are not equivalent resume. |
| 2026-09-15 | Distinguish explicitly reparented nested public adoption from same-identity continuation in P5. | Steward authorized deeper recovery; a captured nested self-agent can have root-equivalent policy without requiring ancestor execution. |
| 2026-09-15 | Clarify P5's fresh-store persistent public-context adoption. | Inspected persistent module intentionally ignores set_messages after loading its own transcript; changing an existing store would not implement recovery. |
| 2026-09-15 | Clarify P5's explicit executable public-context child recovery. | Steward requested actual interrupted-work recovery; historical inspection remains distinct from a newly authorized execution. |
| 2026-09-14 | Extend P2's source-scoped retention to other local dialog editors. | Steward authorized crash-edge editor work; queue edits, file selectors and searches currently disappear when their dialog closes. |
| 2026-09-14 | Clarify structured recovery's uncertainty in P5. | Steward requested interrupted-context and delegated recovery; replaying incomplete calls or inferring successful effects would violate retained intent. |
| 2026-09-14 | Clarify P1's nested-parent and routing preservation. | Steward authorized deeper delegated continuity; durable child records must not become implicit ancestor execution. |
| 2026-09-13 | Specify P1's guarded completed-child continuation. | Steward requested durable delegated workflows; existing receipts retain context but lose executable composition across restart. |
| 2026-09-13 | Clarify P2's retained answer/correction drafts and non-delivery on recovery. | Steward authorized daily-replacement work; these editors currently exist only in client memory. |
| 2026-09-13 | Clarify P5's non-destructive recovery path. | Stop left the steward's journal intact but inaccessible through ordinary resume. |
| 2026-09-12 | Include explicit provider selection and uncertain control state in P1. | A resumed conversation must not silently return to priority selection after an explicit pin. |
| 2026-09-12 | Extend P2 to explicit in-app return without draft loss. | Steward's continuation of the accepted reading/return slice. |
| 2026-09-12 | Clarify canonical context and fail-closed checkpoints in P1. | Steward requested functional conversation resume, not transcript-only redisplay. |
| 2026-09-12 | Initial draft; no ratification claimed. | Supplied handoff and current source inspection. |
| 2026-09-12 | Clarify readers and open questions for replacement runtimes; promises unchanged. | [Direction amendment](../notes/DIRECTION-REVIEW.md); continuation must not depend on frontend lifetime. |

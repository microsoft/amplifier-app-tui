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

1. **Retain identity.** Resume restores conversation, working directory, composition identity, explicit conversation-provider selection and canonical context before accepting work; incompatible or uncertain checkpoints or control state refuse execution explicitly.
   Explicit completed-child continuation verifies its parent, reconstructed composition and inherited mode; inspection alone never starts it, and unsupported or interrupted child records refuse execution.
   Broken: Resuming into an unintended directory breaks the returning person's task.
   Affected: the boundary's clients and the person relying on them.

2. **Retain intent.** Drafts and queued inputs survive closing with their admission state; explicit conversation switching saves the source draft, and failed target preparation preserves the current conversation.
   Unsent answer/correction editors retain source identities separately from canonical context; recovery offers inspection/copy, never automatic delivery or retargeting.
   Broken: An unsent input becoming submitted on return violates intent.
   Affected: the boundary's clients and the person relying on them.

3. **Replay only observations.** History reconstruction never invokes a tool, provider or approval.
   Broken: A repeated external effect during replay violates recovery.
   Affected: the boundary's clients and the person relying on them.

4. **Keep decisions attributable.** Retained decisions name their source and preserve later corrections.
   Broken: An invented or stale summary treated as user instruction violates provenance.
   Affected: the boundary's clients and the person relying on them.

5. **Separate stopping and undo.** Interruption records partial effects without claiming rollback.
   An uncertain session remains inspectable/exportable. Explicit recovery creates a new identity with disclosed historical context, keeps the original intact and never replays unfinished tools or releases queued work.
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
| 2026-09-13 | Specify P1's guarded completed-child continuation. | Steward requested durable delegated workflows; existing receipts retain context but lose executable composition across restart. |
| 2026-09-13 | Clarify P2's retained answer/correction drafts and non-delivery on recovery. | Steward authorized daily-replacement work; these editors currently exist only in client memory. |
| 2026-09-13 | Clarify P5's non-destructive recovery path. | Stop left the steward's journal intact but inaccessible through ordinary resume. |
| 2026-09-12 | Include explicit provider selection and uncertain control state in P1. | A resumed conversation must not silently return to priority selection after an explicit pin. |
| 2026-09-12 | Extend P2 to explicit in-app return without draft loss. | Steward's continuation of the accepted reading/return slice. |
| 2026-09-12 | Clarify canonical context and fail-closed checkpoints in P1. | Steward requested functional conversation resume, not transcript-only redisplay. |
| 2026-09-12 | Initial draft; no ratification claimed. | Supplied handoff and current source inspection. |
| 2026-09-12 | Clarify readers and open questions for replacement runtimes; promises unchanged. | [Direction amendment](../notes/DIRECTION-REVIEW.md); continuation must not depend on frontend lifetime. |

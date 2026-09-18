# Return and retained intent Contract — v1 (DRAFT)

Proposed boundary derived from the implementation handoff. Parent: [composition.v1](composition.v1.md).

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

3. **Replay only observations.** History reconstruction and exports never invoke a tool, provider or approval. Explicit turn branching creates a new identity with validated captured public context and disclosed private-state exclusions; clearing active context preserves identity/history and records that prior effects remain. Neither operation replays work or dispatches held input. Confirmed archival hides a closed conversation from ordinary return without deleting its history; explicit restore reverses that choice within its original directory.
   Ordinary CLI-compatible return discovers the shared project session store and continues the same canonical transcript and identity in either client, without import or implicit execution. TUI display/draft sidecars are not a second context authority; external advances invalidate stale projections and controls. Writer conflicts and unsupported private state refuse explicitly. Historical import/adoption remains an explicit new-identity operation, never a substitute for ordinary resume.
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

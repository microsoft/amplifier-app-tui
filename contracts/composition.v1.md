# Composition and ownership Contract — v1 (DRAFT)

Proposed boundary derived from the implementation handoff.
Parent: [vision](../docs/VISION.md).

## Who builds against this

The application host, terminal and headless clients, and independent bundle authors.
The steward reviews this wording independently of implementation progress.

## What it is

```text
conversation -> session boundary -> composed runtime -> kernel + modules
conversation -> presentation boundary -> terminal
conversation -> continuity boundary -> retained intent and evidence
same public behavior -> replaceable frontend, host, transport and modules
```

The example describes a boundary, not a claim that every feature is implemented.
Acceptance evidence lives in [the acceptance notes](../notes/ACCEPTANCE.md).

## The promises

1. **Respect the seam.** Clients consume identified operations and events, not runtime internals; the seam need not be a process.
   Broken: Changing a widget changes tool authority, or a language boundary becomes mandatory without evidence.
   Affected: client builders and people relying on predictable execution.

2. **Keep policy replaceable.** Execution and context policy stay in the chosen modules.
   Broken: An independent tool needing a TUI import breaks ecosystem compatibility.
   Affected: the boundary's clients and the person relying on them.

3. **Name composition changes.** Every host exclusion or overlay is visible with the effective composition.
   Broken: A missing authored hook with no recorded explanation misleads the operator.
   Affected: the boundary's clients and the person relying on them.

4. **Give each rule one home.** [Session](session.v1.md), [presentation](presentation.v1.md), [continuity](continuity.v1.md), [ecosystem](ecosystem.v1.md) and [performance](performance.v1.md) own their details.
   Broken: A second conflicting definition makes a client's obligations ambiguous.
   Affected: the boundary's clients and the person relying on them.

5. **Bound the responsibility.** This project has at most 600 contract lines and 55 production source files, regardless of language. The [connected-client boundary proposal](../notes/CONNECTED-CLIENT.md) accounts explicitly for five new client modules and proposes extracting the optional standalone host before further independent growth.
   Broken: Exceeding either or gaining a second domain with its own vocabulary and kit requires a split proposal.
   Affected: the boundary's clients and the person relying on them.

6. **Replace implementations, preserve obligations.** Frontend, host, adapters and policy modules may change without preserving their language or topology.
   Broken: A faster replacement silently removes a promised behavior or moves product policy into the thin kernel.
   Affected: ecosystem authors and people depending on the session contract.

## Not in v1

A prescribed wire protocol, mandatory sidecar, remote process supervision, and an operating-system sandbox.

## How the kit checks it

Inspect imports, composition reports, document links and file counts.
The document check validates shape and links; runtime tests supply behavior evidence.
Draft contracts do not seed formal Converge ledger rows.

## Open questions

Does a long-lived child process, in-process bridge or another host best satisfy the measured obligations?
Which lifecycle hook gives the host ownership before partial initialization can fail?

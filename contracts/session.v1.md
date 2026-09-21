# Session admission and outcomes Contract — v1 (DRAFT)

Proposed boundary derived from the implementation handoff.
Parent: [composition.v1](composition.v1.md).

## Who builds against this

The conversation controller and its terminal and headless clients.
The steward reviews this wording independently of implementation progress.

## What it is

```text
open(composition, cwd) -> readiness
operation(request_id, intent, payload) -> accepted(identity) | rejected(reason)
submit is one intent; queue, steer, stop and decision remain distinct
events -> session_id + sequence + turn_id + kind + item_id + payload
execute return + observed completion -> terminal outcome
```

The example describes a boundary, not a claim that every feature is implemented.
Acceptance evidence lives in [the acceptance notes](../notes/ACCEPTANCE.md).

## The promises

1. **Prepare real work.** Standalone readiness follows successful bundle preparation and required module mounts. A connected client distinguishes being connected and able to submit from the host runtime being prepared; execution and admission remain on that host.
   Broken: A missing provider, orchestrator, context or required exported tool shown ready breaks admission.
   Affected: the boundary's clients and the person relying on them.

2. **Admit one turn.** Standalone submission atomically accepts one idle turn or rejects it with a reason. Connected submission follows the host's admission policy and reports command acceptance separately from execution or insertion; the client never invents a local queue.
   Broken: Two racing submissions running together or a rejected draft disappearing breaks intent.
   Affected: the boundary's clients and the person relying on them.

3. **Identify observations.** Events carry conversation, turn and ordered sequence identities.
   Broken: Activity assigned to another turn breaks the account a person reads.
   Affected: the boundary's clients and the person relying on them.

4. **Report the actual ending.** Completion uses runtime evidence; failure, cancellation and unknown outcomes stay distinct.
   Broken: A returned string overriding an error or missing completion signal is false success.
   Affected: the boundary's clients and the person relying on them.

5. **Keep tools generic.** Tool activity retains call identity, arguments and observed result independently of prose.
   End-of-turn observations summarize tool failures and unknown outcomes separately from execution completion; neither counts as a verdict on task acceptance.
   Broken: A failed tool becoming green when an assistant finishes violates the result.
   Affected: the boundary's clients and the person relying on them.

6. **Expose supported controls.** Queue is distinct from steering: only successful completion advances an enabled queue; stop, failure and reopening hold pending work until explicit release. Steering names one active turn; acceptance is not proof of insertion, and unconfirmed corrections never retry or become follow-ups automatically. An explicit copy into an empty idle composer creates only an unsent draft, preserves the original correction status and warns that its earlier effects may remain unknown. Unsupported controls remain explicit.
   In standalone mode, first Stop signals graceful cancellation through active descendants, retains current model/tool results and prevents new work while delegates resolve upward. A second explicit Stop escalates to immediate cancellation without abandoning owned finalization; the current stage and force option remain visible. Graceful stopping never escalates on a timer.
   Broken: An offered control that silently discards intent misleads its caller.
   Affected: the boundary's clients and the person relying on them.

7. **Keep admission accountable across a boundary.** Requests and replies correlate; version/capability disagreement rejects explicitly, and uncertainty never retries a side effect silently.
   Broken: A disconnect duplicates work, a stale decision acts, or an unacknowledged request is reported accepted.
   Affected: people sending corrections and builders replacing a host or transport.

8. **Keep execution independent of painting.** A slow or disconnected view cannot stall controls or erase authoritative outcomes; cleanup covers startup, active work and exit.
   Repeated stop/exit requests do not cancel owned finalization or duplicate cleanup. A blocked local transport cannot trap the terminal; forced exit identifies its owned process boundary and reports uncertain effects, never completed module cleanup or rollback.
   Broken: A blocked renderer delays stop indefinitely, or partial initialization leaves an unowned live session.
   Affected: people controlling work and hosts responsible for resource cleanup.

## Not in v1

Durable intent and history belong to [continuity.v1](continuity.v1.md); module replacement belongs to [ecosystem.v1](ecosystem.v1.md).

## How the kit checks it

Exercise concurrent submits, real fixture tools, failed mounts, stream failure and unknown completion.
Inject delayed readers, startup failure, boundary loss and repeated request IDs; inspect acknowledgements and cleanup.
The document check validates shape and links; runtime tests supply behavior evidence.
Draft contracts do not seed formal Converge ledger rows.

## Open questions

Which request semantics belong in an adapter versus a replacement host without duplicating lifecycle ownership?
What terminal outcome can a host prove when a third-party operation ignores cancellation?

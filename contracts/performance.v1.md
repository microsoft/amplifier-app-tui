# Responsiveness and performance Contract — v1 (DRAFT)

How the terminal earns the claim that it feels at least as fast as the CLI.
Parent: [composition.v1](composition.v1.md); correctness remains in the other seam contracts.

## Who builds against this

People typing during execution, frontend and runtime builders, and reviewers choosing an architecture.
Targets below are proposed acceptance bounds, not measurements or claims of current performance.

## What it is

```text
matched CLI and candidate -> launch / ready / submit / first visible text / control response
key delivered -> visible edit; runtime event -> visible update
record = source pins + configuration + workload + terminal + samples + median + p95
p95 = time at or below which 95 percent of the observations finish
result = measured comparison | regression | insufficient evidence; never a guessed pass
```

The [benchmark protocol](../notes/PERFORMANCE.md) works these promises into experiments.
It does not grant permission to relax them after observing an inconvenient result.

## The promises

1. **Compare like work.** Record the actual CLI baseline and candidate pins, modules, configuration, terminal, hardware, workload and cache conditions before comparison.
   Broken: Different models, missing hooks, warmed caches or shorter history account for an apparent frontend improvement.
   Affected: reviewers deciding whether a replacement improves the experience.

2. **Be no slower on the common path.** Comparable startup-to-ready, submit-to-first-visible-text and local control latency show no median or p95 regression beyond declared measurement uncertainty.
   Broken: The candidate exceeds the matched CLI result, or a cold/warm or provider-delay difference is hidden in a single average.
   Affected: people expecting the TUI to be at least as responsive as the CLI.

3. **Keep local interaction immediate.** Under the declared stress scenes, key-to-visible-edit and event-to-visible-update each stay at or below 50 ms p95.
   Broken: Typing or visible progress crosses the bound during a stream, an approval, a resize or long-history inspection.
   Affected: people composing and inspecting work; passing this bound does not excuse a regression under promise 2.

4. **Do not buy throughput with lost meaning.** Display updates may be coalesced, but admission, decisions, results and terminal outcomes remain identifiable and intact.
   Broken: Dropped events, hidden failures or reordered controls make a benchmark faster by changing what happened.
   Affected: people trusting the visible account and builders reconstructing it.

5. **Bound work on the interactive path.** Declare resource budgets; render and transport queues stay bounded without resending or rebuilding the whole history for every token.
   Broken: A slow consumer creates unbounded pending display work, or elapsed time grows with full-history processing per delta.
   Affected: people using long conversations and hosts sharing machine resources.

6. **Make topology earn its cost.** Select a process boundary, in-process bridge or replacement host only with measured integrated results and lifecycle evidence.
   Broken: A fast isolated renderer or an assumed negligible IPC cost is offered as proof of the complete application's performance.
   Affected: maintainers choosing how to package and operate the runtime.

7. **Report uncertainty honestly.** Preserve samples, repeatable commands and separated runtime/provider/render timings; unknown or noisy comparisons are not passes.
   Broken: A single live request, invented CLI numbers or unrepeatable timing supports a performance claim.
   Affected: the steward relying on evidence before committing to an architecture.

## Not in v1

A guaranteed provider/network response time, a mandated transport, a universal frame-rate target,
or an automatic performance claim from changing implementation language.

## How the kit checks it

Run paired baseline/candidate workloads with separate fresh-process cold and warm reports.
Capture input delivery and actual terminal updates, including long-history and slow-consumer cases.
Retain raw timing samples and policy/configuration equivalence; re-run the behavioral suite too.
No benchmark exists merely because a document-shape test passes.

## Open questions

What measured CLI/runtime build and terminal configuration reproduce the steward's daily baseline?
What practical resource budgets and measurement uncertainty does the first controlled baseline establish?

## Changelog

| Date | Change | Evidence |
|---|---|---|
| 2026-09-12 | Draft matched CLI non-regression, interactive latency and evidence gates without fixing a process topology. | [Steward authorization](../notes/DIRECTION-REVIEW.md): at least CLI-level responsiveness; the 50 ms target is new draft wording. |

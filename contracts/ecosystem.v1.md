# Ecosystem replacement Contract — v1 (DRAFT)

The supported behavior that survives replacing an implementation.
Parent: [composition.v1](composition.v1.md); lifecycle belongs to [session.v1](session.v1.md).

## Who builds against this

Bundle and module authors, host builders, and people choosing their runtime composition.
This contract protects independent parts, not a particular frontend language or host class.

## What it is

```text
anchors / anchors-amp-dev + explicit overlays -> effective composition
orchestrator | context | provider | tool | hook -> independent extension seams
replacement -> observed capability + conformance evidence + named limitations
declared -> resolved -> prepared -> mounted -> usable (different observations)
```

No row in an implementation report implies every extension has been verified.
Receipts live in [acceptance notes](../notes/ACCEPTANCE.md), not in this contract.

## The promises

1. **Keep both presets meaningful.** anchors and anchors-amp-dev resolve their recursive definitions and expose the capabilities the host actually supports.
   Installed launch resolves supported presets without workspace checkouts, names its version and storage, and never silently substitutes the historical UI or imports shared CLI state.
   Broken: A preset name loads a hard-coded lookalike, or agent instructions imply a running external service.
   Affected: people selecting bundles and authors composing them.

2. **Honor composition policy.** Selected sources, overlays, provider selection and effective configuration remain attributable; exclusions and incompatibilities are explicit. Conversation-provider changes use a supported module capability while idle, retain its compatibility guards, and disclose whether other routing is unaffected.
   Mode changes retain transition/tool guards and their durable state. Local capture, remote dispatch, observed context usage and unavailable diagnostics are disclosed separately.
   Broken: A replacement silently omits a policy hook or substitutes a provider to make a demonstration work.
   Affected: operators relying on the configured behavior and its provenance.

3. **Preserve independent extension seams.** Orchestrator, context, provider, tool and hook remain replaceable without importing the terminal frontend.
   Broken: An otherwise conforming module needs a screen-specific wrapper to express its ordinary results or policy.
   Affected: module authors and people assembling their own runtimes.

4. **Keep generic modules useful.** Unknown tools retain structured arguments, results and failures through the generic presentation path.
   Broken: A tool without a custom renderer disappears, loses its error, or becomes an unsupported operation solely for its appearance.
   Affected: authors extending the ecosystem independently of this project.

5. **Do not trade policy for speed.** Replacements preserve approvals, cancellation semantics, context obligations and state isolation on the supported path.
   Broken: A faster benchmark skips enforcement, loses conversation context or shares another session's state.
   Affected: people trusting the runtime with real work.

6. **Prove the replacement, not just the mount.** Conformance includes an exercised swap at each extension seam and live-provider evidence separate from deterministic fixtures.
   Supported delegation and agent-bearing recipes expose real child progress, waiting reasons and inspectable scoped evidence with inherited policy, cancellation and cleanup; restored observations never imply a live child.
   Broken: Import success or a returned string is presented as full compatibility, or a test double is called an independently implemented alternative.
   Affected: maintainers deciding whether a replacement can ship.

## Not in v1

Universal compatibility with every historical extension, identical CLI private internals,
an OS sandbox, or a requirement to retain Foundation PreparedBundle as the host implementation.

## How the kit checks it

Resolve both pinned preset graphs; inspect actual mounts and exercise supported operations.
Swap one independently implemented component at each seam without editing frontend code.
Inject missing hooks, unknown tools and provider failures; compare controls, context and results.
Record exclusions, unsupported paths and untested modules rather than upgrading them to a pass.

## Open questions

Which independent context/orchestrator implementations best probe the first replacement host?
Which authored CLI policies need explicit TUI equivalents rather than configuration reuse?

## Changelog

| Date | Change | Evidence |
|---|---|---|
| 2026-09-13 | Extend P1 to installable native launch and identifiable storage/runtime. | Steward requested uv tool install from private Git; current launcher depends on sibling checkouts and a separately built binary. |
| 2026-09-13 | Clarify P2/P6's context diagnostics and child visibility. | Steward authorized replacement-readiness work; generic child rows hide progress and waiting scope. |
| 2026-09-13 | Extend P2/P6 to mode continuity, logging scope and exercised children. | Real preset delegation and recipe execution failed at missing app-owned session.spawn. |
| 2026-09-12 | Specify scope and policy-preserving provider changes in P2. | The selected orchestrator supplies a conversation-only pin with a same-vendor guard; UI selection must not bypass it. |
| 2026-09-12 | Draft the behavioral boundary for replacing hosts and modules while retaining the ecosystem. | [Steward authorization](../notes/DIRECTION-REVIEW.md); first-slice mounting did not establish full conformance. |

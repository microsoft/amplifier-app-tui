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
   Amplifier dependency declarations and default source references follow canonical main; qualification records the resolved revisions without turning them into update policy. Supported release wheels include the native client without requiring a local compiler. Connected launch uses the Unified service and its configured runtime; standalone live conversations use the CLI session format and existing CLI configuration and explicit isolated policy selects its own Amplifier home. CLI workflow and required bundle/module host-service parity is the baseline, with additive TUI capabilities and named gaps until verified. Launch resolves presets without workspace checkouts and never silently substitutes a historical UI. Local checks explain blockers without mounting modules; shareable diagnostics omit credentials, paths and conversation content and do not imply live readiness.
   Broken: A preset name loads a hard-coded lookalike, or agent instructions imply a running external service.
   Affected: people selecting bundles and authors composing them.

2. **Honor composition policy.** Selected sources, overlays, provider selection and effective configuration remain attributable; exclusions and incompatibilities are explicit. Conversation-provider changes use a supported module capability while idle, retain its compatibility guards, and disclose whether other routing is unaffected. Shared control formats remain owned by their portable app-layer contract and participating module adapters. Unknown required control state blocks execution rather than resetting policy; read-only history stays available. Preserving unknown metadata does not establish support for applying it, and proposals are not implemented capabilities.
   Mode changes retain transition/tool guards and durable state; model discovery is advisory, not selection or credential validation. CLI-compatible composition preserves app behaviors, root instructions, named providers, module overrides, permissions and declared service/storage policy; terminal-only exclusions name replacements. Provider-owned authentication is reused without copying credentials. Local capture, remote dispatch, usage, public effective budget and unavailable occupancy remain distinct.
   Broken: A replacement silently omits a policy hook, treats offline credential checks as remote validation, or bypasses compatibility guards; explicit conversion must preserve the original and require adoption.
   Affected: operators relying on the configured behavior and its provenance.

3. **Preserve independent extension seams.** Orchestrator, context, provider, tool and hook remain replaceable without importing the terminal frontend.
   Broken: An otherwise conforming module needs a screen-specific wrapper to express its ordinary results or policy.
   Affected: module authors and people assembling their own runtimes.

4. **Keep generic modules useful.** Unknown tools retain structured arguments, results and failures through the generic presentation path. Legacy terminal output has bounded, redacted private inspection without interpreting escape controls, guessing child ownership or promoting logs to tool outcomes; retention, redaction limits and unavailable capture are explicit.
   Broken: A tool without a custom renderer disappears, loses its error, or becomes an unsupported operation solely for its appearance.
   Affected: authors extending the ecosystem independently of this project.

5. **Do not trade policy for speed.** Replacements preserve approvals, cancellation semantics, context obligations, host goal-loop safety backstops and state isolation on the supported path. Interactive approval uses actual host capability, not terminal-stdin heuristics; diagnostics cover every configured provider through bounded explicit operations.
   Broken: A faster benchmark skips enforcement, loses conversation context or shares another session's state.
   Affected: people trusting the runtime with real work.

6. **Prove the replacement, not just the mount.** Conformance includes an exercised swap at each extension seam and live-provider evidence separate from deterministic fixtures.
   Supported delegation and agent-bearing recipes, including explicit subprocess children, preserve approvals, questions, scoped progress, nested work, cancellation and cleanup; lost workers never imply safe continuation. Display/context cache limits do not cap execution counts; capacity waits are cancellable and independent across parent branches, preserving module-owned self-delegation depth.
   Broken: Import success or a returned string is presented as full compatibility, or a test double is called an independently implemented alternative.
   Affected: maintainers deciding whether a replacement can ship.

## Not in v1

Universal compatibility with every historical extension, identical CLI private internals,
an OS sandbox, or a requirement to retain Foundation PreparedBundle as the host implementation.

## How the kit checks it

Resolve both current preset graphs; inspect actual mounts and exercise supported operations.
Swap one independently implemented component at each seam without editing frontend code.
Inject missing hooks, unknown tools and provider failures; compare controls, context and results.
Record exclusions, unsupported paths and untested modules rather than upgrading them to a pass.

## Open questions

Which independent context/orchestrator implementations best probe the first replacement host?
Which remaining CLI-private controls need shared app-layer persistence to make switching lossless? Named incompatible state must not be presented as supported same-identity continuation.

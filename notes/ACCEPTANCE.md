# Current acceptance evidence

## Canonical sessions

All live TUI launches use the CLI project/session format under the selected Amplifier
home. Ordinary launch shares CLI configuration; explicit isolated policy uses its
own home without creating a different live-session format. TUI drafts, observations
and controls remain namespaced sidecars. Deterministic fixture journals are private
test infrastructure, not a supported user-session migration or compatibility path.

The actual-entrypoint probe passes CLI → native startup Resume picker → CLI → native
resume, retaining the same identity and explicit conversation turns. It also passes
new ordinary TUI → CLI, plus explicit isolated-composition TUI start/resume using the
same canonical format. Laptop 175×50, narrow 40×20 and custom-composition 80×30 paths
use real app/core/modules and deterministic provider/tool fixtures. Resume performs
no implicit provider/tool call; original transcript bytes and terminal modes survive.

Run `scripts/shared_session_probe.py` as documented in [SMOKE_TESTS](../SMOKE_TESTS.md).
Raw captures/logs/settings stay private. This is actual-entrypoint verification,
not a paid-model, personal-account, latency-parity or arbitrary private-state claim.

## Current checks

The focused shared-session/direction/entrypoint corpus passes **67 tests** (9.09s).
Coverage includes no-fallback discovery, canonical storage for explicit policy,
metadata-only housekeeping, same-ID history/configuration, unknown metadata,
external names, canonical-digest invalidation, private drafts and graceful-stop return.
Four independent loop/context combinations retain module-owned system history
without putting it in the public CLI transcript. These are module/store tests,
not an assertion that every persistent-context entrypoint configuration is verified.

The default Python suite passes **652 tests, 318 opt-in skips** (139.45s), recorded
privately in `.evidence/shared-only-default.xml`. The actual-entrypoint round-trip
probe, including explicit isolated composition, passes. No Rust renderer code is
changed by this work. Ruff lint/format and direction/archive integrity checks pass.
The native navigation/session/shared-store gate passes **44 tests** (22.19s), with
private receipt `.evidence/shared-only-native.xml`.
[SMOKE_TESTS](../SMOKE_TESTS.md) owns additional opt-in preset, terminal, service,
module-swap and installed-artifact gates. Overlapping suites are not additive counts.
No user transcript or account is a synthetic test fixture.

## Reading and presentation

Current source comparison is in [MARKDOWN-GAPS](MARKDOWN-GAPS.md). Structural list
wrapping, block separation, quote continuation and link presentation remain real
gaps. This pass investigates them; it does not claim a Markdown renderer fix.
Existing strong/emphasis/code/table parsing is not proof of complete layout parity.

## Remaining boundaries

- Close one client before opening the same session in the other. The current CLI
  does not honor a lifetime writer lease; TUI stale-write refusal is not atomic
  cross-client exclusion.
- Interrupted shared sessions fail closed. Recovery must retain originals and
  unknown effects; the canonical recovery workflow is not yet implemented.
- Native pins/modes/goals/held input/child controls are not a common CLI private-state
  format. Unsupported state must refuse rather than silently disappear.
- Earlier CLI costs are not imported yet. Available event receipts are the source
  for future accounting; estimates or transcript-token guesses are not substitutes.
- Canonical loading is bounded to 10,000 messages / 8 MiB. Broader module-private
  state and actual-entrypoint persistent-context combinations need separate checks.
- Real provider authorization, personal service destinations and physical devices
  are not certified by fixtures. Policy differences prevent a default CLI latency
  parity claim.

## Released artifacts versus this source

[Release v0.3.0rc6](https://github.com/bkrabach/amplifier-app-tui/releases/tag/v0.3.0rc6)
has verified Linux x86-64/ARM64 and macOS Intel/ARM wheels and paired receipts.
Its source is `840ae1682d05cd9dbab663e9a1d79dfce97a2585`; that release predates shared
canonical sessions. The current checkout and its development launcher contain the
shared implementation; existing release wheels do not acquire checkout changes.
No new wheel/release is claimed by the current source checks.

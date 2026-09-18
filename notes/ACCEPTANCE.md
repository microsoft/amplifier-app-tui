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

Coverage includes no-fallback discovery, canonical storage for explicit policy,
metadata-only housekeeping, same-ID history/configuration, unknown metadata,
external names, canonical-digest invalidation, private drafts and graceful-stop return.
Four independent loop/context combinations retain module-owned system history
without putting it in the public CLI transcript. These are module/store tests,
not an assertion that every persistent-context entrypoint configuration is verified.

The default Python suite passes **662 tests, 321 opt-in skips**, recorded
privately in `.evidence/shared-reading-default.xml`. Rust renderer/native tests pass
**70 tests**, with release build and strict Clippy clean. Ruff lint/format and
direction checks pass. The mixed-reading terminal and accounting corpus passes
**19 tests** (11.07s), including exact source copy and retained draft at 40/80/175
columns. The CLI owner tests pass **2353 tests**, with one skip and one expected
failure; its resume-list fix has synthetic store and actual Click coverage.
The focused native reading, tmux, shared-store and flow gate passes **71 tests,
7 preset-gated skips** (55.02s), privately recorded in
`.evidence/shared-reading-native.xml`.
After the CLI pin update, **77 tests** pass with native/preset gates enabled
(42.35s), including resolver comparison, shared return, actual entrypoint workflows,
usage scope/recovery and Activity preview/copy; receipt `.evidence/shared-reading-pin.xml`.
Thirty warm simulated decision/resize samples measure decision-open p95 **12.4 ms**,
shrink-to-80-column p95 **18.4 ms** and grow-to-175-column p95 **51.8 ms**. Draft and
pending decision survive; no provider or CLI latency parity is inferred. Private
receipt `.evidence/shared-reading-experience.json` includes source hashes and samples.
[SMOKE_TESTS](../SMOKE_TESTS.md) owns additional opt-in preset, terminal, service,
module-swap and installed-artifact gates. Overlapping suites are not additive counts.
No user transcript or account is a synthetic test fixture.

## Reading and presentation

Current source comparison is in [MARKDOWN-GAPS](MARKDOWN-GAPS.md). Structural list
wrapping, loose/tight spacing, quote continuation and heading hierarchy have mixed
block coverage. Journal streaming is compared with the complete styled projection
at every character boundary at 40/80/175 columns. Native terminal captures were
inspected at laptop and narrow widths. HTML-entity-decoded controls remain inert.
Links suppress only exact label/destination duplication; no OSC hyperlinks or blind
URL hiding are claimed. Original Markdown and code copy remain unchanged.

## Recorded accounting and CLI discovery

Historical root, child and utility usage comes from canonical event receipts plus
identified native observations. Explicit metadata/fork ancestry determines child
ownership. Kernel receipt identity joins observers, never token-value equality or
time proximity. Imported receipts seed Session, not the next Turn, and remain
inspectable in Activity. Reopening does not duplicate totals or canonical bytes.
Missing, conflicting, oversized and uncorrelated sources produce partial accounting.
The actual CLI/TUI round-trip probe mounts hooks-logging, reconciles exact synthetic
reported costs and uses a mixed Markdown answer without paid model calls.

CLI discovery requires a saved transcript, retaining log-only diagnostics on disk.
Resume lists label their nonblank transcript-line counts as messages, not user turns.
The app pins tested CLI commit `e2f665137189b48dca1f8778c24f23aa25fddc60`.
[CLI PR346](https://github.com/microsoft/amplifier-app-cli/pull/346) passes all eight
Linux/macOS/Windows unit/integration CI jobs and CLA. Normal reviewer approval is
still required; the pin includes the fix without claiming it is merged into CLI main.

## Remaining boundaries

- Close one client before opening the same session in the other. The current CLI
  does not honor a lifetime writer lease; TUI stale-write refusal is not atomic
  cross-client exclusion.
- Interrupted shared sessions fail closed. Recovery must retain originals and
  unknown effects; the canonical recovery workflow is not yet implemented.
- Native pins/modes/goals/held input/child controls are not a common CLI private-state
  format. Unsupported state must refuse rather than silently disappear.
- Historical accounting is bounded to 512 directory metadata candidates, 128 event
  logs / 64 MiB and 10,000 receipts. Gaps are disclosed; unavailable costs are never
  estimated from transcript tokens or model prices.
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

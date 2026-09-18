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

The default Python suite passes **664 tests, 327 opt-in skips** (139.84s), recorded
privately in `.evidence/viewport-default.xml`. Rust renderer/native tests pass
**72 tests**, with release build and strict Clippy clean. Ruff lint/format and
direction checks pass. The expanded structured-reading, thinking/activity, flow,
compact geometry, tmux and capture-observer gate passes **56 tests** (67.99s),
recorded in `.evidence/viewport-native.xml`.
It includes exact source copy and retained drafts at 40/80/175 columns, with heading
attributes verified directly from terminal cells in both colour and NO_COLOR modes.
Shared store/usage/bridge checks pass **58 tests**.
The actual-entrypoint round-trip probe also checks the visible reconciled On resume
total at laptop and narrow widths, without executing user history.
The CLI owner tests passed **2353 tests**, with one skip and one expected failure;
its merged resume-list fix has synthetic store and actual Click coverage.
Responsiveness evidence lives in [PERFORMANCE](PERFORMANCE.md); these reading
checks do not establish provider or CLI latency parity.
[SMOKE_TESTS](../SMOKE_TESTS.md) owns additional opt-in preset, terminal, service,
module-swap and installed-artifact gates. Overlapping suites are not additive counts.
No user transcript or account is a synthetic test fixture.

## Reading and presentation

Current source comparison is in [MARKDOWN-GAPS](MARKDOWN-GAPS.md). Structural list
wrapping, loose/tight spacing, quote continuation and heading hierarchy have mixed
block coverage. All six ATX heading levels and setext headings use typography and
spacing without source delimiters; cyan contrast and underlined H1/H2 do not rely
solely on a perceptible bold face. NO_COLOR retains the underlines, and expanded
thinking remains secondary. Escaped hashes and code retain their literals.
Soft breaks inherit their text style, including multiline setext headings. Journal
streaming is compared with the complete styled projection at every character boundary
at 40/80/175 columns. Native terminal captures were inspected at laptop and narrow
widths. HTML-entity-decoded controls remain inert.
Links suppress only exact label/destination duplication; no OSC hyperlinks or blind
URL hiding are claimed. Original Markdown and code copy remain unchanged.

The current terminal gate passes **56 tests** (67.99s), recorded privately in
`.evidence/viewport-native.xml`: structured reading, thinking/activity, flow, compact
geometry, real tmux and capture-observer tests. The raster adapter uses actual bold/
italic faces plus underline/strike and preserves reverse video and hidden cursors.
PNG sidecars identify reference-font reconstructions, not the user's terminal pixels.
Separate actual VTE 0.76 screenshots on an owned virtual display compare native TUI
and interactive CLI at 175×50 with the same synthetic canonical conversation.
Those images show the heading contrast/typography in that emulator and font; they
do not establish the user's local presentation or every terminal's glyph fallback.

Startup uses the observed launch cursor instead of archiving a full empty screen.
In actual 175×50 tmux runs, shell markers at rows 1/25/49 now have **zero added blank
rows** before the banner, during use and after exit. The full-height live composer
remains bottom-aligned. Short/long/streaming history, copy mode, exact-width text,
inspection return and height-only/combined resize retain output once without stale
composers. Silent/delayed cursor-reply checks preserve pasted input and bound waiting;
unknown geometry conservatively allocates a bottom row, which may retain stale
layout on a silent-terminal resize rather than erase uncertain previous output.
No user session was executed or changed by these checks; no paid model calls ran.

## Recorded accounting and CLI discovery

Historical root, child and utility usage comes from canonical event receipts plus
identified native observations. Explicit metadata/fork ancestry determines child
ownership. Kernel receipt identity joins observers, never token-value equality or
time proximity. Imported receipts seed Session, not the next Turn, and remain
inspectable in Activity. Reopening does not duplicate totals or canonical bytes.
A derived On resume total reflects the reconciled session ledger; historical turn
footers remain unchanged receipts of their earlier accounting view. Repeated
projection adds neither journal events nor new-turn usage.
Missing, conflicting, oversized and uncorrelated sources produce partial accounting.
The actual CLI/TUI round-trip probe mounts hooks-logging, reconciles exact synthetic
reported costs and uses a mixed Markdown answer without paid model calls.

CLI discovery requires a saved transcript, retaining log-only diagnostics on disk.
Resume lists label their nonblank transcript-line counts as messages, not user turns.
The app pins CLI main merge `5d1068dd83d9c6837558c6aa859329fba23bcd50`.
[CLI PR346](https://github.com/microsoft/amplifier-app-cli/pull/346) is merged after
all eight Linux/macOS/Windows unit/integration CI jobs and CLA passed for its tested head.

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

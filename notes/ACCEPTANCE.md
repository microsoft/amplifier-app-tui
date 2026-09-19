# Current acceptance evidence

## Canonical sessions

All live TUI launches use Foundation's native history API and the CLI project/session format under the selected Amplifier
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
The current probe also proves actual CLI continuation refuses an idle TUI owner
without changing canonical transcript/metadata/log bytes, then succeeds after close.
TUI startup under a competing shared owner visibly refuses and retains editable text.
Common ownership spans native loading through runtime/child cleanup; crash/stale-handle
and complete-backup recovery tests use real Foundation and isolated subprocesses.
Backup recovery is visibly disclosed; repeated snapshots never rewrite source files.

The real Unified storage adapter at `54f3337` passes same-ID TUI → Unified → CLI-read
→ TUI round trips and mutual ownership contention. Unknown metadata and JSON provider
continuation fields survive that path. This does not execute Unified's web/worker
runtime or prove every later CLI save policy: the pinned CLI still applies its own
message sanitizer. The TUI preserves JSON fields and excludes system/developer messages.

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

The default Python suite passes **718 tests, 327 opt-in skips** (142.53s), recorded
privately in `.evidence/shared-foundation-default.xml`. Rust renderer/native tests pass
**73 tests**, with release build and strict Clippy clean. Ruff lint/format and
direction checks pass. The shared history/ownership/activity, CLI compatibility and
independent loop/context gates pass **138 tests** (37.69s), with opt-ins enabled and
no skips, in `.evidence/shared-foundation-integration.xml`.
Native Activity/navigation/flow/tmux regressions pass **29 tests** (51.28s), recorded
in `.evidence/shared-foundation-native.xml`. The actual-entrypoint shared-session
probe additionally passes busy-owner/draft and shared Activity inspection at 175×50;
round trips cover 40×20 as well. Reference-font captures were inspected privately.
The actual-entrypoint round-trip probe also checks the visible reconciled On resume
total at laptop and narrow widths, without executing user history.
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

Foundation now owns CI normalization and exact message/tool/prompt associations.
The host honors CI relocation and uses the root logger only when CI is absent;
dual captures are not summed. Activity → Shared session history reads a bounded
in-memory snapshot, grouping exact turns, utility calls and unassociated observations.
Reopening refreshes; snapshots do not poll, mutate logs or enter the accounting ledger.
Malformed/oversized optional records produce partial views, including hostile duration,
Unicode and label cases. Existing TUI observation/accounting/admission sidecars remain;
this is not a claim that all intent or recovery state can be reconstructed from CI.

CLI discovery requires a saved transcript, retaining log-only diagnostics on disk.
Resume lists label their nonblank transcript-line counts as messages, not user turns.
The app pins CLI `120f7e54d5ddd6e493dc5815f300e04f5e2666da` and Foundation
`b3bdab2adcc2a8fe477aca64c20b77528a95e1df`. The independent global CLI installation
is not automatically upgraded by this source change.

## Remaining boundaries

- Close one client before opening the same session in the other. Cooperating clients
  must share Foundation's owner-state root; the local POSIX lock does not fence older
  nonparticipants, other hosts or remote effects. Native saves remain per-file atomic,
  not a transcript/metadata transaction or a generic cross-thread save/release guarantee.
- Interrupted shared sessions fail closed. Recovery must retain originals and
  unknown effects; the canonical recovery workflow is not yet implemented.
- Native pins/modes/goals/held input/child controls are not a common CLI private-state
  format. [Foundation PR397](https://github.com/microsoft/amplifier-foundation/pull/397)
  proposes DRAFT controls, intent and recovery contracts; no runtime implementation
  or ratification is claimed. Preserve-but-ignore clients are not conforming receivers.
- Historical accounting is bounded to 512 directory metadata candidates, 128 event
  logs / 64 MiB and 10,000 receipts. Gaps are disclosed; unavailable costs are never
  estimated from transcript tokens or model prices.
- Canonical loading is bounded to 10,000 messages / 8 MiB and metadata to 64 KiB.
  Larger Unified effective-configuration metadata can exceed this bound; no universal
  metadata or private-state compatibility is claimed. Full web runtime and broader
  actual-entrypoint persistent-context combinations need separate checks.
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

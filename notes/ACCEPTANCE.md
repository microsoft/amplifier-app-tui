# Current acceptance evidence

## Connected Unified client

Connected mode is implemented as the default installed entrypoint. The host owns
execution and canonical session files. The following checks use private homes,
synthetic data and an explicitly labelled provider, not personal conversations:

- Actual installed macOS ARM wheel with only transport dependencies; no Core,
  Foundation or CLI package installed in the client environment.
- Two native Ratatui processes at 120×40 and 40×20: shared inputs/results,
  private drafts and detachment without Stop; terminal modes restored.
- Actual bundled web SPA plus installed native client: both directions of input
  and response, independent drafts, no browser errors.
- Actual Unified worker, Foundation/Core and loop-live: a detached sender leaves
  work running; another client receives completion; reconnect restores the same
  session; explicit Stop cancels the controlled provider.
- HTTP/SSE checks cover unknown delivery, lost creation acknowledgement, exact
  deduplication, target isolation, nonblocking Stop, history pages and shared names.
- Native unit tests: 78 pass. Rust Clippy and Python Ruff pass. Direction checks
  validate the amended DRAFT documents, not ratification.

Release qualification also passes on macOS ARM64 and Linux ARM64: install with
Cargo absent from PATH, executable loading, privacy scan, connected installation
without execution dependencies, and upgrade from the actual 0.3.0rc6 wheel while
retaining standalone fixture history and drafts. Installed native PTYs, explicit
standalone scripting in text/JSON/trace modes and shell completion pass on both.
Linux additionally passes 17 HTTP/SSE and installed connected-terminal checks.
Receipts accompany only the qualified native artifacts; Intel, physical terminal
emulators, clipboard integration and paid providers are not newly qualified here.

The broad retained standalone suite reports 783 passed, 343 skipped and six
failures on this Mac. All six reproduce on unchanged main with the same test
sources/environment: symlink spelling in computer-source resolution, old macOS
Bash completion, provider-budget fixture, unavailable clipboard behavior, the
terminal-guard observer test, and non-UTF-8 filenames rejected by the filesystem.
These are not asserted passing or hidden by the connected qualification. Missing
source checkouts and obsolete ordinary-launch expectations were addressed before
that comparison; standalone tests now request `--standalone` explicitly where needed.

This is automated native qualification, not paid-provider proof or
physical-terminal qualification. Queue/steer, full configuration
editing, voice, uploads and rich canvas remain outside this first connected slice.
The paired Unified change supplies stable streaming display identity; older
v1 hosts show a receiving indicator until the final response. Catalog filtering
is page-local, and host SSE fan-out is unchanged.

## Optional standalone canonical sessions

Standalone live TUI launches use Foundation's native history API and the CLI project/session format under the selected Amplifier
home. An ordinary standalone launch shares CLI configuration; explicit isolated policy uses its
own home without creating a different live-session format. TUI drafts, admission receipts
and controls remain namespaced sidecars; historical presentation is derived in memory.
No imported TUI journal/checkpoint is required. Deterministic fixture journals are private
test infrastructure, not a supported user-session migration or compatibility path.

The actual-entrypoint probe passes CLI → native startup Resume picker → CLI → native
resume, retaining the same identity and explicit conversation turns. It also passes
new ordinary TUI → CLI, plus explicit isolated-composition TUI start/resume using the
same canonical format. Laptop 175×50, narrow 40×20 and custom-composition 80×30 paths
use real app/core/modules and deterministic provider/tool fixtures. Resume performs
no implicit provider/tool call; original transcript bytes and terminal modes survive.
The current probe also proves actual CLI continuation refuses an idle TUI owner
without changing canonical transcript/metadata/log bytes, then succeeds after close.
TUI startup under a competing shared owner opens a read-only view and retains editable text.
Common ownership spans native loading through runtime/child cleanup; crash/stale-handle
and complete-backup recovery tests use real Foundation and isolated subprocesses.
Backup recovery is visibly disclosed; repeated snapshots never rewrite source files.
Both valid-primary and backup-recovery open/close tests preserve canonical transcript,
metadata and backup bytes and nanosecond modification times. Native reads accept
over 66 MiB / 11,000 messages and 900 KiB metadata in one streaming transcript pass.
The actual native entrypoint also passes at that scale: Ready, visible latest answer,
editable unsent draft, no transcript rewrite or private events journal. Rendering
alone uses a disclosed latest-100/8-MiB window and bounded UTF-8 previews; canonical
transcript and runtime context retain the complete native messages. Export is a
readable display projection, not a lossless canonical backup; it has a separate
32 MiB rendered-output limit.

Actions → Earlier history browses the saved resume snapshot in read-only pages of
up to 100 items, with source previews/copy and older/newer controls. Byte-limited
pages return to their actual preceding boundary, not a guessed 100-item offset.
The large-entrypoint probe exercises paging, preview/copy, narrow resize and return
to an unsent draft; native history/context and transcript modification time survive.
Transport-fixture mouse tests expand/collapse and select across empty Markdown and
hidden child items at 175×50 and 40×20. Rust checks also cover stale anchors, all-empty
views, both transcript views and widths down to zero. These are synthetic records,
not a reproduction using private user messages or a paid provider.

The real Unified storage adapter at `54f3337` passes same-ID TUI → Unified → CLI-read
→ TUI round trips and mutual ownership contention. Unknown metadata and JSON provider
continuation fields survive that path. This does not execute Unified's web/worker
runtime or prove every later CLI save policy: the pinned CLI still applies its own
message sanitizer. The TUI preserves JSON fields and excludes system/developer messages.

Run `scripts/shared_session_probe.py` as documented in [SMOKE_TESTS](../SMOKE_TESTS.md).
Raw captures/logs/settings stay private. This is actual-entrypoint verification,
not a paid-model, personal-account, latency-parity or arbitrary private-state claim.

## Current checks

### Cooperative ownership

Busy startup and Resume retain readable canonical history without mounting a second
runtime. Continue here explicitly requests Foundation release, then acquires and
reloads current history/configuration; it never submits the draft. Outbound release
closes admission, pauses queued input, finishes current calls, saves and disposes
modules before unlocking. Save/cleanup failure retains ownership. An owner change
requires another explicit attempt; timeout never steals a lock or auto-submits.

After five minutes without runtime work or observed user activity, the TUI retires its runtime and releases the
session while retaining the view. The next explicit action reacquires and remounts;
old callbacks cannot borrow its new handle. Pending work/decisions prevent parking.
This is conservative module retirement, not warm runtime reuse or background detach.
Typing, paste, local navigation, delivered mouse events, resize and focus return
renew the timer. Activity is coalesced in memory and never admitted as execution;
background polling/painting do not renew it. Native terminal/tmux-owned scrolling
and selection are outside the app's visibility. External editing prevents automatic
parking but does not delay an explicit cooperative handoff.
Clock-controlled tests pin the 300-second default, last-input/work boundaries,
stale/invalid activity rejection and activity racing listener shutdown. A transport
check sends 5000 notifications without replies or admission-capacity consumption.
The focused host/transport gate passes **41 tests, 1 optional Unified skip** in
`.evidence/user-idle-focused.xml`. Native PTYs at 175×50 and 40×20 use a three-second
test-only interval and real input/external editing, then verify quiet release,
unchanged history, explicit fresh Send and restored terminal/focus modes. They do
not claim a five-minute wall-clock soak. Together with Activity/navigation/flow/tmux
and daily-editor regressions, **37 tests pass** in `.evidence/user-idle-terminal.xml`.
Private reference-font captures were inspected; no personal session was run.

The isolated cross-app environment passes **25 tests** in
`.evidence/user-idle-cross-host.xml`: real Foundation locks/sockets, actual TUI
mounts with deterministic modules, and real CLI/Unified lifecycle adapters with
synthetic collaborator sessions/cleanup. It does not prove actual web UI execution
or arbitrary CLI/Unified runtime draining. Actual native-entrypoint PTYs pass at
**175×50 and 40×20**, including reciprocal handoff, retained draft, automatic idle
release and explicit Send after external history advances. Captures were inspected;
the **37-test** terminal gate above includes Activity/navigation/flow/tmux regressions.
The cross-app and terminal runs use the
published exact Foundation `2c0063a` and CLI `b507233` pins, not sibling overrides.
The actual CLI/native TUI round-trip probe also passes against these pins: new
TUI → CLI, same-ID CLI → TUI → CLI → TUI, 66-MiB history, paging/preview/copy,
shared Activity inspection and busy read-only draft restoration. The CLI subprocess
uses its pinned package and a disposable environment; no personal session is executed.

Foundation [PR399](https://github.com/microsoft/amplifier-foundation/pull/399) is merged:
forked-child cleanup no longer removes or disarms the parent's handoff listener.
The fix passes **2102 tests, 4 skips** in Foundation's own locked environment and all
six upstream CI jobs. CLI [PR356](https://github.com/microsoft/amplifier-app-cli/pull/356)
is merged with the coordinated Foundation pin; its default run passes **2436 tests,
1 skip, 13 deselections and 1 expected failure**, its integration run passes **13 tests**,
and all eight upstream CI jobs pass. No full-suite cross-app Foundation success is
claimed; those checks use each project's own environment.

Five native-host regression cases cover changed composition with pristine, explicit,
pending, unknown-field and malformed provider-control receipts. Only the pristine
default may refresh; other saved state and canonical transcript bytes remain intact,
with no provider calls. The reported personal session has not been independently
identified; this proves the reproduced empty-receipt defect, not its exact diagnosis.

Coverage includes no-fallback discovery, canonical storage for explicit policy,
metadata-only housekeeping, same-ID history/configuration, unknown metadata,
external names, canonical-digest invalidation, private drafts and graceful-stop return.
Four independent loop/context combinations retain module-owned system history
without putting it in the public CLI transcript. These are module/store tests,
not an assertion that every persistent-context entrypoint configuration is verified.

The current default Python run passes **784 tests, 332 opt-in skips**, recorded
privately in `.evidence/user-idle-default.xml` against the exact published pins.
Rust renderer/native tests pass
**77 tests**, with release build and strict Clippy clean. Ruff lint/format and
direction checks pass. The shared history/ownership/activity, CLI compatibility and
independent loop/context gates pass **186 tests** (45.21s), with opt-ins enabled and
no skips, in `.evidence/native-shared-integration.xml`.
Focused native history/host restoration/shared activity checks pass **53 tests** in
`.evidence/history-selection-focused.xml`. Native Activity/navigation/flow/tmux
regressions pass **31 tests** in `.evidence/history-selection-terminal.xml`.
The actual-entrypoint shared-session
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

Historical root, child and utility usage comes from shared recorded event receipts.
Live hooks supply current work without another persisted event history.
Explicit metadata/fork ancestry determines child
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
dual captures are not summed. Ordinary Activity shows canonical/live tool cards with
exactly associated recorded observations beneath them, alongside explicit utility or
unassociated groups when needed. No separate Shared chooser is required.
Reopening refreshes; live timers use memory, never poll logs or duplicate accounting.
Malformed/oversized optional records produce partial views, including hostile duration,
Unicode and label cases. TUI intent/control/admission receipts remain;
this is not a claim that all intent or recovery state can be reconstructed from CI.

CLI discovery requires a saved transcript, retaining log-only diagnostics on disk.
Resume lists label their nonblank transcript-line counts as messages, not user turns.
The app pins CLI `b5072330a28e7e898e5ffecd8efeb5e898351873` and Foundation
`2c0063a187181173dfe2438ce031079e8723f894`, both merged main commits. The independent global CLI installation
is not automatically upgraded by this source change.

## Remaining boundaries

- Cooperating clients can read while another owns execution and explicitly hand off.
  They must share Foundation's owner-state root; the local POSIX lock does not fence older
  nonparticipants, other hosts or remote effects. Native saves remain per-file atomic,
  not a transcript/metadata transaction or a generic cross-thread save/release guarantee.
- Live-loop background execution, external observation while read-only, and detached
  hosts remain separate work. Foundation's release endpoint is not a live-attachment bus.
- Interrupted shared sessions fail closed. Recovery must retain originals and
  unknown effects; the canonical recovery workflow is not yet implemented.
- Native pins/modes/goals/held input/child controls are not a common CLI private-state
  format. [Foundation PR397](https://github.com/microsoft/amplifier-foundation/pull/397)
  proposes DRAFT controls, intent and recovery contracts; no runtime implementation
  or ratification is claimed. Preserve-but-ignore clients are not conforming receivers.
- Historical accounting is bounded to 512 directory metadata candidates, 128 event
  logs / 64 MiB and 10,000 receipts. Gaps are disclosed; unavailable costs are never
  estimated from transcript tokens or model prices.
- Native loading has no TUI-only import byte/message quota. Provider JSON fields are
  compared directly on context restoration; lossy readback refuses before Send.
  Full web runtime and broader
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

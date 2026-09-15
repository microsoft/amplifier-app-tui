# First vertical slice — acceptance evidence

## Confirmed review, historical children and release breadth (2026-09-15)

This continuation follows the existing DRAFT promises (presentation P7, continuity
P5, session P8 and ecosystem P2/P6); it does not redefine the destination to claim
that all residual work is complete. The candidate version is 0.3.0rc3. Prior published
0.3.0rc2 artifacts and user-owned local notes are preserved.

- Conflict-file capture, a separate editable proposal and explicit Apply now work in
  the native Review path. Tests use actual unmerged Git indexes. Capture/editing adds
  no provider turn or workspace write; Apply retains an original private backup,
  refuses detected stale/symlink/hard-link targets, and leaves index/HEAD unchanged.
  A backup-failure gate and a write injected after backup preserve the newer source.
  The native capture was inspected; proposal text must be visible before confirmation.
  This is not a transaction with unrelated external writers, a staging action, an
  automatic conflict solver or attribution of other workspace changes.
- Child public-context capture, cleanup and final receipt now have one shielded
  finalization owner. Repeated cancellation during context capture and cleanup drains
  once and retains an interrupted receipt. This does not certify arbitrary module
  cleanup or fix the separate Rust/Python coroutine scheduling warning.
- Explicit historical recovery copies bounded child public-message excerpts and
  source hashes into read-only recovery evidence. The native Recovered work action
  inspects it alongside historical actions; no children, recipes or private state are
  restarted. A real interrupted fixture child retains its original bytes and causes
  zero operations when the recovered root opens. Foreign/symlink/oversized receipts
  remain unavailable, not guessed valid. Media blocks are omitted from excerpts.
- Static GIF/WebP attachment capture preserves original bytes through storage/public
  context blocks; animated GIF/WebP refuses without conversion. The macOS clipboard
  adapter explicitly requests PNG data; its local parser test is not real desktop proof.
- The release workflow requests an installed PTY fixture gate on each platform:
  ordinary editing/Help, actual tool execution, clean exit, no-replay resume and a
  second turn. Configuration alone does not make an unrun platform pass.

Integrated verification: **439 Python tests passed in 207.34 seconds**, with presets,
native clients and independent swaps enabled. **34 Rust tests**, all-target Clippy,
formatting and Ruff pass. Three unawaited callback warnings remain (two module handler,
one child observer) in real-preset child-question cancellation tests. No warning filter,
kernel patch or synchronous event-order workaround was introduced. Structure remains
584 contract lines / 49 production source files; no formal Converge verdict is implied.

Both real presets pass the [static GIF](evidence/readiness-gif-live.json) and
[static WebP](evidence/readiness-webp-live.json) native gates: controlled colours,
exact canonical source bytes, one completed turn each, zero tools and no extra turn
from source/model-catalog inspection. The [live lifecycle receipt](evidence/readiness-lifecycle-live.json)
repeats completed read/resume without replay and Stop/exit during a child question;
each preset retains one interrupted child/parent, no invented answer and uncertain checkpoint.
These runs billed eight root and two child turns in total. Private native captures were
inspected; they are not publication artifacts.

The [renderer receipt](evidence/readiness-renderer-benchmark.json) covers the 18-cell
scene matrix and clean exits, plus 240 syntax-stress edits. Ratatui's worst cell edit
p95 is 21.1 ms and stream-update p95 24.1 ms; syntax edit p95 is 21.2 ms. First usable
scene paint across 30 launches has median 40.9 / p95 59.1 ms. This is synthetic renderer
work, not live startup, history-catalog I/O, policy-equivalent CLI latency or a final
frontend-selection verdict. Rust's NO_COLOR run and all three OpenTUI tests also pass.

The [local Linux ARM64 wheel](evidence/readiness-local-wheel.json) passes compiler-free
isolated installation, native-byte/load checks, offline diagnostics, and the new
installed PTY fixture gate outside the checkout. Help adds no submission; tool execution,
no-replay resume, second turn and terminal restoration pass. Every wheel member passes
the deterministic privacy scan. This is not yet the four-platform published release or
installed live-provider evidence. New-version platform evidence follows its actual jobs.
Exact interrupted/private-state reconstruction, crash-uncertain recipe effects,
causal agent/test attribution, character-exact resize anchors, broad provider conversion,
matched-policy CLI latency and real desktop/older Linux coverage remain open.

## Continuation: references, diagnostics and transport ownership (2026-09-14)

This is ongoing checkout work, not a replacement of the published 0.3.0rc2 assets or
a claim that every remaining backlog group is complete. Direction was amended before
implementation; contracts remain DRAFT and production source count remains 49/50.

- Explicit file/line reference attachments preserve full-source and excerpt hashes,
  original location and immutable bytes through queue/reopen, sharing one admission
  record with images. Text-only providers do not need vision; mixed sets still do.
- Other local dialog editors now retain source-scoped copies. They never restore into
  a potentially changed target or become submitted context. The 250 ms flush window remains.
- Native host writes move off the UI thread into a bounded queue. Exit owns the host's
  Unix process group, permits three seconds for cooperative shutdown and up to 500 ms
  for direct-child reaping confirmation, then reports uncertainty. A deliberately
  non-reading transport fixture cannot trap the terminal; its inherited descendant is
  no longer running. Detached/remote effects and kernel callback warnings remain open.
- Explicit one-shot diagnostics project provider-reported request fields in memory,
  without enabling logging, building context, adding a provider call or copying raw
  payloads into the host journal. Content can be private; provider redaction, omitted
  fields and bounds mean this is not exact wire serialization, occupancy or delivery proof.
- Index prefix reads now count toward the I/O budget; malformed large integer metadata
  produces partial results instead of breaking search, and Unicode casefold expansion
  no longer shifts a matched excerpt past its source text.

Eight native continuation regressions pass. Both real presets pass the
[controlled-reference live gate](evidence/continuation-live.json): delete source after
capture, queue/close/reopen with no implicit execution, explicitly Run, verify exact
canonical location/bytes and the controlled reply, then inspect a provider-reported
request without an extra turn. Actual private reference and diagnostic captures are
retained locally; reference confirmation and the provider-request menu were visually
inspected. The final all-flags suite passed **422 Python tests in 192.93 seconds**, with
one unawaited `Children.execute.<locals>.observe` callback warning during child cancellation.
The first 422-case run passed with three callback warnings. They remain open, not suppressed.
**34 Rust tests** pass normally and with NO_COLOR, all-target Clippy/fmt pass, and the
OpenTUI comparator's three tests pass. Ruff checks/formatting (137 files), direction
structure (584 contract lines / 49 production files) and archive integrity pass.

The [live lifecycle gate](evidence/continuation-lifecycle-live.json) passes both presets:
completed read/resume without replay, then Stop/exit during a child question, one
interrupted parent/child, no invented answer, uncertain checkpoint and restored terminal.
The [updated index measurement](evidence/continuation-history-benchmark.json) uses
200 synthetic sessions / 100,000 messages / 61.6 MB of journals: four refreshes totaling
2045.9 ms, largest call 560.2 ms, warm search median 17.3 / p95 22.6 ms. Journals stay
unchanged. This excludes catalog/UI/provider/CLI work and is not a parity claim.

A local unpublished Linux ARM64 wheel and source distribution build successfully;
all 39 wheel and 63 source members pass privacy scans. Isolated wheel installation,
exact embedded-native byte/load checks, doctor and offline help pass with no checkout
source imports; diagnostic/native-load checks run with Cargo absent and create no state.
This is not another four-platform release or an installed-live certification. Existing
0.3.0rc2 assets remain untouched; the development command still loads the checkout.

The convention-required fresh-context privacy review found no required redactions in
the source delta, owned new tests/probe, three receipts and exact local package artifacts.
Private captures, user-owned notes and unrelated local state remain excluded from publication.

README/PLAN/PARITY now distinguish delivered reference, image, indexing, provider and
delegation slices from their real residuals. Interrupted/private/subprocess recovery,
causal change/test review and conflict editing, exact request/occupancy and broader provider
conversion, kernel callback cancellation, matched CLI policy and broader interactive
platform evidence are **not complete**. Non-Linux clipboard support and character-exact
resize anchors also remain open.

Historical delivery records below describe the version they verified, not today's
remaining backlog. The current [workflow map](PARITY.md) owns that gap summary.

## Rich inputs, discovery and explicit context controls (2026-09-14)

The current eight-group authorization drives this slice; it does not close all eight
groups. VISION and the interaction, presentation, continuity and ecosystem promises
were amended before implementation. Contracts remain DRAFT. The convention skill
required a fresh-context review of new source, fixtures and evidence before publication.

- Up to four frozen PNG/JPEG snapshots per draft or queued message, per-item removal,
  bounded local thumbnails and explicit Linux desktop clipboard acquisition. Attachment
  identity and bytes survive reopen, rejection and source-file replacement. Clipboard
  acquisition is not remote-terminal clipboard support. Semantic file references remain open.
- Saved-message search uses a private incremental SQLite trigram cache, retaining source
  journals as authority and disclosing partial results. Filtering precedes paging, including
  startup full-content search. Timestamped recall merges directory sessions chronologically;
  older records disclose legacy ordering instead of inventing timestamps.
- Stored public messages are inspectable without a model request; image bytes are omitted
  from the view. Allowlisted provider-dispatch observations are separate from exact wire
  payloads. An explicitly confirmed standalone provider probe may bill, but adds no
  conversation turn, tools, workspace content, model selection change or response text.
- Explicit UTF-8 historical import creates a new composition with a hashed reference,
  preserving the original and performing no replay. Recovery also retains a structured
  historical tool/child/question ledger; uncertain effects stay unknown. Completed child
  restart now supports captured custom JSON orchestrator configuration under existing
  parent/policy/context guards. Interrupted/private-state and subprocess recovery remain open.
- Wide diff inspection can pair removed/added lines side by side; narrow terminals fall
  back to unified text. Copy still returns the original captured unified source. This is
  not agent attribution, conflict editing, or test-state causality.

Integrated gate: **403 Python tests passed**, with native candidates, both presets and
independent swaps enabled (187.42 seconds). The preceding 402-case run emitted two
unawaited logging-callback warnings; the final run emitted none, but the reproducible
cancellation defect remains open. No warning filter or kernel patch hides it.
**33 Rust tests passed** normally and with
NO_COLOR; all-target Clippy, Cargo format, Ruff, direction structure (581 contract lines,
49 production files), and diff checks passed. A first full run exposed premature Ready
publication while directory recall was loading; advertised readiness now waits for recall,
and failed startup releases that guard. A new explicitly gated initial-readiness regression
also preserves early drafts, refuses premature Send and verifies zero automatic execution.
The focused cases and final full run pass.

The [live rich-input receipt](evidence/approachability-live.json) covers both real presets:
capture two images, queue without submission, close, resume without replay, and explicitly
run the queue after replacing source files. Both original colours and exact canonical bytes
were retained. Stored-context inspection and a separately confirmed remote access probe
preserved the checkpoint and unsent draft. Two conversation turns and two standalone probes
were billed; no tools were called. An initial probe command incorrectly combined resume
with a cwd override and was correctly refused before a provider turn; the corrected probe
restores recorded cwd and passes. Private native previews, queues, replies and controls
were captured; no transcript, credential or machine-path literal belongs in this receipt.

The [current lifecycle receipt](evidence/approachability-lifecycle-live.json) repeats both
live preset checks against this revision: completed file read, close/reopen without replay,
then Stop/exit while a delegated child awaits a question. One parent and child remain
interrupted, the question has no answer, and the checkpoint stays uncertain. Each PTY
exited cleanly. Four parent and two child turns are separate from the image/probe gate.

The [synthetic index measurement](evidence/history-index-benchmark.json) covers 200 sessions,
100,000 messages and 61,645,095 journal bytes. Four incremental refreshes indexed the store
in 1,985 ms total (largest call 550 ms). Thirty warm search samples measured median 18.6 ms
and p95 23.6 ms, with all first-message matches found and every journal hash unchanged.
This excludes metadata catalog work, UI, model, CLI policy and cold installation. It is
not a CLI-parity result or a maximum-latency guarantee.

The 0.3.0rc2 Linux ARM64 candidate passes isolated compiler-free installation, native
byte/load verification and an independent review of every wheel member and its receipt.
The [installed live gate](evidence/approachability-installed-live.json) exercises both
presets outside the checkout with remote sources: real delegated file read, close/reopen
without replay, second-turn retained-context reply, and non-submitting help. Four parent
and two child turns pass. Existing 0.3.0rc1 release assets are not overwritten.

The [four-platform release receipt](evidence/release-0.3.0rc2.json) identifies source
`862fe63bc4dc49d47fcf57fa43f7748d1cd8103a`. All four native-unit/build/compiler-free
installation jobs passed. Every downloaded member passed privacy scanning and independent
review; embedded sources match that revision, binary architectures match their wheel tags,
and wheel/native hashes match their adjacent receipts. Because the CI ARM64 binary differs
from the local build, the [exact CI installed-live gate](evidence/approachability-ci-installed-live.json)
repeated delegation/resume/second-turn checks on both presets against those release bytes.
This adds four parent and two child turns, distinct from the earlier local-wheel gate.
The [Git-source install gate](evidence/approachability-git-installed-fixture.json) separately
installed the exact revision and passed fixture tool/resume/second-turn checks outside
the checkout. The release tag resolves to that same tested revision.

The private [0.3.0rc2 prerelease](https://github.com/bkrabach/amplifier-app-tui/releases/tag/v0.3.0rc2)
contains only the four reviewed wheels and adjacent receipts. All eight uploaded assets
were downloaded again and verified before leaving draft status. Temporary CI run/artifacts
and logs were removed after retaining sanitized evidence; private captures/state and
unrelated local notes were not published. Linux ARM64 remains the only platform with
interactive/live-runtime evidence. Four packaging passes do not certify every terminal,
older Linux/musl, arbitrary provider or module. No formal Converge verdict was generated.

Remaining: callback/uncooperative shutdown ownership, semantic references, interrupted
child/private-state/subprocess and uncertain recipe recovery, attributed change/test evidence,
conflict editing, exact request/provider conversion, matched CLI-policy and broader platform
proof. The eight current PLAN rows remain the authoritative open-work record.

## Finalization ownership (2026-09-14)

Continued steward authorization drove LIFE-03. The per-repo-conventions skill kept
the VISION/session P8 amendment ahead of implementation and routed the ownership
lessons into ENGINE-BOUNDARY and SMOKE_TESTS. Contracts remain DRAFT.

Repeated Stop and Stop/exit previously cancelled a stopped turn's awaited checkpoint.
They now preserve finalization; first Stop during a completed turn's checkpoint does
not relabel completion or cancel persistence. Close owns one shared, shielded cleanup
task, rejects admission, joins startup before returning and propagates caller cancellation
only after cleanup drains. Cleanup failures remain visible without an automatic retry.
The startup exception path avoids a recursive open/close wait cycle. Mode transitions
reset the same task-state flags and protect their checkpoint; the new actual-preset
regressions caught stale finalization state after a completed root turn before handoff.
The broader run also exposed an ordering gap in the new cleanup handoff: immediate
close allowed a just-admitted turn to enter execution before cancellation. A strengthened
existing regression now counts actual session.execute calls, rather than accepting an
interrupted ending alone. Stop applies synchronously before the cleanup task is scheduled.

Eight deterministic host cases and four actual-preset mode cases use controlled await
gates around real mounted sessions, not timing guesses or a mocked successful engine.
The [live terminal receipt](evidence/lifecycle-live.json) covers both presets: successful
read_file, exit/reopen with no replay, then delegation to a child asking a structured
question. Selecting Stop and immediately exiting preserves one interrupted parent and
child, stops the question without an answer and retains an uncertain checkpoint. The
four-parent/two-child probe ran twice, including after the last ordering fix: eight
parent and four child turns total. Private completed/waiting terminal captures were
inspected; each isolated PTY exited cleanly and restored terminal modes.

Rust/Python callback cancellation warnings remain unresolved. The earlier full run
passed 380 tests with two unawaited callback warnings; deeper tracing also exposed
orchestrator/raw-field callback allocations but slowed the child-question test beyond
its existing timeout. Those tracing failures are not normal-run failures or evidence
of a general fix. No kernel changes, warning suppression, automatic recovery, cleanup
timeout guarantee or CLI-performance claim is included in this slice.

Final integrated gate after the ordering fix: **384 Python tests passed**, native
candidates/both presets/independent swaps enabled, with **two remaining module-hook
callback warnings** in delegated cancellation. **30 Rust tests passed** both normally
and with NO_COLOR. Clippy warnings-denied, Cargo format, Ruff/format (124 files),
direction/archive integrity (577 contract lines, 48 production files), and diff checks
passed. The live receipt fingerprints match that tested host/mode revision. Temporary
PTY/tmux probe resources were reaped.

Wheel and sdist build; every decompressed wheel member passes the existing privacy
scan, and embedded host/mode sources match the checkout. This is a separate local
candidate, not replacement assets for the published 0.3.0rc1 release.

## Whole-backlog implementation and release candidate (2026-09-14)

The steward authorized all seven backlog groups. The per-repo-conventions skill drove
the VISION/interaction/ecosystem/continuity amendments before implementation and a
fresh-context privacy review before publication. This is progress across those groups,
not closure of every residual or a formal Converge verdict; contracts remain DRAFT.

- Native saved-conversation search covers message content with source identities and
  bounded reads; startup/in-app catalogs page beyond 100 records. Large-store indexing
  is not implemented. No searched message is imported into model context.
- One explicit workspace PNG/JPEG snapshot (2 MiB maximum) survives draft restart and
  is admitted once, by identity, into the canonical context of a vision-capable provider.
  Metadata confirmation precedes attachment; preview/remove do not execute anything.
  Multiple/queued/clipboard images and semantic references remain unsupported.
- Instruction-source inspection projects actual Foundation `mentions:resolved` events;
  it neither rebuilds context nor claims to list every provider instruction. Explicit
  model discovery calls the mounted providers' public catalog API, bounds the result,
  and copies advisory IDs without changing conversation policy. The offline `--setup`
  wizard writes a new private environment-reference overlay, not credentials/shared settings.
- Completed nested/routed children can resume with their actual parent active and exact
  reconstructed policy/context. Persistent child context has identity-isolated files.
  Child lists refresh while open without changing focus. Recipe activity can prepare a
  review request, never silently resume work. Both actual v2 preset tests fail a recipe,
  reopen the host, then explicitly resume without repeating its completed first step.
- The public owned-session factory acquires the session before awaiting initialization,
  preserves Foundation resolver/prompt capabilities, and drains cleanup after partial
  startup failure/cancellation. Explicit uncertain-delivery dismissal preserves a receipt
  and keeps the queue paused; it does not imply retry, rollback or repaired root context.
- Completion wording is shorter while failed/unresolved tools remain visible. The Unix
  resize probe has a 100 ms deadline and replays captured input using the pinned Crossterm
  fork. A silent responder disables later queries; conservative fallback retains history.

Integrated verification: **372 Python tests passed** with native candidates, both presets
and independent swaps enabled; **30 Rust tests passed** both normally and with NO_COLOR.
Clippy warnings-denied, Cargo format, Ruff/format (122 files), direction/archive integrity
(575 contract lines, 48 production files), wheel and sdist builds passed. The final run
reported two cancellation warnings in child/module hook callbacks; earlier runs reported
additional callback variants. This is not complete lifecycle hardening.

The full suite exposed two real integration defects: the new recipe action's old “resume”
description stole fuzzy Resume selection; and history recall could leave input blocked
after a Ready snapshot. The recipe action now says review, and recall completes before
switch publication; native input remains visibly paused until correlated confirmation.
Deterministic delayed-switch tests verify no false Ready or deferred submission.

The final [image/discovery live receipt](evidence/backlog-live.json) covers both presets:
controlled red/blue image identified, exact canonical image bytes, no tool calls, instruction
inspection and explicit model discovery without another turn. The [tool live receipt](evidence/backlog-tools-live.json)
covers successful read_file, rendered tables, syntax-coloured code, exact copy, retained draft
and no extra execution on both presets. Actual private captures were inspected. These four
billed root turns use isolated state; the steward's conversations and local upgrade files
remain untouched.

The [installed-wheel live receipt](evidence/backlog-installed-live.json) separately verifies
the isolated 0.3.0rc1 product outside this checkout, resolving remote bundle sources without
a workspace source map. Both presets executed a real delegated read, then reopened without
submission and answered a second turn from retained context. Offline guidance and allowlisted
support checks created no session state; in-app help added no submission. This gate adds four root
and two child turns; no shared CLI environment was changed.

The final [renderer receipt](evidence/backlog-benchmark.json) contains 30 startup pairs and
18 history/stream cells through 100,000 retained items. Worst Ratatui editing p95 was
**20.402 ms**, stream p95 **21.036 ms**, peak RSS **136040 KiB**. The separate six-grammar,
100-code-block/240-edit case measured **20.891 ms** p95, maximum **42.053 ms**. First editable
startup median/p95 was **41.548/58.282 ms**. These are synthetic renderer measurements,
not equivalent-policy CLI or cold-install performance. Source fingerprints match.

The 0.3.0rc1 Linux ARM64 wheel passed isolated installation with Cargo absent, byte-identical
native extraction, actual executable loading, offline diagnostics/guidance and no state
creation. Source distributions include the native source/build hook and exclude private
archives/state. The new manual four-platform workflow is a packaging/native-unit gate,
not a substitute for terminal or live-provider conformance on those platforms.

Fresh-context review found build-home paths embedded in the earlier candidate executable.
The corrected build remaps compiler paths; the release gate scans every decompressed wheel
member and its receipt, withholds raw build/install logs, and uploads only exact verified
artifacts. Independent review found no remaining blocker for the corrected candidate.
The unsafe local 0.2.1 wheel and receipt were quarantined recoverably, not published.

The first remote matrix also exposed a release-tag defect: Python's universal2 platform
tag was copied onto a single-architecture Rust executable. The macOS artifacts from that
run were rejected despite passing same-machine installation. The corrected hook pins
the build-host macOS major deployment floor and actual architecture, validates `lipo`
output, and the release gate independently checks filename and installed architecture.
A regression test covers both macOS architectures and rejects universal2 as a native target.

The corrected [four-platform receipt](evidence/release-0.3.0rc1.json) records source
`b4a491d79df5a80295db02247e3d9237701764e5`: all four remote native-unit/build/install jobs
passed. Downloaded wheel members were independently privacy-rescanned; wheel/native hashes
and actual ELF/Mach-O architectures match. The Linux ARM64 wheel is byte-identical to the
CI candidate exercised by the [installed fixture/tool/resume probe](evidence/backlog-ci-installed-fixture.json).
The private [0.3.0rc1 prerelease](https://github.com/bkrabach/amplifier-app-tui/releases/tag/v0.3.0rc1)
contains four corrected wheels and their individual receipts, not raw CI logs, private
captures, local state or rejected candidates. Linux builds target the tested Ubuntu 24.04
environment; macOS ARM64/Intel have explicit 14/15 deployment floors. Interactive/live
certification on other platforms and older Linux/musl portability remain open.
All eight published assets were downloaded again and matched to the verified receipts.
Temporary CI runs/artifacts were then removed; sanitized release evidence and the private
release assets remain, not raw runner logs. The existing development command link still
targets this checkout and reports 0.3.0rc1 on relaunch; no running user app was replaced.
An isolated `uv tool install git+https://github.com/bkrabach/amplifier-app-tui@v0.3.0rc1`
also succeeded. Its [installed fixture receipt](evidence/backlog-tagged-git-fixture.json)
verifies remote sources, a real digest tool, reopening without replay, a second turn,
offline checks and non-submitting help outside the checkout. Source installation still
requires Cargo; this is distinct from the compiler-free wheel gates.

Remaining work is explicit in the seven current PLAN rows: uncooperative module cleanup,
interrupted/custom-orchestrator/subprocess child recovery, broader media/references,
large-store indexing, causal Git/test attribution, equivalent-policy CLI performance and
all-seam policy/platform evidence. A passing renderer benchmark does not close CLI parity.

## Syntax-coloured code and fitting-draft recovery (2026-09-14)

READ-03 closes the code-colour gap recorded under READ-02. The per-repo-conventions
skill drove a VISION/presentation P3 amendment before implementation; all contracts remain
DRAFT. Pinned Syntect grammars are bundled in the native binary, not downloaded from reply
metadata. Python, Rust, JavaScript, shell and JSON are exercised. Multiline lexical state
stays within one block; foreground colour does not change copied code or source identity.
Native unfinished fences stay plain; unknown languages, NO_COLOR, parser errors and size
limits retain readable plain source. Highlighting has a 16 KiB per-render budget, 256 lines
per block, 1024 bytes per line and eight cached source/language entries. These bound input,
not worst-case regex CPU time. Code inspection retains its original snapshot separately
from explanatory labels; oversized full blocks also remain plain in truncated previews.

The first wider tmux run exposed an existing viewport-growth defect: returning from a
one-row inspection editor could display only the last line of a fitting three-line draft.
EDIT-02 restores the renderer origin through public textarea operations, without resetting
text, cursor, selection or undo. A deterministic widget test reproduces the precise small-
to-large transition; the actual tmux suite passes after the correction.

Verification: **349 Python tests passed**, **29 Rust tests passed**; colour-enabled and
NO_COLOR runs, Clippy warnings-denied, Ruff/format, Cargo format, direction/archive checks
and wheel/sdist build passed. The build packages the native executable and new grammar
dependency, excluding private state/archives. Four known cancellation warnings remain
(`run_orchestrator`, child observer, module handler and logging handler); no lifecycle fix
or general module-conformance claim is made by this rendering-only wave.

Private native and inspection captures were reviewed. The [live receipt](evidence/syntax-live.json)
exercises both presets with successful read_file, actual coloured code inspection, exact
code copy, retained main draft and zero extra execution from copying. The earlier 23-test
focused run also covers native colour/plain fallback, resize, real fixture resume and tmux
history. No user conversation, new upgrade documents or upstream module sources were changed.

Review focus on relaunch: is code easier to scan in replies and **Actions → Code blocks**,
and does the multiline composer fully recover after returning from a narrow inspection?

The final [benchmark](evidence/syntax-benchmark.json) ran after tests/builds/live calls:
30 startup pairs and 18 retained-history stress cells through 100,000 items. Ratatui's
worst editing p95 was **20.411 ms**, stream p95 **21.432 ms**, peak RSS **135668 KiB**.
The separate 100-code-block/six-grammar case measured **21.121 ms** editing p95 over
240 edits (maximum **35.849 ms**, peak RSS **34388 KiB**), including cold grammar use.
First editable startup median/p95 was **46.764/59.410 ms**. These are synthetic renderer
measurements, not a matched CLI-policy or cold-install comparison. Source fingerprints
match; all test resources are reaped. The private repo and development link remain
intentionally retained, and ordinary `amplifier-tui` picks up this batch on relaunch.

## Edge-to-edge terminal width (2026-09-14)

WIDTH-01 follows the steward's request to remove the remaining side padding. The
per-repo-conventions skill drove the VISION/presentation P6 amendment before code;
contracts remain DRAFT. Native transcript emission, live preview, composer and inspection
now use every column. Markdown indentation and local dialog structure remain unchanged;
the historical OpenTUI comparator retains its old inset. No runtime/kernel changes.

Verification: **347 Python tests passed**, **25 Rust tests passed**, Clippy warnings-denied,
Ruff/format, Cargo format, direction/archive integrity (569 contract lines, 47 production
files) and wheel/sdist build passed. One existing upstream `LoggingHandler.__call__`
cancellation warning remains; this display change does not resolve that lifecycle issue.
The native package includes the executable and excludes private state/archives.

The focused 29-test run checks zero-gutter input at 40/80/160/200 columns in ordinary
and inspection views. A full-width 120-column transcript row survives actual tmux copying,
resize, inspection and exit without loss/duplication. Existing shell/150-row/stream retention
checks also pass. Private edge-to-edge input and both live-preset captures were inspected.
The [live receipt](evidence/edge-to-edge-live.json) records two turns for each preset,
successful read_file/load_skill, ordinary keyboard controls and exit 0. Tests use isolated
state, not the steward's conversation. Existing local edits and running app remain intact.

The [renderer benchmark](evidence/edge-to-edge-benchmark.json) ran separately after tests,
builds and live calls: 30 startup pairs and 18 stress cells through 100,000 retained items.
Ratatui worst-cell editing p95 was **20.920 ms**, stream p95 **21.380 ms**, peak RSS
**135108 KiB**. First editable response median/p95 was **55.996/60.124 ms**; these are
synthetic renderer observations, not matched CLI-policy parity or a startup non-regression
claim. Source fingerprints match the measured renderer. All test resources were reaped;
only the intentionally retained private repository and development command link remain active.

Review focus on relaunch: do the composer and ordinary text now meet both terminal edges,
without application-added spaces in copied multiline text? Linux PTY/tmux 3.4 is verified;
terminal-emulator padding and other platforms are outside this change.

## Full-height workspace and open input (2026-09-14)

WORKSPACE-01 follows the steward's explicit request. The per-repo-conventions workflow
amended VISION and presentation P5/P6 before implementation; all direction remains DRAFT.
This deliberately adapts the studied Codex mechanisms, not every Codex startup path.

- Startup moves the preceding whole screen into native history and opens a fresh primary
  page. The composer sits at the bottom while the transcript grows above it. No alternate
  screen or cursor-position query is needed for startup; early input stays editable.
- Ordinary and inspection composers have no side borders or repeated prompt characters.
  The mode, available actions and a bounded conversation title remain visible. Live views
  omit Ratatui/LIVE RUNTIME and say simply Ready; fixture/simulation warnings, errors and
  independent tool-outcome qualifications remain. Rename still updates the visible title.
- Real tmux tests cover shell origins at top/middle/bottom, exact multiline Unicode copy
  buffers, 150 committed rows, copy during streaming, narrow/wide resize, resized inspection
  return and direct quit, terminal-mode restoration and retained exit output. Tests count
  markers once and verify no leftover composer, not merely a surviving screenshot.
- Full-pane previews contain the transcript. Bottom-only crops may omit short replies
  above the unused space; the steward's new full-height direction supersedes that earlier
  compact-preview guarantee. Terminal scrollback capacity remains terminal-owned.

Two implementation defects were reproduced and fixed: ED at row zero can archive a
provisional full-height frame in tmux; owned-line EL avoids that. Returning from resized
inspection must query the restored primary anchor, not subtract the old live height and
erase short replies. The test observer also now checks actual PTY TIOCGWINSZ before the
next edit: tmux's grid can resize before its PTY. Capturing that intermediate state is not
proof of a completed application redraw. These lessons live in SMOKE_TESTS and ENGINE-BOUNDARY.

Final verification: **344 Python tests passed**, **25 Rust tests passed**, Clippy with
warnings denied, Rust formatting, Ruff/format, direction/archive-integrity checks and
wheel/sdist build. The full suite emitted two cancellation warnings (`run_orchestrator`
and `LoggingHandler.__call__` not awaited); this wave does not resolve runtime cancellation
ownership. Package contents include the native binary and omit private state/archives.

The [live receipt](evidence/workspace-live.json) records both presets, two turns each,
successful read_file/load_skill, keyboard Actions/evidence and exit 0. Actual ready and
completed captures for both presets were inspected privately. No user conversation was
opened, migrated or stopped; the existing development command picks this up on relaunch.

The [benchmark](evidence/workspace-benchmark.json) ran after our tests/builds/live calls:
30 startup pairs and 18 stress cells through 100,000 retained items. Ratatui's worst-cell
edit p95 was **21.301 ms**, stream p95 **21.844 ms**, peak RSS **135152 KiB**. First editable
response median was **41.453 ms**, p95 **57.901 ms**. All 21 live and 25 benchmark source
fingerprints match final code. These are synthetic renderer measurements, not matched
CLI-policy or cold-start parity. All test resources were reaped; the private repository
and development command link remain intentionally retained. Existing local edits are preserved.

Review focus: does the fresh-page startup now feel like the expected workspace, and do
multiline selections feel natural in the steward's terminal/tmux configuration? Linux
PTY/tmux 3.4 is the exercised environment; no universal terminal claim. Resize queries
still have the finite two-second fallback, including return/exit from resized inspection;
ordinary startup and unchanged-size exit no longer need such a query.

## Direct Codex adoption: quieter native surface (2026-09-14)

QUIET-01 / STARTUP-03 / TERMINAL-02 follow the steward-approved direct source study.
The per-repository conventions workflow drove the VISION/presentation amendments first,
then implementation and evidence. Contracts remain DRAFT. This is an original Ratatui
app implementation, not a copied Codex runtime, replacement kernel or full parity claim.

- Ordinary idle controls occupy five rows plus an empty cursor-anchor separator,
  instead of ten permanent dashboard rows. The glyph-wrapped editor grows to six text
  rows. Mode stays visible, long titles are bounded, and Queue/Steer/Stop/questions/pending
  controls earn space when relevant. Existing Actions routes remain available.
- Real hosts report readiness explicitly. Early typing, Unicode, selection and undo
  survive startup; premature Enter never auto-submits on readiness. A late restored draft
  becomes a scoped copy-only recovery entry, persisted before a replacing mutation.
  Corrupt/full backup storage refuses the mutation; no text is injected into model context.
- Missing CPR replies fall back after Crossterm's existing two-second timeout using
  CRLF, not a scrollback purge. Input stays buffered. This is not Codex's 100 ms probe.
- Actual tmux tests preserve the pre-app shell marker, all 150 transcript rows, selection
  through history, copying during active streaming, overlay return and exit output.
  Startup is tested at top/middle/bottom positions. Resize also counts live borders:
  parking on the wide border let tmux reflow its anchor onto a continuation and leak
  stale chrome. An empty live separator fixes this without purging history or sleeping.
  The growth floor now applies only to height growth with an unmoved cursor.

Verification: full native/presets/swaps suite **341 passed** (before the final title-width
cap); final compact/tmux/workflow/observer checks **13 passed**, final default suite
**262 passed / 80 optional skips**, Rust **24 passed**, Clippy warnings-denied, Ruff/format
and direction/archive-integrity checks pass. Full integration still emits four instances
of the previously observed unawaited upstream hook-cancellation warnings; not resolved.
A random UUID containing `999` also exposed a false-positive context-isolation assertion;
that test now checks structured observations instead of searching serialized identities.

Final [live receipt](evidence/compact-live.json): both presets, two turns each, actual
`read_file` and `load_skill` success, keyboard Actions/evidence inspection and exit 0.
The real development PATH link also passed a fixture tool turn from an isolated cwd,
saved an unsent Unicode draft and restored the terminal. No real user conversation was
opened or migrated. Private native `compact-*`, `anchors-inline`, `anchors-amp-dev-inline`
and `compact-development-command` captures were inspected; screenshots are not published.

Final [benchmark receipt](evidence/compact-benchmark.json): 30 alternated startup pairs
and 18 stress cells through 100,000 retained items, run without our tests/builds/provider
work. Ratatui worst cell typing p95 **20.837 ms**, stream p95 **20.998 ms**, peak RSS
**135184 KiB**. First editable response median **46.893 ms**, p95 **61.441 ms**; scene
readiness is separate. The observer now locates the provisional composer rather than
waiting for Send, and recognizes typed tokens across wrapped rows in both candidates.
All 25 benchmark and 21 live source fingerprints match the final tree. These are
synthetic renderer measurements, not cold-start or matched CLI-policy parity. All test
resources are reaped; only the intentionally retained private repo and command link remain.

Remaining scope: visual acceptance by the steward, a shorter owned terminal probe,
unflushed/pre-store startup durability, matched CLI-policy performance, cross-platform
terminal coverage, quieter outcome/status wording and the existing partial-init/hook
cleanup gaps. No global theme replacement, history-purging replay or unbounded queue
was imported. Review question: does the smaller growing composer now leave the right
amount of room for the conversation while keeping mode and actions discoverable?

## Opt-in development command (2026-09-14)

At the steward's explicit request, the ordinary PATH command now follows this checkout
through a symlink to `scripts/dev-launch`. No previous PATH command was overwritten.
The wrapper uses the existing workspace environment and conversation store, preserves
caller cwd, forwards arguments and checks a locked incremental native build before each
interactive launch. Build failure refuses the stale UI; diagnostics do not build. It does
not hot-reload a running session, auto-sync Python dependencies or change release defaults.
The external link is recorded in the workspace manifest and must be removed/replaced
before destroying the checkout. User conversation files and shared CLI installations
were not changed. No new vision promise or formal ratification was needed.

Verification: six wrapper tests plus onboarding/installation tests **30 passed**; the
default suite **258 passed / 74 optional tests skipped**. Ruff/format/direction checks pass.
The actual user PATH link passed doctor/version/check, native build and a real fixture
tool turn from a different cwd, with isolated state and terminal cleanup. An initial probe
accidentally used uv's prepended editable console script; resolving the user's command
before that PATH change fixed the test target. All test process groups were reaped.

## Newcomer approachability — 0.2.1 (2026-09-14)

WELCOME-01 / SETUP-01 move toward interaction P1/P6 and ecosystem P1. Vision/contracts
were clarified first and remain DRAFT. This is guidance and local diagnostics, not new
execution policy, provider onboarding automation or a claim of complete CLI parity.

Implemented:

- `--getting-started` explains a first live conversation versus the labelled fixture,
  costs/trusted module loading, ordinary controls, returning and safe troubleshooting.
  It works without a key, native binary or existing state. README links a short
  [first-conversation guide](../docs/GETTING-STARTED.md) and [support guide](../docs/SUPPORT.md).
- `--check` names local blockers and next steps for the binary, cwd, state location,
  default key, Git and terminal. Custom provider requirements remain unknown. It creates
  no probe files, loads no runtime, makes no network request and validates no credential.
  Access checks do not prove a subsequent write, filesystem quota or remote readiness.
- `--support-report` emits an allowlisted JSON shape, with no paths/environment values,
  usernames/hostnames/configuration files/transcripts. It is separate from path-bearing
  doctor output; users review before sharing and nothing is uploaded. Error checks exit
  1; warnings alone exit 0. Doctor now also fails for a non-executable binary.
- Actions starts with Getting started. Seven Help topics explain ordinary tasks rather
  than only shortcut hints. Topics are local, scrollable, preserve drafts and never send
  their examples. Initial captures exposed squeezed text; topic layout now allocates
  reading room with width-safe scroll hints. Real 40/160-column captures were inspected.
- Non-terminal native launches give a clear error before resume/recovery can touch saved
  state. Informational commands, export/list and the separate headless entrypoint remain
  usable without a terminal. No shared CLI state, credential or user conversation changed.

Early verification: full native/preset/swap suite **324 passed** in 146.73 seconds;
after moving terminal validation before recovery, **16 focused onboarding tests** pass
(including two added cases). Rust **21**, Clippy with warnings denied, Ruff/format and
direction/archive checks pass: 563 contract lines, 46 production files, 51 work items.
The intermittent cancellation warning did not occur in this run; no fix is inferred.
Wheel/sdist build from locked Rust sources succeeds. Initial isolated installed-wheel
fixture and both live presets pass guidance/no-state inspection, help without submission,
tool turns and resume; these receipts precede the final terminal-validation ordering fix.
Final source regression: **326 passed in 142.84 seconds**, with two existing unawaited
coroutine warnings during anchors-amp-dev child-question cancellation (child observation
and module hook handler). This confirms those intermittent warnings remain unresolved.

Final delivery proof at runtime source `683b3d87dcd41d8c7f50bfc6d85a3ff4ae3e502a`:

- Actual private-Git installation succeeds at 0.2.1, not just an editable/workspace build.
  [Fixture receipt](evidence/onboarding-git-fixture.json) and
  [both-preset live receipt](evidence/onboarding-git-live.json) exercise offline guidance,
  allowlisted diagnostics without state creation, help with zero submissions, actual
  child read_file, completed turn, resume with no implicit submission, and marker recall
  on a second turn. Four root/two child live turns in the final gate; the earlier wheel
  gate also billed four root/two child turns. Captures remain private and were inspected.
- All **27 installed Python source fingerprints** match the final source tree; version,
  native binary and entrypoint hashes are recorded. Core 1.6.1 and the existing Foundation
  source pin remain unchanged. Later docs/evidence commits do not amend this runtime proof.
- The documented `uv tool install --reinstall` upgrades a separate prior 0.2.0 Git tool
  environment to 0.2.1. It removes dynamically installed module packages while rebuilding
  that environment, so the next ordinary launch must be allowed to reinstall dependencies.
  An earlier test-owned anchors conversation reached ready afterward, with **zero new
  turn submissions**. This is same-path/default-composition upgrade evidence, not general
  migration or arbitrary-module compatibility. No user conversation or shared CLI was used.

[Final renderer timing](evidence/onboarding-benchmark.json), run separately after all
tests/builds/live probes: 30 startup pairs and all 18 stress cells complete, including
100,000-item history and cleanup. Ratatui worst edit p95 **20.545 ms**, stream p95
**21.109 ms**, peak RSS **135196 KiB**; first usable median **42.327 ms**, p95 **58.694 ms**.
All 24 source fingerprints match. This is warm-cache scene/renderer evidence, not cold
installed startup, menu-reading speed, provider latency or policy-equivalent CLI parity.
The initial latest-1000 native replay bound still differs from the comparator's viewport.
Workspace resources reconciled: 3,616 records, no active test-owned resources. The sole
active entry is the intentionally retained private GitHub repository; visibility unchanged.

Limitations remain explicit: no key storage/import/wizard, remote authentication check,
automatic repair, public visibility/access changes, prebuilt-wheel distribution or new
platform claim. The default provider, bundle/module authority and retained conversation
policy are unchanged. Cross-platform/new-user field trials remain separate from developer
captures and deterministic/runtime evidence.

## Earlier receipt: private Git-installed native product 0.2.0 (2026-09-14 UTC)

This section supersedes historical packaging, source-queue and branch statements below.
Direction was amended before INSTALL-01, OUTCOME-01 and STARTUP-02 implementation;
all vision/contracts remain DRAFT, not formally ratified.

Session review found early missing-spawn failures before an updated-host restart, followed
by three successful actual delegated children. The assistant's production-readiness claim
exceeded its 228-pass/72-skip test evidence. Its Git demonstration made real local changes;
the original test-drive branch, report, marker and modified test bytes were preserved.
The earlier saved composition lacks the question overlay; resume deliberately does not
silently retrofit it. No real user conversation was resumed, executed or migrated by this wave.

Implemented:

- `amplifier-tui` now launches packaged Ratatui, version 0.2.0; `amplifier-tui-host`
  retains the diagnostic/historical entrypoint. Wheel build compiles locked Rust sources;
  sdist includes native source, Cargo lock and build hook. Editable development remains
  separate. No kernel/upstream production edits and no silent Textual fallback.
- Installed launch resolves pinned remote Foundation presets, packaged provider/question
  overlays and independent modules without sibling checkouts/source maps. State is separate
  XDG user data; explicit overrides and guarded existing-state access remain. Version/doctor
  and System expose running identity without printing credentials or calling a model.
- Turn-end summaries count observed root/child tool outcomes independently of assistant
  confidence and loop completion. Child pre/post events count as one call; failed commands
  remain failed even when the parent loop completes. This is not test-coverage attribution.
- Host pending event delivery is capped at 4096 records / 8 MiB serialized payload.
  Journal writes precede delivery; overload closes the connection, stops admission/work,
  retains uncertain state and never retries automatically. Consumption releases byte budget.
  This does not bound all Python heap, canonical context or arbitrary module tasks.

Private publication: [bkrabach/amplifier-app-tui](https://github.com/bkrabach/amplifier-app-tui),
runtime source tested at `66cac722e7b1bde2236c5218e704c1de05b5c548`. The clean `main`
snapshot excludes the earlier git-demo history, private session artifacts, machine paths,
archives and caches. The original local branch was not pushed. Later documentation/evidence
commits do not change this runtime proof. The repository is intentionally retained under
the steward's account and recorded in the workspace resource manifest.

Installed execution evidence:

- Actual `uv tool install git+https://github.com/bkrabach/amplifier-app-tui` succeeded
  in isolated tool/bin directories, using scoped GitHub authentication, with no shared
  CLI/tool-environment mutation. Linux ARM64, core 1.6.1, Foundation source
  `e210edabd947af82d5121a240d6934283ac540b9` (distribution version 1.0.0).
- [Git-installed fixture receipt](evidence/git-installed-fixture.json) and
  [Git-installed live receipt](evidence/git-installed-live.json): outside the source
  checkout, no source map; both live presets delegated an actual child read_file, completed,
  reopened with zero implicit submissions, then recalled the marker in a new tool-free
  turn. Four root/two child live turns in this final gate. The installed question tool was
  mounted; interactive answering remains separately exercised by earlier question gates.
- All 26 installed Python source fingerprints match the tested source tree. Receipts
  also identify package version and native/entrypoint hashes. Live captures were inspected:
  inline transcript and resume work, Activity shows identified bounded JSON observations,
  not a polished narrative; historical pre/post rows are not separate active agents.
- Earlier local-wheel gates also passed both presets. Those receipts precede the final
  source-delivery guard and are not substituted for the final Git-installed evidence.

Regression verification: `TUI_TEST_SWAPS=1 TUI_TEST_PRESETS=1 TUI_TEST_CANDIDATES=1
PYTHONDONTWRITEBYTECODE=1 uv run --no-sync pytest -q --tb=short`: **308 passed** in
144.48 seconds, one unawaited `Children.execute` observer-coroutine warning during the
anchors-amp-dev child-question cancellation test. The warning is recorded, not waived as
fixed. Rust **21** tests and Clippy with warnings denied passed; Ruff check and format
check passed without excluding the steward's reformatted event test. Direction structure
checks pass: 560 contract lines, 45 production source files, 49 work items, all DRAFT.
New fault coverage includes journal retention, count/byte limits, released byte budget,
no initial execution on overload, and connection exit with stdin still open.

[Final synthetic performance receipt](evidence/installed-benchmark.json): 30 alternating
startup pairs and all 18 stress cells completed, including cleanup. Ratatui worst edit
p95 **20.550 ms**, stream p95 **21.064 ms**, peak RSS **135200 KiB**; first usable median
**42.456 ms**, p95 **59.822 ms**. Run separately after builds/tests/live calls; all 24
source fingerprints match. This measures the scene/renderer, not the new host delivery
serialization cost, installed cold startup, provider latency or equivalent-policy CLI speed.
Initial native replay remains disclosed/latest-1000 versus the comparator's virtual viewport.
Resource reconciliation: 3,379 records; no active test-owned resources. The sole active
entry is the intentionally retained private repository, not a leaked test process.

Remaining limits: source installation needs uv, Git, Rust/Cargo and a C linker (Rust 1.93
tested). macOS builds are not exercised; Windows uses WSL2. First uncached preset launch
downloads/installs trusted executable modules and is slower than cached startup. No automatic
CLI credential/settings/history migration or arbitrary recorded-path relocation. Foundation
still withholds a session handle until initialization returns, and cancellation-time hook
coroutine warnings remain. Image input, instruction-source context inspection, attributed
Git/test evidence, broader child/private-context migration, all policy seams and matched
end-to-end CLI performance remain work—not production-readiness claims.

## Historical first-slice receipt

Recorded 2026-09-12. This is an implementation receipt, not a formal Converge ledger.
All new vision/contracts remain DRAFT; the user separately authorized implementation.
The decisive multi-session scenario in the handoff is **not yet complete**.

This historical receipt predates the [direction amendment](DIRECTION-REVIEW.md).
Its passing tests do not establish visual acceptance or the new performance/ecosystem
promises. The existing UI was rejected as a match for the concept; it is retained as a
developer harness. At that point no CLI baseline or replacement frontend had been measured.
The later [terminal comparison receipt](TERMINAL-REVIEW.md) records the new candidates.

## Implemented and exercised

| Boundary | Evidence | Result |
|---|---|---|
| Composition/session P1 | Actual Foundation preparation, Rust-backed core, explicit exported-tool requirements, failed tool/hook load | Ready only after checked initialization; failures refuse admission |
| Session P2–P4 | Concurrent submits, second turn context, provider error, unknown completion, immediate stop | One active turn; distinct rejection/completion/failure/interruption/unknown |
| Session P5, presentation P3–P4 | Independent SHA-256 tool and generic event projection; confident response after tool failure | Tool result stays failed; deltas reconcile into one final block; duplicate event replay has no effects |
| Presentation P1–P2 | Textual Pilot: delayed startup, Unicode multiline draft, selection, paste, streaming, busy submission, tabs, resize | Draft/selection retained; paste does not submit |
| Approval/control subset | Allow, invalid/stale/repeated answer, timeout, stop while pending, stale widget click | Request-specific and single-use; denied/expired request cannot authorize later work |
| Terminal lifecycle | Linux PTY, actual CLI/driver, bracketed paste, completed fixture turn, startup failure and quit | Alternate screen exited, bracketed paste disabled, termios restored exactly |
| Ecosystem subset | Both fully hydrated presets prepared and mounted with independent fixture provider; registered policy hooks checked | Same host, 9/13 agent definitions, no upstream source edits |

Re-run: `TUI_TEST_PRESETS=1 PYTHONDONTWRITEBYTECODE=1 uv run --no-sync pytest -q`:
**26 passed**. Ruff check and format check also passed.
Default tests skip two full-preset tests until `TUI_TEST_PRESETS=1` and the README's
full source/dependency setup are supplied. Fixture tests need only the two upstream
loop/context checkouts; no live provider credential.

`uv build` produced wheel and sdist. The wheel was installed into a fresh virtual
environment with its declared dependencies, separately from the development environment.
The installed fixture passed from outside this project's source directory: 9 identified
events, successful SHA-256 tool result, one final text block, completed outcome and exit 0.

## Live provider evidence

Real Anthropic `claude-haiku-4-5` calls, upstream `provider-anthropic`,
`loop-streaming`, `context-simple`, and `tool-filesystem`:

- Minimal `examples/live.yaml`: read pyproject.toml through read_file; correct project
  name returned; streamed text finalized once; completed outcome and process exit 0.
- `anchors` plus `examples/anthropic.yaml`: same read-only action, 12 identified
  host events, read_file succeeded, one final text block, completed/exit 0.
- `anchors-amp-dev` plus the same provider overlay: same outcome and event count.

The two preset runs were repeated after implementing environment expansion and
initializer failure checks. Earlier runs demonstrated a provider/tool round trip but
had a failed context-intelligence hook; those earlier runs do **not** establish healthy
preset mounting. Final runs registered LoggingHandler, approval_hook, hook-redaction
and hooks-status-context with no initializer warning. Raw logs remain workspace-local,
not committed; commands to reproduce are in SMOKE_TESTS.md.

These are one provider and one read-only action per composition, not CLI policy parity,
all-tool conformance or proof that development infrastructure is available.
No DTU, Gitea instance, delegated child, remote session or other external service was created.

## Simulated, unsupported and untested

- **Simulated:** only the explicitly labeled fixture provider. Its tool really computes
  a SHA-256. The supplied HTML concept remains a separate simulation, not this runtime.
- **Unsupported:** durable drafts/history/decisions, queue, correlated steer, resume,
  reconnect, delegated execution/spawn, child scopes/results, context-choice provenance,
  edit attribution, stale-edit protection and consolidated diff/verification review.
  Review currently presents tool evidence only. Context remains the selected upstream module.
- **Unsupported parity:** CLI settings and policy overlays, slash commands/skills menu,
  dynamic provider switching, multi-conversation supervision, authenticated remote protocol.
- **Untested:** other live providers/orchestrators/context modules, arbitrary hook renderers,
  real IME, Windows/macOS, very large conversations, noncooperative blocking tools,
  fatal mid-initialization failures and signal/kill during arbitrary plugin initialization.

The in-memory projection is idempotent, not a durable replay journal. Memory grows with
the conversation. Stop requests immediate cancellation but cannot undo effects or bound
an extension that blocks/swallows cancellation. If Foundation fails before returning a
partially created session, this host has no public handle for guaranteed cleanup; see
ENGINE-BOUNDARY.md. The initializer diagnostic fallback is pinned and process-scoped.
Logged warnings catch load failures, not a module silently omitting promised behavior;
only explicitly required exports and observed handlers are verified.

## Provenance and method

The read order was original method → ecosystem blueprint → Codex blueprint → DESIGN
and simulated concept, before authoring this project's direction. Archive SHA-256:

| Supplied archive | SHA-256 |
|---|---|
| Original-Converge-Documents.zip | f74eb3122f4003144dc00e5590818a450a6221bfe4ccc449b88cd9dc49bb0b17 |
| Amplifier-Ecosystem-Converge-Blueprint.zip | ff25b818b6ef1dbb2a3da896e574ee23c75ed9a7f7f94426d766477dd1c814d2 |
| Codex-Converge-Blueprint.zip | e3c775bff6f9e94d5b991a84be1377b0a7e999739d4b6c0753f0ec2eee3280e1 |

The original hierarchy was docs/VISION.md → contracts/composition.v1.md → session,
presentation and continuity contracts; the amendment adds ecosystem and performance.
The root delegates seam details; notes do not create additional promises.
Document tests check declared state syntax, shape, sizes, promise
counts and observable numbered signs; they do not confer ratification or a formal verdict.
No separate worker lanes or formal ledger rows were invented for this implementation.

sources.lock.json records 28 inspected repos and 45 recursively resolved source URIs,
including hydrated child metadata. Source overrides reproduce those actual workspace
checkouts instead of silently resolving moving `main` refs again. Runtime host dependencies
are in uv.lock; core is the PyPI 1.6.1 release, whose peeled tag is
5a102ac53da72c1efeb6b248d9474f368e7deda6, not inspected HEAD
6d4cd217f83bb29b671b5c9d854aaa08be14db1b. Latest HEAD's correlation helper was inspected,
not executed. Transitive dynamically installed module dependencies are not fully locked.

## Next work

The [current sourced plan](PLAN.md) supersedes the first slice's sequencing: review the
terminal comparison, close the policy-equivalent CLI and lifecycle/ecosystem gaps, then
choose the frontend/runtime boundary from that evidence. Preserve
the handoff's full decisive scenario as a later acceptance target, not this slice's claim.

## Direction amendment verification

The supplied archive fingerprint and all nine method-file fingerprints were verified.
The direction check reads six DRAFT contracts, 437 total contract lines, language-independent
source-file counts and fourteen uniquely identified work items with resolvable promise IDs.
It generates no formal verdicts. State parsing permits the method's future ratified/locked
headings without granting authority to apply them; promise numbers may have retired gaps.
Negative tests cover malformed state/section/promise/example/size/sign shapes, invalid work
references, duplicate work identities, broken links and source drift. Private archives are
ignored and explicitly excluded from builds. Runtime code is unchanged in this amendment.

Verified 2026-09-12:

- `TUI_TEST_PRESETS=1 PYTHONDONTWRITEBYTECODE=1 uv run --no-sync pytest -q`: **45 passed**,
  including 21 direction/provenance checks and both preset mounts.
- `uv run --no-sync ruff check .` and `uv run --no-sync ruff format --check .`: passed.
- `uv run --no-sync python scripts/check_direction.py --archive amplifier-converge-vision-contracts-20260909T213649Z.zip`:
  structure, references and supplied source integrity passed; no formal verdict emitted.
- `uv build`: wheel and sdist built; inspected both inventories and confirmed neither
  contains ZIP archives. The supplied archive remains untouched and ignored locally.
- Preserved HTML reference matches the supplied concept byte-for-byte. All upstream
  source trees remain clean; the workspace resource manifest has no active resources.

These checks complete DOC-01/DOC-02's amendment and verification work, not visual,
performance or ecosystem acceptance of a replacement runtime. No new live provider calls
were needed for this documentation/checking amendment.

## Executed terminal comparison

Recorded 2026-09-12 after the steward authorized execution. The new code is two terminal
candidates plus an experimental bidirectional adapter to the existing host, not a final
architecture choice or full product port. Vision/contracts remain the same DRAFT destination;
work and evidence changed under their named promises, without changing the promises to fit.

- **60 Python tests passed** with TUI_TEST_PRESETS=1 and TUI_TEST_CANDIDATES=1, including
  ten new real-terminal cases and five bridge/admission tests. Three Rust and three
  TypeScript tests passed; Ruff, Rust Clippy and TypeScript typechecking passed.
- Both candidates passed actual PTY view, evidence, paste, selection, resize and quit
  scripts. Clipboard tests assert the emitted OSC52 payload decodes to the exact result.
  SIGTERM and refused startup restore termios; killed backends retain drafts and report
  uncertainty without retries. Terminal-tester capture adapters are local, not upstream edits.
- The 18-cell synthetic stress matrix and 30 alternated fresh-start pairs have original
  samples in notes/evidence. Each stress cell has at least 200 input/update observations;
  measured p95s are under 50 ms. This is a scoped matrix result, not the whole performance contract.
- Thirty real-fixture runs per frontend and isolated CLI provide integrated timing context.
  CLI composition differences prevent a matched performance-P2 verdict. No daily installation
  settings or editable-module pointers were repointed to the test environment.
- Two **live Anthropic** turns through the new frontends passed: Ratatui/anchors and
  OpenTUI/anchors-amp-dev, each with read_file success and a completed outcome. No shell,
  file write, delegated agent or external service was requested for those turns.

Captures, precise review question, adaptations and residuals are in
[TERMINAL-REVIEW](TERMINAL-REVIEW.md). The live path has no durable drafts/resume,
queue/steer/delegation, slow-reader recovery or guaranteed pre-return initialization
cleanup. Independent swaps at every ecosystem seam still remain to be exercised.

Final packaging check: wheel and sdist built; both inventories exclude private archives,
runtime state, capture intermediates, node_modules and native build output. The installed
wheel ran a completed nine-event fixture turn from outside the project directory. Source
fingerprints match both benchmark receipts. All upstream source trees are clean and the
workspace manifest has zero active test resources. No commit or publication was requested.

## Full-width correction after steward review

Recorded 2026-09-12. The steward found the two clients visually alike and the layout
did not use the terminal width. They were deliberately implementing the same design,
but the handoff did not make that distinction useful. Both renderers also imposed a
112-column centered cap, an unaccepted adaptation missed by the earlier capture sizes.

Amended the DRAFT vision and presentation P6 first, then derived UI-03. Both clients
now use the available width with small edge padding. Engine and simulation/runtime
identity precede the context so they remain visible at narrow widths. README, launcher
help and the review packet distinguish one design from the two rendering engines.
The per-repo-conventions skill guided this direction-first correction and the app-owned
wide-terminal verification gate in SMOKE_TESTS.md; no upstream policy was changed.

Verification:

- **64 Python tests passed**, including four new real-PTY wide-launch/resize cases,
  both real fixture-runtime clients and both preset mounts. Tests assert actual header,
  composer and approval edges at 160/200 columns, repeated narrow/wide transitions,
  draft retention, busy rejection and clean terminal restoration.
- **3 Rust and 3 TypeScript tests passed**; Ruff lint/format, Rust formatting/Clippy,
  TypeScript typechecking and Prettier passed. The Rust release executable was rebuilt.
- Both terminal-tester capture sequences passed; inspected actual 200×40 images for
  each engine and a 60×20 capture. Current full-width images are linked in
  [TERMINAL-REVIEW](TERMINAL-REVIEW.md); older capped captures remain historical.
- Direction structure/source-integrity checks passed: 438 contract lines, 13 production
  source files, 15 sourced work items. No ratification or formal verdict was created.
- Wheel and sdist built. No execution policy or runtime boundary changed, so no new
  billed provider call was needed. Previous timing receipts identify older source
  fingerprints and are not performance acceptance of this changed rendering revision.

This closes the concrete width correction, not the steward's subjective design review
or the remaining product/CLI-parity gates. Existing local changes are preserved.

## Discoverable interaction and ecosystem viability

Recorded 2026-09-12 after the steward authorized source reconciliation and functional
ecosystem wiring. The per-repo-conventions skill guided the direction-first amendment,
source ownership and actual-terminal verification. Added DRAFT interaction.v1 beneath
presentation, then derived UX-01/RUN-01. The source reconciliation names what was adopted
and what remains a gap; it does not imply every researched interaction is implemented.

Ratatui is the working integration client, not a frozen final framework. OpenTUI and
Textual remain historical comparison/regression clients. `scripts/run.py` now launches
real ecosystem execution explicitly; `scripts/compare.py` still defaults to simulation.
No upstream source was modified and no code was committed or published.

Implemented and exercised:

- Visible Actions/Send/Stop and view controls, keyboard focus, searchable local menus,
  mouse activation, evidence/copy, local sent-message recall, help and ordinary quit.
  Slash in an empty draft opens Actions; pasted slash text remains draft text. Menu
  Escape preserves the editor and selection. The entire ordinary approval/tool workflow
  has a Tab/Enter/Escape-only test, not just a shortcut-based automation script.
- Approvals retain the actual runtime option strings and request IDs. Full questions
  and option descriptions are scrollable. Multiple host requests are displayed FIFO;
  a resolved request cannot silently retarget an already focused menu. A controlled
  event-fixture race proves no stale answer is sent; actual SessionHost tests prove
  queued options and answers retain their original scope.
- System separates mounted tools/providers, authored agent definitions and unsupported
  controls. Skills discovery uses the module's public optional capability, without
  importing its implementation or loading a skill. The catalog is a startup snapshot.
  Origins/overlays/hook evidence remain separately inspectable as diagnostic data.
- The credential-free real-kernel probe completed two approved fixture-tool turns through
  ordinary controls. [Fixture receipt](evidence/interaction-fixture.json).
- **Four live Anthropic Haiku 4.5 turns passed:** anchors and anchors-amp-dev each executed
  read_file(pyproject.toml), then load_skill(list=true), observed succeeded tool states and
  completed turn outcomes, inspected evidence, and quit via Actions. Both also displayed
  their public skill-discovery catalog. [Live receipt](evidence/interaction-live.json).
  This proves those operations and a continuing conversation, not all-module conformance.

The first live probe stopped after a successful read_file because its assertion searched
for a nested `success` field below the visible viewport. The inspected screen showed
`status: succeeded`; the probe was corrected to assert that visible result, then both full
two-turn runs passed. This was an observer assertion failure, not hidden runtime success.
Live raw captures can contain local file paths and stay ignored; only fixture captures
are selected for the review packet.

Verification includes Python host/module, both-preset, Linux PTY, startup/disconnect,
selection/paste, wide resize and new interaction regressions; Rust/TypeScript tests;
Ruff, Clippy, formatting, direction/source integrity and distribution build checks.
The direction check now reads seven DRAFT contracts (514 lines), fourteen production
source files and seventeen sourced work items. It emits no formal Converge verdicts.

Final run: **72 Python tests passed**, including seven new ordinary-interaction cases
and the approval-queue adapter case; **3 Rust and 3 TypeScript tests passed**. Visible
Stop was exercised during an actual delayed fixture tool with the correction retained.
Both original capture/resize sequences still pass. Ruff/format, Clippy/Rust formatting,
direction/archive integrity and wheel/sdist build passed. Live and fixture interaction
receipt fingerprints match the final exercised frontend/host/launcher sources.

Actual fixture terminal captures: [searchable actions](evidence/interaction-actions.png)
and [scoped decision choices](evidence/interaction-decision.png). They demonstrate the
implemented controls, not live-model quality or native font/IME conformance.

Remaining: attachment/semantic-reference completion, durable drafts/history/resume,
queue/steer, structured user questions, provider switching, a mode picker, delegated
execution and policy-equivalent CLI acceptance. The ordinary workflow is now testable
against real modules; subjective UX acceptance and complete ecosystem viability remain
separate judgments. Earlier timing matrices predate this interaction code; no new speed
claim or matched engine comparison is made.

## Reading, editing and return wave — 2026-09-12

Source: steward requested Markdown, proper scrollback, conversation resume, boundary
Up/Down history and Tab completion. VISION, presentation P3, interaction P3–4 and
continuity P1 were amended before READ-01 / EDIT-01 / RETURN-01 implementation.
The per-repo-conventions skill kept direction, implementation and evidence separate;
new lessons belong in this app's SMOKE_TESTS, not upstream module/kernel instructions.

Implemented in the working Ratatui client:

- CommonMark-derived headings, emphasis, lists/tasks, quotes, links, fenced/inline code
  and simple table-cell fallback. Unicode grapheme-aware styled wrapping; untrusted
  controls are stripped, HTML is inert and links/images cause no network requests.
- Lazy per-item layouts with item/visual-row anchors. Wheel movement is three lines;
  page movement overlaps by two rows. New output does not move a pinned reader;
  Latest restores tail following. Review uses an index of tools, not repeated scans of
  all assistant history. Resizing retains the item/row, not an exact source character.
- Boundary-aware sent history, original editor/cursor restoration, explicit local
  command and discovered-skill Tab completion, and clearer selected-view styling.
  Skill suggestions are plain text, never claims that a skill has been loaded.
- Private single-writer conversation storage in the app host, not the thin kernel:
  fsynced admission, incremental observation journal, atomic full-context checkpoints
  at completed turns, and separate debounced draft text. `--resume [ID]` and
  `--list-sessions` restore launch identity and canonical context through public
  context get/set APIs. Corrupt/order-mismatched journals, changed effective module
  config, concurrent writers and uncertain checkpoints refuse continuation.

Verification: **86 Python tests, 7 Rust tests and 3 TypeScript tests pass**. Python
includes the existing two-preset, approval, cancellation, disconnect, wide-resize and
keyboard/mouse workflows plus eleven storage tests and three new reading/editor PTY
tests. The fresh-session fixture asserts zero provider/tool calls during restore,
then checks the earlier text in the next provider request. Corruption tests include an
empty journal, missing/duplicate entries and a truncated record. PTY gates assert exact
terminal restoration on exit, not just visible text. Ruff, formatting, Clippy,
direction/archive checks and distribution build are checked separately.

Live proof: both anchors and anchors-amp-dev performed read_file(pyproject.toml),
closed with an unsent memory question, resumed in fresh processes, and correctly
returned the unique marker supplied only before restart. The new turn used no tools.
The assertion reads the **new identified assistant answer**, not the old visible
transcript. [Live receipt](evidence/reading-live.json) records the final four-turn run;
an earlier four-turn run also passed before the corruption/reference guards were
tightened. No private marker, credentials or transcript is published in the receipt.

[Current synthetic timing receipt](evidence/reading-benchmark.json): 30 alternated
startup pairs and 18 stress cells (1k/10k/100k history × 30/100/500 deltas/s × two engines).
Ratatui worst p95 key-to-visible edit **21.316 ms**, event-to-visible update **20.262 ms**;
maximum frontend RSS **134372 KiB**. First-usable median **40.436 ms**, p95 **75.329 ms**.
These include observer/scheduler cost. They measure the scene transport and renderer,
not fsync-enabled host latency, cold caches or policy-matched CLI equivalence. OpenTUI
is a historical implementation comparator, not a matched feature set. Earlier timing
receipts are preserved, not overwritten. No complete performance-contract verdict follows.

Actual [Markdown/scrollback terminal capture](evidence/reading-markdown.png) was inspected;
it is clearly a simulated projection probe, not live model or visual acceptance proof.
Useful next review: read a long real answer, recall/edit the next instruction, then quit
and resume; evaluate whether the reading/continuation flow now feels natural.

Remaining: an in-app session picker, file/attachment completion, semantic references,
syntax highlighting and aligned tables, exact character anchors across width changes,
durable cursor/selection, crash-edge draft writes, repair of interrupted tool context,
arbitrary module-private state, queue/steer, delegation and complete CLI policy/performance
parity. Old pre-storage runs cannot be resumed retroactively. Bundle/module/prompt files
remain live sources, not frozen snapshots; only the effective mount-plan config is hashed.
Raw state and live captures can contain secrets and remain ignored. Existing local changes,
including the pre-existing tracked bytecode edits in amplifier-bundle-modes, are preserved.

## Conversation navigation and local paths — 2026-09-12

Source: steward accepted the reading/return slice and requested continued work. VISION,
continuity P2 and interaction P4 were amended before deriving NAV-01 / FILE-01. Direction
remains DRAFT; no formal Converge verdict or final frontend selection is claimed.

Implemented in Ratatui:

- Actions → Resume opens a searchable picker with compact titles/IDs and selected
  directory/identity details. Actions → New conversation retains the current bundle/cwd.
  `/resume` and `/new` are optional local alternatives. Discovery returns the 100 most
  recent records from this app's state directory, not imported CLI sessions.
- Switching saves the source draft and prepares one fresh engine before replacing the
  view. Active turns must finish or be stopped explicitly. Editing pauses during opening;
  visible Cancel/Escape cancels preparation. Failed preparation retains the source.
  Undo, selection, history browsing, pending actions and view state cannot leak across
  the replacement. Stale conversation requests are rejected at the host boundary.
- Tab completes `./` paths in the current token, preserves surrounding text and quotes
  spaces. Directories end in `/`; another Tab lists children. Lookup inspects one
  directory, at most 2000 names, returning at most 80 suggestions. Hidden names require
  an explicit dot prefix. Traversal escapes, symlink suggestions and nonprinting names
  are excluded. Suggestions are text, not loaded files/attachments; no contents, model
  request or tool execution is involved. Edited/dismissed/stale replies are discarded.

The app-owned `WorkspaceBridge` uses normal Foundation/core composition and public
context APIs. No kernel or upstream module source was changed. Candidate initialization
denies mount-time approvals, never silently grants or routes them against the source.
The final source cleanup/commit cannot be cancelled from the client; an exceptional
cleanup failure is reported, not misrepresented as rollback. The existing Foundation
partial-initialization ownership gap and arbitrary module-private state gap remain.

Verification: **97 Python, 7 Rust and 3 TypeScript tests pass**. Eleven new Python cases
cover actual-kernel new/return, canonical context, drafts, target cwd, preparation failure,
cancellation before/during initialization, discovery bounds/scope, native picker/quoted
path controls and Undo isolation. The delayed-reply test uses an explicitly simulated
protocol fixture; it is not runtime conformance evidence. Actual picker/path PTY images
were inspected and remain private because captures can contain machine paths. Compact
picker labels and Undo isolation were corrected after inspection; SMOKE_TESTS owns
those lessons. Ruff/format, Rust formatting and Clippy pass.

Live proof: both presets performed read_file, then an in-app switch restored their
unsent question and canonical context. Each new identified answer recalled a marker
supplied only before switching. Restore emitted zero execution events; the subsequent
memory turn used no tools. [Live receipt](evidence/navigation-live.json) records the
final four-turn run and exercised source fingerprints. Two earlier four-turn runs also
passed before the final UI guards; this wave used twelve billed read-only turns total.

[Current synthetic timing receipt](evidence/navigation-benchmark.json): 30 alternated
startup pairs and 18 stress cells (1k/10k/100k history × 30/100/500 deltas/s × two engines).
Ratatui worst p95 key-to-visible edit **21.642 ms**, event-to-visible update **20.779 ms**;
maximum frontend RSS **134368 KiB**. First-usable median **40.000 ms**, p95 **72.497 ms**.
Measurements include observer/scheduler cost and exercise the scene renderer/transport,
not the fsync-enabled runtime, local lookup latency, cold caches or policy-matched CLI
equivalence. OpenTUI remains a historical implementation comparator, not a matched
feature set. Previous reading/interaction receipts are preserved as historical evidence.

Final checks: receipt fingerprints match the exercised sources; direction/archive
integrity passes (seven DRAFT contracts, 519 contract lines, 20 production files and
22 sourced work items). Wheel/sdist build and private-state/archive/cache exclusions
pass. All probe resources are reconciled with zero active manifest entries. Existing
local changes, including the four pre-existing modes bytecode edits, remain untouched.

Remaining: interrupted-context repair, crash-edge draft retention, durable cursor and
selection, attachments/semantic references, syntax highlighting/aligned tables, precise
resize anchors, queue/steer, structured questions, provider/mode pickers, delegation and
policy-matched CLI performance. Names-only path lookup is not an OS sandbox against
concurrent filesystem changes. Catalog response size is bounded, but metadata discovery
still scans the app's session directory; no large-catalog latency claim is made.

Useful review: leave distinct drafts in two real conversations, switch through Actions →
Resume, and complete a path containing spaces. Does returning to work feel natural, and
is it clear that completion inserts a name without sending or loading anything?

## Follow-ups and conversation organization — 2026-09-12

Source: steward requested more features toward the studied Codex workflow, powered by
Amplifier. VISION, session P6 and interaction P1 were amended before deriving QUEUE-01 /
ORGANIZE-01. [Workflow coverage](PARITY.md) keeps implementation gaps explicit; it is
not a claim of compatibility with every feature of a current Codex release.

Implemented in the Ratatui integration client:

- Durable follow-up queue: during active execution, the visible Send action becomes
  Queue and Enter admits a separate next turn. Actions → Pending follow-ups exposes
  pause/run, edit, remove and copy. The waiting list and footer distinguish pending
  work from an admitted turn. Queued text enters sent history only when dispatched.
- Successful task completion and checkpoint permit the next enabled queued turn.
  Stop, failed/unknown endings, switch/open and queue editing hold pending input.
  Editing uses a separate modal, supports multiline text/paste, and leaves the main
  draft intact. Stale edit/remove requests reject once the message is admitted.
- Conversation rename updates only metadata; the header also follows the first-message
  title. Local transcript search selects identified source, can jump to the message,
  and keeps the composer unchanged. Assistant replies can be inspected and copied as
  original Markdown via OSC52, not reconstructed rendered text.

Queue records are atomic/fsynced, capped at 20 entries / 65536 characters each. Dispatch
is persisted before normal `SessionHost.submit`, with an input ID in the turn journal.
The app owns admission; Amplifier's composed orchestrator, context, tools and policy hooks
still execute it. No upstream source or thin-kernel changes were made. Queue durability
does not imply a cross-file transaction: ambiguous dispatched records block release and
are never automatically retried. Interrupted-conversation repair remains unavailable.

Search is an explicit local scan, limited to 16 MiB recent message text / 200 matches;
partial results stay visibly labeled. Tool-detail JSON and other conversations are not
searched. Reply catalogs retain at most 100 choices, previews cap at 12000 characters,
and message copy rejects source over 1 MiB rather than silently truncating it.

Verification: **110 Python, 7 Rust and 3 TypeScript tests pass**. Thirteen new Python
cases cover real-kernel queue order, early stop, failure, pause/remove/edit, repeated
admission, storage rejection, restored pending input, uncertain dispatch and metadata
isolation; native terminal workflows exercise these during actual fixture approvals.
Local search/copy tests verify original Markdown bytes, draft preservation, rejected
rename text and partial-result labeling. The last case is explicitly a simulated source
projection fixture, not an alternative engine conformance run.

The partial-search test first failed because selected-row details hid the scan-limit
warning; the display was corrected and the test passed in the full suite. Actual queue
and search terminal captures were inspected, not inferred from code. They remain ignored
because captures can contain machine paths. Per-repo-conventions kept direction and
evidence separate, and the queue/partial-search lessons live in this app's SMOKE_TESTS.

[Live receipt](evidence/workflow-live.json): each preset completed read_file followed by
a queued tool-free memory turn. Identified admission of that follow-up followed the
first terminal outcome, and the new answer remembered a prior marker. Local rename,
search and exact copy added no turns; the unsent draft survived close. The final run
used four billed read-only turns; an earlier four-turn run also passed before the final
search-label/header corrections. This wave used eight billed turns, not a broad ecosystem
or policy-equivalent CLI test.

[Final synthetic timing receipt](evidence/workflow-benchmark.json): 30 alternated
startup pairs and 18 cells (1k/10k/100k history × 30/100/500 deltas/s × both engines).
Ratatui worst p95 edit **21.663 ms**, visible event update **20.874 ms**; peak frontend
RSS **134364 KiB**. First-usable median **53.284 ms**, p95 **78.568 ms**. These include
observer/scheduler cost and measure scene transport/rendering, not fsync queue latency,
search/copy latency, provider time, cold caches or policy-equivalent CLI performance.
The earlier reading/navigation receipts remain historical; this is not a feature-matched
Ratatui/OpenTUI comparison. Final live/timing source fingerprints were verified.

Direction/archive checking passes: seven DRAFT contracts, 521 contract lines, 22
production source files and 24 sourced work items. Ruff/format and Clippy pass. All
probe resources are reconciled with zero active manifest entries; pre-existing local
changes, including modes bytecode, remain preserved. Wheel/sdist build and private
state/archive/cache exclusion checks pass; the wheel includes the new admission adapter.

Remaining: structured questions, correlated active steering, attachments/references,
policy-backed mode/model controls, delegated work, interrupted-context and uncertain
queue recovery, workspace change review and end-to-end CLI performance. Unacknowledged
modal saves remain uncertain on disconnect; no transparent reconnect/retry is offered.
Useful review: queue a correction during a real turn, pause and edit it, then explicitly
release it. Is the distinction between waiting work and changing active work clear?

## Active corrections and scoped model selection — 2026-09-12

Source: steward requested continued feature parity work. VISION and session P6,
ecosystem P2, continuity P1 and interaction P1 were amended before deriving STEER-01
and PROVIDER-01. Per-repo-conventions kept direction separate from evidence and routed
the composition/steering/disconnect lessons to this app's SMOKE_TESTS. All contracts
remain DRAFT; no formal verdict or complete Codex/CLI parity claim is made.

Implemented:

- Actions → Correct active turn: separate multiline editor, stable target turn,
  first-provider-request gate, identified admission and runtime insertion evidence.
  Pending/applied/unconfirmed remain distinct. Corrections are not new turns, do not
  automatically retry, and do not claim to cancel an already-running tool. Limits are
  20 corrections per turn / 65536 characters each. Late rejection preserves editor text.
- Actions → Corrections: latest 100 retained corrections, source inspection/copy and
  insertion status. The main draft stays intact. Applied means inserted into context,
  not model obedience or task acceptance. Stop/failure can leave unconfirmed intent.
- Actions → Conversation provider: actual mounted instances, explicit idle confirmation,
  automatic-priority reset, preserved module vendor guards, durable selection and local
  selection history/copy. Changes pause pending follow-ups. Scope is top-level conversation;
  model-role routing, goal utilities and delegated-agent selection remain unchanged.
- An optional Haiku/Sonnet overlay, with explicit named instances. Default launch remains
  Haiku. Foundation's public composition `id` is mapped to core's `instance_id`, without
  editing either upstream. Recursive includes must author `id` before their own composition.
- Disconnected dialogs keep unacknowledged text copyable/dismissible with visible hints;
  nothing retries, and the main composer is unchanged. Dialog text is not crash-durable.

The composition regression was first observed in an actual terminal: only one of two
configured instances survived. A hand-constructed mount-plan test alone missed it.
Root/overlay normalization and a native two-instance assertion now cover that seam.
The final-stream correction test also exposed a mistaken test assumption: this loop
continues within the same turn when steering arrives during its final generation.
The test now asserts that actual behavior and verifies no duplicate insertion on the
next turn. Stop/provider failure separately exercise unconfirmed outcomes. Unsupported
provider controls close their local menu and explain absence, rather than staying loading.

Verification commands and live/timing scope are in SMOKE_TESTS. The final receipts below
pin the build they exercised; earlier workflow/navigation/reading receipts are historical.

**127 Python, 7 Rust and 3 TypeScript tests pass**, with Ruff/format, cargo fmt/Clippy,
direction/archive checks, wheel/sdist build and private-artifact exclusions. Seventeen
new Python cases cover the composition mapping, actual-kernel controls and native
interaction paths. Lost-acknowledgement and unavailable-scene probes are explicitly
simulated; they are not alternative-orchestrator conformance claims.

[Final live receipt](evidence/controls-live.json): both presets mounted distinct Haiku
and Sonnet instances. Each Haiku turn performed read_file and received an active
correction with matching admitted/applied identity. Selecting Sonnet, closing and
resuming preserved the pin; the next observed selection was Sonnet with basis pinned.
That tool-free continuation recalled the earlier correction marker without repeating
it in the new prompt. Resume and local controls added no execution turns; an unsent
draft survived close. Four final billed turns passed; an earlier four-turn run passed
before the final unsupported-control UI/capability-copy cleanup (eight billed turns
total in this wave). Actual fixture and live terminal captures were inspected and stay
private/ignored because they can contain working-directory or transcript data.

Remaining: structured questions, policy-state-preserving mode controls, attachments,
delegated sessions, workspace diff/test review, interrupted-context and uncertain-control
recovery, arbitrary module-private state restoration, and policy-matched CLI latency.
Useful review: while a real turn runs, use **Correct active turn**, then compare it with
**Queue** for a separate next turn. Is the timing/scope distinction clear without shortcuts?

[Final synthetic timing](evidence/controls-benchmark.json): 30 alternated startup pairs
and 18 cells (1k/10k/100k history × 30/100/500 deltas/s × both frontends). Ratatui worst
edit p95 **21.285 ms**, event-update p95 **20.076 ms**, peak frontend RSS **134428 KiB**.
First-usable median **52.451 ms**, p95 **75.047 ms**. The final run followed all builds,
tests and live activity; an earlier timing run was superseded. This measures scene
transport/rendering including observer/scheduler cost, not control-fsync latency,
provider response time or policy-equivalent CLI non-regression. Both final receipts'
source hashes match. Seven DRAFT contracts, 525 contract lines, 24 production files,
26 sourced work items; zero active manifest resources. Existing workspace changes,
including four modes bytecode edits, are preserved. No commit or publication was made.

## Structured questions and read-only workspace review — 2026-09-12

This wave amends VISION, interaction P8 and presentation P7 before deriving QUESTION-01
and REVIEW-01. All seven contracts remain DRAFT. It continues the existing Ratatui client
without editing the kernel or upstream sources. Earlier receipts remain historical.

**158 Python, 7 Rust and 3 TypeScript tests pass**, including 31 new Python cases. Ruff,
format, cargo fmt/Clippy, method archive/direction, wheel/sdist and private exclusions pass.
The actual loop/core exercises a normally composed independent `request_user_input` tool:
choice and free text, exact request/question/turn/session identities, single admission,
normal pre-tool policy denial, bounds, cancellation/timeout/Stop, persistence failure and
canonical answer restoration. Non-interactive and child-session requests are unavailable,
not simulated interactions. Native PTYs exercise review-before-submit, Escape/reopen,
multiline text, untouched main draft, completed question history and resume without replay.
Unsent local answers are not crash-durable; child question routing is not implemented.

Temporary real Git repositories exercise staged versus unstaged comparisons, untracked
names without contents, unborn HEAD, nested working directories, literal/non-UTF-8 paths,
renames, binary/oversized diffs, changed-status rejection and cancellation/reaping. Configured
external helpers do not run, the index/HEAD stay unchanged, and no model/context work occurs.
Native tests inspect/copy both comparison scopes. This is a bounded read-only observation,
not an atomic snapshot, agent-attributed diff, conflict editor or test-evidence integration.

[Live receipt](evidence/questions-live.json): both presets asked through the real module,
accepted an explicitly reviewed choice plus free text, preserved the separate draft, and
recalled the answer marker in a tool-free turn after resume. Git review added no execution.
Four final billed turns passed. An earlier one-turn question run passed, but its continuation
probe matched “Ready” in restored assistant text before initialization; the host refused
premature admission and retained the draft. A diagnostic restart also admitted no turn.
The fixed, regression-tested probe waits for the actual status row. **Five billed turns
total in this wave.** Real fixture/live terminal captures were inspected and stay private.

[Rendering receipt](evidence/questions-benchmark.json): 30 alternated startup pairs and
18 cells (1k/10k/100k history × 30/100/500 deltas/s × both frontends), run separately after
tests/builds/live activity. Ratatui worst edit p95 **21.192 ms**, event-update p95 **20.523 ms**,
peak frontend RSS **134404 KiB**; first-usable median **40.819 ms**, p95 **71.009 ms**. This is
synthetic scene transport/rendering with observer/scheduler cost, not question-fsync/Git
latency, provider time or a policy-equivalent CLI comparison. Source fingerprints match
both final receipts. Direction: 532 contract lines, 29 production files, 28 sourced items.

The launcher adds the declared question overlay before explicit overlays for new launches;
`--no-questions` opts out. Resume/in-app New preserve recorded composition, so old sessions
are not silently upgraded. Start a fresh launch to use the default question tool.

Useful review: ask the assistant to ask two questions, choose one answer and write another,
then dismiss/reopen before submitting. Is the distinction between editing and sending clear?
In **Workspace changes**, are staged versus unstaged comparison labels understandable?
Remaining high-value work: policy-preserving mode controls, attachments, scoped delegation,
attributed changes/tests, uncertain/interrupted recovery and policy-matched CLI latency.
Existing local changes are preserved; no commit/publication or active external resource remains.

## Structured reading and diff navigation — 2026-09-12

VISION and presentation P3 were amended before deriving READ-02 and REVIEW-02. The
per-repo-conventions practice kept direction, implementation and evidence separate;
all seven contracts remain DRAFT. This is a frontend reading slice, with no new host
operation, kernel change or upstream source edit. Earlier receipts remain historical.

**162 Python, 14 Rust and 3 TypeScript tests pass.** Four new native tests cover an actual
Foundation/core fixture tool turn, wide/narrow table layout, exact Unicode code-content
copy, retained draft and completed resume, bounded catalogs and oversized-copy refusal.
A separately labelled simulated stream updates a source item while its code preview is
open: the old copy remains stable, and refreshing the catalog captures the new content.
Temporary real Git tests similarly change a file after observation; local hunk navigation
and copy keep the original observed text, preserve the draft, and admit no execution.
Rust tests cover alignment, wrapping, styles, narrow labels, multiple tables, code parsing,
hunk bounds and file boundaries. Actual PTY colours distinguish additions and removals.

[Live receipt](evidence/structured-reading-live.json): both actual presets completed one
read-only `read_file` turn each. Each rendered a Markdown table and supplied an identified
code snapshot whose copied content matched the retained response exactly. Inspection/copy
added no execution and preserved the main draft. **Two billed turns total this wave.**
Fixture and live captures were visually inspected; they remain private/ignored. The capture
font lacks the CJK glyph used in the fixture; source preservation/Unicode clipboard checks
pass, but this is not a cross-font or IME claim.

The code catalog is bounded to 100 blocks / 16 MiB of recent assistant source, previews
12000 characters and copies at most 1 MiB. It copies parsed code, not the enclosing Markdown
fences/container indentation, and never executes it. The diff catalog offers at most 100
hunks from one immutable observation, alongside the whole observed diff. A copied hunk is
explicitly not a complete patch. Reflow now combines line and span styles; menu detail
layout is cached by source, width and diff styling instead of rebuilt on every redraw.

Lessons are captured in SMOKE_TESTS: repeated clipboard checks must observe a new OSC52
event instead of matching a stale status message; style tests must check actual colours,
not just +/- source text. A resize test must account for tail-follow before asserting that
an earlier table header is visible. These are app/probe lessons, not upstream obligations.

Useful review: open **Code blocks**, copy a block and return to the draft; in **Workspace
changes**, browse individual hunks. Is source inspection easy to find, and is it clear that
copying does not execute code or apply a patch? Resize a table-bearing reply to assess the
labelled narrow layout. Remaining: syntax highlighting, source-character resize anchors,
policy-preserving mode controls, attachments, scoped delegation, attributed changes/tests,
uncertain/interrupted recovery and policy-matched CLI latency.

[Rendering receipt](evidence/structured-reading-benchmark.json): 30 alternated startup
pairs and 18 cells (1k/10k/100k history × 30/100/500 deltas/s × both frontends), run alone
after builds/tests/live activity. Ratatui worst edit p95 **21.482 ms**, event-update p95
**20.630 ms**, peak frontend RSS **134500 KiB**; first-usable median **40.016 ms**, p95
**58.014 ms**. These are synthetic scene transport/rendering measurements, including
observer/scheduler cost—not large-code-catalog discovery, Git I/O, provider latency or
policy-equivalent CLI non-regression. Source fingerprints match both final receipts.

Ruff/format, cargo fmt/Clippy, direction/archive integrity, wheel/sdist build and private
artifact exclusions pass. Direction: 533 contract lines, 31 production source files,
30 sourced work items. Existing local changes, including the four pre-existing modes
bytecode edits, are preserved. No commit/publication or active manifest resource remains.

## Steward-session repairs — 2026-09-13

Direction was amended before implementation, following the per-repo conventions skill:
VISION plus presentation P3, interaction P8, ecosystem P2/P6 and continuity P5. Work items
COPY-02, QUESTION-02, SPAWN-01, MODE-01 and RECOVER-01 trace those promises. Direction
remains DRAFT: 542 contract lines, 35 production source files and 35 sourced work items;
the structure/archive checks are not behavioral verdicts or Converge service integration.

Implemented in the app, with Foundation/core and upstream modules unchanged:

- Frozen visible drag selection, Unicode-aware copy through OSC52, and bounded private
  Markdown export independent of clipboard support. Selection does not auto-scroll.
- Direct Answer question card above the composer; explicit choice/free-text review and
  submission, without composer-focus theft or interpreting an answer as permission.
- Public app-owned spawn/resume over real Foundation child sessions: separate context,
  parent/child identity, observed agent cards, inherited mode and local capture policy,
  child approvals/questions and Stop cleanup. Delegate-detached children are drained
  before root checkpoint/journal close. Limits: 4 active / 32 retained / 3 nested levels;
  completed child resume is scoped to an open root; subprocess isolation is refused.
- Discovered Modes control and `/mode NAME`, explicit Apply, assistant mode approval
  with denial that does not arm a retry, durable mode/definition validation and restore.
  Activation-failure events cancel work and prevent ready checkpoints. Native human
  mode changes retain module transition checks, but are not assistant tool invocations.
- Explicit historical-context recovery into a new identity; original bytes unchanged,
  saved draft retained, no tool replay or queued admission. Partial assistant deltas
  survive export/recovery. This is not exact interrupted canonical-context restoration.
- System explains local context-intelligence/event logging versus disabled external
  dispatch. No service, remote destination or external account was provisioned.

Final full deterministic gate: **178 Python tests passed** with candidate and preset
gates enabled; **15 Rust and 3 TypeScript tests passed**. Ruff/format, cargo fmt/Clippy,
direction/archive integrity and wheel/sdist build pass. Native PTYs exercise drag-copy,
single-question answering at 40/160 columns, mode selection/restore/clear without model
calls, and recovery confirmation/no replay/original-byte preservation. Captures were
inspected locally. Actual-preset tests execute the real delegate and v2 recipe tools,
deny/approve mode changes, restore a fresh engine, route child questions, and Stop a
child waiting for an answer. Cancellation-only runs intermittently emit unawaited
LoggingHandler/other hook coroutine RuntimeWarnings at event-loop teardown. This remains
an observed shutdown limitation; it is not a claim that every final hook record flushes.
The owned child sessions are drained and the closed-journal write race is fixed.

[Live receipt](evidence/session-repairs-live.json): both actual presets completed delegate
and a declared-dependency v2 agent recipe (two child sessions each), answered the direct
question, approved explore mode, reopened with explore active, and explicitly cleared it
without a model call. Local context-intelligence JSONL was nonempty and remote dispatch
remained disabled. The final run billed six parent plus four child turns. Earlier diagnostic
runs billed nine parent plus six child turns; they found the missing mode-reply identity
and verified the pre-drain implementation. Only the final receipt identifies current source.

Private transcripts, exports and images stay ignored; the original steward session was
exported without launching an engine and was not automatically replaced or recovered.
Existing local changes are preserved; no commit or publication was requested.

Specific steward review: is **Answer question → choose → Submit reviewed answers** now
obvious without instructions, and does drag-copy reach your terminal clipboard? These
are usability/terminal-integration judgments, not a request to rediscover runtime failures.
Remaining scope includes process-restart child resume, subprocess recipe isolation,
crash-durable unsent answers, exact interrupted-context repair, full module-swap coverage
and policy-equivalent CLI latency. A historical recovery fork cannot undo external effects.

[Responsiveness receipt](evidence/session-repairs-benchmark.json): 30 alternated startup
pairs and 18 stress cells, run without concurrent test/build/live workloads. Ratatui worst
editing p95 **21.442 ms**, stream-update p95 **20.560 ms**, peak frontend RSS **134336 KiB**;
first usable median **40.276 ms**, p95 **58.096 ms**. These remain comparable to the prior
structured-reading scene measurements, not proof of policy-equivalent CLI performance,
provider latency, child initialization speed or large export/catalog latency. Both final
live and benchmark source fingerprints match current files. Private/generated distribution
exclusions pass; the workspace resource manifest has zero active entries after probes.

## Everyday navigation, copying and visible controls — 2026-09-13

This section supersedes earlier current-source claims. Direction was amended before
implementation (NAV-02/COPY-03/CONTROL-02); vision/contracts remain DRAFT. No kernel or
upstream source changes, commits, publishing, credential migration or user tmux changes.

- Bare `scripts/run.py --resume` offers a searchable startup chooser before mounting.
  Its Escape test byte-compares all saved state. Explicit `latest`/ID remains available;
  in-app Resume is now beside the composer and retains the existing scoped switch path.
- Directory input recall reads saved root submissions from the same resolved cwd/state
  directory, including older sessions. Tests cover symlink-equivalent cwd, foreign cwd,
  current-session exclusion, corrupt/tail-limited journals and no context/provider work.
  A delayed prefix waits until active recall returns to its original draft/cursor.
- Pending N and Steer are visible keyboard/mouse actions. The actual fixture queue
  edit/remove/advance/Stop and correction insertion tests now enter through these buttons.
  Queueing is a later turn; steering is a separately identified active-turn correction.
- Mode policy is a persistent header, not a transient message or runtime label. Actual
  preset tests check native change/restore/clear, and a bridge routing test ensures a
  child-prefixed mode observation cannot replace the root badge.
- Drag/wheel and edge autoscroll select across multiple visual pages of a frozen source
  snapshot; Unicode/reverse selection and draft retention pass. A code-fenced test
  explicitly checks the older line is absent before dragging, preventing a false pass
  from Markdown soft-break paragraphs that fit on one page.
- Native scrollback leaves the alternate screen and mouse capture, prints bounded
  sanitized retained source, keeps draining runtime events and ignores bracketed paste.
  Enter returns with draft intact. Actual tmux 3.4 on an isolated server/socket was
  attached through a PTY: copy mode reached the first marker, selected to the history
  bottom, and its copied buffer contained lines across pages. The test tears down both
  resources. Capture-pane alone cannot validate the attached copy-mode view.

Full final deterministic gate: **274 Python tests passed**, including the steward's
independently staged event tests, with native/preset gates enabled. **18 Rust / 3
TypeScript tests passed**; cargo fmt/Clippy, release build, direction/archive integrity
and wheel/sdist build pass. Ruff check/format pass for all other files. Global lint
still reports the pre-existing import-order issue in staged `tests/test_events.py`;
that file and staged `TEST_EVENTS_REPORT.md` are untouched. Four hook/logging-coroutine
RuntimeWarnings occurred during child-cancel teardown in this full run. They are the
existing shutdown limitation above, not suppressed and not repaired by this wave.

[Live receipt](evidence/everyday-live.json): four billed read-only turns across anchors
and anchors-amp-dev. Each checks applied steering on the original turn, a queued next
turn recalling that marker, successful read_file, plan badge through new/resume, local
history discovery and a native-view round trip without a new turn or lost draft.
One earlier diagnostic run billed one completed turn before its test timed out waiting
on an intentionally paused queue. The final test explicitly releases it: mode selection
holds pending work, and enqueueing alone does not undo that hold. Captures inspected.

Limits: native scrollback is an explicit 2 MiB source snapshot, not continuous terminal
history while fullscreen; terminal/tmux retention limits still apply. Drag snapshot is
20,000 lines / 2 MiB around the starting viewport and clears on resize. Recall refreshes
on open/switch, scans 16 MiB total / 1 MiB per journal, and retains 1000 entries / 2 MiB;
legacy events have no timestamps, so ordering is by session activity then submission.
This does not import CLI sessions or another state directory, nor establish full parity.

Steward review: restart the Ratatui launcher, try Pending versus Steer beside the composer,
and try `/scrollback` with the normal selection/copy-mode bindings in your own terminal.
These environment/usability checks complement the developer-run attached tmux proof.

[Responsiveness receipt](evidence/everyday-benchmark.json): 30 alternated startup pairs
and 18 stress cells, with no concurrent agent test/build/live workload. Ratatui worst
editing p95 **22.174 ms**, stream-update p95 **20.868 ms**, peak frontend RSS **134416 KiB**.
First usable median **54.889 ms**, p95 **73.797 ms**; startup is slower than the preceding
scene receipt, without evidence attributing that difference to a single cause. These
are warm-cache scene observations, not matched CLI latency, directory-history discovery,
snapshot-entry timing or provider performance. Both new receipt fingerprints match source.
All test-owned tmux/PTY resources are reaped; no existing user session was closed.

## Native terminal lifecycle — 2026-09-13

Work: INLINE-01, presentation P3/P5/P6 and performance P3/P5. The steward reaffirmed
the destination: learn from Codex to replace the Amplifier CLI experience while retaining
Amplifier's ecosystem. Direction was amended first; all contracts remain DRAFT.

The default Ratatui conversation now appends stable Markdown blocks/final items onto
the normal terminal screen. A compact live area holds mode, title, composer and controls.
Native selection belongs to the terminal; F4 or Tab/Enter accesses controls. Fullscreen
menus, Review/System and source inspection restore the primary transcript on return.
Quit leaves emitted transcript behind instead of restoring an empty pre-app shell.
Host, protocol and ecosystem modules are unchanged.

Developer evidence:

- `TUI_TEST_PRESETS=1 TUI_TEST_CANDIDATES=1 PYTHONDONTWRITEBYTECODE=1 uv run --no-sync pytest -q`:
  **276 passed**, three already-known hook/child-cancellation coroutine warnings.
- Cargo release tests: **21 passed**; fmt, Clippy `-D warnings`, Bun **3 passed**.
  Direction/archive integrity and wheel/sdist builds pass. Ruff check/format pass excluding
  the independently staged `tests/test_events.py`; its existing import/format findings
  and staged `TEST_EVENTS_REPORT.md` were preserved, not silently fixed.
- Real isolated tmux tests enter copy mode without `/scrollback`, select across pages,
  check initial and final markers plus every one of 150 rows exactly once, resize repeatedly,
  open/close inspection and exit back to a shell. A short Unicode reply appears in the
  same bottom-20-lines capture slice used by the inspected muxplex preview code.
  A growing 150-paragraph scene produces native history before finalization and no duplicate
  rows afterward. This is terminal evidence, not a deployed-muxplex integration claim.
- [Current fixture receipt](evidence/inline-fixture.json): keyboard-only submission,
  decisions and Actions, two real-kernel tool rounds, evidence inspection and clean exit.
- [Current live receipt](evidence/inline-live-current.json): both actual presets execute
  `read_file` then `load_skill(list=true)` using keyboard controls, inspect exact results
  and exit cleanly. Four billed read-only turns in the final run; eight total in this wave,
  including the earlier pre-replay-bound run. Private `anchors-inline.png` and
  `anchors-amp-dev-inline.png` captures were inspected; they are real executions, not mockups.

The first timing attempt is preserved in
[the preliminary receipt](evidence/inline-benchmark-pre-replay-bound.json): its 100,000-item
case kept typing responsive but failed the four-second exit gate while dumping historical
backlog. P3 was amended before bounding initial replay to the latest **1,000 historical
items**, with visible disclosure and full retained-source inspection/export. This changes
only initial display replay, not model context or subsequent native output.

[Final timing receipt](evidence/inline-benchmark.json): **30 alternated startup pairs,
18 stress cells**, all completed including the four-second cleanup gate. Ratatui worst
editing p95 **20.662 ms**, stream-update p95 **21.090 ms**, peak RSS **135112 KiB**.
First usable median **45.198 ms**, p95 **61.526 ms**. The run was separate from builds,
tests and live workloads. Source fingerprints match the final renderer and observer.
These are warm-cache synthetic scene measurements, not matched CLI policy/latency proof;
Ratatui's disclosed initial native replay and OpenTUI's virtual viewport emit different
terminal output. Retained scene source counts remain 1,000/10,000/100,000 for both.
No framework-wide or provider/network speed claim follows from these measurements.
All test-owned tmux/PTY resources are reaped; the workspace manifest has zero active
resources after verification. No existing user terminal session was closed.

Boundaries: unfinished Markdown blocks stay in an eight-row live preview until stable or
finalized; source inspection remains available. Already committed rows are not replayed
on resize. Terminal history capacity is user-owned. A single huge Markdown block remains
a unit of parsing/layout; this wave does not establish arbitrary-size resource conformance.
Linux/tmux 3.4 and PTY observers were exercised, not every desktop terminal or the steward's
deployed muxplex. Full CLI policy/latency parity and the earlier runtime residuals remain open.

Steward review: after restarting `scripts/run.py`, does ordinary terminal/tmux copying
across pages, retained output after exit, and your muxplex preview now behave naturally?
No special `/scrollback` view should be necessary. In the normal view, use the terminal's
copy binding; app mouse controls are available in inspection, not over native selection.

## Daily-replacement wave — 2026-09-13

Steward authorized the proposed next-work list while away. VISION, continuity P1/P2,
ecosystem P2/P6 and interaction P3 were amended before deriving CHILD-02, DRAFT-02,
INPUT-02, EVIDENCE-02, CONTEXT-01, HARDEN-01 and READY-01. All remain draft targets,
not ratified promises or a claim that the entire replacement plan is finished.

- Delegated work exposes observed progress, permission/answer waiting, child-scoped tool
  and text source, and explicit refresh. It does not call historical receipts live sessions.
  Completed direct children can be explicitly continued after root restart only when their
  parent, reconstructed mount configuration and inherited mode match. Normal inherited
  parent orchestrator configuration is allowed; arbitrary overrides, custom routing,
  nested/unfinished children and older receipts are refused. Dispatch marks the receipt
  running before execution; inspection/reopening alone never starts a child.
- Local answer/correction copies are private atomic/fsynced state with their original
  request/conversation identities. Recovery offers copy/remove, never delivery or retarget.
  Autosave follows a 250 ms input pause, dismissal/submission and normal quit; the last
  unsaved keystrokes can still be lost on sudden death. Saved copies are not admission
  records and can remain after submission. Other dialog editors are not crash-durable.
- Explicit UTF-8 file snapshots are bounded at 64 KiB, workspace-relative and no-symlink,
  with captured content/digest preview before insertion into the draft. Changes afterward
  do not substitute new bytes. This is literal prompt text, not image/multimodal support.
  Idle external editing uses the person's VISUAL/EDITOR command, restores the terminal,
  never submits, and keeps the original draft on failure.
- Activity evidence consolidates identified tool/approval/question/correction observations;
  Context intelligence shows module-observed usage/compaction and configured local capture
  versus disabled remote dispatch. Inspection does not build/compact a request or call a
  model. Indexes are bounded (256 identities; 100 rows / 1 MiB; 16 KiB detail excerpts).
  These are observed sources, not Git authorship, test-coverage attribution, exact current
  context occupancy or an instruction-source index. Child details refresh explicitly.

The adapters stay in the app. No kernel or upstream production code was changed.
Independent packages were added as workspace submodules and installed only into the app
environment: `loop-basic` at `ae0954cc41be54afef3ca97181a0876a29ad1b4c`,
`context-persistent` at `dbfdeeb1576f06099b0dd9de1b3855146f1166ef`.
`test_independent_swaps.py` exercises all four loop/context combinations with streaming/simple:
real fixture-tool round trip, completed resume with zero provider calls, then a second turn.
The persistent module inherits simple's compaction and independently owns an append-only
transcript; its README's memory-loading-only description is incomplete for this pin.
It ignores `set_messages` after loading its own file. Root/child restoration now checks
read-back canonical history before admission, allowing only documented internal `_seq`
restamping. A changed module transcript is refused. Tests use an explicit private temporary
transcript path, never its shared-home default. Per-child persistent storage allocation,
arbitrary module-private-state migration and every policy seam remain unproven.

Verification:

- `TUI_TEST_SWAPS=1 TUI_TEST_PRESETS=1 TUI_TEST_CANDIDATES=1
  PYTHONDONTWRITEBYTECODE=1 uv run --no-sync pytest -q --tb=short`: **300 passed**.
  Two cancellation-time unawaited coroutine warnings remain (child observation and logging
  callbacks). Earlier runs also exposed mode/logging callbacks at that boundary. These are
  not hidden or declared fixed by a passing cleanup test. Partial-initialization handle
  ownership and the unbounded host source-event queue remain HARDEN-01 work.
- Rust **21** tests and Bun **3** comparator tests pass; Cargo fmt/Clippy with warnings
  denied pass. Ruff check/format pass excluding independently staged `tests/test_events.py`,
  whose existing import/format findings and staged report were preserved. Direction/archive
  integrity passes: 556 contract lines, 42 production source files, 46 work items, all DRAFT.
- New deterministic/native tests cover scoped child source/waiting, unchanged inspection
  receipts, guarded restart/rejection, original-byte draft recovery, captured-file stability,
  traversal/symlink/binary/size rejection, external-editor success/failure and zero submission.
  Real tmux/native history, queue, steering, question, modes and previous controls remain in
  the full regression suite. Initial failures found an ambiguous Actions label, moving-footer
  mouse injection and a stale closing-menu frame; fixes exercise the ordinary keyboard path.
- [Final live receipt](evidence/daily-live.json): both actual presets, **four root plus four
  child turns**, successful child read_file evidence, local context inspection, restart with
  unchanged child receipt and zero implicit execution, then explicit same-child continuation
  with remembered project name. Host/renderer/probe fingerprints are recorded. Captures were
  inspected; child details currently show bounded JSON source, not a polished change narrative.
  Total this wave: nine root/nine child turns including the initial diagnostic and the rerun
  after canonical-history guards. Earlier recipe execution remains previous-wave live evidence;
  this live gate specifically checks direct delegation, not interrupted recipe-process recovery.
- Wheel and sdist build successfully; inspection finds no private state, private archive,
  cache or native build trees. This does **not** make the wheel a standalone native product:
  `scripts/run.py` remains the development product launcher; the console entrypoint is still
  the historical harness. Shared CLI settings/credentials and user terminal sessions untouched.

[Final synthetic timing](evidence/daily-benchmark.json): 30 alternated startup pairs and
18 stress cells (1,000/10,000/100,000 items; 30/100/500 deltas per second), all complete
including the four-second cleanup gate. Worst Ratatui edit p95 **20.503 ms**, stream p95
**21.337 ms**, peak RSS **135176 KiB**. First usable median **43.096 ms**, p95 **58.870 ms**.
Run alone after tests/live/builds. This is warm-cache scene/renderer evidence, not root
provider latency, draft-fsync timing or a policy-equivalent CLI comparison. Native replay
remains disclosed/latest-1,000 initially versus the comparator's virtual viewport.
All 42 live and 24 benchmark source fingerprints verified current. Workspace manifest
reconciled: **3,081 records, zero active**; no existing user session was closed.

Remaining work is explicit in PLAN: broader initialization/cancellation/slow-reader ownership;
image input and instruction-source context view; actual Git/test causal attribution;
arbitrary/private-context and interrupted-child continuation; every module-policy seam;
matched end-to-end CLI performance; standalone native launch/package/migration. No shared
CLI state migration, publication or formal Converge ratification occurred.

Steward review after relaunch: try one delegated task, open Actions → Delegated work and
its child tool evidence, then restart/resume and explicitly ask to continue that child.
Is the distinction between active work, historical evidence and continuation clear?
Separately, Insert text file and Edit in external editor should only change the unsent
draft; neither should send. Native selection/scrollback should remain ordinary terminal behavior.

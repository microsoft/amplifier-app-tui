# Verification guide

Post-rc4 gates: `test_post_rc4.py` exercises replayed source-version provenance,
bounded model metadata, named environment references and Linux clipboard fallback.
`test_child_recovery.py` covers both legacy and current receipts with simple/persistent
contexts, same/historical roots, and altered-policy refusal. Native correction reuse
requires an empty idle composer, separate confirmation and zero new turn admissions.
Inspect both correction/model-limit captures. After the full suite, run
`scripts/lifecycle_probe.py --live --adopt-persistent --legacy-receipt --output PATH`:
it changes only its freshly generated test receipt to the legacy shape, never a user's
record, then verifies source preservation after native adoption in both presets.
Clipboard acquisition has one total three-second deadline, preserves source bytes,
and rejects a successful utility response whose format disagrees with the requested MIME.
Utility fixtures are not physical desktop or SSH clipboard proof. Provider setup must
reject non-YAML suffixes before writing; valid JSON content alone is not a loadable filename.
`compare_runtime_policy.py` exits 1 for differing prepared fields, 2 for invalid evidence;
even exit 0 does not prove request-time, credential or latency equivalence.

rc4 gates: persistent direct-child public adoption runs in `test_child_recovery.py`
with `TUI_TEST_SWAPS=1`, both same-root and historical-root paths. Preserve original
receipt and module transcript bytes; a new store must read back imported messages
exactly before execution. A module's existing-file restore policy is never bypassed.
After the integrated gate, `scripts/lifecycle_probe.py --live --adopt-persistent`
exercises the actual recovered-work menu and confirmation with both live presets.
It bills two additional child turns. Generated overlays need a recognized YAML suffix;
successful serialization alone does not establish that Foundation can load the file.
`test_change_evidence.py` links exact unchanged versions to earlier agent observations,
refuses changed versions, and retains unresolved pre-tool evidence once. Context-policy
tests distinguish configuration rows from actual usage/compaction observations; native
inspection opens the detail without sending its retained draft. Native detail checks
wait for the new menu title before asserting detail: the same text may already
be visible in the preceding selection preview. Unique table-cell resize
matching is approximate; repeated/ambiguous cells must fall back rather than guess.
`capture_runtime_policy.py` runs under the respective isolated CLI/TUI interpreter with
a fresh `--state` directory. Keep its receipts private: hashes and module IDs are not
anonymous diagnostic exports. Prepared-policy agreement alone never proves matching
runtime requests or CLI latency. Do not disable policy to obtain a favorable number.

AFK continuation: run `test_owned_execution.py`, `test_child_recovery.py`,
`test_change_evidence.py`, `test_context_transfer.py` and the expanded independent-swap
approval matrix. New native navigation cases cover provider-fork confirmation and
continuous typing autosave. Full-suite evidence precedes billed lifecycle probes.
`benchmark_history.py --terminal` now measures complete catalog/search/checkpoint-page
work and actual native Resume paint separately; neither is matched-policy CLI proof.
`release_wheel.py --output-dir PATH --terminal` keeps experimental wheels apart from
published-version artifacts. `--ci-clipboard` mutates only a disposable macOS GitHub
runner's pasteboard, tests the installed adapter against real PNG bytes, then clears it;
it refuses personal-desktop invocation. Ubuntu 22.04 is a separate CI gate, not musl proof.

Cancellation lesson: cancelling a Rust-backed execution wait immediately can outrun
Python callback scheduling. Own the wait and give the public cancellation token bounded
grace; drain ownership through repeated cancellation without suppressing warnings. This
does not impose a hard deadline on arbitrary cleanup: the native process-group deadline
remains separate. A cooperatively returned cancelled outcome is still interrupted work.
Draft lesson: debounce from the first pending edit, not the latest keystroke, or continuous
typing indefinitely postpones persistence. Terminal assertions must account for wrapped
disclosure text rather than waiting for a substring split across two physical rows.

September continuation gates: `test_conflict_review.py` uses real unmerged indexes to
test capture versus Apply, original backups, unchanged index/mode, stale content,
symlink/hard-link refusal, backup failure and a write injected after backup. Enable
native candidates for the actual proposal/confirmation/composer path; inspect its
capture and assert the proposed text is visible, not only the Apply label. External
writers remain outside a transactional lock. Never retry an ambiguous replacement.
`test_lifecycle.py` gates repeated child cancellation during context capture and cleanup;
ownership survives until the interrupted receipt is saved. Callback warnings are a
separate runtime seam, never suppressed by these tests. `test_recovery_inputs.py` covers
real interrupted-child historical recovery, original receipt preservation, no execution,
unavailable/foreign/oversized child evidence, static GIF/WebP bytes and animation refusal.
The macOS PNG clipboard parser is simulated locally; do not label it desktop verification.
Run `scripts/backlog_probe.py --live --format gif` and `--format webp` with distinct
receipt paths after the integrated suite. Each bills two controlled, tool-free turns.

`scripts/release_wheel.py --terminal` adds installed real-PTY fixture execution, Help
without submission, clean termios restoration, resume without replay and a second turn.
The observer requires pyte; run through `uv run --no-project --with pyte==0.8.2 python`.
CI requests this gate on each wheel platform. An unrun/failed job is not coverage; this
does not verify real desktops, tmux, clipboard acquisition or billed live providers.

macOS observer lesson: the first rc3 CI run reached exit but failed a post-exit slave
`tcgetattr` with ENOTTY. Darwin revokes the controlling terminal when its session leader
exits ([XNU exit implementation](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_exit.c)).
The installed gate now retains a controlling-session guard to compare the actual modes
before that revocation. It never repairs them and propagates nonzero app exits.
`test_terminal_guard.py` proves clean restoration, deliberate raw-mode leakage and
nonzero-exit handling. Default Linux performance probes keep their original topology;
do not substitute guard timings for historical renderer measurements.

Read AGENTS.md, current contracts, notes/PLAN.md and notes/ACCEPTANCE.md when entering verification. Do not use live
credentials in deterministic tests. Run from the project directory after README setup.

```sh
uv run --no-sync python scripts/check_direction.py
PYTHONDONTWRITEBYTECODE=1 uv run --no-sync pytest -q
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv build
```

The direction check validates shape, local links, language-independent source ceilings
and work-to-promise references. Its negative fixtures exercise failures too; it is not
a behavioral Converge ledger. If the private method archive is available, add `--archive`
as documented in [Converge practice](notes/CONVERGE.md). Verify distributions omit ZIPs.
Changes limited to direction/check tooling do not require new billed provider runs;
execution-path changes still owe the relevant live and integration evidence below.

Lifecycle ownership: `tests/test_lifecycle.py` gates real checkpoint/startup/cleanup awaits.
Exercise Stop twice, Stop then exit, cancellation of close waiters, natural completion while
saving, concurrent close, and cleanup failure. Assert one outcome/cleanup and no new execution.
Do not rely on sleeps to hit these races, suppress callback warnings, or call cleanup finished
while its handle is still live. Track startup separately so closing an opening host cannot
return early or wait recursively on itself. After the full suite, run
`PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python scripts/lifecycle_probe.py --live` serially:
four billed root/two child turns across both presets, completed read/resume without replay,
then Stop immediately followed by exit during a child question. Inspect private captures;
verify stopped questions, one interrupted parent/child and an uncertain checkpoint.
Mode changes also use the host's task slot: reset its finalization state for a new mode
operation and protect that operation's checkpoint. The actual-preset regressions in
`tests/test_ecosystem_workflows.py` catch stale state inherited from a completed turn.
Immediate close after submit must make zero calls into session execution, not merely
end with an interrupted status. Apply Stop before handing off to the cleanup task;
otherwise the scheduler can enter the runtime during that handoff. Keep the explicit
call counter in `test_close_before_first_execution_step_cleans_up`.

Direct Codex adoption gate: build Ratatui, then run `TUI_TEST_CANDIDATES=1` with
`tests/test_compact_terminal.py`, `tests/test_tmux_scrollback.py` and the complete native
suite. Verify a fresh primary-screen page, bottom-aligned five-row ordinary idle chrome plus an empty cursor-anchor separator,
growing/wrapped drafts, narrow controls,
visual-row history boundaries, delayed readiness preserving selection, zero implicit
submissions, and startup without any CPR request/reply, retaining typed input. Resize
queries have a 100 ms Unix deadline and replay all captured bytes through the pinned
Crossterm fork; a silent responder disables later probes. Real tmux resize must keep
both SHELL-BEFORE and each transcript marker exactly once. Inspect private `compact-*`
captures alongside actual live-preset ready/completed views. Corrupt local recovery
storage must prevent startup draft overwrite; `test_daily_replacement.py` verifies this.
Run native PTY/tmux probes serially: they share manifest bookkeeping.

Continuation gates: `tests/test_file_references.py` covers source hashes, inclusive LF
line ranges, UTF-8/CRLF, no symlink traversal, deleted-source queue dispatch, text-only
providers and atomic mixed-set admission. `tests/test_request_diagnostics.py` checks
explicit one-shot consent, bounded projection, missing provider exposure, child/probe
scope, clear and no raw host-journal writes. `tests/test_backlog_terminal.py` adds the
actual reference dialog, source-scoped dialog copies, persistent diagnostic status and
a host that deliberately never reads its pipe. The native client must remain escapable,
restore the terminal, report forced/uncertain cleanup and terminate its inherited group.
Do not use a blocking stdin write before starting an exit timeout, or call detached and
remote work reaped. Acknowledgement text can be immediately replaced by Ready: query and
show the diagnostic's real waiting/captured state, not a transient success toast.

After building/testing, run `PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python
scripts/continuation_probe.py --live --allow-private-provider-raw` serially. It makes two
billed turns across both presets with a deliberately explicit raw-provider test overlay
in private state. Queue a file/line reference, delete its source, reopen without composition
overrides, then explicitly Run; check the exact captured source digest/location/content,
controlled reply, no tool calls and no extra diagnostic turn. The overlay authorizes
module-owned raw logging only for this isolated test; never publish its logs or captures.
Inspect private `continuation-*` screenshots and publish only the allowlisted receipt.
The extra flag is not normal app behavior: diagnostics never enable provider logging.

Index regressions must include out-of-range SQLite integers, casefold-expanding text
before a match, and a measured read budget that includes source-prefix fingerprints.
The cache now uses a versioned first-record prefix of at most 4 KiB, charging those reads
to the refresh budget; old derived signatures trigger rebuilding, never journal changes.
Benchmark alone with `scripts/benchmark_history.py --output
notes/evidence/continuation-history-benchmark.json`; retain the original rc2 receipt.

Whole-backlog gates: `tests/test_backlog.py` exercises acquired-handle startup cleanup,
source observations, content paging, explicit uncertain-delivery resolution and immutable
image admission. `tests/test_backlog_terminal.py` exercises image/search controls,
non-submitting recipe review drafts and focus-preserving child-list refresh. With
`TUI_TEST_SWAPS=1`, persistent child storage/continuation is exercised with both independent
loops. With `TUI_TEST_PRESETS=1`, real v2 recipe failure/reopen/resume must skip the completed
step and retry only the explicitly requested unfinished work on both presets.

`PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python scripts/backlog_probe.py --live` makes
two billed controlled-image turns through both presets; compare exact canonical image bytes,
colour identification, zero tool calls, source inspection and private native captures.
Never use a fixture's image transport as proof of real vision capability.
`scripts/approachability_probe.py --live` adds two billed image-set turns and two confirmed
standalone provider probes across both presets. Queue two captured images, replace their
source files, close/reopen, then explicitly Run. Check exact canonical bytes, no implicit
replay, colour identification, retained draft, and unchanged checkpoint after context/probe
inspection. Resume must restore recorded cwd, never combine it with a cwd override.
`scripts/benchmark_history.py` measures synthetic incremental indexing and warm search;
keep its catalog/UI/model/CLI exclusions visible beside any reported timings.
Initial startup, not only conversation switching, must withhold advertised Ready while
directory-history loading still rejects Submit. On failed startup, release that history
guard so the actual startup failure remains visible instead of a permanent loading message.
`PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python scripts/release_wheel.py` verifies an
isolated compiler-free wheel install. `.github/workflows/release-wheels.yml` is manual,
produces private candidate artifacts and does not publish a release; unrun platforms stay unverified.
Release builds remap home/Cargo/project paths in Rust. Scan every decompressed wheel member,
including the executable, and the receipt before upload; build/install logs are withheld.
The workflow uploads only the current verified wheel and receipt. A prior wheel carried
build-home paths despite source-level checks passing: source-only scanning is insufficient.
The per-repo-conventions fresh-context review found this before publication; retain the
regression guard and independently inspect newly introduced artifact formats.
Wheel platform tags must describe the embedded executable, not Python's build tag.
A universal2 Python on macOS produced a falsely universal wheel containing a single
Rust architecture. Set an explicit macOS deployment floor and architecture, verify
the binary with `lipo`, and check both filename and installed executable in the release
gate. Same-machine installation alone cannot falsify a universal2 mislabel. See the
[packaging tag specification](https://packaging.python.org/en/latest/specifications/platform-compatibility-tags/).
Delayed history recall must not expose Ready before conversation switching accepts input;
the explicit delayed-switch native regression covers that lifecycle window.
The benchmark measures the first editable composer separately from scene readiness;
do not wait for Send, which is intentionally disabled during real startup. Its editor
observer recognizes open input and historical border styles and joins wrapped visual rows; test it with
`tests/test_benchmark_observer.py` rather than matching tokens in transcript output.

The suite uses actual bundle preparation, the released Rust-backed core, upstream
streaming orchestrator/context, independent fixture modules, Textual Pilot and Linux
PTY subprocesses. It does not replace the runtime with a mocked successful engine.
The non-completion test deliberately replaces one orchestrator's execute method to
exercise an unknown lifecycle signal; that is not a second-orchestrator conformance run.

## Live read-only action

Installed-product gate: `uv build` must produce a platform-specific wheel containing
`amplifier_tui/_bin/amplifier-ratatui` and an sdist with Cargo sources/lock/build hook.
Install into isolated `UV_TOOL_DIR` and `UV_TOOL_BIN_DIR` paths under `.state`, never
replace the steward's installed CLI. Run the installed `amplifier-tui --doctor`, then
`scripts/install_probe.py --executable /absolute/path/to/isolated/bin/amplifier-tui`.
It uses a working directory outside the source checkout, no source map, real module
downloads/installation, tool execution, the question overlay and explicit resume.
Repeat with `--live --output notes/evidence/installed-live.json` for both actual presets;
four root/two child turns are billed. Finally repeat installation from the private Git URL,
not only a local wheel, before claiming Git-installable delivery. Publication excludes
private session state, raw transcripts and the earlier git-demo branch/marker/report.
Record final source revision separately from the package version and runtime evidence.
`tests/test_installation.py` verifies remote/package configuration, credential-free local
diagnostics, tool-outcome independence and bounded source delivery. Burst the source without
a consumer: journal every observation, cap count/bytes, stop admission, retain an uncertain
checkpoint and never execute the queued initial task. Test byte-budget release on consumption.

For the structured-question/workspace wave, build Ratatui and run the native regression
suite with `TUI_TEST_CANDIDATES=1`. The actual-loop question tests cover explicit review,
stale identities, pre-tool policy denial, limits, timeout/Stop, persistence failure and
canonical resume. Temporary real Git repositories cover staged/unstaged/untracked,
unborn HEAD, nested cwd, literal/non-UTF-8 paths, binary/large diffs, helper suppression,
cancellation/reaping, unchanged index and no model/context work. Native tests exercise
choice/free text, dismissal, main-draft retention, question history and diff copy.

After tests/builds, `PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python scripts/questions_probe.py --live`
executes four billed turns across both presets: question answers and tool-free recall
after resume, plus local Git inspection without execution. Inspect its private captures.
Run benchmark separately, with no concurrent build/tests/provider activity; include the
new Rust modules in source fingerprints. This does not measure control fsync latency.

After `bootstrap_sources.py --workspace .. --all`, supply the provider credential and run:

```sh
PYTHONDONTWRITEBYTECODE=1 uv run --no-sync amplifier-tui --bundle ../amplifier-foundation/bundles/anchors --overlay examples/anthropic.yaml --sources ../tui-sources.json --require-tool read_file --headless 'Use read_file to read pyproject.toml. Report only the project name. Do not edit files, run commands, delegate, or use any other tool.'
```

Repeat for `anchors-amp-dev`. Check session.ready, a read_file result with success true,
text.delta followed by text.final for the same block identity, and completed turn. Verify
the reported hook handlers and no initialization warnings; a response alone is insufficient.
The prompt constrains this action, not the preset's permissions. Do not mistake it for a sandbox.

## Interactive checks

Code colour: run Rust tests both with `env -u NO_COLOR cargo test --release --locked
--manifest-path frontends/ratatui/Cargo.toml` and with `NO_COLOR=1`, then the native
structured-reading tests. Assert actual token foreground variation, exact clipboard
content, multiline lexical state, unknown-language/size fallback, narrow resize and
unchanged draft. Inspect `syntax-native-*` and `syntax-inspection-*` captures.
`structured_reading_probe.py --live --output notes/evidence/syntax-live.json` checks both
real presets. The renderer benchmark also records a separate 240-edit syntax stress case
with six grammars and 100 native code blocks; this is not provider latency or CLI parity.
For editor growth, exercise a narrow inspection frame before returning to a fitting
multiline composer; assert all lines, cursor, selection and undo, not only the last line.

Development command: `scripts/dev-launch` may be symlinked onto the person's PATH by
explicit request. Test diagnostic invocations without Cargo, build failure without stale
launch, argument/cwd forwarding and a real fixture turn through the resolved symlink.
Resolve that PATH command outside `uv run`: uv prepends the editable environment's own
console entrypoint, which is a different launcher. Record the external link for teardown;
never replace an existing command or use real user state for the smoke test.

Newcomer guidance: run `test_onboarding.py` and `test_onboarding_terminal.py` with the
native candidate enabled. Verify missing key/binary/cwd/state errors, no state writes or
runtime imports, custom-provider uncertainty, path-free allowlisted support output, and
non-executable doctor exit codes. Native help must preserve Unicode drafts, allow reading
the final paragraph at 40/160 columns and add zero submissions before an explicit send.
Inspect `onboarding-help-*` captures; a title-only assertion misses unreadable instructions.
Repeat guide/check/support commands and fixture execution from the installed wheel outside
the checkout. Full regression and isolated renderer timing still apply after native edits.

Daily replacement adds `test_daily_replacement.py` and `test_daily_terminal.py`: real child
execution/observations, waiting scope, completed direct-child restart, incompatible/uncertain
receipt rejection, isolated local draft recovery, bounded UTF-8 snapshots, symlink refusal,
and keyboard-only native inspection/external-editor success and failure. The editor test
asserts zero submitted turns; recovery checks original bytes and zero answer delivery.
Use `daily_probe.py` with an explicit live credential after the full suite: four billed root
and four child turns across both presets, including restart/explicit child memory recall.
Inspect `daily-*` captures; its receipt fingerprints host and renderer source. Run PTY owners
serially and the benchmark separately. No inferred Git authorship or exact context meter.
Keep action-search labels unambiguous: a new description containing "Decisions" can shadow
the ordinary decision action. Test old keyboard paths as well as new menus. Inspect evidence
must get enough vertical room for its source, and assertions must tolerate visual wrapping.
Wait for a dialog's closing frame before sending another function key: a stale Search label
can satisfy the next wait, while adjacent Escape sequences can be parsed as literal suffixes.
Child restart must permit exactly inherited parent orchestrator settings (the stock delegate
passes them), without treating arbitrary overrides as reconstructible routing.

Independent swap gate: add `amplifier-module-loop-basic` and
`amplifier-module-context-persistent` as workspace submodules, then install only into this
app's environment with `uv pip install --no-deps -e ../amplifier-module-loop-basic -e
../amplifier-module-context-persistent`. Run `TUI_TEST_SWAPS=1 PYTHONDONTWRITEBYTECODE=1
uv run --no-sync pytest -q tests/test_independent_swaps.py`. Four loop/context combinations
execute a real fixture-tool round trip, completed resume with zero provider calls, and an
explicit second turn. Tests explicitly set the persistent module's transcript path under
temporary storage: its default would use the shared Amplifier home. They characterize its
refusal to replace loaded history and verify host rejection of a mismatching module-owned
transcript. This is not all-module policy, child-persistent-context or arbitrary migration proof.
The simple module restamps internal `metadata._seq`; comparison allows only that difference,
not changed canonical content, tool identities or other metadata. Read source, not only the
persistent module README: the pinned implementation also appends messages to its own file.

Native terminal correction: `test_tmux_scrollback.py` must exercise the DEFAULT view,
not first open `/scrollback`. It checks real attached tmux selection across pages,
short Unicode replies in full-pane capture previews, inspection return, repeated
narrow/wide resizes and transcript retained after exit. Capture all history and count
markers: a still-visible footer or duplicate reply is a failure, not proof of retention.
Never clear history to repair a redraw. tmux can expose old rows on growth without moving
its reported cursor. The observer models DEC 1049 save/restore; real tmux remains the gate.
Locate the composer by its Message heading, not old border glyphs. Prior-conversation terminal
text is expected after New/Resume; assert model-context isolation from checkpoints.
The ordinary view leaves the mouse to terminal selection; injected mouse test sequences
prove action routing, not that default native view captures physical clicks.
Use `interaction_probe.py --output notes/evidence/inline-fixture.json`, then
`interaction_probe.py --live --output notes/evidence/inline-live-current.json` for this
wave's keyboard-only controls (four billed read-only turns across both presets).
Inspect `*-inline.png` as well as the decision/detail captures. Run
`benchmark_candidates.py --output notes/evidence/inline-benchmark.json` alone afterward.
The 100,000-item case must also pass cleanup, not just edit latency: initial replay
is disclosed and limited to 1,000 historical items, while full source remains inspectable.
Do not issue a new cursor-position query during unchanged-size menu/quit cleanup.
If inspection was resized, query the restored primary anchor before clearing, rather
than subtracting its old viewport height and erasing short replies. Exit observers must
keep servicing terminal queries; the existing finite resize fallback still applies.
Leave alternate screen only when owned;
redundant DEC 1049 restore can reposition the cursor into retained text.
With full-height startup, clear owned rows with EL rather than ED from row zero: tmux
may otherwise archive provisional chrome. Resize observers must wait for the pane's
actual PTY TIOCGWINSZ, not only tmux capture dimensions: grid resize can precede the ioctl
update. Wait for complete draft deletion before the next resize; a prefix match can
accept an unfinished synchronized frame. Test multiline tmux copy buffers, not only OSC52.

Everyday navigation adds `tests/test_input_history.py`, `test_everyday_terminal.py` and
`test_tmux_scrollback.py`. The last creates an isolated tmux socket/server, records it
in the workspace manifest, attaches through a PTY, copies old primary-screen history
across pages in real copy mode, verifies draft retention and reaps both resources.
Never run it concurrently with other PTY owners (manifest writes are not locked).
Capture-pane alone is not evidence of the attached copy-mode screen on tmux 3.4.
The suite also exercises bare startup-picker cancellation without state writes, cwd
recall without context import, delayed-history/draft isolation, drag wheel/edge scrolling,
visible Pending/Steer buttons and restored mode badges. Reflow assertions wait for the
new width before issuing navigation; Escape tests wait for dismissal before typing.

After the full native/preset suite and build, run
`PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python scripts/everyday_probe.py --live`.
It bills four read-only turns across both presets, checking identified steering,
queued recall, plan badge through new/resume and a native-view round trip with no extra
turn. Inspect `everyday-*` captures. Then run the benchmark alone:
`uv run --no-sync python scripts/benchmark_candidates.py --output notes/evidence/everyday-benchmark.json`.
Scene timing does not measure history-directory I/O, snapshot entry cost or matched CLI
latency. Preserve independently staged tests when reporting unrelated lint failures.

The structured-reading wave adds Rust table/code/hunk cases and
`tests/test_structured_reading_terminal.py`: actual fixture tool round trip, wide/narrow
tables, Unicode code-content copy, unchanged draft, completed resume, bounded catalog
and oversized-copy refusal. A labelled simulated source update tests that an open code
snapshot stays fixed until catalog refresh. Temporary real Git tests change the file
after observation and verify hunk navigation/copy stays with the original diff.

After tests/builds, run `PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python scripts/structured_reading_probe.py --live`
for two billed read-only turns across both presets: read_file, an actual Markdown table,
and code copy with no extra execution. Inspect `structured-*` private captures. Then run
`benchmark_candidates.py --output notes/evidence/structured-reading-benchmark.json`
separately; its scene timing is not a measurement of large-catalog discovery or Git I/O.

The runtime-control wave adds `tests/test_runtime_controls.py` and
`tests/test_controls_terminal.py`: real-loop early/stale/bounded corrections, observed
insertion, final-stream continuation, stop/failure, replay isolation, actual alternate
provider selection, vendor guards, restored pins and fail-closed control storage.
Native tests exercise multiline corrections, late-editor rejection, provider confirmation,
selection history/copy and resume. A separate simulated lost-acknowledgement transport
tests dialog copy/dismiss; it is not runtime conformance. Inspect `controls-*` captures.

Four billed turns across both presets verify two mounted Anthropic models:

```sh
PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python scripts/controls_probe.py --live
```

Each Haiku turn reads a file and receives an identified active correction. After selecting
Sonnet and restarting, a tool-free turn must recall the correction, with the provider's
observed selection naming the restored pin. Assert actual mounted instance names and
insertion events—not only the chosen label or old transcript text. Receipt:
`notes/evidence/controls-live.json`. Timing uses
`benchmark_candidates.py --output notes/evidence/controls-benchmark.json`; older receipts
remain historical. Scene timing is not control-fsync or matched CLI latency evidence.

The workflow wave adds `tests/test_followups.py` and `tests/test_workflow_terminal.py`:
actual-kernel sequential queue release, pause/edit/remove, stop/failure, duplicate
admission, uncertain dispatch, restored queues and rename/context isolation. PTYs
exercise these controls during actual fixture approvals, modal rejection/cancellation,
local search and exact OSC52 copy. The bounded-search/Markdown case is a clearly
simulated projection probe, not engine conformance. Inspect private `workflow-queue`
and `workflow-search` captures before asking for UX feedback.

Four billed read-only turns verify live queued continuation and local organization:

```sh
PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python scripts/workflow_probe.py --live
```

Each preset reads one file, then a queued tool-free memory question checks canonical
continuity and admission after the prior outcome. Rename/search/copy add no turns.
The sanitized receipt is `notes/evidence/workflow-live.json`; raw state remains private.
Use `benchmark_candidates.py --output notes/evidence/workflow-benchmark.json` for this wave.

The navigation wave adds `tests/test_navigation.py` and `tests/test_navigation_terminal.py`:
actual-kernel new/return/context/draft isolation, failed and cancelled target preparation,
target cwd and completion scope, native picker/path controls and delayed-reply rejection.
Inspect the private `navigation-conversations` / `navigation-files` PTY captures; they
can contain temporary machine paths and must not be published blindly.

For live in-app switching (four billed read-only turns):

```sh
PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python scripts/navigation_probe.py --live
```

This creates both preset conversations, then switches between them inside Ratatui.
Each performs read_file and a context-memory turn; the second prompt does not include
the marker. The new answer, source draft and restored identity are checked separately.
The sanitized receipt is `notes/evidence/navigation-live.json`. Keep older receipts as
historical evidence; benchmark with `--output notes/evidence/navigation-benchmark.json`.

The reading/return wave adds `tests/test_reading_terminal.py` and
`tests/test_conversations.py`. They check Markdown styles, three-line wheel movement
inside one long reply, stable reading during streaming, resize, boundary history,
local completion, fresh-engine context restore, zero replay operations, private files,
single-writer locks and corrupt/uncertain/configuration-mismatched rejection.
The Markdown test captures an actual simulated terminal in `.evidence/interaction`.

For live return evidence (four billed turns across both presets):

```sh
PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python scripts/reading_probe.py --live
```

Each first turn reads pyproject.toml and receives a unique marker. The new engine's
next answer must recall that marker without it appearing in the second prompt. Assert
the **new answer in identified events**, not marker text still visible in old history.
The receipt contains assertions and source hashes, not private transcripts or markers.
Use `benchmark_candidates.py --output notes/evidence/reading-benchmark.json` to keep
the earlier historical timing receipt; source changes invalidate old measurements.

The current Ratatui interaction slice additionally owes:

```sh
PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python scripts/interaction_probe.py
```

This uses real Foundation/core with fixture provider/tool modules, two turns, module
approval, visible actions and exact evidence. It writes ignored terminal images and a
sanitized receipt. Tests include a keyboard-only workflow (Tab/arrows/Enter/Escape),
menu cancellation preserving selection, pasted menu text never executing, stale focused
decisions, actual runtime option scope and queued approval requests. OpenTUI retains its
older controls; do not claim a matched visual comparison after the Ratatui interaction wave.

With explicit provider credentials, this bills four live turns across both presets:

```sh
PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python scripts/interaction_probe.py --live
```

It verifies read_file and load_skill(list=true) through the real-work launcher using
ordinary controls. These operations are read-only requests, not a sandbox. Live capture
intermediates can include machine paths and remain ignored; do not publish them blindly.
The fixture decision capture must wait for the option-list frame, not question text already
visible in the underlying card. Renderer source changes invalidate earlier timing receipts.

The new candidates have real PTY gates, separate from the legacy Textual tests:

```sh
cargo build --release --locked --manifest-path frontends/ratatui/Cargo.toml
cargo test --release --locked --manifest-path frontends/ratatui/Cargo.toml
cargo clippy --release --locked --manifest-path frontends/ratatui/Cargo.toml -- -D warnings
bun test --cwd frontends/opentui
TUI_TEST_PRESETS=1 TUI_TEST_CANDIDATES=1 PYTHONDONTWRITEBYTECODE=1 uv run --no-sync pytest -q
PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python scripts/capture_candidates.py both
```

The capture script requires the workspace's terminal-tester submodule at
fde68aa883ff64b2ee1c94a4b6afa721443ddc55. It does not install an app bundle into the
user's CLI. Its local adapter preserves incremental UTF-8, numeric row order after
resize and hidden-cursor state; upstream source is unchanged. The low-overhead probe
answers cursor-position requests and measures parsed PTY output, not screenshot delay.
All spawned test process groups are recorded and reconciled in the workspace manifest.

Width regressions are checked in actual PTY output, not just layout arithmetic:
both engines launch at 160/200 columns, resize through 60/80/160/200 columns, and
retain the draft. Ratatui's ordinary and inspection composer starts at column zero and
wraps only after the final column; its transcript and tmux copy buffer have no outer gutter.
Test exact-width lines through resize/exit to catch last-column autowrap artifacts.
OpenTUI remains the historical inset comparator. A 120-column-only capture misses fixed-width
canvases. The engines started from one design; Ratatui now carries additional interaction work.

Run candidate timing independently from build/test workloads:

```sh
PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python scripts/benchmark_candidates.py
PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python scripts/benchmark_runtime.py
```

The second script requires isolated CLI setup, never the daily shared Python environment:

```sh
uv venv .state/cli-baseline-env
uv pip install --python .state/cli-baseline-env/bin/python ../amplifier-app-cli
AMPLIFIER_HOME="$PWD/.state/cli-baseline" .state/cli-baseline-env/bin/amplifier bundle add "file://$PWD/src/amplifier_tui/fixtures" --name tui-benchmark
AMPLIFIER_HOME="$PWD/.state/cli-baseline" .state/cli-baseline-env/bin/amplifier run --bundle tui-benchmark --provider fixture --mode single 'Compute a digest'
```

Only create the isolated environment if it does not already exist. Preserve the CLI's
foreign-home guard; never set its shared-venv bypass for these measurements. Its extra
composed policies and the fixture's model-discovery warning mean this is not yet a
policy-equivalent baseline. Read the measurement scope in notes/TERMINAL-REVIEW.md.
Raw samples and sanitized receipts live under notes/evidence; capture intermediates and
all runtime state stay ignored. Verify distributions omit state, caches, node_modules,
native build output and private archives.

With explicit provider credentials, the following bills two live read-only turns:

```sh
PYTHONDONTWRITEBYTECODE=1 uv run --no-sync python scripts/smoke_live_candidates.py
```

It exercises Ratatui/anchors and OpenTUI/anchors-amp-dev. Ordinary pytest remains
credential-free. Confirm live tool success and completion, not just an answer string.

The following verifies the existing Textual reference harness, not the selected product UI.
New frontend candidates owe the real-terminal capture protocol in
[FRONTEND-EVALUATION](notes/FRONTEND-EVALUATION.md) and matched measurements in
[PERFORMANCE](notes/PERFORMANCE.md). No unrun visual/performance gate is a pass.

Start the fixture. Type during startup, submit once, type a multiline second draft
during streaming, resize, switch views and return. Confirm text and selection remain.
PTY tests exercise bracketed paste/Send, a completed turn, startup failure, normal quit,
alternate-screen exit, bracketed-paste disable and exact termios restoration.
Pilot covers correlated approval clicks and stale button identity; host tests cover stop
before execution, during a tool and during an approval. Windows/macOS and real IME remain untested.

## Lessons that own future checks

- Indexed search must find content before the old tail window and beyond page one.
  Exercise append, truncation, corrupt cache, malformed/oversized records and Unicode
  literal queries. Partial indexing is not “no matches.” Timestamp recall needs interleaved
  sessions, current-session replacement and arrivals during an active history browse.
- Media tests compare original provider-request bytes after source files change, queue
  admission, rejection and reopen. Preview pixels must serialize identically across disk;
  thumbnail tuples versus JSON lists caused a real regression. No fixture proves vision.
- Standalone provider probes require explicit confirmation, no conversation/tools, queue
  hold and redacted failures. Observe real native confirmation/result paths; text can wrap
  between terminal rows. Stored-context inspection must not build the next request.
- Historical import must preserve its source, validate the captured digest and make zero
  provider/tool calls before an explicit new submission. It is not cross-vendor canonical
  resume. Completed-child custom settings must be retained exactly, not replaced by the
  current parent's defaults. Interrupted/private-state reconstruction remains separate.

- Git installation must be exercised from the actual private URL, outside the checkout,
  with no sibling source map. A local editable install or successful wheel build is not
  that proof. Fingerprint the installed Python/native files, not just workspace sources.
- Review existing Git history before first publication: a user test-drive commit can hold
  private receipts even when the working tree looks like a new project. Preserve the local
  branch and file bytes; publish only the explicitly reviewed application snapshot.
- Bound source delivery before the transport queue. On overflow, keep journal-first
  observations, refuse new work and test connection shutdown while stdin remains open.
  Record-count bounds alone do not constrain a single huge serialized event.
- Session repairs: `TUI_TEST_PRESETS=1 TUI_TEST_CANDIDATES=1 uv run --no-sync pytest -q`
  includes actual delegate/v2 agent recipes, mode denial/approval/restore/child inheritance,
  native mode controls, drag-copy, direct questions at 40/160 columns and historical
  recovery with original-byte/no-execution assertions. Use PYTHONDONTWRITEBYTECODE=1.
- `uv run --no-sync python scripts/session_repairs_probe.py --live` bills six parent and
  four child turns across both actual presets: read-only delegation/v2 recipe, direct
  question answering, approved mode entry and native clear after restore. Run PTY owners
  serially. Inspect private captures; retain only sanitized assertion/hash receipts.
- Native control replies need conversation identity even when they are not journal
  events. Host-only tests miss replies silently discarded by the real client.
- Dependency-declared v2 recipes need their own execution test: legacy recipe success
  is insufficient. Dependency resolution can exceed a tiny fixture-tool timeout.
- Prepared bundle/module configuration can be mutated by mounts; clone it before
  initialization so later child composition and resume fingerprints remain stable.
- Mode activation can fail through an event rather than an exception. Test this signal;
  an active-mode label alone is not enforcement evidence. Native human mode choices
  are not assistant tool calls, or an assistant allowlist can trap the human in a mode.
- Recovery must include unfinalized assistant deltas and preserve the original byte for
  byte. A flattened historical fork is not faithful interrupted canonical-context resume.
- Delegate timeouts/cancellation may detach child tasks. The host must drain its owned
  children before checkpoint/journal close. Test Stop during a child's pending question,
  not only cancellation of a directly awaited fixture child.

- Named providers cross two public vocabularies: Foundation merges `id`, core mounts
  `instance_id`. Test root/overlay composition AND actual mounts; constructing a mount
  plan by hand misses collapse during composition. Recursive include authors need `id`.
- Steering admission is not insertion. Test first-request gating, exact turn identity,
  duplicate text/request IDs, foreign events, final-stream continuation and Stop/failure.
  This loop can continue after a final answer if a correction arrives during generation.
- Provider changes retain module guards and have their own interrupted-write tests.
  Resume must restore the selected instance before work; display alone is not proof.
- A lost modal acknowledgement must leave text copyable/dismissible without permitting
  an automatic resend. Test a transport that exits without the reply, not just rejection.

- Queue release waits for the execution task AND its checkpoint, not just a painted
  outcome event. Test Stop before execution starts, failure, duplicate admission,
  failed persistence and restoration; reopening is not permission to execute.
- Pending-item edit/remove validates identity and admission state in the host. A menu
  snapshot is not authority. Rejected edits retain their editor text until cancelled.
- Search bounds must remain visible while a result is selected; per-choice details
  must not hide partial-scan warnings. Copy source bytes, not rendered Markdown cells.

- Navigation needs failure/cancellation tests before and during preparation, not just
  successful snapshot replacement. Verify candidate locks are released and stale source
  requests cannot affect the newly selected conversation.
- Conversation switching isolates undo, selection and sent-history browsing state,
  not just the visible draft. Undo in a new conversation must not restore source text.
- Completion replies must match the request, conversation, draft and cursor. Test a
  deliberately delayed response after editing; do not infer this from fast local scans.
- Picker labels must remain identifiable at real terminal widths. Put compact titles/IDs
  in the list and full directory identity in selected details, not a clipped path dump.
- A transcript screenshot is not resume evidence: assert canonical messages in a fresh
  context module and count provider/tool calls before a new explicit submission.
- Scroll one long item, not just many short ones. Assert stable visible rows while an
  unrelated stream grows; item-count offsets can pass short-message-only probes.
- Empty/truncated/missing journal records must not turn a nonempty checkpoint into a
  valid empty conversation. Validate identity, sequence and checkpoint agreement.
- Persist absolute local bundle/overlay references; tool cwd is not launcher cwd.
- A returned assistant string is not completion evidence. Assert runtime outcome separately.
- Foundation's static module-export hints can be stale. Require actual tool names explicitly.
- Failure-tolerant core initialization needs host admission policy. A missing hook is not ready.
- The PyPI core version and inspected source HEAD can differ. Record both, including peeled tag SHA.
- UI click identity must include the original widget/request, not a reused button ID.
- Test cancellation before an asyncio task starts: otherwise its finally block may never run.
- Some upstream repos track bytecode. Use PYTHONDONTWRITEBYTECODE to avoid incidental source changes.
- A smoke-test UI is not a design review. Exercise it and inspect captures before asking a specific steward question.
- A framework or transport is a replaceable implementation choice. Measure its integrated cost before freezing it.
- Contract shape and work traceability can be checked locally; draft detail is not ratification or future-service integration.
- Choice selection is local, not submission. Exercise Esc/reopen with multiple answers,
  and show enough review detail to identify every answer; an invisible second answer is
  not a useful review step. Question arrival must not take the composer's focus.
- On resume, "Ready" can appear in old assistant text before modules initialize. Live
  probes must wait for the current status row, not a whole-screen substring match.
- Repeated copy probes must count new OSC52 observations; an old "Source copied" status
  can remain visible while a later copy is still being processed.
- Reflow must preserve the combination of line and span styles. Test both plain source
  equality and actual colours; a visible plus/minus sign alone does not verify diff colour.
- Narrowing a tail-following transcript can move an earlier table header offscreen.
  Scroll to that source before asserting its narrow layout; do not confuse viewport
  position with lost table content.
- Mounted tools and successful read_file turns do not prove everyday preset viability.
  Exercise delegate and an agent-bearing recipe through session.spawn before claiming
  that coverage. A completed parent turn may contain failed tools.
- Mode gates are not necessarily approval requests: inspect the gate policy and actual
  event. A warn-policy first denial can allow a retry; a later clarification answer
  must not be confused with granting tool permission. Test the whole user-facing path.
- Question-menu tests using known labels do not prove discoverability. Check the
  unanswered transcript card and narrow-width entry point without prior menu knowledge.
  Mouse capture plus ignored drag events is not usable transcript selection/copy.
- A read-only Git command can invoke repository-configured clean/process filters.
  Disable those before both status and diff; --no-ext-diff/--no-textconv alone is insufficient.
  Use literal pathspecs and preserve opaque source identities even for lossy filename display.

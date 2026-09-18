# Matched CLI benchmark protocol

Derived from [performance.v1](../contracts/performance.v1.md). Initial measurements now
exist in the [review packet](TERMINAL-REVIEW.md); matched CLI policy parity is unresolved.
This protocol makes the draft promises testable; it is not a performance receipt.
The comparison includes the entire path, not just IPC microbenchmarks or renderer FPS.

## rc6 readiness measurement — 2026-09-18

Thirty alternating fresh-process, warm-cache pairs use actual CLI/native entrypoints
and the same deterministic digest workload. Builds and other test suites were not
run concurrently. Current prepared captures agree on kernel, provider, hook, session
and instruction fingerprints; they still differ in the extra native question tool
and the skills tool's installed-package configuration. All 21 packaged skill files
are byte-identical between environments; that explains the latter field without
silently normalizing it away. No differences are discarded.
App-owned request guidance and mode observations remain additional request-time
differences. Thus **default-product latency parity is not established**.

| Observation | TUI median / p95 (ms) | CLI median / p95 (ms) |
|---|---:|---:|
| Startup to runtime ready | 564.2 / 597.7 | 447.5 / 510.5 |
| Submit to first visible fixture text | 252.9 / 282.7 | 433.3 / 631.9 |
| Submit to final visible fixture text | 347.3 / 366.6 | 434.1 / 632.7 |

The native path becomes runtime-ready about 117 ms later at the median in this
diagnostic run. Faster visible fixture responses do not cancel that observation or
prove live-provider speed. Readiness is distinct from the immediately editable
startup composer; this probe does not measure the latter. Native local edit p95 is
20.9 ms; Actions open 48.8 ms; inspection open/select/return 17.6/18.8/17.7 ms.
These are 30 idle interaction samples, not the full 200-sample streaming stress gate.
Private receipts retain all samples, bootstrap intervals, source hashes and two
process-tree RSS snapshots. They are not peak-memory, cold-cache or paid-model evidence.

The baseline is the isolated CLI environment used by the configured-policy protocol,
not an assertion about an arbitrary daily installation. Product dependencies remain
pinned; no hooks, question tools or enforcement were removed to improve numbers.
The remaining performance gate is equivalent effective request/workload evidence,
followed by a non-regression comparison—not another renderer-only speed claim.

## Experience-wave measurement boundary

Fresh prepared captures still differ in tool count and skills configuration. Inspecting
the actual configuration identifies the latter as the absolute installed CLI-package
skills directory; all 21 packaged skill files are byte-identical in the two owned
environments. This explains that field without silently removing it from the comparison.
The extra interactive question tool remains a real schema difference. App-owned recipe
guidance and current-mode observations also affect provider requests after preparation.
Mode-observation tests inspect ordered real requests through the actual streaming loop;
they are not proof of CLI-equivalent request construction.

The updated runtime probe measures 30 alternating warm fixture pairs, native local
edit/Actions/inspection/selection/return and tool-success paint. It includes two process-tree RSS snapshots
and a seeded bootstrap interval for the median. Neither snapshots nor warm measurements
claim peak/PSS, cold dependency-download cost, real-provider latency or default-product
parity. Final numbers and source identity belong in the experience acceptance receipt.
Do not disable the question tool or app guidance to manufacture an equivalence verdict.

## Historical configured CLI-policy checkpoint (2026-09-15, unpublished)

The [configured CLI validation](evidence/cli-compatible-validation.md) records 30
alternating actual-entrypoint fixture pairs using pinned CLI `f0ba883` and Foundation
`8a8e4f1`, core 1.6.1. Fresh processes use warm caches, actual product launchers and
isolated app-owned settings; no concurrent tests/builds/provider probes run during timing.

| Observation | TUI median / p95 (ms) | CLI median / p95 (ms) |
|---|---:|---:|
| Startup to ready | 868.1 / 1001.2 | 934.2 / 1038.7 |
| Submit to first visible | 237.8 / 254.7 | 431.8 / 628.8 |
| Submit to final visible | 342.0 / 361.4 | 432.8 / 629.8 |

Fresh actual-resolver captures agree on provider/hook configurations, session and
instruction fields, but differ in tool count (TUI question tool) and the skills-tool
configuration fingerprint across installed environments. Those differences are not
normalized away: **latency parity is NOT ESTABLISHED**. Even prepared equality would not
establish credential identity or request-time equivalence. These fixtures do not measure
personal service workflows, live-provider latency or cold dependency loading. Native
RSS excludes the Python host. Private raw receipt: `.evidence/cli-compatible-runtime.json`.

Use `scripts/benchmark_runtime.py --cli-compatible` with the dedicated app-owned CLI
environment/home and matching fresh policy comparison; see the smoke-test instructions.
Do not reuse foreign cached-home state or bypass its ownership guard. Earlier measurements
below used different policy and cannot be treated as a trend across equivalent workloads.

## Historical rc5 measurement and policy gap

The rc5 [validation record](evidence/rc5-validation.md) adds 30 alternating actual
CLI/native fixture-runtime pairs. Native startup-to-ready p95 is 267.8 ms and first
visible fixture output p95 is 125.6 ms; the corresponding CLI observations are 508.3
and 628.7 ms. **The prepared policies differ**, so these are non-equivalent diagnostic
measurements, not a speedup or non-regression verdict. Final-visible output is recorded
separately. Native-process RSS excludes its host and is not a cross-topology comparison.
The runtime benchmark requires a strict private policy-comparison receipt and a new
exclusive output path; `--native-only` omits the historical OpenTUI comparator.

`scripts/compare_runtime_policy.py --cli CAPTURE --tui CAPTURE --output NEW_RECEIPT`
now validates the capture shape and compares ordered module inventories, source/config,
instructions, session policy and kernel version. Exit 1 means differences; exit 2 means
invalid evidence. Exit 0 only means the compared prepared fields match: credential
values were omitted, and request-time schemas/policy/execution still require proof.
Fresh isolated CLI 0.1.1 / TUI 0.3.0rc5 captures on core 1.6.1 still differ in session,
instruction, tool-count and hook-count fields. No latency verdict is inferred from them.

The rc4 experiment now captures actual prepared policies through the installed isolated
CLI's `resolve_bundle_config` and the TUI's `prepare`, with no session execution. Both
use core 1.6.1 and the same fixture source. The CLI adds `tool-mode`, `tool-skills`,
`hooks-mode`, `hooks-approval`, `hooks-routing` and `hooks-wayfinder`; the TUI's minimal
fixture has none of those extra modules. This confirms a real composition mismatch,
not merely an inferred source-code difference. It does not characterize full presets.
The separate rc5 `anchors` preparation now compares a real preset too: ordered tool
IDs agree, while instructions, skills/filesystem/recipe configurations and hook
inventory differ. CLI terminal hooks and wayfinder are among those differences.
Prepared session fingerprints agree in that capture, not the whole composition.
The minimal-fixture timing table does not measure this separate preset capture.
Reproduce with `scripts/capture_runtime_policy.py --kind cli|tui --state NEW_STATE
--output NEW_RECEIPT` under the respective interpreter, optionally `--sources MAP` for
the TUI, and `--bundle URI` for an explicitly selected bundle instead of the fixture.
State must be a new subdirectory of this checkout's `.state`; use the isolated
CLI environment, never the daily shared environment. Receipts contain module inventories
and policy hashes and must stay private: hashing does not anonymize guessable content.

The AFK continuation measured full catalog/search/checkpoint-page lookup and actual native
Resume paint over 200 synthetic conversations / 100,000 messages (30 warm samples):
p95 37.0 ms and 68.3 ms respectively. The latter includes F4, action search, selection and
observed picker output. `scripts/benchmark_history.py --terminal` reproduces the experiment;
it does not measure a model request or CLI parity. Raw captures remain private; sanitized
scope and results are in [ACCEPTANCE](ACCEPTANCE.md).

The CLI inspected for that historical checkpoint was `772bdb42f135fa310e217d6634dd727039d2d840`.
Its `runtime/config.py` composes modes, packaged CLI expertise, curated skills, model
routing and wayfinder even for a minimal fixture bundle; notification and user app
behaviors add conditional policy. `lib/bundle_loader/prepare.py` also appends optional
global/project AGENTS instruction references after composition. Its prompt/control,
logging and persistence paths differ from this host. Merely supplying the same bundle
name and fixture provider therefore does not produce equivalent work.

Next matched-policy gate must capture and compare effective module configuration,
resolved request instructions/tool schemas, approval/logging/context policy and ownership
at the actual CLI and TUI entrypoints. Normalize only explicitly documented local storage
and renderer differences; never disable CLI policy or import personal configuration merely
to obtain a faster comparison. Until those observations agree, runtime benchmark numbers
remain labelled non-equivalent. No CLI-level non-regression verdict is claimed here.

## Baseline discovery before a topology decision

Identify the steward's actual current CLI executable/runtime build, source pins when
available, launch command, OS/terminal/tmux versions, dimensions and hardware. The inspected
CLI checkout is not automatically the installed daily-use CLI. Record dependency versions,
bundle/provider/model/context/tool/hook settings, history size, logging and approval policy.
Never persist credentials or private prompt text in benchmark artifacts.

Use reproducible workspace checkouts and isolated state. Do not edit/reuse unrelated
checkouts or silently modify the user's CLI settings. Record permitted normalization and
every difference between configurations; a non-equivalent run cannot establish parity.

## Measures and clocks

| Measure | Start | End / separation |
|---|---|---|
| First usable paint | Process launch | Composer accepts and displays input; not merely a header |
| Startup-to-ready | Process launch | Required runtime capabilities are actually usable |
| Submit-to-first-visible-text | Complete submit input delivered | First assistant content painted; distinguish admission and provider wait |
| Local editing | Key/paste delivered to PTY | Expected text/cursor change in captured terminal state |
| Stream presentation | Runtime event available | Corresponding terminal state visible |
| Control response | Stop/decision input delivered | Correlated acknowledgement visible; report actual execution stop separately |
| Resource use | Each scene starts | CPU, RSS/peak, queue depth, bytes sent and work during idle/streaming |

Use monotonic timing and a shared observer where possible. Cross-process clock alignment,
capture resolution and instrumentation overhead must be measured and recorded. A render
callback is not automatically visible terminal output. A fast "stopping" label is not proof
that a tool stopped. Do not use screenshots' wall-clock filenames as latency samples.

## Paired workloads

Separate fresh-process startup with installed dependencies from first-time dependency
download/install; report cold and warm caches independently, without deleting user caches.
Alternate baseline/candidate run order. Start with at least 30 paired repetitions per case
and at least 200 input/update observations per stress scene; increase samples if uncertainty
cannot distinguish pass from regression. This sampling choice is an experiment design,
not permission to loosen performance P2–3.

Use the same deterministic provider/tool stimulus for common-path comparisons, plus real
provider runs to verify integration. Keep provider/network timing separate; a single live
request proves neither a speed advantage nor a regression. Exercise one read/tool round trip,
failure, approval and interruption with policy enabled. Retain original samples, medians,
p95 values, capture overhead and the predeclared uncertainty calculation. A confidence
interval crossing the non-regression boundary leaves the comparison unresolved.

For render/control stress, replay identical streams at 30, 100 and 500 deltas/second with
1,000, 10,000 and 100,000 history items. Include tool-result bursts, multiline paste, resize,
scrolling away from the tail and a deliberately slow reader. This corpus is synthetic and
labeled as such. Record where the current CLI has no equivalent feature; apply the absolute
interaction bound there, without inventing a relative baseline. All rows must retain errors,
decisions and exact final content while display updates may coalesce.

## Architecture experiments derived from the gap

Measure a long-lived bidirectional child process as a candidate, not a given. Compare it
with an in-process/native bridge or a different host only where the profile identifies a
cost worth testing. Language crossings do not require porting all ecosystem modules.
Preserve a single execution/approval authority and a single terminal output owner.

Profile process boot, initialization, Python/module overhead, event serialization, copies,
queueing, context work and rendering separately. Candidate techniques include incremental
identified updates, viewport rendering, lazy detail materialization, bounded/coalesced
display queues and prioritizing control. These are hypotheses, not selected implementations.
Do not hide costs in "background" work that competes with typing or changes policy.

Before the stress run, record numeric memory/queue budgets and cleanup deadlines appropriate
to the chosen architecture. They remain open until measured and proposed; their absence
prevents a performance acceptance claim, not baseline discovery. The existing host's
unbounded queue and full-history formatting are explicit items to examine.

## Receipt and decision

Store a sanitized receipt under this project's evidence notes, with source/configuration
fingerprints, commands, sample paths and whether every measure passes its contract bound.
Do not commit a fake zero-latency baseline or mark an unrun benchmark successful. Preserve
comparison artifacts before choosing a frontend or host. A failure triggers a plan item,
an implementation change, or a separately approved direction amendment—not a relaxed test.

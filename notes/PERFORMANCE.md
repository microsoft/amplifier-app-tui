# Matched CLI benchmark protocol

Derived from [performance.v1](../contracts/performance.v1.md). Initial measurements now
exist in the [review packet](TERMINAL-REVIEW.md); matched CLI policy parity is unresolved.
This protocol makes the draft promises testable; it is not a performance receipt.
The comparison includes the entire path, not just IPC microbenchmarks or renderer FPS.

## Current measurement and policy gap

The AFK continuation measured full catalog/search/checkpoint-page lookup and actual native
Resume paint over 200 synthetic conversations / 100,000 messages (30 warm samples):
p95 37.0 ms and 68.3 ms respectively. The latter includes F4, action search, selection and
observed picker output. `scripts/benchmark_history.py --terminal` reproduces the experiment;
it does not measure a model request or CLI parity. Raw captures remain private; sanitized
scope and results are in [ACCEPTANCE](ACCEPTANCE.md).

The inspected CLI remains source `772bdb42f135fa310e217d6634dd727039d2d840`.
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

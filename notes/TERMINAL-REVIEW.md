# Terminal comparison — review packet

This is the historical engine-comparison receipt. The subsequent interaction wave is
documented in [source reconciliation](INTERACTION-RECONCILIATION.md) and
[acceptance evidence](ACCEPTANCE.md); use `scripts/run.py` for real work. Ratatui now
has discoverable actions and focused runtime choices while OpenTUI retains its earlier
controls. Do not use the old same-design comparison as the current interaction review.

This implements the comparison authorized by the steward, toward presentation P1–8,
session P7–8, and performance P1–7. Direction remains in the DRAFT vision
and contracts; this receipt does not ratify them or relax unmet promises.

## What to review

**Does this terminal adaptation now have the conversation-first hierarchy and quiet
evidence you wanted, and is the persistent composer comfortable for your actual work?**

Please judge that experience, especially the density and the choice to expand detail
in the main body while leaving the composer fixed. You are not being asked to discover
whether ordinary sending, paste, approvals, view switching or quit work: those have
developer-run checks. Native terminal/font/IME and subjective fit still need your judgment.

Use the Ratatui command in the README to review the layout. OpenTUI is a second
implementation of **the same design**, not a second visual proposal; switching engines
is a developer comparison, not a visual choice for the steward. Both default to the same
SIMULATED scene. Ctrl+Y reveals a deliberately failed test; Ctrl+E opens its exact
evidence; Escape returns; Enter sends the prepared draft; type while the reply streams.
Use the separate `--runtime` command only when you want real Amplifier execution.

Current 200×40 terminal captures (synthetic scene):
[Ratatui full width](evidence/ratatui-full-width.png),
[OpenTUI full width](evidence/opentui-full-width.png).
The requested judgment is layout density and composer comfort, not which identical
scene looks different. There is no need to repeat the engine comparison.

Earlier capped-revision captures, retained for comparison: [Ratatui Work](evidence/ratatui-work.png),
[OpenTUI Work](evidence/opentui-work.png), [failed evidence](evidence/failed-evidence.png),
[Ratatui 60×20](evidence/ratatui-narrow.png), [OpenTUI 60×20](evidence/opentui-narrow.png).

## What is actually implemented

Two actual terminal clients, not browser mockups: Ratatui 0.30.2 with ratatui-textarea
0.9.2, and OpenTUI 0.5.11 on Bun. Both consume the same versioned scene and experimental
request/event boundary. Neither frontend imports Amplifier modules or owns execution
policy. The existing host, bundles and kernel remain independent.

The opt-in runtime path mounts real modules through Foundation and the existing host.
Real provider evidence: Ratatui/anchors and OpenTUI/anchors-amp-dev each completed an
Anthropic Haiku read_file turn. [Sanitized live receipt](evidence/live-candidates.json).
That proves those two paths, not every provider/module, CLI policy parity or delegation.

## Terminal-specific adaptations

- Slate surfaces, green emphasis, amber decisions and red failures follow the supplied
  concept. Borders and spacing use whole cells; layout uses the available width with
  small edge padding. The steward rejected the earlier 112-column centered cap.
- Detail replaces the scrollable body, not the composer. Ctrl+T selects the next tool;
  Ctrl+P copies its exact source, not a truncated visible excerpt.
- Enter sends; Alt+Enter/Ctrl+J are portable newline keys. Shift+Enter works only when
  a terminal reports it distinctly. Paste never uses the send path.
- At 60×20 the composer shows one editable row with its own scroll; the conversation
  viewport shrinks. Approval controls remain accessible. At smaller than 32×12 the
  client asks for a resize instead of pretending the layout still fits.
- Unimplemented delegation, queue, steer and durable resume are stated in System,
  not represented by functioning-looking controls. The concept's delegated-agent
  panel and consolidated attributed diff are not yet implemented.
- Keyboard selection and editing are exercised in both. OpenTUI additionally provides
  native mouse editing; Ratatui's composer mouse-position/drag selection needs more work.
- The screenshots use terminal-tester's PTY/pyte/Pillow path with DejaVu Sans Mono.
  They preserve terminal content/colors but do not establish native emoji or IME rendering.

## Developer evidence and boundaries

The Python suite includes actual kernel integration, both preset mounts, request-ID
deduplication, busy draft retention, stale-decision rejection, terminal paste/selection,
view changes, clipboard escape payload, startup failure, backend loss, SIGTERM/quit and
exact termios restoration. Rust and TypeScript have additional source/wrapping checks.
Captures exercise Work/Review/System, failed evidence, streaming drafts and resizing
120×40 → 160×40 → 200×40 → 120×40 → 80×24 → 60×20 → 120×40.
Four additional PTY regressions launch each engine at 160 and 200 columns and assert
full-width rules, inset composer/approval edges, visible engine labels and draft retention
through repeated narrowing and widening. The old 112-column cap fails this geometry gate.

The transport bounds outbound pending records and rejects overloaded/disconnected
connections rather than retrying effects. It does **not** yet provide durable slow-reader
outcomes, reconnection, crash recovery or guaranteed cleanup of a session that Foundation
fails to return during initialization. Those remain HOST-01/CONT-01 obligations.
Normal cooperative cleanup and refused-ready cleanup are exercised; those tests do not
prove arbitrary plugins can be forcibly cancelled safely.

## Measurement interpretation

The measurements below describe the earlier 112-column-capped revision, identified
by source fingerprints in each receipt. They are retained historical evidence, not
fresh performance acceptance for the full-width correction. No new speed claim is made.

[Candidate samples](evidence/candidate-benchmark.json) alternate fresh launches with warm
installed/file caches and exercise 1k/10k/100k history at 30/100/500 deltas per second.
Measurements end at parsed real PTY output, include observer overhead, and do not measure
a physical display's scanout. Scene readiness is observed after the initial usability
probe, so it is an upper bound rather than the earliest possible ready timestamp.
RSS is the frontend process alone, not total frontend + Python runtime memory.

Measured on Linux ARM64; 30 alternated startup pairs and 18 stress cases, each with
at least 200 typing and 200 visible-update observations:

| Measure | Ratatui | OpenTUI |
|---|---:|---:|
| First usable composer, median / p95 | 53.6 / 70.4 ms | 182.9 / 201.7 ms |
| Worst case typing p95 across the stress matrix | 20.5 ms | 26.7 ms |
| Worst case event-to-visible p95 across the matrix | 19.7 ms | 25.4 ms |
| Maximum sampled frontend RSS | 127.8 MiB | 212.7 MiB |

All measured matrix cells are below the draft 50 ms interaction bound and the declared
256 MiB frontend RSS budget. This is not acceptance of the unmeasured resize/approval
latency, slow-consumer, cold-start, total-process-tree memory or native-display cases.

[Runtime samples](evidence/runtime-benchmark.json) exercise the real fixture provider/tool
through both clients and an isolated installation of the inspected CLI revision. The CLI
adds modes, skills, routing and other policies absent from this host; the fixture provider
also lacks the standalone constructor used by the CLI's model-info discovery. The runtime
turn succeeds, but that warning and the composition difference are recorded, not hidden.
These CLI measurements are context, **not** matched non-regression evidence under P2.

Thirty real-fixture runs per client measured startup-to-ready median/p95 of 175.9/194.4 ms
for Ratatui and 290.5/321.9 ms for OpenTUI. Submit-to-first-visible was 113.7/115.4 ms and
112.7/114.5 ms respectively, including the fixture provider's fixed delays. The isolated
CLI measured 922.3/952.8 ms startup and 430.2/629.7 ms first-visible text under its different
composition/display policy. Those differences are not attributed solely to the frontend.

Provisional preference: Ratatui is the stronger candidate on the observed startup,
memory and terminal-output costs. OpenTUI produces a comparable layout and has richer
native editor behavior. No final frontend/host selection or full product port has occurred:
policy-equivalent CLI comparison, independent context/orchestrator/hook swaps, slow-reader
durability and remaining input/visual acceptance still gate SELECT-01.

## Capture and baseline findings

The tester source is pinned at fde68aa883ff64b2ee1c94a4b6afa721443ddc55. Its examples
describe another application; they are not this app's keymap or startup profile.
The local capture adapter corrects split UTF-8 decoding, numeric screenshot row ordering
after resize, and drawing a cursor hidden by DECTCEM. Upstream source is unchanged.
The low-overhead probe answers actual terminal cursor-position requests for prompt_toolkit;
the screenshot helper's built-in settling delay is never called a latency measurement.

The installed CLI correctly refused an isolated AMPLIFIER_HOME with its daily shared
environment. The guard was preserved. Baseline setup instead used a dedicated environment
and state under this project; no daily CLI configuration or module pointers were changed.

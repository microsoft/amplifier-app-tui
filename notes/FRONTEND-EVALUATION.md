# Frontend comparison protocol

Work derived from presentation P1–8, session P7–8 and performance P1–7.
This note applies those draft promises; it adds none and selects no framework.
Ratatui and OpenTUI are candidates. Textual is the retained reference harness, not a candidate.

The implemented comparison and observed limitations are in the [review packet](TERMINAL-REVIEW.md).
This protocol still governs the remaining gates; a receipt does not silently waive them.

## Visual reference and review boundary

[The supplied concept](../design/reference.html) is a preserved simulated reference,
not executable Amplifier behavior. Its hierarchy is the visual baseline: restrained
header/context, Work/Review/System navigation, conversation-led content, quiet activity,
expandable delegated work, a contextual approval card and a persistent composer/footer.
Palette roles are muted neutral surfaces, green emphasis, amber pending decisions and
red failure—not a requirement to reproduce browser fonts or sub-cell pixel spacing.

Capture the proposed terminal adaptation beside each candidate. Explain differences in
spacing, borders, density, color support, keymap, selection and narrow-width behavior.
Do not quietly reinterpret an unavailable feature as an acceptable adaptation. Keep the
same documented interaction script for both candidates; framework defaults do not decide it.
The original concept's Enter/Shift+Enter hints and the old fixture's Ctrl+S keymap differ;
resolve and document that deliberately, including terminals that cannot distinguish keys.

## Shared scenes, then real integration

First use one versioned synthetic event corpus, timing schedule and expected outcomes.
Label it SIMULATED in the terminal. No displayed shell command executes in these scenes.
This isolates the UI comparison; it is not live-provider or ecosystem conformance evidence.

| Scene | Action | Falsifier / evidence to retain |
|---|---|---|
| Startup / error | Type before ready, then inject failure | Missing text, cursor jump, or a false-ready indicator; captures and input trace |
| Streaming | Type a multiline correction during a response | Lost characters, duplicated final text or delayed echo; captures and timings |
| Quiet tools | Expand success and failure detail, copy a result | Raw output dominates by default, error hidden, or copy loses content |
| Review / System | Switch views with a selected draft | Draft/selection reset, lost context, or unsupported features shown working |
| Approval | Open, answer, expire, then deliver a stale click | New request authorized by old input, focus stolen, or wrong action identified |
| Long history | Scroll away, expand detail while new output arrives | Forced jump to bottom, full-history reflow per token, or stalled input |
| Resize | Sweep 120x40, 80x24 and 60x20, then widen | Overlap, inaccessible composer/decision controls or lost source content |
| Shutdown | Stop, quit, startup-abort and simulated boundary failure | False undo/completion, lost admitted identity or broken terminal restoration |

Include emoji, combining and wide characters, tabs, long paths, large pasted text and
color-disabled output. Record OS, terminal/multiplexer, dimensions, fonts where known,
renderer revision and exact replay command with screenshots; supported-terminal claims
must follow actual runs. Real IME behavior remains a device-specific check if inaccessible.

Use terminal-tester's PTY/capture path where suitable; its Ratatui-specific examples may
require instrumentation that our candidate does not yet provide. Inspect the actual module
and repo instructions before integrating it. Never treat raw stdout assertions as a visual
review. Keep test sessions isolated, record external resources, and close only our sessions.

## Decision gates

Compare the two implemented terminal frontends before spending on a full port. Each owes
screenshots, observed interaction results, unresolved defects and the matched measurements
from [PERFORMANCE](PERFORMANCE.md). "Looks better" without captures does not settle P6;
an isolated replay score does not settle the integrated-performance promise.

The next gate exercises the candidate frontend with real ecosystem execution, correlated
control and failure/cleanup behavior. Do not assume the one-shot JSONL client is that host.
Keep the current kernel/modules where they fit; replace the body where evidence warrants it.
Retain compatibility receipts for every changed seam under ecosystem P6.

The review packet asks a concrete question: which candidate better preserves the concept's
visual hierarchy and editing flow, given the recorded tradeoffs? The developer supplies
functional and visual verification first. The steward judges intent, adaptations and
remaining tradeoffs—not whether ordinary buttons or paste work at all.

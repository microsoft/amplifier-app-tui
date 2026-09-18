# Control clarity, authorship and naming — development verification

Scope: FEEDBACK-01..03, toward the amended DRAFT vision and presentation/interaction
contracts. Existing local changes and the checkout-following launcher are preserved.
No kernel or upstream-module changes, personal-service writes, commit or publication.

## Delivered

- Corrections explicitly wait for the next input boundary. Their editor and pending
  status distinguish this from Stop's cancellation request; neither implies rollback.
- Submitted messages, corrections and question answers share the full-width charcoal
  surface, white text and vertical padding. Source text is unchanged. Dark-theme
  secondary grey is darker; expanded thinking retains Markdown structure but every
  text/syntax span stays secondary. Other colour treatments remain supported.
- The last model-call usage and turn/session totals are adjacent, including after the
  call's rows have already been committed to native history and in reflowed inspection.
- The host emits the app-owned `prompt:complete` lifecycle as app-cli does. Configured
  ecosystem naming retains its trigger and model-routing policy; generated titles
  update the catalog and visible title, while explicit user names win even during a
  generation race. Legacy titles whose provenance is uncertain are preserved.
- Naming metadata is module-owned sidecar state, not an opportunity to overwrite app
  admission/composition metadata. Utility calls have visible background activity and
  session-only usage; they cannot become response text, reset a new turn's totals or
  make uncertain work resumable. In-app switching rebinds identity-guarded observations.

## Verification

The clean all-enabled gate passes **628 tests in 320.40 seconds**, with native,
preset and independent module-swap gates on; no skips or warnings. Rust passes 42
tests in each of dark, light, terminal-default and NO_COLOR treatments. Formatting,
strict Clippy, Ruff, three OpenTUI harness tests and direction/archive checks pass.

Both final actual daily-launcher presets pass in-app New, two substantive read-only
turns, one attributed naming call and process resume with generated title and unsent
draft retained without admitting another conversation turn. All 44 runtime/renderer source
fingerprints match. Successful disposable live projects were cleaned up.

Real PTY checks cover laptop 175×50 and narrow 40×20 painted cells, dim expanded
thinking, charcoal corrections and contiguous usage. Existing 32×12 interaction and
six attached-tmux cases also pass. Captures were personally inspected, including the
real live named/resumed sessions and correction editor. Controlled providers/layout
fixtures are distinct from these actual provider runs; raw evidence remains ignored.

Regression checks include actual naming-hook generation, manual-name races, in-app
switching, late utility accounting, uncertain checkpoint refusal and a cooperative
long-running tool: correction stays pending, Stop interrupts, the draft survives.
The first integrated run retained stale label/request-observer assumptions and a short
stream visibility race. A diagnostic SIGINT also interrupted one test's runtime rather
than its pytest owner; only the clean rerun above is authoritative. The focused repeat
passed, and the harness now separates conversation requests from observed utility calls.

Separate timing covers 30 alternating renderer-startup pairs and 18 streaming stress
cells. Across the nine native cells (1,000/10,000/100,000 history items at 30/100/500
deltas per second), typing p95 is **20.7–34.4 ms**, streaming event-to-visible p95
**20.2–42.7 ms**; syntax-stress typing p95 is **21.9 ms**. First-usable composer
median/p95 is 61.8/81.0 ms in the controlled scene, not bundle/provider startup.
All 27 benchmark source fingerprints match. Runs were separate from this wave's
builds, tests, provider calls and capture generation. These are warm-file, shared-host
PTY observations, not CLI-policy parity or physical-device proof.
The benchmark's simulated Stop acknowledgment does not certify real tool cancellation.

## Important limits

**The long-grep cancellation defect is diagnosed, not fixed here.** The inspected
tool-search checkout (`0c7f4a7`) calls synchronous `subprocess.run` inside async execution;
its Python fallback also does synchronous scanning. A bounded actual-module probe with
a controlled 150 ms subprocess mock delayed a scheduled 10 ms input task until the
search returned. No user files were searched. Result `head_limit` is applied after the
search, not a bound on search work. A blocked host cannot promptly process either a
correction or Stop; changing buttons alone is not a complete remedy. Cancellation and
subprocess ownership must be fixed at the tool seam, not hidden behind an unowned thread.

Interact/native-copy switching remains unchanged and is not declared good UX. The
steward asked to reconsider it; a single explicit inspector alongside a permanently
copyable transcript is a candidate direction, not an implemented redesign.
Automatic naming requires the configured naming hook and enough useful context; the
module may defer. No alternative app-owned naming model or pricing estimates are added.
Physical mobile comfort, new-platform releases and policy-equivalent CLI latency remain
separate gates. No newer published wheel is implied.

Review after relaunch: are thinking and metadata comfortably secondary while responses
and corrections remain easy to read, with the final usage block visually grouped?

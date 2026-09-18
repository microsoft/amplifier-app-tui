# Conversation-first Activity — development verification

Scope: ACTIVITY-01..03, derived from the amended DRAFT vision and presentation /
interaction contracts before implementation. This is app/renderer work, not a kernel
change, a formal Converge verdict, a new published artifact or complete CLI parity.
Existing local changes and the daily development launcher are preserved.

## Delivered experience

- Default black transcript, white conversation text, full-width charcoal user messages
  and composer with vertical padding. No user/assistant role headings or normal
  turn-complete message. One live working/waiting/stopping tail owns that indication.
- Single-line tools and public-thinking excerpts, with blank separation. Public thinking
  expands as Markdown; its observed source can be copied without Markdown rendering
  changing the bytes. No additional provider calls or private-reasoning reconstruction.
- Visible Activity / `/activity` opens a read-only tree: exact root call → child agent →
  observed tools/public blocks → nested children. Each level offers a preview and bounded
  source evidence. Stable identity preserves focus during refresh and concurrent updates.
  Recipe display progress with an observed origin belongs under its call; warnings and
  failed/unknown child tools remain visible in the conversation.
- Native committed rows remain terminal-owned and immutable, not clickable widgets.
  Mouse/keyboard drill-down belongs to temporary inspection; Escape restores the draft.
  Ordinary terminal/tmux copy and retained history remain available outside inspection.

The app observes the pinned loop's optional task-keyed dispatch map at actual execution,
not a guessed last-call timestamp. Missing correlation stays unknown. Tool instances,
schemas and policy remain module-owned; the wrapper preserves instance-bound execution
guards and restores its scoped observation in `finally`. No upstream/kernel edits.

## Verification

Final integrated repeat: **610 passed in 308.56 seconds**, with preset, native candidate
and module-swap gates enabled, no skips, warnings or test deselections. Unrelated user
notes were excluded from document traversal, not test selection. Runtime source was
frozen for the final live runs and integrated checks.
Development HEAD plus uncommitted source is the candidate; HEAD alone is not its identity.

- Eight new actual-runtime/index tests cover two parallel parent calls, nested children,
  unknown ancestry, stable order, explicit excerpt bounds, failed-tool visibility,
  grouped progress and instance-bound guard denial. Four new native PTY cases cover
  mouse/keyboard drill-down at 175×50, 40×20 and 32×12, retained draft/no replay, and
  observed-thinking Markdown/source-copy through an explicitly labelled transport fixture.
- Both final live presets pass the bounded Activity journey through the actual daily
  executable: one completed root turn and two completed children each, real delegate
  and agent-bearing recipe, exact originating-call checks and child-tool evidence opened
  through ordinary UI input. All 44 runtime/renderer source fingerprints match the
  checkout. Successful isolated state was removed; private receipts remain ignored.
- Six actual tmux cases cover attached copy mode, streaming history, exit retention,
  inspection return and resize. Short-reply cases additionally shrink to 40×20 and
  verify one surviving composer, retained multiline draft and unduplicated history.
  Screenshot-emulator resize captures are not terminal reflow evidence; actual tmux
  assertions are authoritative for that boundary. Physical mobile usability is untested.
- 37 Rust tests pass in dark/light/terminal-default/NO_COLOR environments; Cargo fmt and
  strict all-target Clippy pass, as do the retained comparator's three Bun tests.
- Ruff check and format and structural direction checks pass; production
  source remains at 50 files. Contracts remain DRAFT, without formal verdict rows.
- Actual live laptop screens, child/tool inspection, narrow Activity and expanded
  thinking captures were inspected. Iteration grouped noisy recipe progress, removed
  opaque child-block notices and enlarged Markdown previews to avoid needless clipping.

Failed attempts remain distinct: the first integrated attempt exposed stale-idle observer
races and a direction line-budget violation. A later attempt passed 608 tests and failed
two navigation observers that wrongly waited for a model turn after New/Resume. Those
actions must not execute a turn; their tests now wait for the restored/new context.
A subsequent repeat passed 609 tests and caught an older provider-adoption test reading
the candidate checkpoint before its UI snapshot committed. It now awaits the new identity
on screen, rather than accepting the source conversation's still-visible Ready footer.
One wider live journey stopped on an unexpected model clarification instead of silently
answering it. Another chose a failed delegate ahead of a successful retry; the bounded
driver now names the available agent and selects the successful call explicitly. Neither
failed run is counted as a passing full mode/question/queue journey on this source.

## Measured responsiveness

Thirty alternating renderer startup pairs and 18 streaming stress cells ran separately
from this wave's builds, tests, captures and live traffic. Native first usable composer
was median 60.3 ms / p95 67.3 ms; this is a simulated scene, not configured-runtime startup.
Native editing p95 across the nine history/rate combinations was 19.9–34.9 ms; syntax
stress editing p95 was 23.5 ms (maximum 44.5 ms). These satisfy the local 50 ms editing
target for the measured workloads, not a CLI-parity or live-provider latency claim.
Warm caches, shared Linux ARM host and observer/scheduler costs remain in scope. Raw
private receipts fingerprint the source; historical OpenTUI comparisons have different
history projections and are not equivalent-output performance measurements.

Fresh-context semantic privacy review covers the scoped source/fixtures and sanitized
verification prose. Raw receipts, screenshots and local session state remain private;
no artifact or release was published. Test resources were reaped or confirmed absent;
only the seven explicitly retained pre-existing deliverable resources remain active.

## Limits and review

Activity is a disclosed bounded index: latest 256 identities, 100 siblings / 1 MiB,
16 KiB detail and 8192-character public-text excerpts. Unobserved child content and
private state are unavailable; older root evidence remains in Review/export. This is
not an unlimited reconstructed execution trace or support for every opaque recipe step.

Relaunch `amplifier-tui` to load the checkout; running sessions do not hot-reload.
Review question: does the quiet conversation surface remain understandable during real
work, and can Activity answer “what happened inside this call?” without losing the draft?
No publication, personal-service/account verification, new cross-platform certification
or policy-equivalent CLI speed claim is included.

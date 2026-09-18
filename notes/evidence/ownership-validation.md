# Child ownership and forked-skill clarity — development verification

This follow-up repairs existing presentation.v1:4/7, session.v1:3 and continuity.v1:1
obligations. It does not change the vision, module execution authority, skill prompts
or personal configuration. Changes already present after the preceding review were
preserved; previous source fingerprints are historical, not this revision's receipt.

## Behavior

- Child hook messages are public Activity observations with explicit child ownership.
  During a tool invocation they belong to that tool; during mounting or otherwise
  outside an observed tool they belong to the child. Shared ID prefixes never label
  different agents as the same source. Warning/error notices remain visible as compact
  counts, separately from failed tools, with messages and severity available in Activity.
- Child observation IDs include the execution identity, not just a provider call ID
  and optional request counter. Resumed work cannot overwrite the earlier execution's
  tool rows. Progress also checks parent/execution identity and rejects late obsolete
  child updates before bubbling them into the parent's current work.
- Forked skills use the module's explicit skill metadata for their label. Compact
  summaries distinguish completed execution from inner tool errors or hook warnings,
  use minutes/hours for long work, and omit repeated final status text. Decimal cost
  display remains host-owned; neither labels nor inspection change accounting.

## Evidence

Both initial regressions failed against the pre-fix source: parallel child notices
were unlinked root messages, and a resumed provider reused the earlier tool identity.
The actual runtime regressions now pass, including parallel startup/tool notices,
saved-journal inspection, thinking/usage-named hook sources, reused provider IDs,
current-run sibling filtering and late obsolete child progress. Fixtures are synthetic,
not captured user content. Existing sustained accounting and truncation tests remain.

The focused native/activity/flow/attached-tmux gate passes **19 tests**. Inspected
native captures at 175×50 and 40×20 show forked-skill labels and separately attributed
tool/hook warnings; the three-size input test also exercises 32×12. Rust passes
**48 tests** in default, no-colour, terminal and high-contrast treatments; release
build, strict Clippy and Ruff pass. These are controlled terminal observations, not
a physical-mobile or performance-parity claim.

The final all-enabled integration passes **654 tests in 346.10 seconds**, with zero
skips, failures or warnings (`.evidence/ownership-integrated-1.xml`, private receipt).
This includes **19 independent loop/context swap cases**; no additional packages were
needed for those gates. A separate real-terminal drilldown opened a child hook warning
through its delegate/agent subtree and public preview without requesting execution;
the captured layout was inspected.

Both final live daily-launcher presets pass: one root turn, four parallel delegates
plus one recipe child, 13 attributed model calls, recursive Activity inspection and
resume with the draft retained and no extra admitted turn. Final captures for both
presets were inspected; all **44 runtime/renderer source fingerprints match** the
final revision (`.evidence/ownership-live-flow-1.json`, private receipt). Owned successful
raw state was cleaned; captures and receipts remain private. No owned test PTYs,
tmux sessions or receivers remain active.
These isolated preset runs do not certify personal services or the full user setup.

The direction/archive guard and 22 document tests pass, retaining DRAFT status,
595 contract lines and 50 production source files. No new contract obligation or
formal Converge verdict was created for these repairs.

The skill-required fresh-context privacy review found no identifying private literals
or clear overclaims in the scoped new source, synthetic fixtures and evidence prose.
It was a read-only semantic review, not independent execution of these tests.

## Boundaries

- A skill-loading tool can actually execute a forked skill and nested agents; a long
  duration/call count is not necessarily a rendering error. A review skill may contain
  cleanup instructions. Displaying that honestly is not enforcement of read-only
  review or protection against contradictory task/skill instructions.
- No hidden review budget, retry policy, tool exclusion or automatic cancellation was
  introduced. Read-only enforcement and uncooperative module cancellation remain
  execution-policy concerns, not promises made by a compact status row.
- Old unlinked messages and collided historical IDs are not rewritten or reconstructed.
  The new ownership guarantees apply to newly observed work. Native copying and the
  explicit Interact tradeoff remain unchanged.
- Independent-module tests are opt-in; a run without their enabling flag is not proof
  that packages are unavailable. Installed-wheel and personal-service verification are
  separate from a development checkout's runtime/terminal checks.

Raw sessions, terminal captures and local receipts remain private. No publication or
new release certification is claimed.

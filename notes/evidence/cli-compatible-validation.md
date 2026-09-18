# Configured CLI compatibility — development evidence

2026-09-15. Uncommitted development work after rc5; published artifacts are unchanged.
Direction was amended first under Converge: ecosystem P1/P2, presentation P4,
interaction P6 and continuity P3. Contracts remain DRAFT, not ratified verdicts.
No kernel or upstream module source was changed.

## Delivered scope

- Ordinary **new** `amplifier-tui` launches use pinned CLI policy helpers and layered
  global/project/local settings. Active bundle, default/configured app behaviors,
  root instructions, named providers, module overrides, sources, permissions and routing
  carry through. Invalid settings or failed declared behavior loading refuse startup.
  Explicit preset/bundle/overlay launches remain isolated unless opted into CLI policy.
- CLI policy preserves declared recipe/logging/context-intelligence destinations.
  Existing CLI `keys.env` loading retains ambient-variable precedence; provider token
  lookup remains module-owned. No keys/settings are copied into the TUI's store or
  rewritten. Interactive login still belongs outside the TUI.
- Tool arguments/results, child result excerpts, hook source/severity, public thinking,
  retry/throttle, effective context budget and root usage/cost where reported appear
  inline. Excerpts are bounded; exact tool evidence stays inspectable. Missing cost
  and occupancy are unknown. Root totals identify the last reported provider, not a
  single-provider attribution when routing changes.
- `/skill NAME arguments` reuses CLI skill semantics and completes discovered names.
  Familiar read-only aliases open local views; unsupported slash commands refuse
  without a model request. Local commands cannot silently enter the queue.
- Resume offers bounded CLI metadata discovery for the exact working directory,
  newest observed directories first. Confirmation creates a new conversation with a
  captured historical text reference. Original files stay unchanged; tools do not
  replay. No canonical CLI private-state/session migration is claimed.

Existing conversations retain saved policy; older records remain isolated. Different
CLI homes/policies or working directories require launcher `--resume`, not in-process
switching. The dedicated CLI-policy host adopts its selected process cwd so relative
module paths (including project skills) see the right workspace. Configured hooks can
have startup effects, including when mounting a new import conversation.

## Verification

- Integrated gate: **526 passed in 248.79 seconds**, candidates/presets/independent swaps
  enabled, no warnings or skips. Private JUnit: `.evidence/cli-compatible-tests-verified.xml`.
- Native: 36 normal-color tests and 36 with `NO_COLOR`; Clippy passes. OpenTUI's three
  regression tests pass. Direction shape: 592 contract lines / 50 production files.
- Final documentation checks: 22 passed in 0.09 seconds; Ruff check and format check
  (156 files) and `git diff --check` pass. Document enumeration explicitly excluded
  unrelated user-owned notes without reading their contents. No formal verdict generated.
- Eleven targeted compatibility tests cover immutable settings, invalid-policy refusal,
  identities, session/agent overrides, exact controlled comparison to the actual CLI
  resolver, declared destinations, real-kernel tools, skill arguments, synthetic saved
  keys, decimal costs, no-replay import, metadata bridge, cross-cwd switch refusal and
  public thinking event ordering/deduplication.
  Both real presets compose actual CLI defaults plus controlled configuration and
  execute a shell tool and delegation. Personal services are not fixtures.
- Native fixture plus **both live presets** pass command refusal, project-local skill
  discovery under `--cwd`, inline results, actual Resume/CLI history menus and import
  confirmation/cancellation. Live runs perform two billed read-only turns in controlled
  workspaces with explicit environment credentials. Captures were visually inspected:
  file argument/result, public thinking, effective budget and reported token/cost footer
  are visible. Raw state/screenshots stay private. Receipts:
  [fixture](cli-compatible-fixture-ordered.json), [live](cli-compatible-live-ordered.json).

The first integrated run had 498 passes, 23 skipped swap cases and two failures: an
old default-launch expectation and delayed autosave refusal obscuring startup's
not-ready state. The test now explicitly selects isolated policy; the native refusal
preserves admission/local-draft status. The corrected all-enabled gate above passes.
Probe development also caught a relocated relative source map, an Escape/paste injection
race, a missing inspection allowlist entry and selection of a refresh row instead of
the history item. Live captures then exposed late thinking delivery interrupting the
streamed answer. The observer now consumes public stream-block completion and suppresses
the duplicate final-content event; a regression test covers ordering. The final full gate
above includes all code changes, and refreshed native/live captures show contiguous
answers. Import confirmation also warns that configured hooks can mount before Send.
Failed attempts are not successful evidence.

## Policy and performance

Pinned CLI: `f0ba88398043f6b012d151360397893e46cd5d52`.
Pinned Foundation: `8a8e4f11918afd38ea8fe8f69cbec002226324f7`; core 1.6.1.
Fresh actual-resolver captures compare the controlled fixture with CLI defaults and
the native adapter. Provider/hook inventories and configurations, session and instruction
fingerprints match. Two differences remain: the TUI question tool adds a tool, and
`tool-skills` configuration fingerprints differ across separate installed environments.
No normalization erased those differences. Raw captures/comparison remain private.
Prepared equality would still not prove credential identity, request-time equivalence
or live latency. The verdict remains **NOT ESTABLISHED**.

Thirty alternating actual-entrypoint fixture pairs completed with CLI compatibility
enabled. These are fresh processes with warm dependency caches; no concurrent tests,
builds or live-provider probes, and no Cargo compilation inside measured startup.

| Observation (ms) | TUI median / p95 | CLI median / p95 |
|---|---:|---:|
| Startup to ready | 868.1 / 1001.2 | 934.2 / 1038.7 |
| Submit to first visible | 237.8 / 254.7 | 431.8 / 628.8 |
| Submit to final visible | 342.0 / 361.4 | 432.8 / 629.8 |

Private receipt: `.evidence/cli-compatible-runtime.json`; all recorded source hashes
were rechecked against the final implementation. Prepared fields still differ as above,
so these numbers are diagnostic, not a speedup/non-regression claim. They do not measure
the user's full configured ecosystem, live-provider latency or cold dependency loading.
Native RSS excludes the Python host and cannot support a whole-process memory comparison.

Benchmark preflight first exposed an editable install without a packaged native binary;
the native measurement now uses the actual workspace product launcher. A prior owned CLI
environment then refused foreign cached-home ownership. That guard was not bypassed:
a new dedicated app-owned environment/home was installed, its dependency-source conflict
resolved with explicit local constraints, and both policies recaptured before timing.
Failed preflight receipts remain private and are not successful benchmark evidence.

## Remaining validation and limits

This is not certification of a user's whole configured ecosystem. Identity-provider
login/refresh, personal remote destination health, memory save/injection and specialized
service-backed workflows still need scoped end-to-end runs. Declared policy preservation
is not an HTTP-delivery or external-state receipt. No personal conversations were
inspected and no personal configured service session was launched. General CLI command
mutation (`/goal`, directory-policy editing, arbitrary provider changes) is not implemented;
unsupported commands now refuse safely. Imports omit media/executable/private state and
are bounded to 1 MiB. Catalogs disclose their 5000-entry / 100-row / 200-ms limits.

No release, push or artifact replacement is part of this checkpoint. Existing changes
and user-owned notes remain preserved. Relaunch the checkout-linked command for new
code; existing conversations are not hot-reloaded.
The workspace manifest has no active temporary probe resources: its seven retained
entries are the private repository, five existing releases and the daily command link.

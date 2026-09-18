# Everyday CLI workflows — development validation

Direction: interaction P4/P6, presentation P1/P4/P5, ecosystem P4/P6.
Vision and contracts were amended before implementation; all remain DRAFT.
This is unpublished checkout work, not a new release or a parity verdict.
[Source comparison](../CLI-WORKFLOW-GAPS.md) records the gaps and remaining priorities.

## Implemented scope

- Inspection clears its own alternate screen without Ratatui's cursor-position query.
  Native primary-screen scrollback and bounded resize policy remain unchanged.
- Root and child tool outcomes recognize bounded JSON/Python-literal success envelopes.
  Malformed, oversized, overly deep and non-envelope text remains unknown. No `eval`;
  original evidence is retained and a failed turn/tool cannot become success from prose.
- Native Actions and Tab expose cached discovered skill names/aliases; a command with
  arguments can be inserted into an empty draft and requires explicit Send. An occupied
  draft is preserved. Turn-end refresh catches lazy module discovery; stale-session
  catalogs are ignored and closing-session refresh cannot drop the final outcome.
- Recipe file candidates are separate from observed recipe activity and active runs.
  Bounded names-only browsing scans working-directory/composed-bundle recipe folders;
  selection appends an unsent review request without replacing a selection or executing.
  A mounted recipes tool receives app-owned ephemeral discovery guidance, explicitly
  listed among CLI-policy differences. The recipe module remains execution authority.
- Startup failures remain readable in native history and after rejected Enter or late
  draft refusals. Drafts remain editable; the UI tells the person to correct and relaunch.

## Verification record

Targeted actual root/child runtime, both-preset recipe semantics and real memory skill
loading pass. The memory test mounts actual skill definitions, not a memory service:
it establishes command loading/argument flow, not memory writes or remote delivery.
Native PTY gates exercise silent cursor replies through F3/resize/F1/F4, skill menu
insertion/Tab/Send separation, stale catalogs, startup failure and recipe-draft retention.
Captured screens were inspected. PTY closure verifies clean exit and terminal restoration.

The initial integrated run had 549 passes and one direction-document line-budget
failure in 257.74 seconds; that failure is retained, not relabelled as success. The
contract wording was compacted without dropping its promise.

Final all-enabled run: **551 passed in 258.83 seconds**, no warnings or skips, with
`TUI_TEST_CANDIDATES=1 TUI_TEST_PRESETS=1 TUI_TEST_SWAPS=1`. Native Rust tests pass
36 normally and 36 with NO_COLOR; Clippy passes with warnings denied; historical
OpenTUI has 3 passing tests. Ruff checks/format and diff whitespace checks pass.
Direction shape remains 593 contract lines and 50 production files; no formal verdict.
The direction scan excludes unrelated user-owned local notes without opening them.

Configured fixture and live native probes pass. Both anchors presets load the real
discovered skill with literal arguments, then use read_file; recipe selection is an
unsent review draft, unsupported commands refuse, and CLI-history import is cancelled
at confirmation with original source unchanged. Live skill result, retained recipe
draft and tool-output captures were visually inspected. Four controlled live turns;
no personal service certification, recipe execution during browsing or speed verdict.
Separate real recipe execution/delegation regressions pass in the integrated suite.

Private receipts (not release artifacts); all recorded source hashes match final code:

| Receipt under `.evidence/` | SHA-256 |
|---|---|
| cli-workflows-tests-final.xml | 15ec3ad9020b27ad5d5592209003135e3848863bfc7d2d2ccb9c3008d46aa3cb |
| cli-workflows-fixture-final.json | 49cbe33499afe5c2d8fae4848a9045b7a9d383cb2928da34b65cc3e13ba38699 |
| cli-workflows-live.json | 6f59a0e121c6562175cf044b717ef643ec870d7401076da35851685456129bb0 |

All owned probe resources were reaped. The seven pre-existing retained resources
(repository, five releases and development command link) are unchanged. Relaunching
the checkout-linked command uses this code; already-running sessions are not hot-reloaded.

## Limits

No personal settings, conversation contents or remote service destinations are fixtures.
Configured live probes use an owned home/workspace and read-only requests. Namespace
skills remain unavailable until the module resolves them; no keypress downloads sources.
The catalog's time budget is cooperative, not a hard deadline on a blocked filesystem.
Recipe candidates are not validated definitions, all-repository discovery or permission
to run. The injected guidance cannot guarantee a model's judgment. Existing historical
statuses are not rewritten. Broader CLI mutation commands, authentication, canonical
private-state continuation and service-delivery receipts remain open. Earlier timing
receipts describe their earlier source; no new CLI latency-equivalence claim is made.

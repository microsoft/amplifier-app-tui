# Scoped CLI controls — development validation

Direction: interaction P6, continuity P1/P3, ecosystem P2/P6. Vision/contracts were
amended first and remain DRAFT. This is local checkout work, not a release or a parity
verdict. Earlier user changes are retained; no kernel or upstream module was modified.

## Implemented and exercised

- Goal setup/status/clear uses the pinned CLI parser and streaming loop's goal state.
  Setup starts no turn; the next explicit Send authorizes runtime continuation. An
  active-cap badge and actual goal-progress events stay visible. Goal/control records
  restore with compatible TUI sessions; missing/pending state refuses resume. The
  fixture exercises the real loop's one-turn cap, not a simulated goal engine.
- Root tool enable/disable uses Foundation's actual configurator. Directory controls
  update supported filesystem write/edit instances, not just configuration labels;
  actual denied writes and both-preset reopen enforcement pass. Shared settings,
  children, bash and other tools are unchanged. Mode changes cannot silently re-enable
  locally disabled tools. Arbitrary live config mutation is not claimed.
- Provider use/auto/status/models/test forms reuse the existing capability and probe
  adapters. Mode arguments, aliases and trailing prompts preserve module guards;
  failed activation cannot send the trailing prompt. Controls cannot be queued.
- Asynchronous mounted-provider login uses module-owned storage and a cancellable host
  task. Prompts are bounded transient wire data, never journal/context items, never
  automatic focus changes. Native Actions reopens them; Stop clears them and preserves
  the draft. The actual ChatGPT wrapper adopts tokens from a **synthetic OAuth exchange**
  into its explicitly owned test file. This is not real account authorization.
- CLI history can adopt complete paired public messages into a new TUI identity. The
  test writes source history through the actual CLI SessionStore, validates tool pairs,
  checks exact portable-message readback and retains original bytes/draft. Incomplete
  calls refuse. No original identity, private state, credential or policy reconstruction.
- Actual memory modules save to a disposable instance, inject that text into the next
  real runtime request, and refuse non-human writes. No personal store/timer is touched.
  Actual intelligence fan-out sends authenticated HTTP events to an owned loopback
  receiver, honors exclusions, keeps local JSONL and records HTTP 401 failures. The UI
  projects bounded root-session forwarding diagnostics without URLs/raw error detail.
  Neither no failures nor HTTP acceptance is proof of remote graph indexing.

## Verification

The all-enabled integrated gate passes **571 tests in 272.42 seconds**, with no skips
or warnings (`TUI_TEST_PRESETS=1 TUI_TEST_CANDIDATES=1 TUI_TEST_SWAPS=1`). The existing
private user-note filenames are excluded from the documentation scanner in the runner;
their contents were not read, edited or published. No source edits/builds ran during
the full gate. Rust passes 36 tests normally and 36 with NO_COLOR; Clippy uses
`-D warnings`. OpenTUI's three comparator tests pass. Ruff/check-format passes 162 files.
Direction remains within 594 contract lines and 50 production source files.

The first full run retained 568 passes and three failures: an obsolete unsupported-goal
expectation, an observation test assuming every non-policy row has one schema, and a
real fuzzy-menu collision between `system` and `filesystem`. Exact local command names
now take precedence over fuzzy labels. Focused reruns and the complete gate pass; the
failed receipt remains distinct, not overwritten or relabelled green.

Live testing then exposed an unsolicited mode picker after a typed mode command.
Only identified picker requests now open that menu. A rapid mode-change/exit/resume
test also exposed premature completion and a journal/checkpoint sequence mismatch.
Completion now follows the context read and immediately precedes the synchronous
checkpoint, without an intervening await. Probes wait for that unique completion
status, not historical mode text. The final full gate and both live presets pass these
fixes; earlier green receipts are historical, not evidence for the final source.

After the full gate, test-only markers made optional ecosystem dependencies conditional
on `TUI_TEST_PRESETS=1`. The focused tests pass both configurations: 14 enabled tests;
9 passes and 5 expected skips without optional modules. No production source changed.

Private receipts (raw JUnit contains environment identity and is not publishable):

| Receipt | SHA-256 |
|---|---|
| `cli-controls-tests-mode-final.xml` | `04f57f7b1d25bebb63692a7b081519ac9bbceef30baa0bd0daabe86c3abadf62` |
| `cli-controls-fixture-mode-final.json` | `fee5a7b640d600c2f521465d3f1e920197e97ea4d5e245c0be5b4d265ab9be47` |
| `cli-controls-live-mode-final.json` | `d54e2cba373cd925a110a7ec1f0403df7b16d07510da4319ce09d88f57bf2332` |

The configured native fixture probe passes goal/config/provider controls alongside
skill/recipe discovery, tool execution and source-preserving history confirmation.
Both live presets pass controls, actual skill arguments, explicit mode activation,
real read-file execution under that mode, mode deactivation and source-preserving
history confirmation. All 45 recorded source hashes in each final probe match the
checkout. Native goal/auth and final live tool captures were inspected; PTY tests verify
clean exit and terminal restoration. No owned PTY or HTTP receiver remains active;
the seven retained repository/release/daily-command resources are unchanged. Relaunch
the development-linked `amplifier-tui` to use these changes. No latency equivalence
claim is made.

## Remaining boundaries

Canonical original-identity CLI/private-state continuation remains unsupported: a
transcript does not record enough policy/private state to safely reconstruct it.
Structured public adoption is the supported advance, not a renamed canonical resume.
Synchronous or mount-time interactive login still requires the provider's external
entrypoint; real browser authorization needs the account owner. Personal memory and
remote intelligence/indexing health remain unverified by these isolated tests. Global
config save, arbitrary live module reconfiguration, vendor-private message conversion
and broader platform/performance certification require separate work and evidence.

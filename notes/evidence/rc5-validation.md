# rc5 validation — 2026-09-15

Release candidate source: `67150fd825ea71b2dd231adfe6da3ec5450c6b24`, version
`0.3.0rc5`. Product changes are in `d4df1409a276205f413dc1933f7ea76f23f001e5`;
the later commit adds live verification and capture assertions only. The private
[v0.3.0rc5 prerelease](https://github.com/bkrabach/amplifier-app-tui/releases/tag/v0.3.0rc5)
is published at that source. Earlier releases remain unchanged.
All contracts remain DRAFT; these observations are not formal Converge verdicts.

## Seven scoped advances

1. Actual-entrypoint timing now requires an immutable private policy-comparison
   receipt and records final-visible output separately. Policy capture accepts an
   explicit bundle URI. Fresh CLI 0.1.1 / TUI rc5 preparations on core 1.6.1 still
   differ in session, instructions and tool/hook counts. No policy is removed to
   produce a favorable comparison; request-time equivalence remains unproven.
   A separate fresh `anchors` preparation finds the same ordered tool IDs, but
   differing instructions, skills/filesystem/recipe configuration and hook inventory.
   Terminal-hook removal and CLI wayfinder explain some inventory differences; no
   normalization claims the remaining effective policy is equivalent.
2. Explicit interrupted nested-child adoption validates bounded ancestry, root
   identity and exact effective policy before importing supported public context
   into a new child under the current root. It never executes ancestors or rewrites
   original receipts. Persistent adoption uses a fresh store with exact readback.
   Real recipe tests also remove checkpoint progress from their own generated state:
   the runner refuses unsafe resume without repeating the completed write. Inspection
   explains that public refusal; it does not implement another recipe engine.
3. **Stop and keep replacement draft** is discoverable in Actions. Confirmation
   stops current work and holds the queue, retaining text and attachments unsent.
   Escape cancels. No follow-up is automatically admitted; Stop does not undo effects.
4. Context inspection retains bounded provider-dispatch numeric reservations when
   the provider exposes them. No private token meter is read, no raw logging is
   enabled, and thinking/output reservations are not blindly added. Missing effective
   budgets remain unknown; these declarations are not current occupancy.
5. Explicit simple pytest commands can correlate a new/changed workspace-relative
   JUnit report with existing tool/source evidence. The safe 64 KiB snapshot reader
   retains its hash and counts actual case elements, not untrusted summary totals.
   Stale, malformed, unsafe or shell-ambiguous reports cannot claim fresh results.
   Reports do not prove semantic coverage, exclusive authorship or assertion truth.
6. Pasted drafts receive persistence priority ahead of ordinary typing debounce.
   The native test observes the exact multiline draft on disk within 200 ms, without
   a turn, then separately waits for both rendered lines before capture. This narrows
   the loss window; unacknowledged final keystrokes remain a crash boundary.
7. Provider-auth investigation documents the CLI's public module login seam and
   terminal/storage constraints. No TUI OAuth control or token migration is claimed.
   Release receipts now identify source commit and tracked-source cleanliness.

## Integrated and live gates

- Full suite: **514 passed in 226.55 seconds**, candidates/presets/independent swaps
  enabled, no warnings. Rust: 36 normal and 36 NO_COLOR tests; all-target Clippy passes.
  Bun: 3 passed. Ruff/format: 151 files. Direction: 588 contract lines / 49 production
  files; archive integrity verified separately. No kernel or upstream source changes.
- Following the full gate, the native controls suite passed again: 9 tests in 7.14
  seconds, including the strengthened paste-paint assertion.
- Both live presets pass read/no-replay resume and Stop/exit during a real nested
  persistent-child question, followed by explicit adoption through native menus.
  The selected child is interrupted; its ancestor reports a wrapped cancellation
  failure. Both original receipts and the persistent transcript stay byte-identical.
  The new child completes without tools in fresh storage under the recovered root.
  Native confirmation, adopted-result, Stop/draft and pasted-text captures inspected.
- Probe diagnostics exposed Foundation's intentional child-delegate exclusion and
  concatenating list overlays. The corrected isolated fixture explicitly uses the
  module's falsy-null exclusion behavior. Product defaults stay unchanged; this is
  not a general replacement contract. Failed diagnostic attempts are not success
  evidence. The runtime's wrapped ancestor cancellation remains labelled failed.

## Actual-entrypoint timing, non-equivalent policies

Thirty alternating fresh-process pairs, warm installed/source caches, common Linux
PTY observer and deterministic fixture provider with two requests and one SHA-256
tool. Values include observer/scheduler costs; these are not live-provider timings.

| Observed boundary | Native median / p95 | CLI median / p95 |
|---|---|---|
| Startup to ready | 240.4 / 267.8 ms | 454.0 / 508.3 ms |
| Submit to first visible fixture text | 122.9 / 125.6 ms | 430.8 / 628.7 ms |
| Submit to final visible fixture text | 221.7 / 228.7 ms | 432.1 / 629.5 ms |

CLI source: `772bdb42f135fa310e217d6634dd727039d2d840`. The CLI adds modes,
skills, routing and other app policy absent from the minimal TUI fixture. The strict
comparison reports different prepared fields and **latency verdict NOT ESTABLISHED**.
Do not use this table as a matched-policy speedup, non-regression or parity verdict.
Native-process RSS excludes its host, so no cross-topology memory claim is made.
An earlier diagnostic used the wrong native exit key; its failed receipt is retained
separately. The corrected harness completed all 30 pairs. Raw receipts remain private.

## Isolated renderer timing

Thirty alternating fresh-process native/OpenTUI pairs, warm OS caches, Linux PTY/pyte
at 120x40. Native first-paint p95 is **43.5 ms**, first usable composer **58.3 ms**,
scene ready **104.0 ms**. Nine native 1k/10k/100k-history by 30/100/500-update cells
report editing p95 **18.5–20.1 ms** and Stop acknowledgement **16.8–20.3 ms**. A
separate 100-block syntax simulation reports editing p95 **21.2 ms**. Nine historical
OpenTUI stress cells also completed; its viewport projection differs. These synthetic
renderer observations include observer/scheduler cost and establish no provider,
cold-cache, matched-output or CLI-policy equivalence.

## Five-platform candidate artifacts

All five jobs at the candidate source passed Rust tests, compiler-free installation,
offline diagnostics and actual installed-native PTY fixture tool/resume/Help/second-turn
checks with terminal restoration. Both macOS jobs additionally exercised their real
disposable PNG pasteboards. No physical desktop, SSH clipboard or musl proof is implied.

| Build platform | Wheel SHA-256 | Native SHA-256 |
|---|---|---|
| Ubuntu 22.04 x86-64 — release selection | `f85273418fb5ba1f43506a8079442e7b0694d9eea1fd4ef85af5a178b0945780` | `c60a09e2946745cce17cec7ca1d829a17cdf9b84c2a1853370af995f466c6f8f` |
| Ubuntu 24.04 ARM64 | `2925d27827aa10e968df4ee6f1a94364142a9ab3cb057a4685bf26644f28792a` | `d7682265c9fa84d2ed31bc6a0f7ef83ed55d168be3636277710d938cb40f2e90` |
| macOS 14 ARM64 | `f8f8496cd78fff8306622eaf1316cd152a4359d5d89a316d39961f2180995105` | `c45cfc77abfdde46c832afd4f361c94944caeb71d2d426755b22b634b09b4472` |
| macOS 15 Intel | `013c179d39d159dece641767f781ea1adc5eb9d2a8c30c2968f0e56125f9eb3a` | `2a68bdd4dd63eb651fbe224d19b1d837e86aded2e83a2532e45a51f5c4ed7a00` |
| Ubuntu 24.04 x86-64 — separate experiment | `29ca3e513fb06357d2d1898dd256e6a84dbed1240e58ac2973d942081dd034fa` | `fa5709b849c241ef8ba684efd5f61ecde7b429c1f79e9971ac18ba59240d24fe` |

The two Linux x86 builds share a wheel filename but have different bytes. Only the
Ubuntu 22.04 build is selected for release. Receipts report the exact candidate commit
and clean tracked source. Independent privacy review decompressed all 195 members,
verified RECORD hashes/sizes, wheel/native digests and 34 packaged source/assets per
wheel against the checkout; no scoped publication blocker was found.

The exact CI ARM wheel was separately installed with `uv tool install` into an isolated
tool directory. Both live presets pass outside the checkout, with remote sources and
no workspace source map: delegation/read-only child tools, Help without submission,
resume without replay and a second turn. Installed native digest matches the table.
These are real provider calls, separate from the five CI fixture gates.

The wheel README is the candidate source's pre-publication snapshot; its stale final
“local-only” sentence is corrected in subsequent repository documentation, not by
rewriting reviewed artifact bytes. Current release instructions belong to the release
notes and repository README.

All four selected wheel/receipt pairs were uploaded to the private prerelease and
redownloaded into a separate directory. All eight files compare byte-identical to
the reviewed copies; the remote tag resolves to the candidate source above. The
temporary five-job CI run and uploads were then deleted, with direct API HTTP 404
confirmation. Reviewed local evidence and published release assets remain retained.
No probe PTY/tmux resources remain active. The private repository, five releases and
checkout-backed development command are intentional owner-retained resources; the
development command must be removed or replaced before deleting its checkout.

## Remaining boundaries

Policy-equivalent CLI latency; arbitrary module-private/nested exact reconstruction;
missing original policy; crash-uncertain recipe effects; detached/remote cancellation;
effective context occupancy; semantic test coverage/exclusive causality; general
structural reflow, final unflushed keys, physical-desktop/SSH clipboard breadth and
musl remain open. Login investigation is documentation, not implemented TUI OAuth.

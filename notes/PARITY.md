# Everyday workflow coverage

[PLAN](PLAN.md) owns the current work queue.
Native controls and explicit CLI handoff together cover the audited CLI workflows,
not every hypothetical native wizard or arbitrary module-private-state transition.

This is a gap map against the **pinned Codex/Amplifier studies** cited in
[interaction reconciliation](INTERACTION-RECONCILIATION.md), not a claim of parity with
every feature in a current Codex release. Direction belongs to [VISION](../docs/VISION.md)
and contracts; verified scope belongs to [ACCEPTANCE](ACCEPTANCE.md).

| Workflow | Working path | Remaining gap |
|---|---|---|
| Learn and troubleshoot | Offline guide, local Help/check/support report, provider overlay wizard, standalone access probe; mounted asynchronous provider login with transient prompts and Stop ownership | Real account authorization, synchronous/mount-time login, keychain migration and cross-platform breadth |
| Read and inspect | Default inline terminal/tmux scrollback, retained transcript after exit, responsive Markdown tables, syntax highlighting, exact tool/code copy, fullscreen inspection; stable-projection character resize anchors and approximate unique table-cell matching | List/paragraph/quote layout and link clutter remain; see [Markdown comparison](MARKDOWN-GAPS.md). Ambiguous resize anchors use explicit item fallback; inspection temporarily owns the alternate screen |
| Compose | Multiline/paste safety, directory recall, completion, immutable file/line and PNG/JPEG/static GIF/WebP sets, queues, thumbnails, external editor; bounded Linux clipboard MIME fallback and actual macOS CI PNG pasteboard gates | Physical-desktop/remote clipboard breadth; broader/animated formats |
| Keep working during a turn | Follow-up queue; pause/run/edit/remove; scoped steering with observed insertion; Stop holds pending work; confirmed uncertain-correction copy into an empty unsent draft; confirmed Stop retaining a replacement draft without sending | Replacement requires a separate Send after reviewing the ending; earlier uncertain effects cannot be reversed by copying a draft |
| Return | Same-identity canonical CLI/TUI project sessions; Foundation native history and common writer ownership; names, settings, context writeback and bounded shared Activity/accounting | Portable controls and shared uncertainty recovery; large metadata and arbitrary private state; full web runtime gate. Switch clients sequentially; nonparticipants are not fenced |
| Organize | Names, paged pickers, incremental private full-text index, jump/copy; synthetic 100k-message index/search, complete catalog and native Resume paint measurements | Larger/cold-state breadth; exhaustive search beyond disclosed record/index bounds |
| Decide | Scoped approvals; direct question card, choice/free-text review, cancellation, child routing; scoped durable answer/correction/dialog copies; prioritized pasted-draft persistence | Last unflushed keystrokes; recovered copies never auto-submit |
| Change runtime behavior | Loaded configuration inspection; supported component toggles, metadata diff/set and confirmed shared saves; retained provider/mode/goal policy, goal safety breaker, bounded all-provider diagnostics and argument completion; root filesystem controls | Arbitrary hot reinitialization, hook mutation, child/bash permission changes, private-state conversion and vendor-specific message formats |
| Delegate | Capacity-aware children/v2 recipes, actual subprocess spawning, scoped approvals/questions/activity/accounting, graceful tree cancellation and force escalation; guarded same-identity completed/drained continuation with routing changes; explicit public recovery | Arbitrary private-state reconstruction, receipts without adequate original policy, crash-uncertain recipe effects and independently detached/remote processes |
| Administer and script | Pinned CLI entrypoint for setup, bundles/modules/sources, routing, notifications, update/reset and shared canonical sessions; installed prompt/stdin/text/JSON/trace and read-only shell completion; native clear/branch/export/direct tools and reversible archive | Native archival is a TUI visibility flag, not CLI deletion; not every wizard has a second native implementation |
| Review changes | Independent root/child outcomes; Git/diff/hunk review; confirmed conflict proposals; tool/agent-correlated source digests, unchanged-version links across resume, command return code, retained interrupted evidence and fresh explicit JUnit report hashes/case counts | Exclusive causal attribution, semantic test coverage, report assertion truth, external-writer transaction and automatic conflict resolution not claimed |
| Inspect context | Allowlisted configuration and catalog limits; public effective-budget events; inline root usage/cost where reported; compaction, stored messages, dispatch reservations, memory-only request projection and instruction-source index | Budget/catalog/dispatch declarations are not occupancy; exact wire, missing/provider-redacted fields and non-reporting module sources |
| Recover | Fail-closed checkpoints/control records; no replay; source-scoped dialog copies; explicit uncertain follow-up dismissal; read-only historical child/action evidence | Last unflushed keystrokes; exact interrupted-context/module-private recovery |
| Perform | Native renderer, bounded projections/delivery, non-blocking writes, owned host process group and cooperative execution grace; latest integrated run reports no callback warnings; reproducible stress receipts and strict prepared-policy comparator | Policy-equivalent CLI latency, arbitrary cancellation edge cases, detached/remote cleanup and broader all-seam policy conformance |
| Install | Private pinned Git installation; compiler-free rc6 wheels with source/digest receipts and platform-specific verification | rc6 predates shared sessions; source installation still needs Rust/linker; physical-terminal/live breadth beyond tested gates and musl remain |

New ordinary launches reuse pinned CLI layered settings and default/configured behaviors;
isolated policy remains available. Unsupported slash commands refuse locally, `/skill`
reuses CLI semantics, and generic tool/result/child/wait/warning content appears inline.
Native skill aliases now appear in Actions/Tab with explicit insertion versus Send;
recipe-file browsing is separate from active runs and observed activity. Root/child
serialized result envelopes receive bounded normalization, and inspection works without
cursor replies. [Service-module evidence](evidence/cli-controls-validation.md) adds actual memory
save/injection into owned stores and intelligence HTTP delivery/failure diagnostics.
Personal destinations and remote indexing remain unverified; the diagnostics inspector
never turns an absence of failures into delivery proof. The provider wrapper is tested
with synthetic OAuth, not a human's real browser authorization.

Current priority is tracked once in [PLAN](PLAN.md): interchangeable CLI/TUI clients,
shared canonical data and full CLI feature parity. Readiness work remains recorded
separately; prior handoff-only coverage is not a full interactive-parity verdict.
Arbitrary private-state recovery, exclusive causal attribution and every possible
platform are limitations, not an implicitly authorized endless feature queue.
Prepared-policy/request differences still prevent a default-product latency verdict.
The native client remains Ratatui; OpenTUI is a historical comparator and Textual a test harness.

# Everyday workflow coverage

This is a gap map against the **pinned Codex/Amplifier studies** cited in
[interaction reconciliation](INTERACTION-RECONCILIATION.md), not a claim of parity with
every feature in a current Codex release. Direction belongs to [VISION](../docs/VISION.md)
and contracts; verified scope belongs to [ACCEPTANCE](ACCEPTANCE.md).

| Workflow | Working path | Remaining gap |
|---|---|---|
| Learn and troubleshoot | Offline first-conversation guide, local Help, --check, allowlisted --support-report, explicit private provider/model overlay wizard | Credential validation and cross-platform readiness |
| Read and inspect | Default inline terminal/tmux scrollback, retained transcript after exit, responsive Markdown tables, syntax highlighting, exact tool/code copy, fullscreen inspection | Character-exact resize anchors; inspection temporarily owns the alternate screen |
| Compose | Multiline/paste safety, same-directory recall, completion, immutable text/PNG/JPEG snapshots, idle external editor | Globally timestamped recall, semantic references, image clipboard/thumbnails/multiple queued attachments |
| Keep working during a turn | Follow-up queue; pause/run/edit/remove; scoped steering with observed insertion; Stop holds pending work | Interrupted-tool replacement; uncertain correction recovery |
| Return | Canonical context, saved drafts, startup and in-app resume pickers, explicit historical recovery fork, composition/cwd validation | Exact interrupted-context repair, arbitrary module-private state |
| Organize | Names, transcript and bounded cross-conversation content search, paged pickers, jump/copy | Indexed large catalogs; exhaustive older-journal content search beyond disclosed bounds |
| Decide | Scoped approvals; direct question card, choice/free-text review, cancellation, child routing; scoped durable answer/correction copies | Last unflushed keystrokes, other dialog editors; recovered copies never auto-submit |
| Change runtime behavior | Explicit setup/overlays; mode badge, retained provider/mode selection, named instances, vendor guard; advisory provider model discovery | In-place arbitrary model reconfiguration and cross-vendor context conversion |
| Delegate | Scoped children and v2 recipes, approvals/questions/cancellation, refreshing child list, guarded completed/nested/routed continuation, isolated persistent child context; recipe review and failed-step resume proof | Interrupted child reconstruction, arbitrary orchestrator overrides, subprocess isolation; crash-uncertain recipe effects |
| Review changes | Independent root/child tool-outcome summary and Activity evidence; bounded read-only Git status, coloured diff, snapshot hunk navigation/copy | Agent-attributed changes/tests, conflict editing, side-by-side diff |
| Inspect context | Observed usage/compaction, local capture/dispatch policy and last-observed instruction-source index | Exact current request/occupancy; inline or non-reporting module sources |
| Recover | Fail-closed checkpoints/control records; no silent replay; copy/dismiss; explicit uncertain follow-up dismissal with retained receipt | Crash-edge editor retention, exact interrupted-context/module-private recovery |
| Perform | Native renderer, bounded projections/delivery, owned partial-startup cleanup, 100 ms Unix resize probe, reproducible stress receipts | Policy-equivalent CLI latency, cancellation warnings and broader all-seam policy conformance |
| Install | Private Git install; four-platform 0.3.0rc1 native wheels with compiler-free install/native-unit gates; Linux ARM64 installed-live/tool/resume evidence | Other-platform interactive/live breadth; older Linux/musl support; Git source install still needs Rust/linker; automatic CLI migration unsupported |

The remaining high-value runtime work includes cancellation edge ownership,
attributed change/test review, platform/release gates and matched CLI measurements. Those need exercised
host/module seams, not controls that translate silently into something else. The current
native client remains Ratatui; OpenTUI is a historical comparator and Textual a test harness.

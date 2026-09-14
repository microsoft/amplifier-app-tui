# Everyday workflow coverage

This is a gap map against the **pinned Codex/Amplifier studies** cited in
[interaction reconciliation](INTERACTION-RECONCILIATION.md), not a claim of parity with
every feature in a current Codex release. Direction belongs to [VISION](../docs/VISION.md)
and contracts; verified scope belongs to [ACCEPTANCE](ACCEPTANCE.md).

| Workflow | Working path | Remaining gap |
|---|---|---|
| Learn and troubleshoot | Offline first-conversation guide, task-based local Help, actionable --check, allowlisted --support-report | No automatic provider wizard, credential validation or cross-platform readiness claim |
| Read and inspect | Default inline terminal/tmux scrollback, retained transcript after exit, responsive Markdown tables, exact tool/code copy, fullscreen inspection | Syntax highlighting, character-exact resize anchors; inspection temporarily owns the alternate screen |
| Compose | Multiline/paste safety, same-directory cross-session recall, command/skill/path Tab completion, immutable UTF-8 snapshots, idle external editor | Globally timestamped recall, semantic attachments, images |
| Keep working during a turn | Follow-up queue; pause/run/edit/remove; scoped steering with observed insertion; Stop holds pending work | Interrupted-tool replacement; uncertain correction recovery |
| Return | Canonical context, saved drafts, startup and in-app resume pickers, explicit historical recovery fork, composition/cwd validation | Exact interrupted-context repair, arbitrary module-private state |
| Organize | Names, bounded local transcript search, jump to message, exact Markdown copy | Cross-conversation content search, large-catalog pagination |
| Decide | Scoped approvals; direct question card, choice/free-text review, cancellation, child routing; scoped durable answer/correction copies | Last unflushed keystrokes, other dialog editors; recovered copies never auto-submit |
| Change runtime behavior | Explicit bundle/overlay launch; persistent active-mode badge, retained provider/mode selection, named instances, vendor guard | Dynamic model discovery/configuration; cross-vendor context conversion |
| Delegate | Real scoped children, in-process v2 agent recipes, approvals/questions/cancellation, scoped evidence, guarded completed direct-child continuation after restart | Nested/custom/interrupted child continuation; subprocess-isolated recipe steps |
| Review changes | Independent root/child tool-outcome summary and Activity evidence; bounded read-only Git status, coloured diff, snapshot hunk navigation/copy | Agent-attributed changes/tests, conflict editing, side-by-side diff |
| Inspect context | Observed usage/compaction and configured context-intelligence capture/dispatch | Exact context occupancy and instruction-source index |
| Recover | Fail-closed checkpoints/control records; no silent replay; disconnected dialog copy/dismiss | Explicit uncertain-admission recovery and crash-edge editor retention |
| Perform | Native renderer, bounded projections, bounded source delivery with journal-first overload failure, reproducible stress receipts | Policy-equivalent end-to-end CLI latency, partial-init ownership, cancellation warnings and broader module-swap conformance |
| Install | Private Git uv-tool installation with embedded native executable, remote presets, version/doctor, isolated state | Build-time Rust/C linker required; macOS untested, Windows via WSL2; automatic CLI state migration unsupported |

The next high-value runtime work includes broader initialization/cancellation ownership,
image input, attributed change/test review and matched CLI measurements. Those need exercised
host/module seams, not controls that translate silently into something else. The current
native client remains Ratatui; OpenTUI is a historical comparator and Textual a test harness.

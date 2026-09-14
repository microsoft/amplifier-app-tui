# Everyday workflow coverage

This is a gap map against the **pinned Codex/Amplifier studies** cited in
[interaction reconciliation](INTERACTION-RECONCILIATION.md), not a claim of parity with
every feature in a current Codex release. Direction belongs to [VISION](../docs/VISION.md)
and contracts; verified scope belongs to [ACCEPTANCE](ACCEPTANCE.md).

| Workflow | Working path | Remaining gap |
|---|---|---|
| Read and inspect | Responsive tables, Markdown, visual-line scrollback, scrollable drag snapshots, explicit terminal/tmux native view, exact tool/code copy | Continuous native scrollback while fullscreen, syntax highlighting, character-exact resize anchors |
| Compose | Multiline/paste safety, same-directory cross-session recall, command/skill/path Tab completion | Globally timestamped recall, semantic attachments, images |
| Keep working during a turn | Follow-up queue; pause/run/edit/remove; scoped steering with observed insertion; Stop holds pending work | Interrupted-tool replacement; uncertain correction recovery |
| Return | Canonical context, saved drafts, startup and in-app resume pickers, explicit historical recovery fork, composition/cwd validation | Exact interrupted-context repair, arbitrary module-private state |
| Organize | Names, bounded local transcript search, jump to message, exact Markdown copy | Cross-conversation content search, large-catalog pagination |
| Decide | Scoped approvals; direct question card, choice/free-text review, cancellation, child routing and retained outcomes | Crash-durable unsent answers |
| Change runtime behavior | Explicit bundle/overlay launch; persistent active-mode badge, retained provider/mode selection, named instances, vendor guard | Dynamic model discovery/configuration; cross-vendor context conversion |
| Delegate | Real scoped children, in-process v2 agent recipes, approvals/questions/cancellation, open-root child resume | Process-restart child resume; subprocess-isolated recipe steps |
| Review changes | Independent tool evidence; bounded read-only Git status, coloured staged/unstaged diff, snapshot hunk navigation/copy | Agent-attributed changes/tests, conflict editing, side-by-side diff |
| Recover | Fail-closed checkpoints/control records; no silent replay; disconnected dialog copy/dismiss | Explicit uncertain-admission recovery and crash-edge editor retention |
| Perform | Native renderer, bounded projections, reproducible stress receipts | Policy-equivalent end-to-end CLI latency and broader module-swap conformance |

The next high-value runtime work includes durable child continuation,
attachments and attributed change/test review. Those need exercised
host/module seams, not controls that translate silently into something else. The current
native client remains Ratatui; OpenTUI is a historical comparator and Textual a test harness.

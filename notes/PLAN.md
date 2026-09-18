# Work derived from current direction

Authority: [VISION](../docs/VISION.md) and the referenced DRAFT contracts.
This is a current work queue, not a delivery log or formal Converge verdict ledger.
The product has one canonical live-session format: the CLI project/session store.
Disposable test journals do not establish a migration or compatibility obligation.

| Item | Source promises | Work | Observable completion / falsifier | State |
|---|---|---|---|---|
| SHARED-01 | continuity.v1:1, continuity.v1:3, ecosystem.v1:1 | Canonical session return | Same-project CLI/TUI/CLI round trips retain ID and messages without import or replay | Implemented; actual entrypoint and native picker checks in ACCEPTANCE |
| SHARED-02 | continuity.v1:2, ecosystem.v1:2 | Shared configuration and display state | Names, unknown metadata, session settings and drafts survive; newer CLI history replaces stale display projections | Implemented within documented controls/accounting limits |
| READ-08 | presentation.v1:3, presentation.v1:6, presentation.v1:7 | Structural Markdown layout | Lists retain indentation; ATX/setext headings use typography without source delimiters at 40/80/175 columns, including disabled colour, streaming and exact copy | Implemented; terminal-cell style, source-copy and streaming checks pass |
| READ-09 | presentation.v1:3, interaction.v1:3 | Semantic links without URL clutter | Labels remain readable while the actual target/location remains inspectable and safely usable through terminals/tmux | Conservative duplicate-target suppression implemented; nonredundant targets remain visible without OSC links |
| SHARED-04 | presentation.v1:4, ecosystem.v1:2, ecosystem.v1:6 | Cross-client accounting and controls | Known CLI usage survives return without double-counting; pins/modes/goals/children retain supported ownership and state | Recorded accounting and current resume summary implemented; private-control interchange remains pending |
| RETURN-01 | interaction.v1:1, continuity.v1:3 | CLI return-list accuracy | Transcript-line counts are labelled messages; log-only directories do not masquerade as resumable sessions | Implemented and pinned; CLI PR346 merged into main after green CI |
| SHARED-03 | continuity.v1:1, continuity.v1:5, ecosystem.v1:5 | Writer ownership and interrupted/private state | Cooperative clients refuse simultaneous writes; crash recovery never invents tool outcomes | TUI stale-write detection implemented; close one client before opening the other; cooperative CLI lease/recovery pending |
| READY-05 | ecosystem.v1:6, performance.v1:1 | Representative ecosystem acceptance | Actual persistent-context entrypoint switching and policy-matched responsiveness have reproducible evidence | Module/store combinations pass; broader entrypoint/policy comparison remains |
| READY-06 | ecosystem.v1:6 | External integrations | Explicitly scoped provider/account/device checks establish real behavior | Paid calls, personal service writes and physical devices require a named test scope |

Use owned temporary homes and synthetic histories for execution tests. Personal
sessions may be inspected when requested, never silently reused as writable fixtures.
Native fixtures, real-module integration and live-provider evidence are distinct.
The next adoption boundary is cooperative writer ownership and private-state
interchange. Reading improvements and recorded accounting do not establish safe
simultaneous clients or restore controls that lack a common representation.

# Work derived from current direction

Authority: [VISION](../docs/VISION.md) and the referenced DRAFT contracts.
This is a current work queue, not a delivery log or formal Converge verdict ledger.
The product has one canonical live-session format: the CLI project/session store.
Disposable test journals do not establish a migration or compatibility obligation.

| Item | Source promises | Work | Observable completion / falsifier | State |
|---|---|---|---|---|
| SHARED-01 | continuity.v1:1, continuity.v1:3, ecosystem.v1:1 | Canonical session return | Same-project CLI/TUI/CLI round trips retain ID and messages without import or replay | Implemented; actual entrypoint and native picker checks in ACCEPTANCE |
| SHARED-02 | continuity.v1:2, ecosystem.v1:2 | Shared configuration and display state | Names, unknown metadata, session settings and drafts survive; newer CLI history replaces stale display projections | Implemented within documented controls/accounting limits |
| READ-08 | presentation.v1:3, presentation.v1:6, presentation.v1:7 | Structural Markdown layout | Nested and multiline lists retain hanging indentation and block spacing at 40/80/175 columns in streaming and final output | Next; source comparison and reproduction in MARKDOWN-GAPS |
| READ-09 | presentation.v1:3, interaction.v1:3 | Semantic links without URL clutter | Labels remain readable while the actual target/location remains inspectable and safely usable through terminals/tmux | Design from Codex capability-aware links; no blind destination hiding |
| SHARED-04 | presentation.v1:4, ecosystem.v1:2, ecosystem.v1:6 | Cross-client accounting and controls | Known CLI usage survives return without double-counting; pins/modes/goals/children retain supported ownership and state | Pending; session totals currently disclose unavailable earlier usage |
| SHARED-03 | continuity.v1:1, continuity.v1:5, ecosystem.v1:5 | Writer ownership and interrupted/private state | Cooperative clients refuse simultaneous writes; crash recovery never invents tool outcomes | TUI stale-write detection implemented; close one client before opening the other; cooperative CLI lease/recovery pending |
| READY-05 | ecosystem.v1:6, performance.v1:1 | Representative ecosystem acceptance | Actual persistent-context entrypoint switching and policy-matched responsiveness have reproducible evidence | Module/store combinations pass; broader entrypoint/policy comparison remains |
| READY-06 | ecosystem.v1:6 | External integrations | Explicitly scoped provider/account/device checks establish real behavior | Paid calls, personal service writes and physical devices require a named test scope |

Use owned temporary homes and synthetic histories for execution tests. Personal
sessions may be inspected when requested, never silently reused as writable fixtures.
Native fixtures, real-module integration and live-provider evidence are distinct.
The immediate UX priorities are Markdown structure, link presentation and continuity
of already-recorded usage; writer coordination protects against simultaneous clients
but does not replace those everyday adoption fixes.

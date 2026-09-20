# Work derived from current direction

Authority: [VISION](../docs/VISION.md) and the referenced DRAFT contracts.
This is a current work queue, not a delivery log or formal Converge verdict ledger.
The product has one canonical live-session format: the CLI project/session store.
Disposable test journals do not establish a migration or compatibility obligation.

| Item | Source promises | Work | Observable completion / falsifier | State |
|---|---|---|---|---|
| LIVE-01 | continuity.v1:6, session.v1:6, interaction.v1:1 | Reciprocal Foundation handoff | Busy sessions remain readable; explicit Continue here and graceful outbound release preserve draft/history; timeout/failure/races never steal ownership | Implemented and verified with Foundation PR399; upstream review and coordinated CLI/TUI dependency pins gate publication |
| LIVE-02 | continuity.v1:7, performance.v1:2, ecosystem.v1:5 | Settled idle release and fresh reacquisition | No release during execution/decisions/auxiliary work; old hosts retire before unlock; next explicit mutation reloads external changes | Implemented; conservative remount verified, same dependency gate as LIVE-01 |
| LIVE-03 | session.v1:3, session.v1:6, ecosystem.v1:3 | Optional upstream live runtime | Correlated generations and background delegates retain module choice, provenance and graceful/force cancellation | After ownership gates; upstream stop/provenance seams require verification |
| LIVE-04 | continuity.v1:3, presentation.v1:3, performance.v1:5 | Bounded external observation | Read-only refresh follows native revisions without replay, reprinting committed history or losing selection | After ownership gates; live attachment remains a separate protocol |
| READ-11 | presentation.v1:3, presentation.v1:5, performance.v1:5 | Bounded return and safe selection | Latest 100 historical items, explicit older/newer pages, draft/source unchanged; empty/hidden rows and stale anchors never crash Interact | Implemented; native mouse, resize, byte-limited page reversal and large-session entrypoint checks pass |
| SHARED-01 | continuity.v1:1, continuity.v1:3, ecosystem.v1:1 | Canonical session return | Same-project CLI/TUI/CLI round trips retain ID and messages without import or replay | Implemented; actual entrypoint and native picker checks in ACCEPTANCE |
| SHARED-02 | continuity.v1:2, ecosystem.v1:2 | Shared configuration and display state | Names, unknown metadata, session settings and drafts survive; newer CLI history replaces stale display projections | Implemented within documented controls/accounting limits |
| READ-08 | presentation.v1:3, presentation.v1:6, presentation.v1:7 | Structural Markdown layout | Lists retain indentation; ATX/setext headings use typography without source delimiters at 40/80/175 columns, including disabled colour, streaming and exact copy | Implemented; terminal-cell style, source-copy and streaming checks pass |
| READ-10 | presentation.v1:3, presentation.v1:6, presentation.v1:8 | Visible heading hierarchy | Cyan headings and underlined major sections stand apart without relying only on bold; captures reproduce text attributes and disclose reference fonts | Implemented; terminal-cell, reference-raster and actual VTE checks; source copy and dim thinking preserved |
| SCREEN-01 | presentation.v1:5, presentation.v1:6 | Cursor-owned startup and live padding | Top/middle/bottom launches add no artificial blank page to tmux history; resize/inspection/exit retain output once; silent cursor replies preserve input | Implemented; zero added gap at three launch positions, short/long/streaming tmux retention and resize checks pass |
| READ-09 | presentation.v1:3, interaction.v1:3 | Semantic links without URL clutter | Labels remain readable while the actual target/location remains inspectable and safely usable through terminals/tmux | Conservative duplicate-target suppression implemented; nonredundant targets remain visible without OSC links |
| SHARED-04 | presentation.v1:4, ecosystem.v1:2, ecosystem.v1:6 | Cross-client accounting and controls | Known CLI usage survives return without double-counting; pins/modes/goals/children retain supported ownership and state | Recorded accounting and current resume summary implemented; private-control interchange remains pending |
| RETURN-01 | interaction.v1:1, continuity.v1:3 | CLI return-list accuracy | Transcript-line counts are labelled messages; log-only directories do not masquerade as resumable sessions | Implemented and pinned; CLI PR346 merged into main after green CI |
| SHARED-03 | continuity.v1:1, continuity.v1:5, ecosystem.v1:5 | Foundation writer ownership and native history | Cooperating CLI/TUI/web writers contend on one lock; backups preserve complete messages and corrupt history never becomes empty | Implemented; actual CLI/TUI and real Unified storage-adapter gates pass; full web runtime remains separate |
| SHARED-05 | continuity.v1:3, presentation.v1:4, performance.v1:5 | Shared activity without duplicated history | Ordinary Activity combines scoped CI observations and canonical messages in memory; no private transcript journal or separate source chooser | Implemented; exact association, memory-only live refresh and ordinary terminal inspection pass |
| SHARED-07 | continuity.v1:1, continuity.v1:3, performance.v1:5 | Native history at real-session scale | Large transcripts and metadata resume through Foundation without import quotas, lossy provider-field restoration or duplicated journals; previews alone are bounded | Implemented; large synthetic native-entrypoint and unchanged-source open/close gates pass |
| SHARED-06 | ecosystem.v1:2, continuity.v1:2, session.v1:7 | Propose portable controls and recovery upstream | DRAFT Foundation proposal identifies data ownership, unsupported participants, no-replay boundaries and cross-client checks | Proposed in Foundation PR397; review/adapter implementation remain, no ratification or conformance claim |
| READY-05 | ecosystem.v1:6, performance.v1:1 | Representative ecosystem acceptance | Actual persistent-context entrypoint switching and policy-matched responsiveness have reproducible evidence | Module/store combinations pass; broader entrypoint/policy comparison remains |
| READY-06 | ecosystem.v1:6 | External integrations | Explicitly scoped provider/account/device checks establish real behavior | Paid calls, personal service writes and physical devices require a named test scope |

Use owned temporary homes and synthetic histories for execution tests. Personal
sessions may be inspected when requested, never silently reused as writable fixtures.
Native fixtures, real-module integration and live-provider evidence are distinct.
The manager owns dependency integration, current direction, cross-client/terminal gates
and reviewed publication. Parallel agents share this working copy with disjoint file
ownership; these are not Converge worktree lanes. Shared ownership/history adoption
uses existing APIs; portable-control design is proposed separately and does not imply
that current clients enforce new contracts or recover arbitrary private-module state.

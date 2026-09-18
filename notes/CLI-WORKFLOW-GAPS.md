# Everyday CLI gap analysis — 2026-09-16

## New priority — bidirectional native adoption (2026-09-18)

The steward supersedes the handoff-only disposition below: full CLI experience and
shared-data compatibility are the baseline. SHARED-01–04 in [PLAN](PLAN.md) own this
work. The first slice shares canonical project sessions, ordinary Resume, directory
recall/search and session-scoped settings. Native/private-control equivalence,
cooperative cross-client ownership and historical accounting remain explicit gaps.
Historical rows below do not certify those newly required round trips.

## Follow-up boundary — 2026-09-18

The historical table below describes the original gaps, not a current backlog.
PARITY-01–07 in [PLAN](PLAN.md) now maps the later implementation and verification:
goal breaker; loaded configuration controls and confirmed shared saves; argument
completion and all-provider diagnostics; legacy module output; cancellation-aware
child admission/process spawning and canonical continuation; confirmed context clear,
turn branches, private exports, direct tools and reversible conversation archival;
installed scripting and read-only shell completion.

Setup, bundle/module/source administration, routing, provider setup, directory and
notification configuration, update/reset, and canonical CLI session administration
remain explicit `amplifier-tui COMMAND` or `amplifier-tui cli …` handoff to pinned CLI
policy. They work on the CLI store, not the native store. This is supported entrypoint
compatibility, not a second native implementation of every wizard. Native ordinary
Resume stays directory-local; structured adoption is not original private-state resume.

Computer-use approval transport is merged upstream (PR 19, 2026-09-18).
Remaining verification boundaries: personal remote destinations/devices, real account login,
arbitrary private module state, and billed provider behavior are not certified by
offline fixtures. No speculative service/device dashboards were added. Exact failed-
then-corrected and final gate evidence belongs in [ACCEPTANCE](ACCEPTANCE.md).

## Original comparison

Source comparison against pinned amplifier-app-cli `f0ba883` and the current local
TUI implementation. No claim about a newer remote revision or universal ecosystem
compatibility. Personal transcript/configuration content is not a fixture or publication
artifact. Direction: interaction P4/P6, presentation P1/P4/P5, ecosystem P4/P6.

| Workflow | CLI / ecosystem source behavior | TUI gap and priority |
|---|---|---|
| Inspection without terminal cursor reports | CLI explicitly tests CPR-unsupported input; basic terminal input remains usable | Native startup has a fallback, but inspection calls Ratatui clear(), which queries the cursor before clearing. Fix first |
| Tool outcomes | Loop emits model-dumped results or falls back to strings; tools can return dictionaries, and hooks can serialize/truncate results | Root/child observers accept only dictionaries, producing unknown outcomes and empty previews. Normalize bounded recognized envelopes after policy hooks; preserve original evidence |
| Module-advertised commands | CommandProcessor obtains user-invocable skill aliases from discovery and refreshes misses; memory uses that skill mechanism | Host already supports skill aliases. Native action/Tab catalogs lack those aliases and stay at initial discovery. Fix generic discoverability, not memory-specific writes |
| Recipe discovery | Recipes `list` lists active sessions, not recipe files; execution takes an explicit path | Existing Recipes inspector shows historical calls only. Add separately labelled file discovery and an unsent review request; teach scope to runtime |
| Startup failures | CLI prints startup failures directly | Send/late draft refusal replaces the native failure explanation with a generic not-ready message. Keep failure visible and draft retained |
| Modes, provider selection and skills | CLI has argument dispatch, mode aliases/trailing prompts and provider scope controls | Native menus support mode/provider operations, but not all CLI argument forms. Do not claim arbitrary slash-command parity or silently drop arguments |
| Goal, configuration mutation, directory policy, clear/fork | CLI has dedicated semantics and persistence in CommandProcessor | Still needs deliberate native controls and lifecycle tests. Generic CLI handler reuse would introduce printing, destructive context edits or mismatched persistence |
| CLI continuity and authentication | CLI owns canonical session state and provider login flows | Text-reference import and existing credentials work; canonical private-state resume and interactive login remain separate work |
| Service observability | Memory/intelligence hooks can mount, inject, capture and dispatch independently | Loaded-module/status notices are not delivery receipts. End-to-end service testing must isolate external writes and prove the configured destination |

The first five rows describe the pre-change gaps addressed in this batch. No lower-priority row is declared complete
because a command name is recognized. Skill commands may invoke a model/tools after an
explicit Send; unsupported commands remain local refusals. Recipe selection is not
validation, execution or a promise that every discovered YAML file is a runnable recipe.

## Source anchors and remaining priorities

CLI `amplifier_app_cli/main.py`: `CommandProcessor.process_input`,
`_populate_skill_shortcuts`, `_load_skill`, `_handle_mode`, `_handle_provider`,
`_handle_goal`, `_clear_context`, `_fork_session`, `_handle_config_toggle` and
`_manage_allowed_dirs`. These separate prompt construction, module capability calls,
printed presentation and persistent configuration changes; copying the whole dispatcher
would not be a safe native integration. CLI CPR coverage lives in
`tests/test_interactive_slash_completion.py`.

Streaming loop `c458634`, `amplifier_module_loop_streaming/__init__.py`, serializes
non-model tool results with `str(result)` in both execution paths. Recipes `bf5f88c`,
`amplifier_module_tool_recipes/__init__.py:_list_sessions`, owns the active-run meaning.
Skills `f5b1bb1`, `SkillsDiscovery.get_shortcuts`, exposes cached user-invocable metadata;
`SkillsTool` resolves namespace sources lazily on the first provider request. Memory
`b0497fe`, `skills/memory/SKILL.md`, declares the user-invocable command and arguments.
Ratatui-core 0.1.2, `terminal/buffers.rs:Terminal::clear`, owns the cursor-query call.

The implemented path keeps those owners: module metadata supplies native command
choices and refreshes after turns, the pinned CLI supplies skill argument semantics,
and the recipe engine still owns validation/execution. A namespace skill not yet
resolved remains absent until module discovery; argument-sidecar completion is not
implemented. Browsing scans declared local recipe folders only, not a remote registry.
The recipe guidance hook is explicitly app-owned policy, injected only where the tool
is mounted. It does not guarantee model compliance or change recipe permissions.

The following priorities drove the subsequent [scoped control batch](evidence/cli-controls-validation.md):

1. Native goal lifecycle and deliberate configuration/directory controls, with saved
   scope, capability refusal and confirmation where effects require it. Complete CLI
   mode/provider argument forms without silently discarding trailing text.
2. Canonical CLI continuity and provider-owned interactive authentication. Historical
   text import is useful but cannot substitute for either.
3. Isolated memory read/write/injection and context-intelligence delivery receipts
   against the intended service. Loaded hooks and mounted tools are not that evidence.

See [validation](evidence/cli-workflows-validation.md) for tested scope and limits.

The subsequent batch adds durable streaming-loop goals, root tool/directory controls,
mode arguments/trailing prompts, provider commands, asynchronous module-owned login,
structured public CLI adoption and isolated memory/HTTP delivery tests. It does not
claim canonical original-identity/private-state resume, arbitrary live/global config,
real browser authorization or personal remote indexing. Those remain substantive
boundaries rather than another list of cosmetic polish tasks.

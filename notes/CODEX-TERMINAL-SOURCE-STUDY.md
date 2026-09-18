# Current Codex terminal source study

Inspected 2026-09-14 at upstream main
[`2f8603f07547247e698748884542ba60a157621c`](https://github.com/openai/codex/tree/2f8603f07547247e698748884542ba60a157621c),
confirmed against remote HEAD after fetching. The workspace now has a `codex`
submodule; the earlier supplied blueprint remains pinned to its historical source.
This is source analysis, not a run of that binary, an upstream test result, a
benchmark, or acceptance of our UI. No runtime behavior or contract is changed here.

## Action emphasis follow-up (2026-09-17)

Re-read the same local pin, not newly fetched HEAD. `tui/styles.md` distinguishes
primary/bold text, dim metadata and semantic accents. `exec_cell/render.rs` uses
Read/Search/List verbs, small outcome markers, shell highlighting and output limits
after wrapping. `history_cell/mcp.rs` separates cyan tool identity from dim arguments;
`multi_agents.rs` distinguishes agent identity and outcome. `history_cell/plans.rs`
emphasizes the active task over completed/pending entries. `status_indicator_widget.rs`
and `summary_shimmer.rs` animate the live label while measures stay steady.

READ-07 adapts that hierarchy, not Codex's exact colours: existing muxplex cyan
actions/completion, amber running/unknown, red negative states and muted evidence.
Structured spans survive width clipping and paint-time animation. A parent's success
never paints child errors cyan. Known tools get concise action names; unfamiliar tools
keep generic names and exact identity/arguments remain inspectable. Command previews
reuse the existing bounded highlighter, with eight wrapped result rows and explicit
full-evidence access. Active todo text is bold cyan; completed/pending remain muted.
No command regrouping/reparenting, execution changes or animation of committed history
is introduced. These are app presentation choices; source inspection alone is not a
performance or visual-quality claim. Verification lives in ACCEPTANCE.

## Ctrl-C follow-up (2026-09-17; recommendation, not adopted)

Re-inspected the same local source pin above, not newly fetched remote HEAD.
The [official command guide](https://learn.chatgpt.com/docs/developer-commands?surface=cli)
describes basic exit shortcuts; source defines the state-dependent precedence below.
This is source inspection, including upstream test cases, not an upstream test run.

| State | Codex at this pin | Current TUI / recommended change |
|---|---|---|
| Dialog, question or search active | Offer cancellation to that surface first; some approval views interrupt work | Current global quit runs before dialog handling. Route local cancellation first, preserving the main draft and respecting actual decision semantics. |
| Nonempty composer, idle or working | Clear into recallable history; stay open. This press does not also interrupt the turn. | Current shortcut quits. Adopt only with recoverable text, pending paste and attachment state; clearing text alone is insufficient. |
| Empty composer, cancellable work active | Interrupt work and pause an active goal; stay open | Current shortcut quits and shuts down the host. Route to the existing Stop operation; keep interrupted/uncertain outcomes honest. |
| Empty composer, idle | Shutdown-first quit | Same broad intent; retain our owned-process cleanup and native history. |
| Repeated press while work is still active | Another interrupt, not immediate forced exit | Keep a distinct explicit quit escape for an uncooperative host. Do not infer that repeated Ctrl-C grants destructive cancellation. |

`chatwidget/interaction.rs::handle_key_event` accepts Ctrl-C on **Press** only and
normalizes the letter's case. `on_ctrl_c` delegates to `bottom_pane::on_ctrl_c`
before checking work. That pane cancels local views/search before clearing a draft.
`chat_composer::clear_for_ctrl_c` flushes pending paste and records rich local history;
`review_mode.rs::ctrl_c_cleared_prompt_is_recoverable_via_history` tests text plus
image recovery. A separate persistent history entry carries text, not the whole
attachment state. Our selected-text Ctrl-C copy behavior should remain an explicit
exception, and native terminal copy must remain terminal-owned.

Crucially, `bottom_pane/mod.rs::DOUBLE_PRESS_QUIT_SHORTCUT_ENABLED` is **false**.
Nearby comments and unused arming paths still describe double-press behavior, so
they are not evidence that this build requires two presses to exit. Tests exercise
repeated interrupts without arming quit and Caps Lock handling.

Our raw-key handler currently quits on Ctrl-C/Ctrl-Q before local dialogs (except
selected-text copy); it also lacks the Ctrl-C Press-only/case-normalization guard.
An OS-delivered SIGINT is a separate shutdown path, not a raw composer key. Adoption
needs explicit startup/disconnection rules and real PTY tests for all table rows,
draft/image recovery, key repeats, Caps Lock and cooperative versus blocked work.
The startup transport repair does **not** change this keyboard policy.

Sources: [routing and interrupt/quit policy](https://github.com/openai/codex/blob/2f8603f07547247e698748884542ba60a157621c/codex-rs/tui/src/chatwidget/interaction.rs#L551),
[view/draft precedence](https://github.com/openai/codex/blob/2f8603f07547247e698748884542ba60a157621c/codex-rs/tui/src/bottom_pane/mod.rs#L862),
[disabled double-press experiment](https://github.com/openai/codex/blob/2f8603f07547247e698748884542ba60a157621c/codex-rs/tui/src/bottom_pane/mod.rs#L206),
[rich draft recovery](https://github.com/openai/codex/blob/2f8603f07547247e698748884542ba60a157621c/codex-rs/tui/src/bottom_pane/chat_composer.rs#L1756),
[regression cases](https://github.com/openai/codex/blob/2f8603f07547247e698748884542ba60a157621c/codex-rs/tui/src/chatwidget/tests/review_mode.rs#L1007).

## Finding: inline is the right category, not the complete implementation

Codex uses Ratatui 0.30.2, a pinned fork of Crossterm, and its own terminal driver
derived from Ratatui's `Terminal`. The ordinary conversation uses the primary screen.
An application-owned live viewport sits below transcript rows written into terminal
history. This is not a permanently fullscreen alternate-screen conversation, nor
just a conventional scrollable transcript widget.

The live viewport uses the available terminal width and its content's requested
height. Its initial anchor comes from the cursor position, so fresh startup does
**not** unconditionally clear the shell and claim a whole new screen. A source test
explicitly preserves shell text above the first viewport. The proposed fresh-screen
startup from our preceding discussion would be an Amplifier UX decision, not a
faithful copy of this Codex startup path. We have not established the exact version
or launch path behind the steward's observed Codex session.

Sources: [dependency declarations](https://github.com/openai/codex/blob/2f8603f07547247e698748884542ba60a157621c/codex-rs/Cargo.toml#L415),
[initialization](https://github.com/openai/codex/blob/2f8603f07547247e698748884542ba60a157621c/codex-rs/tui/src/tui.rs#L425),
[cursor-anchored terminal](https://github.com/openai/codex/blob/2f8603f07547247e698748884542ba60a157621c/codex-rs/tui/src/custom_terminal.rs#L180),
[first-viewport test](https://github.com/openai/codex/blob/2f8603f07547247e698748884542ba60a157621c/codex-rs/tui/src/tui.rs#L175).

## Implementation map and implications

Paths below are relative to `codex-rs/tui/src` at the pin above unless stated otherwise.

| Concern | Codex implementation | What it teaches this app |
|---|---|---|
| Initial responsiveness | `terminal_probe.rs`, `startup_draft.rs`: bounded startup probes (100 ms default), input replay after startup probing, editable but non-submitting provisional composer while setup runs | Show a useful draft before runtime readiness; protect its complete state through handoff. Do not confuse provider readiness with editor readiness. |
| Viewport geometry | `tui.rs::draw`, `draw_with_resize_reflow`; `chatwidget/rendering.rs`; `bottom_pane/chat_composer.rs::desired_height_with_textarea_right_reserve` | Size controls from draft, popup and footer content. Our `native.rs::paint_inline` reserves a fixed ten rows before live output/decisions; that is our layout policy, not an inline-terminal requirement. |
| Native history | `insert_history.rs`; `tui/scrollback.rs` | Write stable rows above the live viewport, reset scroll regions, and restore cursor bookkeeping. Standard insertion uses a restricted history scroll region and CRLF. Full-screen insertion clears stale controls before scrolling the primary screen. “FullScreen” here is an insertion strategy, not alternate-screen mode. |
| Terminal differences | `tui/scrollback.rs::detect` | Windows Terminal and Zellij receive distinct strategies. Comments identify terminals where scroll-up commands or partial scroll regions discard rows. Our primary-screen CRLF strategy already follows part of this principle; merely copying escape sequences is not a compatibility proof. |
| Streaming Markdown | `streaming/controller.rs`, `streaming/render.rs`, `streaming/table_holdback.rs` | Separate committed output from a mutable live tail. Tables must be held back when later rows can change column widths. Preserve source separately from display rows. Our journal already has stable-block/live-tail separation; compare edge cases before replacing it. |
| Temporary inspection | `tui.rs::enter_alt_screen`, `leave_alt_screen`; `app/event_dispatch.rs` diff and fullscreen-decision paths | Save/restore the inline viewport and invalidate the render baseline after returning. Alternate-screen permission is not proof that ordinary chat enters it. Not every Codex popup is fullscreen. |
| Exit | `app/startup.rs` end of `App::run`; `custom_terminal.rs::clear`; `tui.rs::restore_after_exit`; `app/exit_summary.rs` | Clear from the live viewport down, restore terminal modes/cursor, leave already-emitted transcript above it. Exit messaging distinguishes stopping an embedded runtime from disconnecting from persistent work. |
| Frame cost | `tui/frame_requester.rs`, `tui/frame_rate_limiter.rs`, `chatwidget/transcript.rs` | Coalesce redraw requests, cap notifications at 120 FPS, and cache active-cell layout. The cap is a scheduling constant, not measured user latency. Avoid rebuilding retained history on every keystroke. |
| Theme and density | `tui/styles.md`; `bottom_pane/footer.rs`; `bottom_pane/chat_composer.rs` | Prefer terminal-default primary text, dim secondary text and contextual hints. Our permanent mode/runtime/tab/navigation/action/status rows explain much of the dashboard-like density. Preserve required mode visibility while simplifying competing chrome. |
| Rich input | `bottom_pane/chat_composer.rs`, `chat_composer_history.rs`, `paste_burst.rs` | Model draft/history/popups/paste as explicit state. Persistent text history differs from full local draft history. Enter submission and Tab queueing are distinct from popup completion. Borrow the timing/state distinctions; do not silently replace our currently documented keybindings. |
| Execution boundary | `app_server_session.rs`; sibling crate `app-server-client/src/lib.rs` | A typed request/notification/server-request interface can support both in-process and remote clients. Modularity does not require a subprocess. Our Python ecosystem still needs an appropriate language boundary, and that choice needs measurement rather than inference from Codex. |

## Important exception: resize is not strictly append-only

Current Codex stores source-backed history cells and can rebuild terminal scrollback
after width changes or height growth. `transcript_reflow.rs` debounces resize work
for 75 ms. `app/resize_reflow.rs::clear_terminal_for_resize_replay` calls
`custom_terminal.rs::clear_scrollback_and_visible_screen_ansi` on the primary screen.
That function emits an explicit scrollback purge (`CSI 3 J`) and screen clear before
source-backed replay. Thread switching uses the purge helper too.

The implementation calls this Codex-owned history, but the escape sequence itself
does not distinguish prior shell output from application output. **Inference:** on
terminals honoring that purge, earlier shell history may be lost. Actual multiplexer
behavior needs testing. There are terminal-specific replay row caps and visible
truncation notices; the cap is display history, not canonical conversation deletion.

This is an adoption decision, not something to copy wholesale. Our presentation
P3/P5 promises native history without erasure/duplication on resize. We currently
leave committed terminal rows alone and reflow source in inspection. Any change to
that policy must reconcile the contract and test shell preservation, user selection,
tmux history, source fidelity and bounded replay together.

Sources: [resize replay](https://github.com/openai/codex/blob/2f8603f07547247e698748884542ba60a157621c/codex-rs/tui/src/app/resize_reflow.rs#L276),
[purge operation](https://github.com/openai/codex/blob/2f8603f07547247e698748884542ba60a157621c/codex-rs/tui/src/custom_terminal.rs#L552),
[reflow scheduling](https://github.com/openai/codex/blob/2f8603f07547247e698748884542ba60a157621c/codex-rs/tui/src/transcript_reflow.rs),
[row caps](https://github.com/openai/codex/blob/2f8603f07547247e698748884542ba60a157621c/codex-rs/tui/src/resize_reflow_cap.rs).

The app-server client also deliberately uses an **unbounded local consumer event
queue** so unread notifications do not block request responses. That is not a reason
to remove our journal-first bounded delivery contract. Learn the separation of
control and events while retaining explicit overload behavior and memory budgets.

## Recommended next slice, not implemented by this study

Work toward existing presentation P1/P3/P5/P6/P8, interaction P1/P2/P3, and performance
promises rather than starting another framework comparison:

1. Replace fixed-height everyday chrome with a content-sized composer and quiet,
   context-sensitive footer. Keep mode, waiting questions and queue/steer timing
   discoverable. Compare fresh startup and one short reply before adding features.
2. Add an editable startup draft with bounded capability probes and explicit runtime
   readiness. Transfer text, cursor, paste state and selection without submission.
3. Evaluate a more explicit terminal-owner abstraction against our current renderer,
   using Codex's insertion, cursor invalidation and terminal-specific tests as a map.
   Preserve existing history behavior unless a direction amendment is approved.
4. Expand acceptance to start at top/middle/bottom shell cursor positions, long
   output while copying, narrow/wide and height-only resize, temporary inspection,
   normal/error exit, and bottom-of-pane previews. Count missing/duplicate rows and
   verify pre-app shell markers as well as app text. Test silent/delayed terminal
   probe replies and typing during setup. Use actual tmux alongside an emulator.

Codex test examples inspected: `tui.rs` first-viewport and scheduled-insertion tests,
`tui/scrollback_tests.rs` native history and stale-composer tests, plus composer
snapshots. These were read, not executed. No Codex build, live model call, installed
Codex replacement, user conversation execution, or new terminal session was performed.
Before porting code, retain applicable upstream attribution: the repository has an
Apache-2.0 license and `custom_terminal.rs` carries its Ratatui-derived MIT notice.

## Authorized adoption follow-through

After this study, the steward authorized implementation. QUIET-01 / STARTUP-03 /
TERMINAL-02 in [PLAN](PLAN.md) now track the content-sized native surface, explicit
readiness, startup draft recovery and conservative cursor-query fallback. The historical
ten-row descriptions above describe the inspected baseline, not the new implementation.
The app's [presentation contract](../contracts/presentation.v1.md) was amended first.
Behavior and remaining limits belong in [acceptance evidence](ACCEPTANCE.md), not an
inferred upstream certification. The implementation is original app code; no upstream
terminal driver or execution policy was copied. The two-second fallback is intentionally
distinguished from Codex's 100 ms probe, and history-purging resize remains unadopted.

The steward subsequently requested full-height appearance and borderless input
(WORKSPACE-01). This is an explicit Amplifier adaptation, not a claim about every
Codex launch path. At the same source pin, `bottom_pane/chat_composer.rs` around
`render_with_mask` paints a styled borderless block, a single prompt marker and a
separate textarea; continuation rows have no box sides. Our open input omits even
that marker so selected draft rows contain only text and inset whitespace. A fresh
primary-screen page removes the need for a startup cursor query; resize queries
remain separate. Ordinary live renderer/runtime labels are removed, not fixture
warnings or inspectable composition facts.

# Current Codex terminal source study

Inspected 2026-09-14 at upstream main
[`2f8603f07547247e698748884542ba60a157621c`](https://github.com/openai/codex/tree/2f8603f07547247e698748884542ba60a157621c),
confirmed against remote HEAD after fetching. The workspace now has a `codex`
submodule; the earlier supplied blueprint remains pinned to its historical source.
This is source analysis, not a run of that binary, an upstream test result, a
benchmark, or acceptance of our UI. No runtime behavior or contract is changed here.

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

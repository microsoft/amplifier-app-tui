# Markdown and round-trip reading

## Source basis

Read-only comparison with Codex checkout
`2f8603f07547247e698748884542ba60a157621c` and this app's
`frontends/ratatui/src/markdown.rs`. Both use pulldown-cmark and Ratatui.
This is source-derived analysis, not a claim about the newest remote revision.
No user transcript, private URL or machine identity is a test fixture here.

Codex source anchors:

- `codex-rs/tui/src/markdown_render.rs`: IndentContext, start/end paragraph,
  start/end list/item, flush_current_line, heading and blockquote rendering.
- `codex-rs/tui/src/markdown_render/web_links.rs`: terminal capability policy;
  unknown terminals and multiplexers retain visible destinations.
- `codex-rs/tui/src/markdown_render/local_links.rs`: file-label/location handling.
- `codex-rs/tui/src/markdown_render/streaming.rs` and
  `markdown_stream.rs`: stable incremental rendering.
- `markdown_render_tests.rs` and snapshots: multiline findings, code inside
  lists, mixed URLs, local references and narrow tables.

## Confirmed gaps

| Area | Current TUI behavior | Required direction |
|---|---|---|
| Wrapped lists | Item marker is drawn once; generic reflow wraps continuation rows at column zero | Carry initial/subsequent indentation with each block; continuation text aligns with its item, not the terminal edge |
| Nested and loose lists | List depth only indents markers; paragraph endings inside lists lose block spacing | Preserve item/paragraph boundaries and a single deliberate separator; no blank line for every tight-list row |
| Following sections | List end only pops the counter; the next heading/prose can attach directly to the list | Block-aware spacing before the next section |
| Blockquotes | Quote prefix is inserted at paragraph start, not every wrapped line | Carry quote prefix through wrapped lines and nested blocks |
| Headings | All levels share the same bold style | Distinct accessible hierarchy without relying solely on colour |
| Links | Every destination is appended, even when redundant; long file-view URLs dominate layout | Preserve target semantics; prefer concise file references, and label-only web links only with usable hyperlink support |
| Streaming | Stable-prefix emission and final reflow can see different structural boundaries | Test chunk splits through list items, links, tables and fenced blocks; committed output must neither duplicate nor lose structure |

Already implemented: emphasis/strong/strikethrough, inline and fenced code, task
markers, syntax colour, width-aware tables and narrow key/value fallbacks. They still
need adversarial mixed-block tests; parser support alone is not layout parity.

Do not simply hide all URLs: Codex deliberately keeps them visible in unknown terminals
and tmux/screen. Our renderer currently has no OSC hyperlink transport. Resolve that
capability and retain inspect/copy access before discarding visible targets. Keep copied
Markdown/code unchanged and keep untrusted escape sequences inert.

## Session observations and decisions

The observed CLI → TUI → CLI use retains identity and both user turns. Different
history projections are expected: CLI resume shows conversation text while TUI also
shows compact captured tool calls. Historical thinking and usage absent from the
canonical transcript must not be synthesized from the response or a guessed cost.

The pinned CLI's `commands/session.py:_get_session_display_info` counts transcript lines
and the resume menu labels that value as turns. Tool messages and injected context
are included, so the label does not mean user turns. A correction belongs in the
CLI; the TUI must not change canonical messages to make that number smaller.

Priorities: fix structural Markdown first, design conservative link presentation,
then import authoritative usage receipts without double counting. Retain the explicit
close-one-client-before-opening-the-other rule while cooperative writer safety is
implemented. Full private controls and crash recovery remain separate acceptance gates.

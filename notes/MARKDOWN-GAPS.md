# Markdown and round-trip reading

## Source basis

Read-only comparison with Codex checkout
`2f8603f07547247e698748884542ba60a157621c` and this app's
`frontends/ratatui/src/markdown.rs`. Both use pulldown-cmark and Ratatui.
This is source-derived analysis, not a claim about the newest remote revision.
No user transcript, private URL or machine identity is a test fixture here.
Codex retains heading hash markers in its display. This TUI deliberately uses
typography instead, following its presentation contract; shared parser choice
does not require identical reading policy.

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

## Current implementation and limits

| Area | Current TUI behavior | Verification / remaining boundary |
|---|---|---|
| Wrapped lists | Structural initial/continuation prefixes align wrapped rows with each item's text column | 40/80/175-column tests include nested items and changing number widths |
| Nested and loose lists | Paragraph boundaries retain deliberate spacing; tight list rows remain compact | Mixed lists, continuation paragraphs, code and tables retain container indentation |
| Following sections | A single blank row separates the next block | Headings do not attach directly to preceding list text |
| Blockquotes | Every wrapped content row retains its quote prefix, including nested blocks | Quote scope ends before following ordinary prose |
| Headings | ATX and setext use distinct bold/underline/italic styles and block spacing without source delimiters | Styles survive wrapping and NO_COLOR; escaped hashes and code stay literal; source copy retains delimiters |
| Links | Exact label/destination duplicates display once; other destinations remain visible | No OSC hyperlink transport; long nonredundant URLs remain intentionally visible in tmux/unknown terminals |
| Streaming | The journal's incremental styled output matches completed structural rendering | Every-character splits through lists, links, tables and fences at 40/80/175 columns |

Emphasis/strong/strikethrough, inline and fenced code, task markers, syntax colour,
width-aware tables and narrow key/value fallbacks remain supported. Native tests
verify exact source copying and unsent-draft retention independently of layout.

Do not simply hide all URLs: Codex deliberately keeps them visible in unknown terminals
and tmux/screen. Our renderer currently has no OSC hyperlink transport. Resolve that
capability and retain inspect/copy access before discarding visible targets. Keep copied
Markdown/code unchanged and keep untrusted escape sequences inert, including controls
decoded from HTML entities by the Markdown parser.

## Session observations and decisions

The observed CLI → TUI → CLI use retains identity and both user turns. Different
history projections are expected: CLI resume shows conversation text while TUI also
shows compact captured tool calls. Historical thinking and usage absent from the
canonical transcript must not be synthesized from the response or a guessed cost.

CLI return lists count nonblank transcript messages and label them messages, including
tool messages and injected context. Log-only directories are not resume candidates;
their diagnostic files remain untouched. Canonical messages are never rewritten to
make a display count smaller.

Historical usage comes from attributed logging receipts plus native observations,
joined only by kernel event identity. It contributes to Session, never the next Turn;
missing or uncorrelated sources remain explicit gaps. Earlier per-call evidence is
inspectable in Activity without flooding the root conversation.
A derived On resume summary shows the reconciled session total separately from
historical turn footers. It does not rewrite receipts or create new usage.
Retain the explicit close-one-client-before-opening-the-other rule. Full private
controls and crash recovery remain separate acceptance gates.

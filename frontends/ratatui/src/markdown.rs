//! Source-only Markdown projection. No HTML execution, network fetches or OSC links.
use super::*;
use pulldown_cmark::{CodeBlockKind, Event as Md, Options, Parser, Tag, TagEnd};
use unicode_segmentation::UnicodeSegmentation;
use unicode_width::UnicodeWidthStr;

pub fn reflow(lines: Vec<Line<'static>>, width: usize) -> Vec<Line<'static>> {
    let width = width.max(1);
    let mut result = Vec::new();
    for line in lines {
        let mut cells: Vec<(String, Style)> = Vec::new();
        let mut used = 0;
        for span in line.spans {
            let style = line.style.patch(span.style);
            for cell in span.content.graphemes(true) {
                let size = cell.width();
                if used + size > width && !cells.is_empty() {
                    let split = cells
                        .iter()
                        .rposition(|(s, _)| s == " ")
                        .filter(|i| *i > cells.len() / 3)
                        .map(|i| i + 1)
                        .unwrap_or(cells.len());
                    let tail = cells.split_off(split);
                    result.push(make_line(cells));
                    cells = tail;
                    used = cells.iter().map(|(s, _)| s.width()).sum();
                }
                cells.push((cell.to_string(), style));
                used += size;
            }
        }
        result.push(make_line(cells));
    }
    result
}

fn make_line(cells: Vec<(String, Style)>) -> Line<'static> {
    let mut spans: Vec<Span<'static>> = Vec::new();
    for (cell, style) in cells {
        if let Some(last) = spans.last_mut()
            && last.style == style
        {
            last.content.to_mut().push_str(&cell);
        } else {
            spans.push(Span::styled(cell, style));
        }
    }
    Line::from(spans)
}

pub fn render(source: &str, width: usize) -> Vec<Line<'static>> {
    render_code(source, width, true)
}

pub fn render_live(source: &str, width: usize) -> Vec<Line<'static>> {
    render_code(source, width, false)
}

pub fn render_secondary(source: &str, width: usize) -> Vec<Line<'static>> {
    let mut lines = render(source, width);
    for line in &mut lines {
        line.style = line.style.fg(palette().muted);
        for span in &mut line.spans {
            span.style = span.style.fg(palette().muted);
        }
    }
    lines
}

// Prefixes belong to structural containers, not physical source lines. Every
// wrapped row keeps its quote scope and aligns with the item's text column.
#[derive(Default)]
struct Layout {
    lines: Vec<Line<'static>>,
    current: Vec<Span<'static>>,
    prefixes: Vec<(String, String, bool)>,
    width: usize,
}

impl Layout {
    fn prefix(&self, first: bool) -> Vec<Span<'static>> {
        let mut left = self.width.saturating_sub(1);
        self.prefixes
            .iter()
            .map(|(initial, subsequent, used)| {
                let value = if first && !used { initial } else { subsequent };
                let text: String = value
                    .graphemes(true)
                    .take_while(|g| {
                        if g.width() > left {
                            return false;
                        }
                        left -= g.width();
                        true
                    })
                    .collect();
                Span::styled(text, Style::default().fg(palette().muted))
            })
            .collect()
    }

    fn available(&self) -> usize {
        self.width
            .saturating_sub(self.prefix(true).iter().map(Span::width).sum())
            .max(1)
    }

    fn flush(&mut self) {
        if self.current.is_empty() {
            return;
        }
        let body = Line::from(std::mem::take(&mut self.current));
        for (i, line) in reflow(vec![body], self.available()).into_iter().enumerate() {
            let mut spans = self.prefix(i == 0);
            spans.extend(line.spans);
            self.lines.push(Line::from(spans));
        }
        for (_, _, used) in &mut self.prefixes {
            *used = true;
        }
    }

    fn blank(&mut self) {
        self.flush();
        if self.lines.last().is_some_and(|line| line.width() != 0) {
            self.lines.push(Line::default());
        }
    }

    fn push_line(&mut self, line: Line<'static>) {
        self.current = line
            .spans
            .into_iter()
            .map(|mut span| {
                span.style = line.style.patch(span.style);
                span
            })
            .collect();
        if self.current.is_empty() {
            self.current.push(Span::raw(""));
        }
        self.flush();
    }
}

fn render_code(source: &str, width: usize, colour: bool) -> Vec<Line<'static>> {
    let source = safe(source);
    let mut layout = Layout {
        width: width.max(1),
        ..Layout::default()
    };
    let mut styles = vec![Style::default().fg(palette().ink)];
    let mut lists: Vec<Option<u64>> = Vec::new();
    let mut loose_lists = Vec::new();
    let mut item_depths = Vec::new();
    let mut links: Vec<(String, String)> = Vec::new();
    let mut table: Option<tables::Table> = None;
    let mut code: Option<(String, String)> = None;
    let mut colour_budget = syntax::MAX_BYTES;
    for event in Parser::new_ext(
        &source,
        Options::ENABLE_STRIKETHROUGH | Options::ENABLE_TABLES | Options::ENABLE_TASKLISTS,
    ) {
        let style = *styles.last().unwrap();
        match event {
            Md::Start(tag) => {
                let next = match &tag {
                    Tag::Heading { level, .. } => {
                        style.fg(palette().ink).add_modifier(match level {
                            pulldown_cmark::HeadingLevel::H1 => {
                                Modifier::BOLD | Modifier::UNDERLINED
                            }
                            pulldown_cmark::HeadingLevel::H2 => Modifier::BOLD,
                            pulldown_cmark::HeadingLevel::H3 => Modifier::BOLD | Modifier::ITALIC,
                            pulldown_cmark::HeadingLevel::H4 => Modifier::UNDERLINED,
                            pulldown_cmark::HeadingLevel::H5 => Modifier::ITALIC,
                            pulldown_cmark::HeadingLevel::H6 => {
                                Modifier::ITALIC | Modifier::UNDERLINED
                            }
                        })
                    }
                    Tag::Strong | Tag::TableHead => style.add_modifier(Modifier::BOLD),
                    Tag::Emphasis => style.add_modifier(Modifier::ITALIC),
                    Tag::Strikethrough => style.add_modifier(Modifier::CROSSED_OUT),
                    Tag::CodeBlock(_) => style.fg(palette().amber).bg(palette().panel),
                    Tag::Link { .. } => {
                        style.fg(palette().green).add_modifier(Modifier::UNDERLINED)
                    }
                    _ => style,
                };
                match tag {
                    Tag::Table(alignments) => {
                        layout.flush();
                        table = Some(tables::Table {
                            alignments,
                            rows: vec![],
                        });
                    }
                    // ATX and setext share typography; source delimiters belong
                    // only in source inspection/copy, not the reading view.
                    Tag::Heading { .. } => layout.blank(),
                    Tag::Paragraph => {
                        if item_depths.last() == Some(&styles.len())
                            && let Some(loose) = loose_lists.last_mut()
                        {
                            *loose = true;
                        }
                        if layout.prefixes.last().is_none_or(|(_, _, used)| *used) {
                            layout.blank();
                        }
                    }
                    Tag::BlockQuote(_) => {
                        layout.flush();
                        layout.prefixes.push(("│ ".into(), "│ ".into(), false));
                    }
                    Tag::List(start) => {
                        if lists.is_empty() {
                            layout.blank();
                        } else {
                            layout.flush();
                        }
                        lists.push(start);
                        loose_lists.push(false);
                    }
                    Tag::Item => {
                        layout.flush();
                        let marker = match lists.last_mut() {
                            Some(Some(n)) => {
                                let s = format!("{n}. ");
                                *n += 1;
                                s
                            }
                            _ => "• ".to_string(),
                        };
                        let subsequent = " ".repeat(marker.width());
                        layout.prefixes.push((marker, subsequent, false));
                        item_depths.push(styles.len() + 1);
                    }
                    Tag::CodeBlock(kind) => {
                        layout.flush();
                        let language = match kind {
                            CodeBlockKind::Fenced(s) => s.to_string(),
                            _ => String::new(),
                        };
                        layout.push_line(Line::styled(
                            format!("── {language}"),
                            Style::default().fg(palette().muted),
                        ));
                        code = Some((language, String::new()));
                    }
                    Tag::TableRow | Tag::TableHead => {
                        layout.flush();
                        if let Some(table) = &mut table {
                            table.rows.push(vec![]);
                        }
                    }
                    Tag::Link { dest_url, .. } | Tag::Image { dest_url, .. } => {
                        links.push((safe(&dest_url), String::new()));
                    }
                    _ => (),
                }
                styles.push(next);
            }
            Md::End(tag) => {
                styles.pop();
                match tag {
                    TagEnd::CodeBlock => {
                        if let Some((language, source)) = code.take() {
                            let lines = if colour {
                                syntax::lines(&source, &language, &mut colour_budget)
                            } else {
                                syntax::plain(&source)
                            };
                            for line in lines {
                                layout.push_line(line);
                            }
                        }
                        layout.blank();
                    }
                    TagEnd::Table => {
                        if let Some(table) = table.take() {
                            for line in table.render(layout.available()) {
                                layout.push_line(line);
                            }
                        }
                        layout.blank();
                    }
                    TagEnd::Paragraph | TagEnd::Heading(_) | TagEnd::HtmlBlock => {
                        layout.blank();
                    }
                    TagEnd::Item => {
                        layout.flush();
                        if loose_lists.last() == Some(&true) {
                            layout.blank();
                        }
                        layout.prefixes.pop();
                        item_depths.pop();
                    }
                    TagEnd::TableRow | TagEnd::TableHead => layout.flush(),
                    TagEnd::TableCell => {
                        if let Some(row) = table.as_mut().and_then(|t| t.rows.last_mut()) {
                            row.push(Line::from(std::mem::take(&mut layout.current)));
                        }
                    }
                    TagEnd::List(_) => {
                        lists.pop();
                        loose_lists.pop();
                        if lists.is_empty() {
                            layout.blank();
                        }
                    }
                    TagEnd::BlockQuote(_) => {
                        layout.flush();
                        layout.prefixes.pop();
                        layout.blank();
                    }
                    TagEnd::Link | TagEnd::Image => {
                        if let Some((url, label)) = links.pop()
                            && url != label
                        {
                            // No OSC transport: tmux/unknown terminals still need
                            // the destination. Autolinks and exact path labels do not
                            // need a second identical target. Never rewrite source.
                            layout.current.push(Span::styled(
                                format!(" ({url})"),
                                Style::default().fg(palette().muted),
                            ));
                        }
                    }
                    _ => (),
                }
            }
            Md::Text(value) | Md::Html(value) | Md::InlineHtml(value) => {
                // Entity decoding happens in the parser, after source sanitizing.
                // Decoded terminal controls must stay inert too.
                let value = safe(&value);
                if let Some((_, source)) = &mut code {
                    source.push_str(&value);
                    continue;
                }
                for (_, label) in &mut links {
                    label.push_str(&value);
                }
                for (i, part) in value.split('\n').enumerate() {
                    if i > 0 {
                        layout.flush();
                    }
                    if !part.is_empty() {
                        layout.current.push(Span::styled(part.to_string(), style));
                    }
                }
            }
            Md::Code(value) => {
                let value = safe(&value);
                for (_, label) in &mut links {
                    label.push_str(&value);
                }
                layout.current.push(Span::styled(
                    value.to_string(),
                    style.fg(palette().amber).bg(palette().panel),
                ));
            }
            Md::SoftBreak => {
                for (_, label) in &mut links {
                    label.push(' ');
                }
                layout.current.push(Span::styled(" ", style));
            }
            Md::HardBreak => layout.flush(),
            Md::Rule => {
                layout.blank();
                layout.push_line(Line::styled(
                    "─".repeat(layout.available()),
                    Style::default().fg(palette().line),
                ));
                layout.blank();
            }
            Md::TaskListMarker(done) => layout.current.push(Span::styled(
                if done { "☑ " } else { "☐ " },
                style.fg(palette().green),
            )),
            _ => (),
        }
    }
    layout.flush();
    layout.lines
}

#[cfg(test)]
mod tests {
    use super::*;

    fn text(source: &str, width: usize) -> Vec<String> {
        render(source, width)
            .iter()
            .map(ToString::to_string)
            .collect()
    }

    #[test]
    fn wrapped_lists_keep_item_columns_and_loose_paragraphs() {
        for width in [40, 80, 175] {
            let words = "wrapped content ".repeat(20);
            let source = format!(
                "9. **First** {words}\n   - Nested {words}\n10. Second\n\n    Another paragraph\n\n## Next section\n\nAfter list."
            );
            let lines = text(&source, width);
            let mut in_nested = false;
            for line in &lines {
                assert!(line.width() <= width, "{line:?}");
                if line.contains("• Nested") {
                    in_nested = true;
                }
                if line.starts_with("10.") {
                    in_nested = false;
                }
                if line.contains("wrapped") && !line.contains("First") && !line.contains("Nested") {
                    assert!(
                        line.starts_with(if in_nested { "     " } else { "   " }),
                        "{line:?}"
                    );
                }
            }
            let paragraph = lines
                .iter()
                .position(|l| l.contains("Another paragraph"))
                .unwrap();
            assert_eq!(lines[paragraph], "    Another paragraph");
            assert!(lines[paragraph - 1].is_empty());
            let heading = lines
                .iter()
                .position(|l| l.contains("Next section"))
                .unwrap();
            assert!(lines[heading - 1].is_empty());
            assert!(lines[heading + 1].is_empty());
            assert_eq!(
                text("- One\n- Two\n- Three", width),
                ["• One", "• Two", "• Three", ""]
            );
        }
    }

    #[test]
    fn quotes_code_and_tables_remain_inside_their_containers() {
        let source = "1. List\n\n   > Quoted words that must wrap and stay visibly inside this quote with enough words.\n   >\n   > - Quoted list item with enough words to wrap onto a second or third row.\n\n   ```rs\n   let preserved = \"界\";\n     indented();\n   ```\n\n   | Name | Value |\n   |---|---|\n   | A | B |\n\n   Following paragraph.\n\nOutside.";
        let lines = text(source, 40);
        assert!(lines.iter().any(|l| l.starts_with("   │ • Quoted list")));
        assert!(lines.iter().any(|l| l.starts_with("   │   ")), "{lines:#?}");
        assert!(lines.iter().any(|l| l == "   let preserved = \"界\";"));
        assert!(lines.iter().any(|l| l == "     indented();"));
        assert!(lines.iter().any(|l| l.starts_with("   ┌")));
        assert!(lines.iter().any(|l| l == "   Following paragraph."));
        assert!(lines.iter().any(|l| l == "Outside."));
        assert!(lines.iter().all(|l| l.width() <= 40));
    }

    #[test]
    fn links_only_omit_redundant_targets_and_headings_keep_hierarchy() {
        let source = "# Title\n\n## Section\n\n### Detail\n\n<https://example.test/a> [https://example.test/b](https://example.test/b) [README](docs/README.md#L12) [`src/lib.rs`](src/lib.rs)";
        let value = text(source, 175).join("\n");
        assert_eq!(value.matches("https://example.test/a").count(), 1);
        assert_eq!(value.matches("https://example.test/b").count(), 1);
        assert_eq!(value.matches("src/lib.rs").count(), 1);
        assert!(value.contains("README (docs/README.md#L12)"));
        for heading in ["Title", "Section", "Detail"] {
            assert!(value.lines().any(|line| line == heading));
        }
        assert_eq!(render_live(source, 40), render(source, 40));
    }

    #[test]
    fn heading_typography_survives_wrapping_without_source_delimiters() {
        let styles = [
            Modifier::BOLD | Modifier::UNDERLINED,
            Modifier::BOLD,
            Modifier::BOLD | Modifier::ITALIC,
            Modifier::UNDERLINED,
            Modifier::ITALIC,
            Modifier::ITALIC | Modifier::UNDERLINED,
        ];
        for width in [40, 80, 175] {
            for (level, modifier) in styles.into_iter().enumerate() {
                let title =
                    "A heading with enough words to wrap and retain its typography ".repeat(4);
                let atx = format!("{} {} ###", "#".repeat(level + 1), title.trim());
                let lines = render(&atx, width);
                assert!(lines.iter().all(|line| line.width() <= width));
                for span in lines.iter().flat_map(|line| &line.spans) {
                    assert!(!span.content.contains('#'));
                    assert_eq!(span.style.add_modifier, modifier);
                }
                assert_eq!(render_live(&atx, width), lines);
                if level < 2 {
                    let setext = format!(
                        "{}\n{}",
                        title.trim(),
                        if level == 0 { "===" } else { "---" }
                    );
                    assert_eq!(render(&setext, width), lines);
                }
            }
        }
        let literal = text("\\# Literal\n\n`## inline`\n\n```text\n### code\n```", 80);
        for expected in ["# Literal", "## inline", "### code"] {
            assert!(literal.iter().any(|line| line == expected), "{literal:?}");
        }
    }

    #[test]
    fn soft_breaks_inherit_inline_and_setext_heading_styles() {
        for source in ["**first\nsecond**", "first\nsecond\n---"] {
            let lines = render(source, 80);
            assert_eq!(lines[0].to_string(), "first second");
            assert!(
                lines[0]
                    .spans
                    .iter()
                    .all(|span| span.style.add_modifier.contains(Modifier::BOLD))
            );
        }
    }

    #[test]
    fn secondary_markdown_never_uses_conversation_white_or_syntax_colours() {
        let source = "# Thought\n\n**consider** `code` [reference](https://example.test)\n\n```rs\nlet x = 1;\n```";
        let lines = render_secondary(source, 80);
        assert!(
            lines
                .iter()
                .all(|line| line.style.fg == Some(palette().muted))
        );
        assert!(
            lines
                .iter()
                .flat_map(|line| &line.spans)
                .all(|span| span.style.fg == Some(palette().muted))
        );
        assert!(
            lines
                .iter()
                .flat_map(|line| &line.spans)
                .any(|span| span.style.add_modifier.contains(Modifier::BOLD))
        );
        assert!(
            lines
                .iter()
                .any(|line| line.to_string().contains("let x = 1;"))
        );
    }
    #[test]
    fn table_columns_align_wrap_and_retain_inline_styles() {
        let source = "| Name | Count | Note |\n| :--- | ---: | :---: |\n| **界** | 12 | several words in this cell |\n| Beta | 3 | `code` |";
        for width in [32, 45, 80, 160] {
            let lines = render(source, width);
            assert!(lines.iter().all(|line| line.width() <= width));
            let rows: Vec<_> = lines
                .iter()
                .filter(|l| l.to_string().starts_with('│'))
                .collect();
            assert!(rows.len() >= 3);
            assert!(rows.iter().all(|line| line.width() == rows[0].width()));
            assert!(
                rows.iter()
                    .flat_map(|line| &line.spans)
                    .any(|s| s.content.contains('界')
                        && s.style.add_modifier.contains(Modifier::BOLD))
            );
            assert!(
                rows.iter()
                    .flat_map(|line| &line.spans)
                    .any(|s| s.content == "code" && s.style.fg == Some(palette().amber))
            );
        }
    }
    #[test]
    fn narrow_tables_keep_labels_and_all_cells() {
        let lines = render(
            "| Name | Value |\n| --- | --- |\n| Alpha | 12 |\n| Beta | 34 |",
            16,
        );
        let text = lines
            .iter()
            .map(ToString::to_string)
            .collect::<Vec<_>>()
            .join("\n");
        for expected in ["Name:", "Value:", "Alpha", "Beta", "12", "34"] {
            assert!(text.contains(expected), "{text}");
        }
        assert!(lines.iter().all(|line| line.width() <= 16));
    }
    #[test]
    fn table_end_restores_following_prose_and_multiple_tables() {
        let lines = render(
            "| A | B |\n|---|---|\n| x | y |\n\nafter\n\n| C | D |\n|---|---|\n| z | q |",
            80,
        );
        let text = lines
            .iter()
            .map(ToString::to_string)
            .collect::<Vec<_>>()
            .join("\n");
        assert_eq!(text.matches('┌').count(), 2);
        assert!(text.contains("after"));
        assert_eq!(text.matches('x').count(), 1);
        assert_eq!(text.matches('z').count(), 1);
    }
    #[test]
    fn markdown_styles_preserve_code_links_and_source() {
        let source = "# Heading\n\n**bold** and `code` [link](https://example.test)\n\n- one\n- two\n\n```rs\nlet x = 1;\n```";
        let lines = render(source, 80);
        let text = lines
            .iter()
            .map(ToString::to_string)
            .collect::<Vec<_>>()
            .join("\n");
        assert!(!text.contains("**"));
        assert!(text.contains("• one"));
        assert!(text.contains("https://example.test"));
        assert!(text.contains("let x = 1;"));
        assert!(
            lines
                .iter()
                .flat_map(|l| &l.spans)
                .any(|s| s.style.add_modifier.contains(Modifier::BOLD))
        );
        assert!(source.contains("**bold**"));
    }
    #[test]
    fn graphemes_and_terminal_controls() {
        let lines = render("界e\u{301}🦀abc\x1b[31m", 4);
        assert!(lines.iter().all(|l| l.width() <= 4));
        assert!(!lines.iter().any(|l| l.to_string().contains('\x1b')));
        assert!(lines.iter().any(|l| l.to_string().contains("e\u{301}")));
        for source in ["&#27;[31m", "[label](x&#27;[31m)"] {
            assert!(!text(source, 40).join("\n").contains('\x1b'));
        }
    }
}

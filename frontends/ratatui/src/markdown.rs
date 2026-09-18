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

fn render_code(source: &str, width: usize, colour: bool) -> Vec<Line<'static>> {
    let source = safe(source);
    let mut lines = Vec::new();
    let mut current: Vec<Span<'static>> = Vec::new();
    let mut styles = vec![Style::default().fg(palette().ink)];
    let mut lists: Vec<Option<u64>> = Vec::new();
    let mut links = Vec::new();
    let mut quote = 0;
    let mut table: Option<tables::Table> = None;
    let mut code: Option<(String, String)> = None;
    let mut colour_budget = syntax::MAX_BYTES;
    let flush = |lines: &mut Vec<Line<'static>>, current: &mut Vec<Span<'static>>| {
        if !current.is_empty() {
            lines.push(Line::from(std::mem::take(current)));
        }
    };
    for event in Parser::new_ext(
        &source,
        Options::ENABLE_STRIKETHROUGH | Options::ENABLE_TABLES | Options::ENABLE_TASKLISTS,
    ) {
        let style = *styles.last().unwrap();
        match event {
            Md::Start(tag) => {
                let next = match &tag {
                    Tag::Heading { .. } => style.fg(palette().ink).add_modifier(Modifier::BOLD),
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
                        flush(&mut lines, &mut current);
                        table = Some(tables::Table {
                            alignments,
                            rows: vec![],
                        });
                    }
                    Tag::Heading { .. } | Tag::Paragraph => {
                        // A loose list paragraph starts after its already drawn
                        // marker; don't strand the bullet on a line of its own.
                        if lists.is_empty() {
                            flush(&mut lines, &mut current);
                        }
                        if quote > 0 {
                            current.push(Span::styled(
                                "│ ".repeat(quote),
                                Style::default().fg(palette().muted),
                            ));
                        }
                    }
                    Tag::BlockQuote(_) => {
                        quote += 1;
                    }
                    Tag::List(start) => {
                        lists.push(start);
                    }
                    Tag::Item => {
                        flush(&mut lines, &mut current);
                        let indent = "  ".repeat(lists.len().saturating_sub(1));
                        let marker = match lists.last_mut() {
                            Some(Some(n)) => {
                                let s = format!("{n}. ");
                                *n += 1;
                                s
                            }
                            _ => "• ".to_string(),
                        };
                        current.push(Span::styled(
                            format!("{indent}{marker}"),
                            Style::default().fg(palette().green),
                        ));
                    }
                    Tag::CodeBlock(kind) => {
                        flush(&mut lines, &mut current);
                        let language = match kind {
                            CodeBlockKind::Fenced(s) => s.to_string(),
                            _ => String::new(),
                        };
                        lines.push(Line::styled(
                            format!("── {language}"),
                            Style::default().fg(palette().muted),
                        ));
                        code = Some((language, String::new()));
                    }
                    Tag::TableRow | Tag::TableHead => {
                        flush(&mut lines, &mut current);
                        if let Some(table) = &mut table {
                            table.rows.push(vec![]);
                        }
                    }
                    Tag::Link { dest_url, .. } | Tag::Image { dest_url, .. } => {
                        links.push(dest_url.to_string());
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
                            lines.extend(if colour {
                                syntax::lines(&source, &language, &mut colour_budget)
                            } else {
                                syntax::plain(&source)
                            });
                        }
                        if lists.is_empty() {
                            lines.push(Line::default());
                        }
                    }
                    TagEnd::Table => {
                        if let Some(table) = table.take() {
                            lines.extend(table.render(width));
                        }
                        lines.push(Line::default());
                    }
                    TagEnd::Paragraph | TagEnd::Heading(_) | TagEnd::HtmlBlock => {
                        flush(&mut lines, &mut current);
                        if lists.is_empty() {
                            lines.push(Line::default());
                        }
                    }
                    TagEnd::Item | TagEnd::TableRow | TagEnd::TableHead => {
                        flush(&mut lines, &mut current)
                    }
                    TagEnd::TableCell => {
                        if let Some(row) = table.as_mut().and_then(|t| t.rows.last_mut()) {
                            row.push(Line::from(std::mem::take(&mut current)));
                        }
                    }
                    TagEnd::List(_) => {
                        lists.pop();
                    }
                    TagEnd::BlockQuote(_) => {
                        quote = quote.saturating_sub(1);
                    }
                    TagEnd::Link | TagEnd::Image => {
                        if let Some(url) = links.pop() {
                            current.push(Span::styled(
                                format!(" ({url})"),
                                Style::default().fg(palette().muted),
                            ));
                        }
                    }
                    _ => (),
                }
            }
            Md::Text(value) | Md::Html(value) | Md::InlineHtml(value) => {
                if let Some((_, source)) = &mut code {
                    source.push_str(&value);
                    continue;
                }
                for (i, part) in value.split('\n').enumerate() {
                    if i > 0 {
                        lines.push(Line::from(std::mem::take(&mut current)));
                    }
                    if !part.is_empty() {
                        current.push(Span::styled(part.to_string(), style));
                    }
                }
            }
            Md::Code(value) => current.push(Span::styled(
                value.to_string(),
                style.fg(palette().amber).bg(palette().panel),
            )),
            Md::SoftBreak => current.push(Span::raw(" ")),
            Md::HardBreak => {
                lines.push(Line::from(std::mem::take(&mut current)));
            }
            Md::Rule => {
                flush(&mut lines, &mut current);
                lines.push(Line::styled(
                    "─".repeat(width),
                    Style::default().fg(palette().line),
                ));
            }
            Md::TaskListMarker(done) => current.push(Span::styled(
                if done { "☑ " } else { "☐ " },
                style.fg(palette().green),
            )),
            _ => (),
        }
    }
    flush(&mut lines, &mut current);
    reflow(lines, width)
}

#[cfg(test)]
mod tests {
    use super::*;
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
    }
}

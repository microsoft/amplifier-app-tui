//! Lazy item layout plus an exclusive bottom-row anchor. None means follow tail.
//! Source items are never replaced by rendered fragments; streaming invalidates
//! only the changed item. Stable projections retain a character boundary on resize.
use super::*;

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Anchor {
    pub item: usize,
    pub row: usize,
}

pub struct Layout {
    width: usize,
    selected: bool,
    joined_usage: bool,
    live_second: Option<u64>,
    lines: Vec<Line<'static>>,
}

impl App {
    pub fn resize_transcript(&mut self, width: u16) {
        if self.body.width == width {
            return;
        }
        for view in 0..2 {
            let Some(anchor) = self.anchors[view] else {
                self.anchor_offsets[view] = None;
                continue;
            };
            let Some(old) = self.layouts.get(anchor.item).and_then(Option::as_ref) else {
                continue;
            };
            let old_lines = old
                .lines
                .iter()
                .map(ToString::to_string)
                .collect::<Vec<_>>();
            let offset = self.anchor_offsets[view]
                .filter(|(item, _)| *item == anchor.item)
                .map(|(_, offset)| offset)
                .unwrap_or_else(|| old_lines.iter().take(anchor.row).map(String::len).sum());
            let original_width = self.body.width;
            self.body.width = width;
            let new_lines = self
                .layout(anchor.item)
                .iter()
                .map(ToString::to_string)
                .collect::<Vec<_>>();
            self.body.width = original_width;
            if let Some(row) = reanchor(&old_lines, &new_lines, offset) {
                self.anchors[view] = Some(Anchor {
                    item: anchor.item,
                    row,
                });
                self.anchor_offsets[view] = Some((anchor.item, offset));
            } else {
                self.anchor_offsets[view] = None;
                if let Some(row) = cell_anchor(&old_lines, &new_lines, anchor.row) {
                    self.anchors[view] = Some(Anchor {
                        item: anchor.item,
                        row,
                    });
                    self.status =
                        "Table layout changed; retained unique matching cell (approximate)".into();
                } else {
                    self.status =
                        "Layout changed structurally; retained item, character anchor unavailable"
                            .into();
                }
            }
        }
    }
    pub fn begin_selection(&mut self, x: u16, y: u16) {
        let Some(end) = self.viewport_end() else {
            self.selection = selection::Selection::default();
            return;
        };
        let mut anchor = end;
        let mut rows = Vec::new();
        let mut bytes = 0;
        loop {
            let line = self.layout(anchor.item)[anchor.row.saturating_sub(1)].to_string();
            bytes += line.len();
            if bytes > 1024 * 1024 || rows.len() >= 10000 {
                break;
            }
            rows.push(line);
            let Some(previous) = self.previous(anchor) else {
                break;
            };
            anchor = previous;
        }
        rows.reverse();
        let offset = rows.len().saturating_sub(self.body.height as usize);
        anchor = end;
        while let Some(next) = self.following(anchor) {
            let line = self.layout(next.item)[next.row - 1].to_string();
            bytes += line.len();
            if bytes > 2 * 1024 * 1024 || rows.len() >= 20000 {
                break;
            }
            rows.push(line);
            anchor = next;
        }
        self.selection.offset = offset;
        self.selection.begin(x, y, self.body);
        self.selection.snapshot = rows;
        self.selection.pointer = Some((x, y));
        self.status = "Select with drag + wheel/edge scroll · snapshot capped at 20k lines/2 MiB · Native scrollback for terminal/tmux".into();
    }
    pub fn reveal_item(&mut self, item: usize) {
        self.anchor_offsets[0] = None;
        self.view = 0;
        self.expanded = false;
        let Some(item) = self
            .following_item(item)
            .or_else(|| self.preceding_item(item))
        else {
            self.anchors[0] = None;
            return;
        };
        self.selected = item;
        let mut anchor = Anchor { item, row: 1 };
        for _ in 1..self.body.height {
            let Some(next) = self.following(anchor) else {
                break;
            };
            anchor = next;
        }
        self.anchors[0] = Some(anchor);
    }
    fn layout(&mut self, index: usize) -> &Vec<Line<'static>> {
        let width = self.body.width as usize;
        let selected = index == self.selected;
        let live_seconds = self.flow.clocks.seconds(&self.items[index].id);
        let live_second = live_seconds.map(|seconds| seconds.floor() as u64);
        let joined_usage = self.items[index].kind != "assistant"
            && self
                .items
                .iter()
                .skip(index + 1)
                .find(|item| !native::hidden(item))
                .is_some_and(native::is_usage);
        if self.layouts[index].as_ref().is_none_or(|l| {
            l.width != width
                || l.selected != selected
                || l.joined_usage != joined_usage
                || l.live_second != live_second
        }) {
            let item = &self.items[index];
            let mut lines = if item.kind == "assistant" {
                let mut lines = markdown::render(&item.text, width);
                if lines.last().is_some_and(|line| line.width() != 0) {
                    lines.push(Line::default());
                }
                lines
            } else {
                native::live_lines(item, width, live_seconds)
            };
            if self.inline_open.contains(&item.id) && native::expandable(item) {
                let detail: Value = serde_json::from_str(&item.detail).unwrap_or(Value::Null);
                if native::usage_call(item) {
                    lines.extend(
                        wrap(detail["text"].as_str().unwrap_or(&item.text), width)
                            .into_iter()
                            .map(|s| Line::styled(s, Style::default().fg(palette().muted))),
                    );
                } else if let Some(rows) = native::todo_rows(&detail) {
                    lines.extend(native::todo_checklist(rows, width));
                } else if detail["source"] == "thinking" {
                    lines.extend(markdown::render_secondary(
                        detail["text"].as_str().unwrap_or(&item.text),
                        width,
                    ));
                } else {
                    lines.extend(tool_detail_lines(&detail, width));
                }
                lines.push(Line::styled(
                    if native::usage_call(item) || native::todo_rows(&detail).is_some() {
                        "[ Activity: full evidence ]"
                    } else {
                        "[ Activity: children and full evidence ]"
                    },
                    Style::default().fg(palette().green),
                ));
                lines.push(Line::default());
            }
            if joined_usage && lines.last().is_some_and(|line| line.width() == 0) {
                lines.pop();
            }
            self.layouts[index] = Some(Layout {
                width,
                selected,
                joined_usage,
                live_second,
                lines,
            });
        }
        &self.layouts[index].as_ref().unwrap().lines
    }

    fn preceding_item(&mut self, end: usize) -> Option<usize> {
        let mut end = end.min(self.items.len());
        loop {
            let item = if self.view == 0 {
                (0..end).rev().find(|&i| !native::hidden(&self.items[i]))
            } else {
                let at = self.tool_indices.partition_point(|&i| i < end);
                self.tool_indices[..at]
                    .iter()
                    .rev()
                    .copied()
                    .find(|&i| !native::hidden(&self.items[i]))
            }?;
            // Not every source item paints a row (empty assistant messages,
            // Markdown-only definitions, hidden observations). A row anchor must.
            if !self.layout(item).is_empty() {
                return Some(item);
            }
            end = item;
        }
    }

    fn following_item(&mut self, mut start: usize) -> Option<usize> {
        loop {
            let item = if self.view == 0 {
                (start..self.items.len()).find(|&i| !native::hidden(&self.items[i]))
            } else {
                self.tool_indices
                    .iter()
                    .skip(self.tool_indices.partition_point(|&i| i < start))
                    .copied()
                    .find(|&i| !native::hidden(&self.items[i]))
            }?;
            if !self.layout(item).is_empty() {
                return Some(item);
            }
            start = item + 1;
        }
    }

    fn viewport_end(&mut self) -> Option<Anchor> {
        let Some(anchor) = self.anchors[self.view] else {
            return self.tail();
        };
        if let Some(item) = self.items.get(anchor.item)
            && !native::hidden(item)
            && (self.view == 0 || item.kind == "tool")
        {
            let len = self.layout(anchor.item).len();
            if len > 0 {
                return Some(Anchor {
                    row: anchor.row.clamp(1, len),
                    ..anchor
                });
            }
        }
        // A formerly visible item may disappear while the reader is anchored.
        // Prefer the preceding visible boundary, then the first remaining row.
        if let Some(item) = self.preceding_item(anchor.item.saturating_add(1)) {
            return Some(Anchor {
                item,
                row: self.layout(item).len(),
            });
        }
        self.following_item(0).map(|item| Anchor { item, row: 1 })
    }

    pub fn tail(&mut self) -> Option<Anchor> {
        let item = self.preceding_item(self.items.len())?;
        Some(Anchor {
            item,
            row: self.layout(item).len(),
        })
    }

    fn previous(&mut self, anchor: Anchor) -> Option<Anchor> {
        if anchor.row > 1 {
            return Some(Anchor {
                row: anchor.row - 1,
                ..anchor
            });
        }
        let item = self.preceding_item(anchor.item)?;
        Some(Anchor {
            item,
            row: self.layout(item).len(),
        })
    }

    fn following(&mut self, anchor: Anchor) -> Option<Anchor> {
        if anchor.row < self.layout(anchor.item).len() {
            return Some(Anchor {
                row: anchor.row + 1,
                ..anchor
            });
        }
        let item = self.following_item(anchor.item + 1)?;
        Some(Anchor { item, row: 1 })
    }

    pub fn scroll_lines(&mut self, amount: isize) {
        self.anchor_offsets[self.view] = None;
        let Some(mut anchor) = self.viewport_end() else {
            return;
        };
        for _ in 0..amount.unsigned_abs() {
            let next = if amount > 0 {
                self.previous(anchor)
            } else {
                self.following(anchor)
            };
            let Some(next) = next else {
                break;
            };
            anchor = next;
        }
        // The earliest viewport is a full first page, not a single first row
        // floating above empty space. Compute only that page, never all history.
        if amount > 0
            && let Some(item) = self.following_item(0)
        {
            let mut first_page = Anchor { item, row: 1 };
            for _ in 1..self.body.height {
                let Some(next) = self.following(first_page) else {
                    break;
                };
                first_page = next;
            }
            if (anchor.item, anchor.row) < (first_page.item, first_page.row) {
                anchor = first_page;
            }
        }
        self.anchors[self.view] = if Some(anchor) == self.tail() {
            None
        } else {
            Some(anchor)
        };
    }

    pub fn transcript_rows(&mut self) -> Vec<(usize, Line<'static>)> {
        let Some(mut anchor) = self.viewport_end() else {
            return vec![];
        };
        let mut rows = Vec::new();
        for _ in 0..self.body.height {
            if let Some(line) = self.layout(anchor.item).get(anchor.row - 1) {
                rows.push((anchor.item, line.clone()));
            }
            let Some(previous) = self.previous(anchor) else {
                break;
            };
            anchor = previous;
        }
        rows.reverse();
        rows
    }
}

fn tool_detail_lines(detail: &Value, width: usize) -> Vec<Line<'static>> {
    let quiet = Style::default().fg(palette().muted);
    let heading = Style::default()
        .fg(palette().green)
        .add_modifier(Modifier::BOLD);
    let mut lines = Vec::new();
    let name = safe(detail["name"].as_str().unwrap_or("unknown"));
    let mut preview = detail.clone();
    if preview["error"].is_null() && !detail["result"]["error"].is_null() {
        preview["error"] = detail["result"]["error"].clone();
    }
    if detail["name"] == "bash"
        && let Some(command) = detail["arguments"]["command"].as_str()
    {
        lines.extend(markdown::reflow(
            vec![Line::styled(format!("Request · {name} command"), heading)],
            width,
        ));
        let source = safe(&command.chars().take(2400).collect::<String>());
        let mut budget = syntax::MAX_BYTES;
        let mut command_lines = syntax::lines(&source, "bash", &mut budget);
        // Syntax roles are useful here, but ordinary tool text isn't a response.
        for line in &mut command_lines {
            for span in &mut line.spans {
                if span.style.fg == Some(palette().ink) {
                    span.style = span.style.fg(palette().muted);
                }
                span.style.bg = None;
            }
        }
        let rows = markdown::reflow(command_lines, width);
        let clipped = rows.len() > 12 || command.chars().count() > 2400;
        lines.extend(rows.into_iter().take(12));
        if clipped {
            lines.extend(
                wrap("[command excerpt; full evidence in Activity]", width)
                    .into_iter()
                    .map(|s| Line::styled(s, quiet)),
            );
        }
        if let Some(args) = preview["arguments"].as_object_mut() {
            args.remove("command");
        }
    }
    for (label, source) in tool_sections(&preview) {
        let title = if lines.is_empty() {
            format!("{label} · {name}")
        } else {
            label.to_owned()
        };
        lines.extend(markdown::reflow(
            vec![Line::styled(
                title,
                if label == "Error" {
                    Style::default()
                        .fg(palette().red)
                        .add_modifier(Modifier::BOLD)
                } else {
                    heading
                },
            )],
            width,
        ));
        // Bound display rows AFTER wrapping: a long unbroken output must not
        // monopolize the inspector at mobile widths. Activity retains the source.
        let rows = wrap(&safe(&source), width);
        let limit = if label == "Result" || label == "Agents" {
            8
        } else {
            16
        };
        let clipped = rows.len() > limit;
        lines.extend(rows.into_iter().take(limit).map(|s| Line::styled(s, quiet)));
        if clipped {
            lines.extend(
                wrap("[preview excerpt; full evidence in Activity]", width)
                    .into_iter()
                    .map(|s| Line::styled(s, quiet)),
            );
        }
        lines.push(Line::default());
    }
    if lines.is_empty() {
        lines.extend(markdown::reflow(
            vec![Line::styled(format!("Tool · {name}"), heading)],
            width,
        ));
    }
    lines
}

#[cfg(test)]
fn tool_preview(detail: &Value) -> String {
    tool_sections(detail)
        .into_iter()
        .map(|(label, source)| format!("{label}\n{source}"))
        .collect::<Vec<_>>()
        .join("\n\n")
}

fn tool_sections(detail: &Value) -> Vec<(&'static str, String)> {
    let mut parts = Vec::new();
    for (key, label) in [
        ("arguments", "Request"),
        ("child_progress", "Agents"),
        (
            "child_progress_omitted",
            "Earlier agents retained in Activity",
        ),
        ("result", "Result"),
        ("error", "Error"),
    ] {
        if key == "child_progress_omitted" && detail[key].as_u64().unwrap_or(0) == 0 {
            continue;
        }
        if !detail[key].is_null() {
            let value = if key == "result" && !detail[key]["output"].is_null() {
                &detail[key]["output"]
            } else {
                &detail[key]
            };
            let source = if let Some(value) = value.as_str() {
                value.to_string()
            } else if let Some(fields) = value.as_object() {
                fields
                    .iter()
                    .filter(|(_, value)| !value.is_null())
                    .map(|(key, value)| {
                        format!(
                            "{key}: {}",
                            value.as_str().map(str::to_string).unwrap_or_else(|| {
                                serde_json::to_string_pretty(value).unwrap_or_default()
                            })
                        )
                    })
                    .collect::<Vec<_>>()
                    .join("\n")
            } else if key == "child_progress" {
                value
                    .as_array()
                    .map(|rows| {
                        rows.iter()
                            .map(|row| {
                                let warnings =
                                    native::child_alerts(std::slice::from_ref(row)).join(" · ");
                                let cost = row["cost_display"]
                                    .as_str()
                                    .map(str::to_owned)
                                    .unwrap_or_else(|| "not reported".into());
                                let task = row["task_title"].as_str().map(|title| {
                                    format!("Task: {} ({})\n", title,
                                        row["task_title_source"].as_str().unwrap_or("display title"))
                                }).unwrap_or_default();
                                format!(
                                    "{}{} · {} · {}\n{} calls · {} tools · Cost: {}{}\nWarnings: {}",
                                    task,
                                    row["agent"].as_str().unwrap_or("Agent"),
                                    match row["status"].as_str().unwrap_or("unknown") {
                                        "waiting_capacity" => "waiting for capacity",
                                        status => status,
                                    },
                                    row["activity"].as_str().unwrap_or(""),
                                    row["calls"]
                                        .as_u64()
                                        .map(|v| v.to_string())
                                        .unwrap_or_else(|| "Unknown".into()),
                                    row["tools_completed"]
                                        .as_u64()
                                        .map(|v| v.to_string())
                                        .unwrap_or_else(|| "unknown".into()),
                                    cost,
                                    if row["cost_partial"] == true {
                                        " (partial)"
                                    } else {
                                        ""
                                    },
                                    if !warnings.is_empty() {
                                        &warnings
                                    } else if row["warnings"].is_object()
                                        && row["notices"].is_object()
                                    {
                                        "none"
                                    } else {
                                        "not reported"
                                    }
                                )
                            })
                            .collect::<Vec<_>>()
                            .join("\n")
                    })
                    .unwrap_or_default()
            } else {
                serde_json::to_string_pretty(value).unwrap_or_default()
            };
            if source.trim().is_empty() {
                continue;
            }
            let excerpt: String = source.chars().take(2400).collect();
            parts.push((
                label,
                format!(
                    "{excerpt}{}",
                    if source.chars().count() > 2400 {
                        "\n[preview excerpt; full evidence in Activity]"
                    } else {
                        ""
                    }
                ),
            ));
        }
    }
    parts
}

fn reanchor(old: &[String], new: &[String], offset: usize) -> Option<usize> {
    if old.concat() != new.concat() {
        return None;
    }
    let mut consumed = 0;
    Some(
        new.iter()
            .position(|line| {
                consumed += line.len();
                consumed >= offset
            })
            .map_or(new.len(), |i| i + 1)
            .max(1),
    )
}

// Deliberately weaker than a source anchor: only a unique complete cell can
// bridge a table's column/stacked layout. Repeated or wrapped cells refuse.
fn cell_anchor(old: &[String], new: &[String], row: usize) -> Option<usize> {
    if old.len() > 20000 || new.len() > 20000 {
        return None;
    }
    let line = old.get(row.checked_sub(1)?)?;
    let cells = |line: &str| -> Vec<String> {
        line.split('│')
            .map(str::trim)
            .filter(|s| !s.is_empty())
            .map(str::to_owned)
            .collect()
    };
    for cell in cells(line)
        .into_iter()
        .rev()
        .filter(|s| s.chars().count() >= 2)
    {
        if old
            .iter()
            .flat_map(|s| cells(s))
            .filter(|s| s == &cell)
            .count()
            != 1
        {
            continue;
        }
        let matches: Vec<_> = new
            .iter()
            .enumerate()
            .filter(|(_, s)| cells(s).contains(&cell))
            .map(|(i, _)| i + 1)
            .collect();
        if matches.len() == 1 {
            return Some(matches[0]);
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn selection_skips_zero_row_items_and_repairs_stale_anchors() {
        let mut app = App::new(vec!["true".into()]).unwrap();
        app.child.wait().unwrap();
        app.draft.insert_str("Keep this draft");
        for (id, kind, text, detail) in [
            ("empty-first", "assistant", "", json!({})),
            ("a", "assistant", "First visible answer", json!({})),
            ("empty-middle", "assistant", "   \n\n", json!({})),
            (
                "tool",
                "tool",
                "Probe",
                json!({"name":"fixture_probe","result":"done"}),
            ),
            (
                "hidden",
                "tool",
                "Child",
                json!({"name":"fixture_probe","child_id":"child","parent_item_id":"tool"}),
            ),
            ("b", "assistant", "Last visible answer", json!({})),
            (
                "empty-last",
                "assistant",
                "[ref]: https://example.org",
                json!({}),
            ),
        ] {
            app.upsert(Item {
                id: id.into(),
                kind: kind.into(),
                text: text.into(),
                status: "succeeded".into(),
                detail: detail.to_string(),
            });
        }
        for width in [175, 40, 1, 0] {
            app.resize_transcript(width);
            app.body = Rect::new(0, 0, width, 20);
            for view in 0..2 {
                app.view = view;
                for item in [0, 2, 4, 6, 99] {
                    app.anchors[view] = Some(Anchor { item, row: 999 });
                    app.transcript_rows();
                    app.begin_selection(0, 0);
                    app.scroll_lines(100);
                    app.scroll_lines(-100);
                    assert!(!app.selection.snapshot.is_empty());
                }
            }
        }
        app.view = 0;
        app.body.width = 175;
        app.anchors[0] = None;
        app.begin_selection(0, 0);
        let text = app.selection.snapshot.join("\n");
        assert!(text.contains("First visible answer"));
        assert!(text.contains("Last visible answer"));
        assert_eq!(app.draft.lines().join("\n"), "Keep this draft");
        // A valid anchor can become empty after an observed update.
        app.anchors[0] = Some(Anchor { item: 5, row: 1 });
        app.upsert(Item {
            id: "b".into(),
            kind: "assistant".into(),
            ..Default::default()
        });
        app.begin_selection(0, 0);
        assert!(
            !app.selection
                .snapshot
                .join("\n")
                .contains("Last visible answer")
        );
        for index in [1, 3] {
            app.upsert(Item {
                id: app.items[index].id.clone(),
                kind: "assistant".into(),
                ..Default::default()
            });
        }
        app.begin_selection(0, 0);
        assert!(app.transcript_rows().is_empty());
        assert!(app.selection.snapshot.is_empty());
        assert!(app.tail().is_none());
    }

    #[test]
    fn expanded_commands_keep_source_roles_and_bound_wrapped_output() {
        let command = "printf '%s\\n' '界面 é 👩‍💻'\n  echo done";
        let detail = json!({"name":"bash","arguments":{"command":command,"timeout":30},
            "result":{"output":"x".repeat(2000)}});
        let original = detail.clone();
        for width in [32, 40, 175] {
            let rows = tool_detail_lines(&detail, width);
            assert!(rows.iter().all(|r| r.width() <= width));
            assert!(rows.len() < 40);
            let content = rows
                .iter()
                .map(ToString::to_string)
                .collect::<Vec<_>>()
                .join("\n");
            assert!(content.contains("Request · bash command"));
            assert!(content.contains("timeout: 30"));
            assert!(content.contains("[preview excerpt;"));
            assert!(!content.contains(&"x".repeat(width + 1)));
            if width == 175 {
                assert!(content.contains(command));
            }
            if !matches!(palette().syntax_theme, SyntaxTheme::Plain) {
                assert!(
                    rows.iter()
                        .flat_map(|r| &r.spans)
                        .all(|s| s.style.fg != Some(palette().ink))
                );
            }
        }
        assert_eq!(detail, original);
        let error = tool_detail_lines(
            &json!({"name":"bash","result":{"output":"partial", "error":{"message":"fixture failure"}}}),
            175,
        );
        assert!(error.iter().any(|r| r.to_string() == "Error"));
        assert!(
            error
                .iter()
                .any(|r| r.to_string() == "message: fixture failure")
        );
        assert_eq!(
            tool_detail_lines(&json!({"name":"fixture.empty"}), 175)[0].to_string(),
            "Tool · fixture.empty"
        );
        let unknown = tool_detail_lines(
            &json!({"name":"fixture.external","arguments":{"raw":"payload"}}),
            175,
        );
        assert!(unknown.iter().any(|r| r.to_string() == "raw: payload"));
    }
    #[test]
    fn task_titles_are_marked_as_display_excerpts_without_replacing_the_request() {
        let detail = serde_json::json!({
            "arguments": {"instruction":"Task: Review file tools\nDo not change any files."},
            "child_progress":[{"task_title":"Review file tools", "task_title_source":"instruction heading",
                "agent":"explorer #2", "status":"running", "activity":"read_file"}]
        });
        let preview = tool_preview(&detail);
        assert!(preview.contains("instruction: Task: Review file tools\nDo not change any files."));
        assert!(preview.contains("Task: Review file tools (instruction heading)"));
        assert!(preview.contains("explorer #2 · running · read_file"));
    }
    #[test]
    fn structural_table_resize_retains_unique_cell_but_refuses_ambiguity() {
        let source = "| Name | Value |\n|---|---|\n| Alpha | 12 |\n| Beta | 34 |";
        let render = |width| {
            markdown::render(source, width)
                .iter()
                .map(ToString::to_string)
                .collect::<Vec<_>>()
        };
        let wide = render(80);
        let narrow = render(16);
        let row = wide.iter().position(|s| s.contains("Beta")).unwrap() + 1;
        let selected = cell_anchor(&wide, &narrow, row).unwrap();
        assert_eq!(narrow[selected - 1].trim(), "34");
        assert_eq!(cell_anchor(&narrow, &wide, selected), Some(row));
        assert_eq!(
            cell_anchor(&["│ same │ same │".into()], &["same".into()], 1),
            None
        );
        assert_eq!(
            cell_anchor(&["unique".into()], &["unique".into(), "unique".into()], 1),
            None
        );
    }
    #[test]
    fn resize_preserves_original_unicode_boundary_without_roundtrip_drift() {
        let source = "one two 界界 e\u{301} 👩‍💻 repeated repeated tail";
        let lines = |width| {
            markdown::reflow(vec![Line::from(source)], width)
                .iter()
                .map(ToString::to_string)
                .collect::<Vec<_>>()
        };
        let narrow = lines(12);
        let offset = narrow.iter().take(2).map(String::len).sum();
        for width in [20, 8, 40, 12] {
            let rows = lines(width);
            let row = reanchor(&narrow, &rows, offset).unwrap();
            assert!(rows.iter().take(row).map(String::len).sum::<usize>() >= offset);
            if width == 12 {
                assert_eq!(row, 2);
            }
        }
        assert!(reanchor(&narrow, &["different projection".into()], offset).is_none());
    }
}

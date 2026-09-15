//! Read-only Git observation menus; never turn local inspection into agent work.
use super::*;
use interaction::Choice;

pub fn diff_lines(source: &str, width: usize) -> Vec<Line<'static>> {
    markdown::reflow(
        safe(source)
            .split('\n')
            .map(|line| {
                let style = if line.starts_with("diff --git ") || line.starts_with("@@ ") {
                    Style::default().fg(GREEN).add_modifier(Modifier::BOLD)
                } else if line.starts_with("--- ") || line.starts_with("+++ ") {
                    Style::default().fg(AMBER)
                } else if line.starts_with('+') {
                    Style::default().fg(GREEN)
                } else if line.starts_with('-') {
                    Style::default().fg(RED)
                } else {
                    Style::default().fg(INK)
                };
                Line::styled(line.to_string(), style)
            })
            .collect(),
        width,
    )
}

pub fn hunks(text: &str) -> (Vec<(usize, usize)>, bool) {
    let mut result: Vec<(usize, usize)> = Vec::new();
    let mut open: Option<usize> = None;
    let mut offset = 0;
    for line in text.split_inclusive('\n') {
        let hunk = line.starts_with("@@ -");
        if hunk || line.starts_with("diff --git ") {
            if let Some(i) = open.take() {
                result[i].1 = offset;
            }
            if hunk {
                if result.len() == 100 {
                    return (result, true);
                }
                open = Some(result.len());
                result.push((offset, text.len()));
            }
        }
        offset += line.len();
    }
    (result, false)
}

pub fn side_by_side_lines(source: &str, width: usize) -> Vec<Line<'static>> {
    if width < 80 {
        return diff_lines(source, width);
    }
    let column = (width - 3) / 2;
    let mut output = Vec::new();
    let mut removed = Vec::new();
    let mut added = Vec::new();
    let flush =
        |left: &mut Vec<String>, right: &mut Vec<String>, output: &mut Vec<Line<'static>>| {
            for index in 0..left.len().max(right.len()) {
                let l = markdown::reflow(
                    vec![Line::styled(
                        left.get(index).cloned().unwrap_or_default(),
                        Style::default().fg(RED),
                    )],
                    column,
                );
                let r = markdown::reflow(
                    vec![Line::styled(
                        right.get(index).cloned().unwrap_or_default(),
                        Style::default().fg(GREEN),
                    )],
                    column,
                );
                for row in 0..l.len().max(r.len()) {
                    let a = l.get(row).cloned().unwrap_or_default();
                    let b = r.get(row).cloned().unwrap_or_default();
                    let padding = " ".repeat(column.saturating_sub(a.width()));
                    let mut spans = a.spans;
                    spans.push(Span::raw(padding));
                    spans.push(Span::styled(" │ ", Style::default().fg(MUTED)));
                    spans.extend(b.spans);
                    output.push(Line::from(spans));
                }
            }
            left.clear();
            right.clear();
        };
    let cleaned = safe(source);
    for line in cleaned.lines() {
        if line.starts_with('-') && !line.starts_with("--- ") {
            if !added.is_empty() {
                flush(&mut removed, &mut added, &mut output);
            }
            removed.push(line.to_owned());
        } else if line.starts_with('+') && !line.starts_with("+++ ") {
            added.push(line.to_owned());
        } else {
            flush(&mut removed, &mut added, &mut output);
            output.extend(diff_lines(line, width));
        }
    }
    flush(&mut removed, &mut added, &mut output);
    output
}

impl App {
    pub fn review_lookup(&mut self, selection: Option<(String, String)>) {
        if !self.nav.enabled {
            self.status = "Workspace review is unavailable in this presentation harness".into();
            return;
        }
        self.review_request = Some((self.request + 1).to_string());
        self.menu("Workspace changes · reading local Git state", vec![]);
        match selection {
            Some((id, token)) => self.send(json!({"op":"workspace_diff","id":id,"token":token})),
            None => self.send(json!({"op":"workspace_changes"})),
        }
    }

    pub fn review_result(&mut self, v: &Value) {
        if self
            .review_request
            .as_ref()
            .is_none_or(|id| v["request_id"] != *id)
            || v["session_id"] != self.nav.session
        {
            return;
        }
        self.review_request = None;
        let refresh = Choice {
            label: "Refresh Workspace changes".into(),
            action: Action::WorkspaceChanges,
            detail: String::new(),
        };
        if v["error"].is_string() {
            self.menu("Workspace changes · unavailable", vec![refresh]);
            self.ui.menu.as_mut().unwrap().detail = safe(&string(v, "error"));
        } else if v["type"] == "workspace_changes" {
            let mut choices = vec![refresh];
            choices.extend(v["rows"].as_array().into_iter().flatten().map(|r| Choice {
                label: format!(
                    "{} · {} · {}",
                    string(r, "scope"),
                    string(r, "status"),
                    safe(&string(r, "path")).replace('\n', " ↵ ")
                ),
                action: Action::WorkspaceDiff(string(r, "id"), string(v, "token")),
                detail: String::new(),
            }));
            self.menu("Workspace changes · observed, not attributed", choices);
            self.ui.menu.as_mut().unwrap().detail = format!(
                "Repository: {}\n{}\n{}",
                safe(&string(v, "root")),
                safe(&string(v, "notice")),
                if v["limited"] == true {
                    "Partial listing: first 500 rows (untracked directories are grouped)."
                } else if v["rows"].as_array().is_some_and(|r| r.is_empty()) {
                    "No changes reported by Git (ignored files and submodule contents omitted)."
                } else {
                    "Select staged / unstaged separately. Untracked directories are grouped; contents are not read."
                }
            );
        } else {
            self.workspace_hunk(Arc::new(v.clone()), usize::MAX);
        }
    }

    pub fn workspace_hunks(&mut self, snapshot: Arc<Value>) {
        let text = string(&snapshot, "text");
        let (ranges, limited) = hunks(&text);
        let mut choices = vec![Choice {
            label: "Whole observed diff".into(),
            action: Action::WorkspaceHunk(snapshot.clone(), usize::MAX),
            detail: String::new(),
        }];
        choices.extend(ranges.iter().enumerate().map(|(i, (start, end))| Choice {
            label: format!(
                "Hunk {} · {}",
                i + 1,
                safe(text[*start..*end].lines().next().unwrap_or(""))
            ),
            action: Action::WorkspaceHunk(snapshot.clone(), i),
            detail: String::new(),
        }));
        self.menu("Observed diff hunks · local snapshot", choices);
        self.ui.menu.as_mut().unwrap().detail = format!(
            "{} · {}\n{}\nSelecting a hunk reads this captured diff only; it does not refresh Git, apply a patch or run a model.",
            safe(&string(&snapshot, "path")),
            safe(&string(&snapshot, "base")),
            if limited {
                "Partial catalog: first 100 hunks. Whole diff remains available."
            } else if ranges.is_empty() {
                "No unified text hunks (binary, untracked or non-text result)."
            } else {
                "Captured hunks; workspace files may have changed since inspection."
            }
        );
    }

    pub fn workspace_hunk(&mut self, snapshot: Arc<Value>, at: usize) {
        let v = &snapshot;
        let text = string(v, "text");
        let (ranges, _) = hunks(&text);
        let selected = ranges.get(at).map(|(start, end)| &text[*start..*end]);
        if at != usize::MAX && selected.is_none() {
            return;
        }
        let source = selected.unwrap_or(&text);
        let body = format!(
            "Repository: {}\nPath: {} · {}\nComparison: {}\n{}\n\n{}",
            safe(&string(v, "root")),
            safe(&string(v, "path")),
            string(v, "scope"),
            safe(&string(v, "base")),
            safe(&string(v, "notice")),
            safe(source)
        );
        self.menu(
            "Workspace diff · read-only · PgUp/PgDn to read",
            vec![
                Choice {
                    label: if selected.is_some() {
                        "Copy this hunk (not a complete patch)"
                    } else {
                        "Copy observed diff text"
                    }
                    .into(),
                    action: Action::CopySource(Arc::from(source)),
                    detail: String::new(),
                },
                Choice {
                    label: "Browse hunks in this snapshot".into(),
                    action: Action::WorkspaceHunks(snapshot.clone()),
                    detail: String::new(),
                },
                Choice {
                    label: "Side-by-side removed / added lines".into(),
                    action: Action::WorkspaceSide(snapshot.clone(), at),
                    detail: "Read-only layout; copying always uses the original unified diff."
                        .into(),
                },
                Choice {
                    label: "Refresh Workspace changes".into(),
                    action: Action::WorkspaceChanges,
                    detail: String::new(),
                },
            ],
        );
        self.ui.menu.as_mut().unwrap().detail = body;
        self.ui.menu.as_mut().unwrap().diff = true;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn side_by_side_is_width_safe_and_preserves_original_copy_source() {
        let source = "@@ -1 +1 @@\n-界界old\n+new🙂\n context";
        let rows = side_by_side_lines(source, 80);
        assert!(rows.iter().all(|line| line.width() <= 80));
        assert!(rows.iter().any(
            |line| line.to_string().contains("-界界old") && line.to_string().contains("+new🙂")
        ));
        assert_eq!(side_by_side_lines(source, 40), diff_lines(source, 40));
        assert_eq!(source, "@@ -1 +1 @@\n-界界old\n+new🙂\n context");
    }
    #[test]
    fn hunk_slices_keep_source_and_stop_at_file_boundaries() {
        let text =
            "diff --git a/a b/a\n@@ -1 +1 @@\n-old\n+界\ndiff --git a/b b/b\n@@ -2 +2 @@\n-a\n+b\n";
        let (rows, limited) = hunks(text);
        assert!(!limited);
        assert_eq!(rows.len(), 2);
        assert_eq!(&text[rows[0].0..rows[0].1], "@@ -1 +1 @@\n-old\n+界\n");
        assert!(text[rows[1].0..rows[1].1].ends_with("+b\n"));
    }
    #[test]
    fn hunk_limit_and_diff_styles_are_explicit() {
        let text = "@@ -1 +1 @@\n-a\n+b\n".repeat(101);
        let (rows, limited) = hunks(&text);
        assert!(limited && rows.len() == 100);
        let lines = diff_lines("-old\n+new\n context", 80);
        assert_eq!(lines[0].spans[0].style.fg, Some(RED));
        assert_eq!(lines[1].spans[0].style.fg, Some(GREEN));
        assert_eq!(lines[2].to_string(), " context");
    }
}

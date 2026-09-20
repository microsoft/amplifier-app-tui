//! Normal-screen output ownership. The runtime and retained source remain independent.
//! Committed rows are never repainted. Only a small live region is cursor-addressed.
use super::*;
use crossterm::{cursor, queue, style::ResetColor, terminal as tty};
use ratatui::{TerminalOptions, Viewport, backend::CrosstermBackend, widgets::Widget};
use std::collections::{BTreeSet, VecDeque};
use std::hash::{Hash, Hasher};
use unicode_width::UnicodeWidthStr;
const MAX_REPLAY_ITEMS: usize = 1000;

// Paint-only clocks for observed live children. No tick events, source rewrites,
// cost extrapolation, or full-history scans. Repeated sibling snapshots must not
// restart a quiet child's clock; final outcomes retain their reported duration.
#[derive(Default)]
pub struct ActivityClocks {
    items: HashMap<String, HashMap<String, (f64, Option<Instant>)>>,
}

impl ActivityClocks {
    pub fn observe(&mut self, item: &Item) {
        if item.kind != "tool" {
            return;
        }
        let mut previous = self.items.remove(&item.id).unwrap_or_default();
        if !matches!(item.status.as_str(), "running" | "waiting") {
            return;
        }
        let detail: Value = serde_json::from_str(&item.detail).unwrap_or_default();
        let Some(children) = detail["child_progress"].as_array() else {
            return;
        };
        let mut clocks = HashMap::new();
        for child in children {
            if !matches!(child["status"].as_str(), Some("running" | "waiting")) {
                continue;
            }
            let (Some(id), Some(seconds)) = (
                child["child_id"].as_str(),
                child["elapsed_seconds"].as_f64(),
            ) else {
                continue;
            };
            if !seconds.is_finite() || seconds < 0.0 {
                continue;
            }
            let clock = previous
                .remove(id)
                .filter(|(value, _)| *value == seconds)
                .unwrap_or((seconds, Some(Instant::now())));
            clocks.insert(id.to_owned(), clock);
        }
        if !clocks.is_empty() {
            self.items.insert(item.id.clone(), clocks);
        }
    }

    pub fn seconds(&self, item: &str) -> Option<f64> {
        self.items
            .get(item)?
            .values()
            .map(|(seconds, at)| seconds + at.map_or(0.0, |at| at.elapsed().as_secs_f64()))
            .reduce(f64::max)
    }

    pub fn freeze(&mut self) {
        for children in self.items.values_mut() {
            for (seconds, at) in children.values_mut() {
                if let Some(at) = at.take() {
                    *seconds += at.elapsed().as_secs_f64();
                }
            }
        }
    }
}

#[derive(Default)]
pub struct TurnMeter {
    pub phase: String,
    turn: String,
    received: Option<Instant>,
    elapsed: f64,
    values: Value,
}

impl TurnMeter {
    pub fn state(&mut self, turn: &str, busy: bool) {
        if !busy || self.turn != turn {
            *self = Self::default();
            self.turn = turn.into();
        }
    }

    pub fn observe(&mut self, value: Value) {
        if string(&value, "turn_id") != self.turn {
            return;
        }
        if let Some(elapsed) = value["elapsed_seconds"]
            .as_f64()
            .filter(|v| v.is_finite() && *v >= 0.0)
        {
            self.elapsed = elapsed.max(self.seconds());
            self.received = Some(Instant::now());
        }
        self.values = value;
    }

    fn seconds(&self) -> f64 {
        self.elapsed + self.received.map_or(0.0, |at| at.elapsed().as_secs_f64())
    }

    fn rows(&self, label: &str, width: usize) -> Vec<String> {
        let mut parts = vec![label.to_owned()];
        if self.received.is_some() {
            parts.push(elapsed_label(self.seconds().floor()));
        }
        if self.values.is_object() {
            let turn = &self.values["turn"];
            parts.push(match turn["calls"].as_u64() {
                Some(1) => "1 call".into(),
                Some(n) => format!("{n} calls"),
                None => "calls not reported".into(),
            });
            let tokens = if let Some(n) = turn["tokens"].as_f64() {
                let count = if width < 80 && n >= 1_000_000.0 {
                    format!("{:.2}M", n / 1_000_000.0)
                } else if width < 80 && n >= 1_000.0 {
                    format!("{:.1}k", n / 1_000.0)
                } else {
                    let digits = format!("{n:.0}");
                    digits
                        .chars()
                        .enumerate()
                        .fold(String::new(), |mut s, (i, c)| {
                            if i > 0 && (digits.len() - i).is_multiple_of(3) {
                                s.push(',');
                            }
                            s.push(c);
                            s
                        })
                };
                format!(
                    "{count} tokens{}",
                    if turn["tokens_partial"] == true {
                        " (partial)"
                    } else {
                        ""
                    }
                )
            } else if turn["calls"] == 0 {
                "tokens pending".into()
            } else {
                "tokens not reported".into()
            };
            parts.push(format!("Turn usage: {tokens}"));
            parts.push(format!(
                "Turn {}",
                safe(turn["cost"].as_str().unwrap_or("not reported"))
            ));
            let session_cost = safe(
                self.values["session"]["cost"]
                    .as_str()
                    .unwrap_or("not reported"),
            );
            if self.values["earlier_usage_unavailable"] == true && width < 80 {
                let cost = if session_cost == "not reported" {
                    "unknown"
                } else {
                    session_cost.trim_end_matches(" (partial)")
                };
                parts.push(format!("Session {cost} (partial history)"));
            } else {
                parts.push(format!("Session {session_cost}"));
            }
            if self.values["earlier_usage_unavailable"] == true && width >= 80 {
                parts.push("earlier usage unavailable".into());
            }
        }
        let mut rows = Vec::new();
        let mut row = String::new();
        for part in parts {
            if !row.is_empty()
                && UnicodeWidthStr::width(row.as_str()) + 3 + UnicodeWidthStr::width(part.as_str())
                    > width
            {
                rows.push(std::mem::take(&mut row));
            }
            if !row.is_empty() {
                row.push_str(" · ");
            }
            row.push_str(&part);
        }
        if !row.is_empty() {
            rows.push(row);
        }
        rows.into_iter()
            .flat_map(|row| wrap(&row, width.max(1)))
            .collect()
    }
}

fn work_rows(app: &App, width: usize) -> Vec<Line<'static>> {
    if !app.flow.busy || app.disconnected {
        return vec![];
    }
    let phase = format!("● {}", app.flow.meter.phase);
    let rows = app.flow.meter.rows(
        if !app.flow.cancellation.is_empty() {
            "● Stopping"
        } else if app.approval.is_some() || !app.questions.pending.is_empty() {
            if width < 60 {
                "● Waiting"
            } else {
                "● Waiting for your answer"
            }
        } else if app.status.to_lowercase().contains("stop") {
            "● Stopping"
        } else if !app.flow.meter.phase.is_empty() {
            &phase
        } else {
            "● Working"
        },
        width,
    );
    let hint = match app.flow.cancellation.as_str() {
        "graceful" if width < 60 => "Ctrl-C again: force stop",
        "graceful" => "Finishing current calls · Ctrl-C again to force stop",
        "immediate" if width < 60 => "Stopping now · may leave effects",
        "immediate" => "Stopping now · partial effects may remain",
        _ => "",
    };
    let mut rows: Vec<_> = rows
        .iter()
        .map(|row| activity::line(row, activity::running(app)))
        .collect();
    if !hint.is_empty() {
        rows.extend(
            wrap(hint, width)
                .into_iter()
                .map(|row| Line::styled(row, Style::default().fg(palette().red))),
        );
    }
    rows
}

pub fn elapsed_label(seconds: f64) -> String {
    let seconds = seconds.round().max(0.0) as u64;
    if seconds < 60 {
        format!("{seconds}s")
    } else if seconds < 3600 {
        format!("{}m {:02}s", seconds / 60, seconds % 60)
    } else {
        format!(
            "{}h {:02}m {:02}s",
            seconds / 3600,
            seconds % 3600 / 60,
            seconds % 60
        )
    }
}

pub fn child_alerts(children: &[Value]) -> Vec<String> {
    child_badges(children)
        .into_iter()
        .map(|(text, _)| text)
        .collect()
}

fn child_badges(children: &[Value]) -> Vec<(String, Color)> {
    let mut alerts = Vec::new();
    for (field, key, singular, plural) in [
        ("warnings", "failed", "tool error", "tool errors"),
        ("warnings", "unknown", "unknown outcome", "unknown outcomes"),
        (
            "warnings",
            "interrupted",
            "interrupted tool",
            "interrupted tools",
        ),
        ("notices", "warning", "hook warning", "hook warnings"),
        ("notices", "error", "hook error", "hook errors"),
    ] {
        let count: u64 = children
            .iter()
            .map(|row| row[field][key].as_u64().unwrap_or(0))
            .sum();
        if count > 0 {
            alerts.push((
                format!("{count} {}", if count == 1 { singular } else { plural }),
                color(key),
            ));
        }
    }
    for status in ["failed", "unknown", "interrupted"] {
        let count = children
            .iter()
            .filter(|row| row["status"] == status)
            .count();
        if count > 0 {
            alerts.push((
                format!(
                    "{count} {} {status}",
                    if count == 1 { "agent" } else { "agents" }
                ),
                color(status),
            ));
        }
    }
    alerts
}

fn current_activity(row: &Value) -> Option<String> {
    let activity = row["activity"].as_str().unwrap_or("Working");
    (!matches!(
        activity,
        "succeeded" | "failed" | "interrupted" | "completed" | "Completed"
    ))
    .then(|| activity.to_string())
}

struct Pending {
    item: Item,
    offset: usize,
    heading: bool,
    complete: bool,
}

#[derive(Default)]
pub struct Journal {
    pending: HashMap<String, Pending>,
    order: Vec<String>,
    dirty: BTreeSet<usize>,
    indices: HashMap<String, usize>,
    emitted: HashMap<String, u64>,
    rows: VecDeque<Line<'static>>,
    banner: bool,
    active: BTreeSet<usize>,
    pub skip_replay_item: bool,
    separator_tail: bool,
}

fn fingerprint(item: &Item) -> u64 {
    let mut h = std::collections::hash_map::DefaultHasher::new();
    (&item.kind, &item.text, &item.status).hash(&mut h);
    h.finish()
}

/// Compact only the terminal projection. Source items and inspection stay exact.
fn hidden_child(item: &Item, detail: &Value) -> bool {
    detail["child_id"].is_string()
        && detail["parent_item_id"].is_string()
        && !matches!(item.status.as_str(), "failed" | "interrupted" | "unknown")
}

fn hidden_with_detail(item: &Item, detail: &Value) -> bool {
    (item.kind == "tool" && hidden_child(item, detail))
        || (item.kind == "notice"
            && detail["source"] == "usage"
            && detail["child_id"].is_string()
            && detail["parent_item_id"].is_string())
        || (item.kind == "outcome" && matches!(item.status.as_str(), "completed" | "succeeded"))
}

pub fn hidden(item: &Item) -> bool {
    let detail: Value = serde_json::from_str(&item.detail).unwrap_or(Value::Null);
    hidden_with_detail(item, &detail)
}

pub fn expandable(item: &Item) -> bool {
    let detail: Value = serde_json::from_str(&item.detail).unwrap_or(Value::Null);
    (item.kind == "tool" && !hidden_child(item, &detail))
        || (item.kind == "notice" && detail["source"] == "thinking")
        || (usage_call(item) && !hidden_child(item, &detail))
}

pub fn usage_call(item: &Item) -> bool {
    let detail: Value = serde_json::from_str(&item.detail).unwrap_or(Value::Null);
    item.kind == "notice" && detail["source"] == "usage" && detail["usage_call"].is_object()
}

pub fn is_usage(item: &Item) -> bool {
    let detail: Value = serde_json::from_str(&item.detail).unwrap_or(Value::Null);
    item.kind == "notice"
        && detail["source"] == "usage"
        && !matches!(item.status.as_str(), "error" | "warning")
}

/// Format retained display evidence, without recomputing prices or token totals.
fn compact_usage(detail: &Value, width: usize) -> String {
    let source = detail["text"].as_str().unwrap_or("");
    let (header, measures) = source.split_once('\n').unwrap_or((source, ""));
    let fields: Vec<_> = measures.split(" · ").collect();
    let cost = fields
        .iter()
        .find_map(|s| s.strip_prefix("Cost: "))
        .unwrap_or("not reported");
    let model = detail["provider"]["model"]
        .as_str()
        .unwrap_or("model unknown");
    let model = match detail["provider"]["provider"].as_str() {
        Some(provider) if width >= 80 => format!("{provider}/{model}"),
        _ => model.to_owned(),
    };
    let cost = if cost == "not reported" {
        "cost unknown"
    } else {
        cost
    };
    let model = one_line(&model, width.saturating_sub(cost.width() + 14).max(4));
    let mut parts = vec!["▸ Usage".into(), model, cost.into()];
    if detail["usage_scope"] == "session" {
        parts.push("session-only".into());
    }
    if let Some(ms) = detail["duration_ms"]
        .as_f64()
        .filter(|n| n.is_finite() && *n >= 0.0)
    {
        parts.push(format!("{:.1}s", ms / 1000.0));
    }
    for field in &fields {
        if let Some(value) = field.strip_prefix("Input: ") {
            parts.push(format!("in {value}"));
        }
        if let Some(value) = field.strip_prefix("Output: ") {
            parts.push(format!("out {value}"));
        }
    }
    if let Some(basis) = detail["provider"]["basis"].as_str() {
        parts.push(basis.into());
    }
    // The original timestamp, not the time history was reopened.
    if let Some(stamp) = header.rsplit(" · ").next().filter(|s| s.contains(':')) {
        parts.push(stamp.split_once(' ').map_or(stamp, |(_, time)| time).into());
    }
    one_line(&parts.join(" · "), width)
}

/// Recognize the public todo schema only after observed successful execution.
/// Updates return counts, so validate those against the submitted replacement.
/// Unknown/truncated/failed results remain ordinary tools with exact evidence.
pub fn todo_rows(detail: &Value) -> Option<&Vec<Value>> {
    if detail["name"] != "todo"
        || detail["status"] != "succeeded"
        || detail["result"]["success"] != true
        || !detail["result"]["error"].is_null()
    {
        return None;
    }
    let output = &detail["result"]["output"];
    let rows = if let Some(rows) = output["todos"].as_array() {
        rows
    } else if detail["arguments"]["action"] == "update" && output["status"] == "updated" {
        detail["arguments"]["todos"].as_array()?
    } else {
        return None;
    };
    if rows.len() > 256
        || output["count"].as_u64()? != rows.len() as u64
        || !rows.iter().all(|r| {
            r["content"].is_string()
                && r["activeForm"].is_string()
                && matches!(
                    r["status"].as_str(),
                    Some("pending" | "in_progress" | "completed")
                )
        })
    {
        return None;
    }
    for (key, state) in [
        ("completed", "completed"),
        ("in_progress", "in_progress"),
        ("pending", "pending"),
    ] {
        if !output[key].is_null()
            && output[key].as_u64()
                != Some(rows.iter().filter(|r| r["status"] == state).count() as u64)
        {
            return None;
        }
    }
    Some(rows)
}

pub fn todo_checklist(rows: &[Value], width: usize) -> Vec<Line<'static>> {
    let mut lines = Vec::new();
    for row in rows {
        let (symbol, label, fg) = match row["status"].as_str() {
            Some("completed") => ("✓", "done", palette().muted),
            Some("in_progress") => ("→", "active", palette().green),
            _ => ("○", "pending", palette().muted),
        };
        let source = row["content"].as_str().unwrap_or("");
        let mut excerpt: String = source.chars().take(1024).collect();
        if excerpt.len() < source.len() {
            excerpt.push_str("… [Activity for full task]");
        }
        lines.extend(
            wrap(&format!("{symbol} [{label}] {}", safe(&excerpt)), width)
                .into_iter()
                .map(|s| {
                    Line::styled(
                        s,
                        if row["status"] == "in_progress" {
                            Style::default().fg(fg).add_modifier(Modifier::BOLD)
                        } else {
                            Style::default().fg(fg)
                        },
                    )
                }),
        );
    }
    lines
}

fn user_lines(source: &str, width: usize) -> Vec<Line<'static>> {
    use unicode_width::UnicodeWidthStr;
    let style = Style::default().fg(palette().ink).bg(palette().panel);
    let mut lines = vec![Line::styled(" ".repeat(width), style)];
    lines.extend(wrap(&safe(source), width).into_iter().map(|s| {
        let padding = width.saturating_sub(s.width());
        Line::styled(format!("{s}{}", " ".repeat(padding)), style)
    }));
    lines.push(Line::styled(" ".repeat(width), style));
    lines.push(Line::default());
    lines
}

pub fn ordinary_lines(item: &Item, width: usize) -> Vec<Line<'static>> {
    live_lines(item, width, None)
}

pub fn live_lines(item: &Item, width: usize, live_seconds: Option<f64>) -> Vec<Line<'static>> {
    let live_seconds =
        live_seconds.filter(|_| matches!(item.status.as_str(), "running" | "waiting"));
    let detail: Value = serde_json::from_str(&item.detail).unwrap_or(Value::Null);
    if hidden_with_detail(item, &detail) {
        return vec![];
    }
    if matches!(item.kind.as_str(), "user" | "correction") {
        let mut lines = user_lines(&item.text, width);
        if item.kind == "correction" {
            let label = match item.status.as_str() {
                "pending" => {
                    "Correction pending · waits for the next input boundary; Stop requests cancellation"
                }
                "applied" => "Correction applied",
                _ => "Correction unconfirmed · not retried or queued",
            };
            lines.extend(
                wrap(label, width)
                    .into_iter()
                    .map(|s| Line::styled(s, Style::default().fg(palette().muted))),
            );
            lines.push(Line::default());
        }
        return lines;
    }
    if item.kind == "question" && detail["answers"].is_object() {
        let mut lines = Vec::new();
        for question in detail["questions"].as_array().unwrap_or(&vec![]) {
            lines.extend(
                wrap(question["question"].as_str().unwrap_or("Question"), width)
                    .into_iter()
                    .map(|s| Line::styled(s, Style::default().fg(palette().muted))),
            );
            let answer = &detail["answers"][question["id"].as_str().unwrap_or("")];
            lines.extend(user_lines(
                answer["option"]
                    .as_str()
                    .or(answer["text"].as_str())
                    .unwrap_or(""),
                width,
            ));
        }
        return lines;
    }
    if item.kind == "tool" {
        // Child details live under Activity; failures must still surface at root.
        if hidden_child(item, &detail) {
            return vec![];
        }
        if let Some(todos) = todo_rows(&detail) {
            let done = todos.iter().filter(|r| r["status"] == "completed").count();
            let active = todos
                .iter()
                .filter(|r| r["status"] == "in_progress")
                .count();
            let pending = todos.len() - done - active;
            let mut rows = vec![Line::styled(
                one_line(
                    &format!(
                        "▸ Todo · {done}/{} done · {active} active · {pending} pending",
                        todos.len()
                    ),
                    width,
                ),
                Style::default().fg(palette().green),
            )];
            if let Some(row) = todos.iter().find(|r| r["status"] == "in_progress") {
                rows.push(Line::styled(
                    one_line(
                        &format!("→ {}", row["activeForm"].as_str().unwrap_or("")),
                        width,
                    ),
                    Style::default()
                        .fg(palette().green)
                        .add_modifier(Modifier::BOLD),
                ));
            } else if let Some(row) = todos.iter().find(|r| r["status"] == "pending") {
                rows.push(Line::styled(
                    one_line(
                        &format!("Next: {}", row["content"].as_str().unwrap_or("")),
                        width,
                    ),
                    Style::default().fg(palette().muted),
                ));
            }
            rows.push(Line::default());
            return rows;
        }
        let name = detail["name"]
            .as_str()
            .unwrap_or_else(|| item.text.lines().next().unwrap_or("Tool"));
        let target = [
            "command",
            "file_path",
            "path",
            "pattern",
            "query",
            "agent",
            "skill_name",
            "operation",
            "instruction",
        ]
        .iter()
        .find_map(|key| detail["arguments"][key].as_str())
        .unwrap_or("");
        let task = detail["arguments"]["instruction"].as_str().unwrap_or("");
        if let Some(children) = detail["child_progress"]
            .as_array()
            .filter(|rows| !rows.is_empty())
        {
            let warnings = if detail["child_totals"].is_object() {
                child_badges(std::slice::from_ref(&detail["child_totals"]))
            } else {
                child_badges(children)
            };
            let child_count = detail["child_count"]
                .as_u64()
                .unwrap_or(children.len() as u64);
            let label = if child_count == 1 {
                children[0]["agent"].as_str().unwrap_or(name).to_string()
            } else {
                format!("{child_count} agents")
            };
            let mut parts = Vec::new();
            let title = if child_count == 1 {
                children[0]["task_title"]
                    .as_str()
                    .filter(|s| !s.is_empty())
                    .map(str::to_owned)
            } else if children
                .iter()
                .any(|row| row["task_title"].as_str().is_some())
            {
                Some(format!("{child_count} tasks"))
            } else {
                None // Saved older observations keep their original preview.
            };
            if width < 80 {
                let name = label.rsplit(':').next().unwrap_or(&label);
                parts.push(if (width < 36 || title.is_some()) && name.contains('#') {
                    format!("#{}", name.rsplit('#').next().unwrap_or(name))
                } else {
                    name.to_string()
                });
                parts.extend(
                    children
                        .iter()
                        .filter_map(current_activity)
                        .map(|s| s.replace(" · running", "")),
                );
                return vec![
                    action_row(
                        title.as_deref().unwrap_or(action_name(name)),
                        &item.status,
                        &warnings,
                        &parts,
                        width,
                    ),
                    Line::default(),
                ];
            }
            parts.push(format!("{name} · {label}"));
            let calls: u64 = detail["child_calls"].as_u64().unwrap_or_else(|| {
                children
                    .iter()
                    .map(|r| r["calls"].as_u64().unwrap_or(0))
                    .sum()
            });
            parts.push(if children.iter().all(|r| r["calls"].as_u64().is_some()) {
                format!("{calls} calls")
            } else {
                "calls unavailable".into()
            });
            if let Some(omitted) = detail["child_progress_omitted"].as_u64().filter(|n| *n > 0) {
                parts.push(format!("{omitted} earlier in Activity"));
            }
            if let Some(cost) = detail["child_cost_display"].as_str() {
                parts.push(format!(
                    "{}{}",
                    cost,
                    if detail["child_cost_partial"] == true {
                        " (partial)"
                    } else {
                        ""
                    }
                ));
            } else if calls > 0 {
                parts.push("cost unavailable".into());
            }
            let elapsed = children
                .iter()
                .filter_map(|r| r["elapsed_seconds"].as_f64())
                .fold(live_seconds.unwrap_or(0.0), f64::max);
            if elapsed > 0.0 {
                parts.push(elapsed_label(elapsed));
            }
            if title.is_none() && width >= 100 && !task.is_empty() {
                parts.push(one_line(task, 30));
            }
            parts.extend(children.iter().filter_map(current_activity));
            return vec![
                action_row(
                    title.as_deref().unwrap_or(action_name(name)),
                    &item.status,
                    &warnings,
                    &parts,
                    width,
                ),
                Line::default(),
            ];
        }
        let target = if !task.is_empty() { task } else { target };
        let mut metadata = Vec::new();
        if matches!(item.status.as_str(), "failed" | "error") {
            let error = &detail["result"]["error"];
            if let Some(reason) = error
                .as_str()
                .or(error["message"].as_str())
                .or(detail["error"].as_str())
            {
                metadata.push(one_line(reason, 60));
            }
        }
        metadata.push(target.into());
        return vec![
            action_row(action_name(name), &item.status, &[], &metadata, width),
            Line::default(),
        ];
    }
    let projected = item.text.clone();
    if item.kind == "notice" && !matches!(item.status.as_str(), "error" | "warning") {
        match detail["source"].as_str() {
            Some("thinking") => {
                let source = detail["text"].as_str().unwrap_or(&item.text);
                let excerpt: String = source.chars().take(1024).collect();
                let first = markdown::render(&excerpt, width.max(1))
                    .into_iter()
                    .map(|line| line.to_string())
                    .find(|line| !line.trim().is_empty())
                    .unwrap_or_default();
                return vec![
                    Line::styled(
                        one_line(&format!("▸ Thinking · {first}"), width),
                        Style::default().fg(palette().muted),
                    ),
                    Line::default(),
                ];
            }
            Some("usage") => {
                if usage_call(item) {
                    return vec![
                        Line::styled(
                            compact_usage(&detail, width),
                            Style::default().fg(palette().muted),
                        ),
                        Line::default(),
                    ];
                }
                let source = detail["text"].as_str().unwrap_or("");
                let mut rows: Vec<_> = wrap(source, width)
                    .into_iter()
                    .map(|line| Line::styled(line, Style::default().fg(palette().muted)))
                    .collect();
                rows.push(Line::default());
                return rows;
            }
            _ => (),
        }
    }
    let mut rows: Vec<_> = item_lines(&item.kind, &projected, &item.status, width, false)
        .into_iter()
        .map(|(text, fg)| Line::styled(safe(&text), Style::default().fg(fg)))
        .collect();
    if !rows.is_empty() {
        rows.push(Line::default());
    }
    rows
}

pub fn one_line(source: &str, width: usize) -> String {
    use unicode_segmentation::UnicodeSegmentation;
    use unicode_width::UnicodeWidthStr;
    let source = safe(source)
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ");
    if source.width() <= width {
        return source;
    }
    let mut text = String::new();
    for glyph in source.graphemes(true) {
        if text.width() + glyph.width() + 1 > width {
            break;
        }
        text.push_str(glyph);
    }
    text.push('…');
    text
}

/// Presentation vocabulary only: unknown ecosystem tools retain their own name.
fn action_name(name: &str) -> &str {
    match name {
        "read_file" => "Read",
        "grep" => "Search",
        "glob" => "List files",
        "bash" => "Run",
        "write_file" => "Write",
        "edit_file" => "Edit",
        "apply_patch" => "Patch",
        "load_skill" => "Load skill",
        "delegate" => "Delegate",
        "todo" => "Tasks",
        _ => name,
    }
}

/// Reserve state and the leading warning before shortening a task title. The raw
/// evidence is untouched. Spans carry roles through clipping and paint-time motion.
fn action_row(
    title: &str,
    status: &str,
    badges: &[(String, Color)],
    metadata: &[String],
    width: usize,
) -> Line<'static> {
    let state = match status {
        "interrupted" if width < 40 => "stopped",
        "succeeded" | "completed" => "done",
        "running" | "waiting" | "failed" | "error" | "interrupted" | "cancelled" | "stopping"
        | "stopped" | "unknown" => status,
        _ => "unknown",
    };
    let muted = Style::default().fg(palette().muted);
    let reserved = state.width()
        + 6
        + badges.first().map_or(0, |(s, _)| s.width() + 3)
        + if badges.is_empty() {
            metadata
                .first()
                .filter(|s| s.starts_with('#'))
                .map_or(0, |s| s.width() + 3)
        } else {
            0
        };
    let title_width = width.saturating_sub(reserved).clamp(1, 48);
    let mut spans = vec![
        Span::styled("▸ ", muted),
        Span::styled(
            one_line(title, title_width),
            Style::default()
                .fg(palette().green)
                .add_modifier(Modifier::BOLD),
        ),
        Span::styled(" · ", muted),
        Span::styled(
            state.to_owned(),
            Style::default().fg(color(if state == "done" { "completed" } else { state })),
        ),
    ];
    for (text, fg) in badges {
        spans.push(Span::styled(" · ", muted));
        spans.push(Span::styled(text.clone(), Style::default().fg(*fg)));
    }
    for text in metadata.iter().filter(|s| !s.is_empty()) {
        spans.push(Span::styled(" · ", muted));
        spans.push(Span::styled(one_line(text, width), muted));
    }
    clip_spans(spans, width)
}

fn clip_spans(spans: Vec<Span<'static>>, width: usize) -> Line<'static> {
    use unicode_segmentation::UnicodeSegmentation;
    let clipped = spans.iter().map(Span::width).sum::<usize>() > width;
    let mut remaining = width.saturating_sub(usize::from(clipped));
    let mut output = Vec::new();
    'spans: for span in spans {
        let mut text = String::new();
        for glyph in span.content.graphemes(true) {
            if glyph.width() > remaining {
                output.push(Span::styled(text, span.style));
                break 'spans;
            }
            remaining -= glyph.width();
            text.push_str(glyph);
        }
        output.push(Span::styled(text, span.style));
    }
    if clipped && width > 0 {
        output.push(Span::styled("…", Style::default().fg(palette().muted)));
    }
    Line::from(output)
}

/// Only completed top-level Markdown blocks are immutable while streaming.
/// Blank lines inside fenced code, lists or tables are not independent blocks.
fn stable_end(source: &str) -> usize {
    use pulldown_cmark::{Options, Parser};
    let mut depth = 0usize;
    let mut end = 0;
    for (event, range) in Parser::new_ext(source, Options::all()).into_offset_iter() {
        match event {
            pulldown_cmark::Event::Start(_) => depth += 1,
            pulldown_cmark::Event::End(_) => {
                depth = depth.saturating_sub(1);
                if depth == 0 && source[range.end..].starts_with('\n') {
                    end = range.end;
                }
            }
            _ => (),
        }
    }
    end
}

impl Journal {
    pub fn begin_replay(&mut self, count: usize) -> usize {
        let skip = count.saturating_sub(MAX_REPLAY_ITEMS);
        if skip > 0 {
            self.rows.push_back(Line::styled(
                format!("Showing latest {MAX_REPLAY_ITEMS} of {count} historical items. Transcript / Export retains full source."),
                Style::default().fg(palette().amber),
            ));
        }
        skip
    }
    pub fn banner(&mut self, title: &str, mode: &str) {
        if !self.banner {
            self.rows.push_back(Line::styled(
                format!(
                    "amplifier · {}{}",
                    safe(title),
                    chrome::runtime_notice(mode)
                ),
                Style::default().fg(palette().green),
            ));
            self.rows.push_back(Line::default());
            self.banner = true;
        }
    }

    pub fn reset(&mut self) {
        // Switching is idle-only. Preserve any queued output from the prior identity.
        self.finish();
        let mut rows = std::mem::take(&mut self.rows);
        while !self.dirty.is_empty() {
            self.prepare(80);
            rows.append(&mut self.rows);
        }
        self.rows = rows;
        self.pending.clear();
        self.order.clear();
        self.dirty.clear();
        self.indices.clear();
        self.emitted.clear();
        self.active.clear();
        self.banner = false;
        self.separator_tail = false;
    }

    pub fn observe(&mut self, item: &Item, complete: bool) {
        if self.skip_replay_item {
            return;
        }
        let signature = fingerprint(item);
        if self.emitted.get(&item.id) == Some(&signature) {
            return;
        }
        let index = *self.indices.entry(item.id.clone()).or_insert_with(|| {
            self.order.push(item.id.clone());
            self.order.len() - 1
        });
        let entry = self
            .pending
            .entry(item.id.clone())
            .or_insert_with(|| Pending {
                item: item.clone(),
                offset: 0,
                heading: false,
                complete,
            });
        if !item.text.starts_with(&entry.item.text[..entry.offset]) {
            // A genuine source revision cannot rewrite terminal history. Label it.
            self.rows.push_back(Line::styled(
                "Updated source follows",
                Style::default().fg(palette().amber),
            ));
            entry.offset = 0;
            entry.heading = false;
        }
        entry.item = item.clone();
        entry.complete =
            complete && !matches!(item.status.as_str(), "running" | "waiting" | "pending");
        self.active.insert(index);
        self.dirty.insert(index);
    }

    pub fn finish(&mut self) {
        for entry in self.pending.values_mut() {
            entry.complete = true;
        }
        self.dirty
            .extend(self.pending.keys().map(|id| self.indices[id]));
    }

    pub fn prepare(&mut self, width: usize) {
        // Bounded dirty-item work, not a full-history walk on every key/token.
        for _ in 0..32 {
            if self.rows.len() >= 128 {
                break;
            }
            let Some(index) = self.active.first().copied() else {
                break;
            };
            self.dirty.remove(&index);
            let id = &self.order[index];
            let Some(entry) = self.pending.get_mut(id) else {
                continue;
            };
            let item = &entry.item;
            if hidden(item) {
                self.emitted.insert(id.clone(), fingerprint(item));
                self.pending.remove(id);
                self.active.remove(&index);
                continue;
            }
            if self.separator_tail && (entry.complete || item.kind == "assistant") {
                if !is_usage(item) {
                    self.rows.push_back(Line::default());
                }
                self.separator_tail = false;
            }
            if item.kind == "assistant" {
                let rest = &item.text[entry.offset..];
                let end = if entry.complete {
                    rest.len()
                } else {
                    stable_end(rest)
                };
                if end == 0 && !entry.complete {
                    break;
                }
                entry.heading = true;
                self.rows.extend(markdown::render(&rest[..end], width));
                entry.offset += end;
                if self.rows.back().is_some_and(|line| line.width() != 0) {
                    self.rows.push_back(Line::default());
                }
                if !entry.complete {
                    break;
                }
            } else if entry.complete {
                let mut lines = ordinary_lines(item, width);
                // Defer activity spacing until the next visible item is known.
                // Once written to terminal history a blank cannot be taken back.
                self.separator_tail = lines.last().is_some_and(|line| line.width() == 0);
                if self.separator_tail {
                    lines.pop();
                }
                self.rows.extend(lines);
            } else {
                break;
            }
            self.emitted.insert(id.clone(), fingerprint(item));
            self.pending.remove(id);
            self.active.remove(&index);
        }
    }

    fn live(&self, width: usize, clocks: &ActivityClocks) -> Vec<Line<'static>> {
        let mut lines = Vec::new();
        // Replay drains in bounded batches above the live projection. Start
        // at the first unfinished item, so replay cannot hide new work and
        // completed history is not laid out again on every input or delta.
        let Some(start) = self
            .active
            .iter()
            .find(|index| !self.pending[&self.order[**index]].complete)
        else {
            return lines;
        };
        // Active items only. Completed history is owned by the terminal.
        let mut separator = self.separator_tail;
        for index in self.active.range(*start..) {
            let Some(p) = self.pending.get(&self.order[*index]) else {
                continue;
            };
            if hidden(&p.item) {
                continue;
            }
            if separator && !is_usage(&p.item) {
                lines.push(Line::default());
            }
            separator = false;
            if p.item.kind == "assistant" {
                lines.extend(markdown::render_live(&p.item.text[p.offset..], width));
                if lines.last().is_some_and(|line| line.width() != 0) {
                    lines.push(Line::default());
                }
            } else {
                let mut rows = live_lines(&p.item, width, clocks.seconds(&p.item.id));
                separator = rows.last().is_some_and(|line| line.width() == 0);
                if separator {
                    rows.pop();
                }
                lines.extend(rows);
            }
        }
        while lines
            .last()
            .is_some_and(|l| l.to_string().trim().is_empty())
        {
            lines.pop();
        }
        lines
    }

    pub fn has_work(&self) -> bool {
        !self.rows.is_empty()
            || self
                .active
                .first()
                .is_some_and(|index| self.dirty.contains(index))
    }
}

fn draw_interactive(f: &mut Frame, app: &mut App) {
    let area = f.area();
    f.render_widget(
        Block::default().style(Style::default().bg(palette().bg).fg(palette().ink)),
        area,
    );
    app.ui.buttons.clear();
    app.rows.clear();
    let meter = work_rows(app, area.width as usize);
    let meter_h = (meter.len() as u16).max(1);
    let chrome = chrome::Chrome::new(app, area.width, area.height.saturating_sub(meter_h + 1));
    if area.width < 32 || area.height < chrome.height + meter_h + 1 {
        return;
    }
    app.resize_transcript(area.width);
    app.body = Rect::new(
        0,
        1,
        area.width,
        area.height.saturating_sub(chrome.height + meter_h + 1),
    );
    text(
        f,
        Rect::new(0, 0, area.width, 1),
        if area.width < 60 {
            "Interact · Enter expand · Esc"
        } else {
            "Interact · click or ↑/↓ Enter · Esc returns native copy"
        },
        palette().green,
    );
    for (row, (index, line)) in app.transcript_rows().into_iter().enumerate() {
        let y = app.body.y + row as u16;
        let label = line.to_string();
        if label.starts_with("[ Activity:") {
            app.button(
                f,
                Rect::new(0, y, area.width, 1),
                label,
                Action::Inspect("activity_tree".into(), Some(app.items[index].id.clone())),
            );
        } else {
            if label.starts_with('▸') {
                app.rows.push((y, index));
            }
            let line = activity::tool_line(line, activity::running(app));
            let line = if index == app.selected && label.starts_with('▸') {
                line.style(Style::default().fg(palette().green))
            } else {
                line
            };
            text(f, Rect::new(0, y, area.width, 1), line, palette().ink);
        }
    }
    let base = area.height - chrome.height;
    for (row, line) in meter.iter().enumerate() {
        f.render_widget(
            Paragraph::new(line.clone()),
            Rect::new(0, base - meter_h + row as u16, area.width, 1),
        );
    }
    if app.approval.is_some() {
        app.button(
            f,
            Rect::new(0, base - meter_h, area.width, 1),
            format!(
                "{} [ Review decision ]",
                meter
                    .first()
                    .map(ToString::to_string)
                    .unwrap_or_else(|| "● Waiting".into())
            ),
            Action::Decisions,
        );
    } else if !app.questions.pending.is_empty() {
        app.button(
            f,
            Rect::new(0, base - meter_h, area.width, 1),
            format!(
                "{} [ Answer question ]",
                meter
                    .first()
                    .map(ToString::to_string)
                    .unwrap_or_else(|| "● Waiting".into())
            ),
            Action::Questions,
        );
    }
    chrome.draw(f, app, Rect::new(0, base, area.width, chrome.height));
}

type Tty = Terminal<CrosstermBackend<io::Stdout>>;
static ALTERNATE_OWNED: AtomicBool = AtomicBool::new(false);

// Called only on the UI/input thread, outside Crossterm polling. All bytes go
// back through its parser (including partial Unicode/paste and internal CPRs).
#[cfg(unix)]
fn bounded_cursor_row() -> io::Result<Option<u16>> {
    use std::fs::OpenOptions;
    use std::io::Read;
    use std::os::fd::AsRawFd;
    use std::os::unix::fs::OpenOptionsExt;
    static SILENT: AtomicBool = AtomicBool::new(false);
    if SILENT.load(Ordering::Relaxed) {
        return Ok(None);
    }
    let mut input = OpenOptions::new()
        .read(true)
        .custom_flags(libc::O_NONBLOCK | libc::O_NOCTTY)
        .open("/dev/tty")?;
    write!(io::stdout(), "\x1b[6n")?;
    io::stdout().flush()?;
    let deadline = Instant::now() + Duration::from_millis(100);
    let mut bytes = Vec::new();
    let result = (|| -> io::Result<Option<u16>> {
        loop {
            if let Some(row) = reported_cursor_row(&bytes) {
                return Ok(Some(row));
            }
            if Instant::now() >= deadline || bytes.len() >= 65536 {
                return Ok(None);
            }
            let mut fd = libc::pollfd {
                fd: input.as_raw_fd(),
                events: libc::POLLIN,
                revents: 0,
            };
            let timeout = deadline
                .saturating_duration_since(Instant::now())
                .as_millis()
                .max(1) as i32;
            // SAFETY: fd points to one live pollfd for this call; input owns the descriptor.
            let ready = unsafe { libc::poll(&mut fd, 1, timeout) };
            if ready < 0 {
                let error = io::Error::last_os_error();
                if error.kind() == io::ErrorKind::Interrupted {
                    continue;
                }
                return Err(error);
            }
            if ready == 0 {
                return Ok(None);
            }
            let mut chunk = [0; 4096];
            match input.read(&mut chunk) {
                Ok(0) => return Ok(None),
                Ok(n) => bytes.extend_from_slice(&chunk[..n]),
                Err(error)
                    if matches!(
                        error.kind(),
                        io::ErrorKind::WouldBlock | io::ErrorKind::Interrupted
                    ) =>
                {
                    continue;
                }
                Err(error) => return Err(error),
            }
        }
    })();
    event::buffer_input(&bytes)?;
    if matches!(result, Ok(None)) {
        // Do not mistake a late response for a later query's anchor.
        SILENT.store(true, Ordering::Relaxed);
    }
    result
}

#[cfg(not(unix))]
fn bounded_cursor_row() -> io::Result<Option<u16>> {
    cursor::position().map(|(_, row)| Some(row))
}

fn reported_cursor_row(bytes: &[u8]) -> Option<u16> {
    let mut paste = false;
    for at in 0..bytes.len() {
        let suffix = &bytes[at..];
        if suffix.starts_with(b"\x1b[200~") {
            paste = true;
        }
        if suffix.starts_with(b"\x1b[201~") {
            paste = false;
        }
        if paste || !suffix.starts_with(b"\x1b[") {
            continue;
        }
        let end = suffix[2..]
            .iter()
            .position(|c| !c.is_ascii_digit() && *c != b';')?
            + 2;
        if suffix[end] != b'R' {
            continue;
        }
        let text = std::str::from_utf8(&suffix[2..end]).ok()?;
        let Some((row, col)) = text.split_once(';') else {
            continue;
        };
        if let (Ok(row), Ok(col)) = (row.parse::<u16>(), col.parse::<u16>())
            && row > 0
            && col > 0
        {
            return Some(row - 1);
        }
    }
    None
}

pub struct Screen {
    terminal: Tty,
    area: Rect,
    size: (u16, u16),
    alternate: bool,
    primary_size: (u16, u16),
}

impl Screen {
    pub fn new() -> io::Result<Self> {
        tty::enable_raw_mode()?;
        // Install cleanup before any fallible terminal initialization.
        let old = std::panic::take_hook();
        std::panic::set_hook(Box::new(move |info| {
            restore();
            old(info);
        }));
        let result = (|| {
            execute!(
                io::stdout(),
                EnableBracketedPaste,
                EnableFocusChange,
                DisableMouseCapture
            )?;
            let size = tty::size()?;
            // Only rows ABOVE the shell's cursor are prior output. Scroll those
            // rows into history, not a full page of unused space below the prompt.
            // A silent terminal conservatively starts at the bottom; without a
            // trustworthy position we cannot erase the preceding screen.
            let launch_row = bounded_cursor_row()?;
            let row = launch_row
                .unwrap_or(size.1.saturating_sub(1))
                .min(size.1.saturating_sub(1));
            execute!(
                io::stdout(),
                ResetColor,
                cursor::MoveTo(0, size.1.saturating_sub(1))
            )?;
            if launch_row.is_some() {
                for _ in 0..row {
                    write!(io::stdout(), "\r\n")?;
                }
            } else {
                // We do not know whether the bottom row contains prior output.
                // Allocate one fresh row before taking ownership of it.
                write!(io::stdout(), "\r\n")?;
            }
            let origin = if launch_row.is_some() { 0 } else { row };
            execute!(io::stdout(), cursor::MoveTo(0, origin))?;
            let area = Rect::new(0, origin, size.0, 1);
            let terminal = Terminal::with_options(
                CrosstermBackend::new(io::stdout()),
                TerminalOptions {
                    viewport: Viewport::Fixed(area),
                },
            )?;
            Ok(Self {
                terminal,
                area,
                size,
                alternate: false,
                primary_size: size,
            })
        })();
        if result.is_err() {
            restore();
        }
        result
    }

    fn clear_live(&mut self) -> io::Result<()> {
        // tmux can archive a whole screen when ED starts at row zero. Erase
        // individual owned lines so a provisional full-height frame isn't history.
        let mut out = io::stdout();
        queue!(out, ResetColor)?;
        for y in self.area.y..self.size.1 {
            queue!(
                out,
                cursor::MoveTo(0, y),
                tty::Clear(tty::ClearType::CurrentLine)
            )?;
        }
        execute!(out, cursor::MoveTo(0, self.area.y))
    }

    fn resize(&mut self) -> io::Result<()> {
        let size = tty::size()?;
        if size != self.size {
            if !self.alternate {
                // Cursor is parked at the live region's origin after every frame.
                // Ask the terminal where resize/reflow moved it; never clear history.
                // Without a reply, resized/reflowed rows have uncertain ownership.
                // Preserve them and allocate one fresh bottom row, never a page.
                let observed = bounded_cursor_row()?;
                let y = if let Some(y) = observed {
                    y
                } else {
                    execute!(
                        io::stdout(),
                        ResetColor,
                        cursor::MoveTo(0, size.1.saturating_sub(1))
                    )?;
                    write!(io::stdout(), "\r\n")?;
                    size.1.saturating_sub(1)
                };
                self.area.y = y.min(size.1.saturating_sub(1));
            }
            self.size = size;
        }
        Ok(())
    }

    pub fn paint(&mut self, app: &mut App) -> io::Result<()> {
        self.resize()?;
        let inspect = app.view != 0
            || app.interacting
            || app.expanded
            || app.ui.menu.is_some()
            || app.flow.prompt.is_some()
            || app.flow.quit_confirmation.is_some()
            || app.anchors[0].is_some()
            || app.selection.start.is_some();
        if inspect && !self.alternate {
            self.primary_size = self.size;
            ALTERNATE_OWNED.store(true, Ordering::SeqCst);
            execute!(io::stdout(), tty::EnterAlternateScreen, EnableMouseCapture)?;
            self.alternate = true;
            self.terminal = Terminal::new(CrosstermBackend::new(io::stdout()))?;
            // Fresh buffers and the whole alternate screen are ours. Ratatui's
            // clear() saves the cursor via CPR; silent PTYs cannot answer it.
            execute!(
                io::stdout(),
                tty::Clear(tty::ClearType::All),
                cursor::MoveTo(0, 0)
            )?;
        } else if !inspect && self.alternate {
            self.leave_inspection()?;
        }
        if self.alternate {
            self.terminal.draw(|f| {
                if app.interacting
                    && app.view == 0
                    && app.ui.menu.is_none()
                    && app.flow.prompt.is_none()
                    && app.flow.quit_confirmation.is_none()
                    && !app.expanded
                {
                    draw_interactive(f, app);
                } else {
                    draw(f, app);
                }
            })?;
            return Ok(());
        }
        let width = self.size.0.max(1);
        app.native.prepare(width as usize);
        execute!(io::stdout(), tty::BeginSynchronizedUpdate)?;
        let result = self.paint_inline(app, width);
        let end = execute!(io::stdout(), tty::EndSynchronizedUpdate);
        result.and(end)
    }

    fn append(&mut self, rows: impl Iterator<Item = Line<'static>>) -> io::Result<()> {
        self.clear_live()?;
        let width = self.size.0.max(1);
        for line in rows {
            // Reflow queued rows after a resize; never re-emit committed rows.
            for line in markdown::reflow(vec![line], width as usize) {
                let rect = Rect::new(0, self.area.y, self.size.0, 1);
                let mut buffer = Buffer::empty(rect);
                Paragraph::new(line)
                    .style(Style::default().bg(palette().bg))
                    .render(Rect::new(0, rect.y, width, 1), &mut buffer);
                let empty = Buffer::empty(rect);
                self.terminal
                    .backend_mut()
                    .draw(empty.diff(&buffer).into_iter())?;
                execute!(io::stdout(), ResetColor, cursor::MoveTo(0, rect.y))?;
                write!(io::stdout(), "\r\n")?;
                self.area.y = (self.area.y + 1).min(self.size.1.saturating_sub(1));
            }
        }
        Ok(())
    }

    fn paint_inline(&mut self, app: &mut App, width: u16) -> io::Result<()> {
        let appended = !app.native.rows.is_empty();
        if !app.native.rows.is_empty() {
            let n = app.native.rows.len().min(128);
            self.append(app.native.rows.drain(..n))?;
        }
        let mut live: Vec<_> = app
            .native
            .live(width as usize, &app.flow.clocks)
            .into_iter()
            .map(|line| activity::tool_line(line, activity::running(app)))
            .collect();
        if !app.background.is_empty() && !app.disconnected {
            live.push(activity::line(
                &format!("● {}…", app.background),
                activity::running(app),
            ));
        }
        let decision = app.approval.is_some() || !app.questions.pending.is_empty();
        let meter = work_rows(app, width as usize);
        let meter_h = meter.len() as u16;
        let extra = if !decision {
            0
        } else if self.size.1 < 18 && meter_h > 1 {
            1
        } else {
            3
        };
        let chrome =
            chrome::Chrome::new(app, width, self.size.1.saturating_sub(extra + meter_h + 1));
        let available = self.size.1.saturating_sub(chrome.height + extra + 1) as usize;
        if app.flow.busy {
            // Prefer the last actual task over blank padding on tiny screens.
            // Committed history is unchanged; this only sizes the mutable tail.
            while live.last().is_some_and(|line| line.width() == 0) {
                live.pop();
            }
            if !live.is_empty() && live.len() + meter.len() < available {
                live.push(Line::default());
            }
            live.extend(meter);
        }
        let live_h = live.len().min(available) as u16;
        if live.len() > live_h as usize && live_h > 0 && meter_h > 0 && live_h <= meter_h + 1 {
            // At the smallest size, preserve the last task as well as metrics.
            // An omission banner would consume the only remaining task row.
            // Put its upward history cue on the meter instead.
            live.drain(..live.len() - live_h as usize);
            let meter_start = live_h.saturating_sub(meter_h) as usize;
            let first = live[meter_start].to_string().replacen('●', "↑", 1);
            live[meter_start] = activity::line(&first, activity::running(app));
        } else if live.len() > live_h as usize && live_h > 0 {
            let omitted = live.len() - live_h as usize + 1;
            live.drain(..omitted);
            live.insert(
                0,
                Line::styled(
                    format!("↑ {omitted} earlier rows · Activity"),
                    Style::default().fg(palette().muted),
                ),
            );
        }
        let height = (chrome.height + extra + live_h + 1)
            .max(self.size.1.saturating_sub(self.area.y))
            .min(self.size.1)
            .max(1);
        if self.area.height != height || self.area.width != self.size.0 {
            self.clear_live()?;
        }
        let scroll = (self.area.y + height).saturating_sub(self.size.1);
        if scroll > 0 {
            self.clear_live()?;
            execute!(
                io::stdout(),
                cursor::MoveTo(0, self.size.1.saturating_sub(1))
            )?;
            for _ in 0..scroll {
                write!(io::stdout(), "\r\n")?;
            }
            self.area.y = self.area.y.saturating_sub(scroll);
        }
        self.area.width = self.size.0;
        self.area.height = height;
        if appended || self.terminal.get_frame().area() != self.area {
            self.terminal = Terminal::with_options(
                CrosstermBackend::new(io::stdout()),
                TerminalOptions {
                    viewport: Viewport::Fixed(self.area),
                },
            )?;
        }
        self.terminal.draw(|f| {
            let a = f.area();
            app.ui.buttons.clear();
            app.rows.clear();
            if a.width < 32 || a.height < chrome.height + extra + 1 {
                text(f, a, "Please resize to at least 32 × 12", palette().amber);
                return;
            }
            // Park on a genuinely empty separator, not a wide border that tmux
            // can reflow onto a continuation row. This row is live, not history.
            f.render_widget(
                Block::default().style(Style::default().bg(palette().bg).fg(palette().ink)),
                a,
            );
            app.body = Rect::new(0, a.y + 1, width, live_h);
            for (row, line) in live
                .iter()
                .rev()
                .take(live_h as usize)
                .collect::<Vec<_>>()
                .into_iter()
                .rev()
                .enumerate()
            {
                text(
                    f,
                    Rect::new(0, a.y + 1 + row as u16, width, 1),
                    line.clone(),
                    palette().ink,
                );
            }
            let base = a.bottom().saturating_sub(chrome.height + extra);
            if app.items.is_empty() && base > a.y + 6 {
                let welcome = "What would you like to accomplish?\n\nDescribe a task, paste text, or open Actions for files, tools and help.\nYour draft stays yours until you send it.";
                for (i, line) in wrap(welcome, width as usize).into_iter()
                    .take(base.saturating_sub(a.y + 2) as usize).enumerate() {
                    text(f, Rect::new(0, a.y + 3 + i as u16, width, 1), line,
                        if i == 0 { palette().ink } else { palette().muted });
                }
            }
            if decision {
                let (label, prompt, action) = if let Some(approval) = &app.approval {
                    (
                        "[ Review decision ]",
                        safe(&string(approval, "command")),
                        Action::Decisions,
                    )
                } else {
                    let (id, q) = app.questions.pending.iter().next().unwrap();
                    (
                        "[ Answer question ]",
                        safe(&string(&q["questions"][0], "question")),
                        Action::QuestionOpen(id.clone()),
                    )
                };
                if extra == 3 {
                    text(
                        f,
                        Rect::new(0, base, width, 1),
                        "Waiting for you · draft stays yours",
                        palette().amber,
                    );
                    text(f, Rect::new(0, base + 1, width, 1), prompt, palette().ink);
                }
                app.button(f, Rect::new(0, base + extra - 1, width.min(28), 1), label, action);
            }
            let base = base + extra;
            app.tab_y = u16::MAX;
            chrome.draw(f, app, Rect::new(0, base, width, chrome.height));
            if decision {
                // Tab starts at Actions; the explicit decision remains reachable.
                app.ui.buttons.rotate_left(1);
            }
        })?;
        // A stable cursor anchor lets the terminal tell us where reflow moved the live region.
        execute!(io::stdout(), cursor::MoveTo(0, self.area.y), cursor::Hide)?;
        io::stdout().flush()
    }

    fn leave_inspection(&mut self) -> io::Result<()> {
        execute!(io::stdout(), DisableMouseCapture, tty::LeaveAlternateScreen)?;
        ALTERNATE_OWNED.store(false, Ordering::SeqCst);
        self.alternate = false;
        // DEC 1049 restores primary output. A changed size needs the actual
        // restored anchor: subtracting the old (possibly full-height) live area
        // can clear committed short replies. Ordinary return/exit needs no query.
        if self.size != self.primary_size {
            self.size = self.primary_size;
            self.resize()?;
        }
        self.terminal = Terminal::with_options(
            CrosstermBackend::new(io::stdout()),
            TerminalOptions {
                viewport: Viewport::Fixed(self.area),
            },
        )?;
        Ok(())
    }

    pub fn finish(&mut self, app: &mut App) -> io::Result<()> {
        if self.alternate {
            self.leave_inspection()?;
        }
        self.resize()?;
        app.native.finish();
        while app.native.has_work() {
            app.native.prepare(self.size.0.max(1) as usize);
            let rows = std::mem::take(&mut app.native.rows);
            self.append(rows.into_iter())?;
        }
        self.clear_live()?;
        io::stdout().flush()
    }

    pub fn external_editor(&mut self, app: &mut App) -> io::Result<()> {
        if self.alternate {
            self.leave_inspection()?;
        }
        self.primary_size = self.size;
        ALTERNATE_OWNED.store(true, Ordering::SeqCst);
        execute!(
            io::stdout(),
            tty::EnterAlternateScreen,
            DisableBracketedPaste,
            DisableFocusChange,
            DisableMouseCapture,
            cursor::Show
        )?;
        self.alternate = true;
        tty::disable_raw_mode()?;
        let result = crate::external_editor::edit(&app.draft.lines().join("\n"));
        tty::enable_raw_mode()?;
        execute!(io::stdout(), EnableBracketedPaste, EnableFocusChange)?;
        self.size = tty::size()?;
        self.leave_inspection()?;
        match result {
            Ok(value) => {
                app.draft.select_all();
                app.draft.insert_str(value);
                app.draft_pending = true;
                app.draft_changed = Instant::now();
                app.status = "Editor returned · draft remains unsent".into();
            }
            Err(error) => app.status = format!("External editor: {error}; original draft retained"),
        }
        Ok(())
    }
}

fn restore() {
    if ALTERNATE_OWNED.swap(false, Ordering::SeqCst) {
        let _ = execute!(io::stdout(), tty::LeaveAlternateScreen);
    }
    let _ = execute!(
        io::stdout(),
        tty::EndSynchronizedUpdate,
        DisableBracketedPaste,
        DisableFocusChange,
        DisableMouseCapture,
        ResetColor,
        cursor::Show
    );
    let _ = tty::disable_raw_mode();
}

impl Drop for Screen {
    fn drop(&mut self) {
        restore();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn action_roles_survive_clipping_and_do_not_conflate_parent_and_child_outcomes() {
        for status in [
            "running",
            "succeeded",
            "failed",
            "unknown",
            "interrupted",
            "future-state",
        ] {
            let item = Item { kind:"tool".into(), status:status.into(),
                detail:json!({"name":"delegate","child_progress":[{
                    "agent":"fixture:reader #1","task_title":"Review 界面 é 👩‍💻 source",
                    "status":"succeeded","warnings":{"failed":2,"unknown":1},"notices":{"warning":1}}]}).to_string(), ..Default::default() };
            for width in [0, 1, 8, 32, 40, 175] {
                let row = ordinary_lines(&item, width).remove(0);
                assert!(row.width() <= width, "{}", row);
                if width >= 32 {
                    assert!(row.to_string().contains("2 tool errors"), "{row}");
                    assert_eq!(row.spans[1].style.fg, Some(palette().green));
                }
                if width == 175 {
                    for (label, fg) in [
                        ("2 tool errors", palette().red),
                        ("1 unknown outcome", palette().amber),
                        ("1 hook warning", palette().amber),
                    ] {
                        assert_eq!(
                            row.spans
                                .iter()
                                .find(|s| s.content == label)
                                .unwrap()
                                .style
                                .fg,
                            Some(fg)
                        );
                    }
                }
            }
        }
        assert_eq!(action_name("read_file"), "Read");
        assert_eq!(
            action_name("third-party.read_file"),
            "third-party.read_file"
        );
        let row = action_row(
            "third-party.tool",
            "future-state",
            &[],
            &["raw target".into()],
            175,
        );
        assert!(
            row.to_string()
                .contains("third-party.tool · unknown · raw target")
        );
        assert_eq!(row.spans[3].style.fg, Some(palette().amber));
        let clipped = clip_spans(vec![Span::raw("a👩‍💻é界z")], 5);
        assert_eq!(clipped.to_string(), "a👩‍💻é…");
    }

    #[test]
    fn todo_projection_uses_confirmed_schema_and_never_infers_done_from_success() {
        let mut detail = json!({"name":"todo","status":"succeeded",
            "arguments":{"action":"update","todos":[
                {"content":"Inspect sources","activeForm":"Inspecting sources","status":"completed"},
                {"content":"Check layout","activeForm":"Checking layout","status":"in_progress"},
                {"content":"Review result","activeForm":"Reviewing result","status":"pending"}]},
            "result":{"success":true,"output":{"status":"updated","count":3,"completed":1,"in_progress":1,"pending":1}}});
        let item = Item {
            id: "plan".into(),
            kind: "tool".into(),
            status: "succeeded".into(),
            detail: detail.to_string(),
            ..Default::default()
        };
        for width in [32, 40, 175] {
            let lines = ordinary_lines(&item, width);
            assert!(lines[0].to_string().contains("1/3 done"));
            assert!(lines[1].to_string().contains("Checking layout"));
            assert!(lines.iter().all(|r| r.width() <= width));
        }
        let checklist = todo_checklist(todo_rows(&detail).unwrap(), 175);
        assert_eq!(
            checklist
                .iter()
                .map(ToString::to_string)
                .collect::<Vec<_>>(),
            [
                "✓ [done] Inspect sources",
                "→ [active] Check layout",
                "○ [pending] Review result"
            ]
        );
        detail["status"] = "failed".into();
        assert!(todo_rows(&detail).is_none());
        detail["status"] = "succeeded".into();
        detail["result"]["output"]["completed"] = 3.into();
        assert!(todo_rows(&detail).is_none());
        detail["result"] = "truncated output".into();
        assert!(todo_rows(&detail).is_none());
    }

    #[test]
    fn compact_usage_is_one_row_with_exact_source_still_expandable() {
        let source = "Usage · fixture/test-model · pinned · 2.5s · 2026-01-01 12:00:00 UTC\nInput: 1,000 (90% cached) · Output: 25 · Total: 1,025 · Cost: $0.012345";
        let detail = json!({"source":"usage","text":source,"provider":{"model":"test-model","provider":"fixture","basis":"pinned"},"duration_ms":2500,"usage_call":{"input_tokens":1000,"output_tokens":25,"cost_usd":"0.012345"}});
        let mut item = Item {
            id: "call".into(),
            kind: "notice".into(),
            status: "info".into(),
            detail: detail.to_string(),
            ..Default::default()
        };
        for width in [32, 40, 175] {
            let lines = ordinary_lines(&item, width);
            assert_eq!(lines.len(), 2);
            assert!(lines[0].width() <= width);
            assert!(lines[0].to_string().contains("$0.012345"));
            assert!(expandable(&item));
            assert_eq!(
                serde_json::from_str::<Value>(&item.detail).unwrap()["text"],
                source
            );
        }
        let row = ordinary_lines(&item, 175)[0].to_string();
        for field in [
            "test-model",
            "pinned",
            "2.5s",
            "in 1,000 (90% cached)",
            "out 25",
            "12:00:00 UTC",
        ] {
            assert!(row.contains(field), "{row}");
        }
        let mut child = detail;
        child["child_id"] = "nested-fixture".into();
        child["parent_item_id"] = "parent-fixture".into();
        item.detail = child.to_string();
        assert!(ordinary_lines(&item, 175).is_empty());
        assert!(!expandable(&item));
    }

    #[test]
    fn turn_meter_retains_every_measure_at_laptop_and_mobile_widths() {
        let mut meter = TurnMeter::default();
        meter.state("turn", true);
        meter.observe(json!({"turn_id":"turn", "elapsed_seconds":444,
            "turn":{"calls":8,"tokens":1234567,"cost":"$1.23"},
            "session":{"cost":"$4.56"}}));
        for width in [32, 40, 175] {
            let rows = meter.rows("● Working", width);
            assert!(rows.iter().all(|row| row.width() <= width));
            assert!(rows.len() <= 3);
            let text = rows.join("\n");
            for needle in [
                "Working",
                "7m 24s",
                "8 calls",
                "Turn usage:",
                "tokens",
                "Turn $1.23",
                "Session $4.56",
            ] {
                assert!(text.contains(needle), "{text}");
            }
            assert!(text.contains(if width < 80 { "1.23M" } else { "1,234,567" }));
        }
        meter.received = Some(Instant::now() - Duration::from_secs(2));
        assert!(meter.rows("● Working", 175).join("").contains("7m 26s"));
        meter.state("turn", true); // approval/Stop state must not restart the timer
        assert!(meter.seconds() >= 446.0);
        meter.state("next", true);
        meter.observe(json!({"turn_id":"turn", "elapsed_seconds":999}));
        assert!(meter.received.is_none() && meter.values.is_null());
        meter.state("next", false);
        assert!(meter.received.is_none());
    }

    #[test]
    fn turn_meter_discloses_missing_partial_and_legacy_usage() {
        let mut meter = TurnMeter::default();
        meter.state("turn", true);
        meter.observe(json!({"turn_id":"turn", "elapsed_seconds":1,
            "turn":{"calls":0,"tokens":null,"cost":"pending"},
            "session":{"cost":"$2.00 (partial)"}, "earlier_usage_unavailable":true}));
        let text = meter.rows("● Working", 175).join("\n");
        assert!(text.contains("tokens pending") && text.contains("Turn pending"));
        assert!(text.contains("$2.00 (partial)") && text.contains("earlier usage unavailable"));
        meter.values["turn"] = json!({"calls":1, "tokens":null, "cost":"not reported"});
        assert!(
            meter
                .rows("● Stopping", 32)
                .join("\n")
                .contains("tokens not reported")
        );
        meter.values["turn"] =
            json!({"calls":2,"tokens":100,"tokens_partial":true,"cost":"$0.10 (partial)"});
        assert!(
            meter
                .rows("● Working", 32)
                .join("\n")
                .contains("100 tokens (partial)")
        );
    }

    #[test]
    fn all_user_authored_transcript_text_has_the_same_full_width_surface() {
        for width in [32, 175] {
            for kind in ["user", "correction", "question"] {
                let item = Item {
                    kind: kind.into(), text: "User authored 界".into(), status: "applied".into(),
                    detail: json!({"questions":[{"id":"q", "question":"Choose?"}], "answers":{"q":{"option":null,"text":"User authored 界"}}}).to_string(),
                    ..Default::default()
                };
                let lines = ordinary_lines(&item, width);
                let row = lines
                    .iter()
                    .position(|line| line.to_string().contains("User authored"))
                    .unwrap();
                for line in &lines[row - 1..=row + 1] {
                    assert_eq!(line.width(), width);
                    assert_eq!(line.style.bg, Some(palette().panel));
                    assert_eq!(line.style.fg, Some(palette().ink));
                }
                assert!(lines[row].to_string().starts_with("User authored"));
            }
        }
    }

    #[test]
    fn usage_joins_activity_but_not_responses_in_committed_and_live_rows() {
        let call = Item {id:"usage".into(),kind:"notice".into(),text:"usage".into(), detail:json!({"source":"usage","usage_call":{},"text":"Usage · fixture/model\nInput: 10 · Output: 2 · Cost: $0.01"}).to_string(),..Default::default()};
        for width in [32, 40, 175] {
            for kind in ["tool", "notice", "assistant"] {
                let before = Item {
                    id: "before".into(),
                    kind: kind.into(),
                    text: "Marker".into(),
                    status: "succeeded".into(),
                    detail: json!({"name":"probe", "source":"thinking", "text":"Marker"})
                        .to_string(),
                    ..Default::default()
                };
                let mut log = Journal::default();
                log.observe(&before, true);
                log.prepare(width);
                let mut rows: Vec<_> = log.rows.drain(..).map(|l| l.to_string()).collect();
                log.observe(&call, true);
                log.prepare(width);
                rows.extend(log.rows.drain(..).map(|l| l.to_string()));
                let at = rows.iter().position(|s| s.starts_with("▸ Usage")).unwrap();
                assert_eq!(
                    rows[at - 1].is_empty(),
                    kind == "assistant",
                    "{kind}: {rows:?}"
                );
                let mut live = Journal::default();
                live.observe(&before, false);
                live.observe(&call, true);
                let rows: Vec<_> = live
                    .live(width, &ActivityClocks::default())
                    .iter()
                    .map(|l| l.to_string())
                    .collect();
                let at = rows.iter().position(|s| s.starts_with("▸ Usage")).unwrap();
                assert_eq!(
                    rows[at - 1].is_empty(),
                    kind == "assistant",
                    "live {kind}: {rows:?}"
                );
            }
        }
    }

    #[test]
    fn streamed_response_keeps_its_gap_after_committed_rows_are_drained() {
        let mut log = Journal::default();
        let reply = Item {
            id: "response".into(),
            kind: "assistant".into(),
            text: "# Marker\n\n".into(),
            ..Default::default()
        };
        log.observe(&reply, false);
        log.prepare(80);
        let mut rows: Vec<_> = log.rows.drain(..).map(|l| l.to_string()).collect();
        assert!(!rows.is_empty());
        log.observe(&reply, true);
        log.prepare(80);
        rows.extend(log.rows.drain(..).map(|l| l.to_string()));
        let usage = Item {id:"usage".into(), kind:"notice".into(), detail:json!({"source":"usage","usage_call":{},"text":"Usage · fixture/model\nInput: 10 · Output: 2 · Cost: $0.01"}).to_string(), ..Default::default()};
        log.observe(&usage, true);
        log.prepare(80);
        rows.extend(log.rows.drain(..).map(|l| l.to_string()));
        let at = rows.iter().position(|s| s.starts_with("▸ Usage")).unwrap();
        assert!(rows[at - 1].is_empty());
        assert!(rows[at - 2].contains("Marker"));
    }

    #[test]
    fn usage_totals_join_last_call_even_when_the_call_is_already_committed() {
        let mut log = Journal::default();
        let call = Item {id:"call".into(),kind:"notice".into(),text:"Input: 10 · Output: 2".into(), detail:json!({"source":"usage","usage_call":{"input_tokens":10},"text":"Input: 10 · Output: 2"}).to_string(),..Default::default()};
        log.observe(&call, true);
        log.prepare(80);
        let prior: Vec<_> = log.rows.drain(..).map(|line| line.to_string()).collect();
        assert!(prior.last().unwrap().starts_with("▸ Usage"));
        let totals = Item {
            id: "totals".into(),
            kind: "notice".into(),
            text: "Turn: $0.01 · Session: $0.02".into(),
            detail: json!({"source":"usage","text":"Turn: $0.01 · Session: $0.02"}).to_string(),
            ..Default::default()
        };
        log.observe(&totals, true);
        log.prepare(80);
        assert!(log.rows.front().unwrap().to_string().contains("Turn:"));
        assert!(log.separator_tail);
        log.rows.clear();
        let next_call = Item {
            id: "call-2".into(),
            ..call
        };
        log.observe(&next_call, true);
        log.prepare(80);
        log.rows.clear();
        log.observe(
            &Item {
                id: "reply".into(),
                kind: "assistant".into(),
                text: "Next response".into(),
                ..Default::default()
            },
            true,
        );
        log.prepare(80);
        assert!(log.rows.front().unwrap().to_string().is_empty());
        assert_eq!(log.rows[1].to_string(), "Next response");
    }

    #[test]
    fn compact_activity_preserves_source_and_failures() {
        let item = Item {
            id: "thought".into(),
            kind: "notice".into(),
            text: "[thinking] Original retained thinking".into(),
            status: "info".into(),
            detail: json!({"source":"thinking", "text":"word ".repeat(1000)}).to_string(),
        };
        let rows = ordinary_lines(&item, 175);
        assert!(rows.len() < 5);
        assert!(
            rows.iter()
                .any(|line| line.to_string().contains("Thinking"))
        );
        assert_eq!(item.text, "[thinking] Original retained thinking");
        let failure = Item {
            status: "error".into(),
            ..item.clone()
        };
        assert!(
            ordinary_lines(&failure, 175)
                .iter()
                .any(|line| line.to_string().contains("Original retained"))
        );
        let tool = Item {
            id: "tool".into(),
            kind: "tool".into(),
            text: "example\n".to_owned() + &"line\n".repeat(20),
            status: "unknown".into(),
            detail: "Exact original result".into(),
        };
        let rows = ordinary_lines(&tool, 80);
        assert!(rows[0].to_string().contains("unknown"));
        assert!(!rows[0].to_string().starts_with(' '));
        assert_eq!(rows.len(), 2); // One summary and a separator; source retained.
        assert_eq!(tool.detail, "Exact original result");
    }

    #[test]
    fn delegate_task_title_leads_stats_and_survives_narrow_layout() {
        for (ordinal, title) in [(1, "Map startup paths"), (2, "Review file tools")] {
            let mut item = Item {
                id: format!("task-{ordinal}"), kind: "tool".into(), status: "running".into(),
                detail: json!({"name":"delegate", "arguments":{"instruction":"Original full instructions"},
                    "child_progress":[{"agent":format!("probe:explorer #{ordinal}"),"task_title":title,
                        "status":"running", "activity":"read_file · running", "calls":12,
                        "elapsed_seconds":125}], "child_cost_display":"$0.03"}).to_string(),
                ..Default::default()
            };
            for width in [175, 80, 40, 32] {
                let rows = ordinary_lines(&item, width);
                let text = rows[0].to_string();
                assert_eq!(rows.len(), 2);
                assert!(
                    text.contains("running") && text.contains(&format!("#{ordinal}")),
                    "{text}"
                );
                assert!(
                    text.contains(title.split_whitespace().next().unwrap()),
                    "{text}"
                );
                assert!(!text.contains("Original full"));
                if width == 175 {
                    assert!(text.find(title).unwrap() < text.find("12 calls").unwrap());
                    assert!(
                        text.contains("$0.03")
                            && text.contains("2m 05s")
                            && text.contains("read_file")
                    );
                }
            }
            let mut detail: Value = serde_json::from_str(&item.detail).unwrap();
            detail["child_progress"][0]["warnings"] = json!({"failed":1});
            item.detail = detail.to_string();
            item.status = "succeeded".into();
            assert!(
                ordinary_lines(&item, 32)[0]
                    .to_string()
                    .contains("1 tool error")
            );
            assert!(item.detail.contains("Original full instructions"));
        }
    }

    #[test]
    fn retained_progress_preview_uses_full_ledger_counts_and_warning_badges() {
        let item = Item {
            id: "bounded".into(),
            kind: "tool".into(),
            status: "running".into(),
            detail: json!({"name":"delegate", "child_progress":[
                {"agent":"probe #1","status":"running","calls":2},
                {"agent":"probe #100","status":"succeeded","calls":2}],
                "child_count":100,"child_calls":200,"child_progress_omitted":98,
                "child_totals":{"warnings":{"failed":9},"notices":{"warning":3}},
                "child_cost_display":"$1.00"})
            .to_string(),
            ..Default::default()
        };
        let row = ordinary_lines(&item, 220).remove(0);
        let text = row.to_string();
        for expected in [
            "100 agents",
            "200 calls",
            "$1.00",
            "98 earlier in Activity",
            "9 tool errors",
            "3 hook warnings",
        ] {
            assert!(text.contains(expected), "{expected}: {text}");
        }
        assert!(
            row.spans
                .iter()
                .any(|s| s.content.contains("9 tool errors") && s.style.fg == Some(palette().red))
        );
    }

    #[test]
    fn legacy_delegate_progress_does_not_invent_zero_calls() {
        let item = Item { id: "legacy".into(), kind: "tool".into(), text: "delegate".into(), status: "succeeded".into(),
            detail: json!({"name":"delegate", "child_progress":[{"agent":"probe #1","activity":"Completed"}]}).to_string() };
        let text = ordinary_lines(&item, 175)
            .iter()
            .map(ToString::to_string)
            .collect::<String>();
        assert!(text.contains("calls unavailable"));
        assert!(!text.contains("0 calls"));
    }

    #[test]
    fn elapsed_work_uses_readable_units() {
        assert_eq!(elapsed_label(9.2), "9s");
        assert_eq!(elapsed_label(59.8), "1m 00s");
        assert_eq!(elapsed_label(125.0), "2m 05s");
        assert_eq!(elapsed_label(3675.0), "1h 01m 15s");
    }

    #[test]
    fn quiet_child_clocks_survive_sibling_updates_and_freeze_without_rewriting_source() {
        let detail = json!({"name":"delegate", "child_progress":[
            {"child_id":"quiet", "status":"running", "elapsed_seconds":5},
            {"child_id":"busy", "status":"running", "elapsed_seconds":2},
            {"child_id":"done", "status":"succeeded", "elapsed_seconds":1},
            {"child_id":"unknown", "status":"running"}
        ]});
        let mut item = Item {
            id: "call".into(),
            kind: "tool".into(),
            status: "running".into(),
            detail: detail.to_string(),
            ..Item::default()
        };
        let mut clocks = ActivityClocks::default();
        clocks.observe(&item);
        let observed = Instant::now() - Duration::from_secs(3);
        clocks
            .items
            .get_mut("call")
            .unwrap()
            .get_mut("quiet")
            .unwrap()
            .1 = Some(observed);
        let mut update = detail.clone();
        update["child_progress"][1]["elapsed_seconds"] = json!(3);
        item.detail = update.to_string();
        clocks.observe(&item);
        assert_eq!(clocks.items["call"]["quiet"].1, Some(observed));
        assert_eq!(clocks.items["call"].len(), 2);
        let elapsed = clocks.seconds("call").unwrap();
        assert!((8.0..9.0).contains(&elapsed));
        assert!(
            live_lines(&item, 175, Some(elapsed))[0]
                .to_string()
                .contains("8s")
        );
        assert!(ordinary_lines(&item, 175)[0].to_string().contains("5s"));
        assert_eq!(item.detail, update.to_string());
        clocks.freeze();
        let frozen = clocks.seconds("call");
        assert!(clocks.items["call"].values().all(|(_, at)| at.is_none()));
        assert_eq!(clocks.seconds("call"), frozen);
        item.status = "interrupted".into();
        clocks.observe(&item);
        assert!(clocks.items.is_empty());
        let row = ordinary_lines(&item, 175).remove(0);
        assert_eq!(row.spans[3].content, "interrupted");
        assert_eq!(row.spans[3].style.fg, Some(palette().red));
    }

    #[test]
    fn forked_skill_completion_keeps_inner_tool_and_hook_errors_explicit() {
        let item = Item {
            id: "skill".into(), kind: "tool".into(), text: "load_skill".into(), status: "succeeded".into(),
            detail: json!({"name":"load_skill", "child_progress":[{
                "agent":"Skill · fixture-review #1", "status":"succeeded", "activity":"succeeded",
                "calls":3, "elapsed_seconds":125, "warnings":{"failed":2}, "notices":{"warning":1,"error":0}
            }], "child_cost_display":"$0.03"}).to_string(),
        };
        let text = ordinary_lines(&item, 175)[0].to_string();
        assert!(text.contains("done · 2 tool errors · 1 hook warning"));
        assert!(text.contains("load_skill · Skill · fixture-review #1"));
        assert!(text.contains("2m 05s"));
        assert!(!text.contains("succeeded"));
        assert!(!text.contains("agent failed"));
    }

    #[test]
    fn delegate_cost_uses_the_host_decimal_display() {
        let item = Item {
            id: "delegate".into(),
            kind: "tool".into(),
            text: "delegate".into(),
            status: "succeeded".into(),
            detail: json!({
                "name": "delegate",
                "child_progress": [
                    {"agent": "probe #1", "activity": "Completed", "calls": 1},
                    {"agent": "probe #2", "activity": "Completed", "calls": 1}
                ],
                "child_cost_usd": "0.305",
                "child_cost_display": "$0.30",
                "child_cost_partial": false
            })
            .to_string(),
        };
        let text = ordinary_lines(&item, 175)
            .iter()
            .map(ToString::to_string)
            .collect::<String>();
        assert!(text.contains("$0.30"));
        assert!(!text.contains("cost unavailable"));
    }

    #[test]
    fn hidden_child_usage_has_no_rows_or_usage_separators() {
        let mut log = Journal::default();
        for n in 0..80 {
            let item = Item { id: format!("child-usage-{n}"), kind: "notice".into(), text: "Private observed usage".into(),
                detail: json!({"source":"usage","usage_call":{"cost_usd":"0.01"},"child_id":"child","parent_item_id":"child:child"}).to_string(), ..Default::default() };
            assert!(hidden(&item));
            assert!(ordinary_lines(&item, 175).is_empty());
            assert!(!expandable(&item));
            log.observe(&item, true);
        }
        while log.has_work() {
            log.prepare(175);
        }
        assert!(log.rows.is_empty());
        assert!(!log.separator_tail);
    }
    #[test]
    fn cursor_response_parser_ignores_paste_and_handles_fragments() {
        assert_eq!(reported_cursor_row(b"\x1b[12;"), None);
        assert_eq!(reported_cursor_row(b"typed\x1b[12;3Rmore"), Some(11));
        assert_eq!(reported_cursor_row(b"\x1b[200~\x1b[99;3R\x1b[201~"), None);
        assert_eq!(
            reported_cursor_row(b"\x1b[200~\x1b[99;3R\x1b[201~\x1b[2;1R"),
            Some(1)
        );
        assert_eq!(reported_cursor_row(b"\x1b[0;1R"), None);
    }
    #[test]
    fn stable_markdown_blocks_wait_for_real_boundaries() {
        assert_eq!(stable_end("Hello **world"), 0);
        assert_eq!(stable_end("```rs\nfirst\n\nsecond\n"), 0);
        assert!(stable_end("First paragraph.\n\nSecond") > 0);
        assert_eq!(stable_end("| A | B |\n|---|---|\n|x|y|"), 0);
    }
    #[test]
    fn streamed_structural_markdown_matches_completed_projection() {
        let source = "# Title\n\n## Review\n\n### Subsection\n\n#### Topic\n\n##### Detail\n\n###### Note\n\nSetext title\n===\n\nMultiline setext\nsection\n---\n\n9. First item with enough repeated words to wrap at a narrow width without losing its column.\n   - Nested 界 item that also wraps and preserves its parent.\n10. Second item\n\n    A continuation paragraph.\n\n> Quoted words with a [reference](https://example.test/guide) that wraps.\n\n```rs\nlet x = 1;\n```\n\n| A | B |\n|---|---|\n| x | y |\n\nDone.\n";
        for width in [40, 80, 175] {
            let mut log = Journal::default();
            let mut painted = Vec::new();
            let mut item = Item {
                id: "structural-stream".into(),
                kind: "assistant".into(),
                ..Default::default()
            };
            for (index, ch) in source.char_indices() {
                item.text = source[..index + ch.len_utf8()].into();
                log.observe(&item, false);
                log.prepare(width);
                painted.extend(log.rows.drain(..));
            }
            log.observe(&item, true);
            log.prepare(width);
            painted.extend(log.rows.drain(..));
            assert_eq!(painted, markdown::render(source, width));
        }
    }
    #[test]
    fn running_calls_keep_following_observations_in_order_without_busy_polling() {
        let mut log = Journal::default();
        let mut tool = Item {
            id: "tool".into(),
            kind: "tool".into(),
            status: "running".into(),
            text: "delegate".into(),
            ..Default::default()
        };
        let usage = Item {
            id: "usage".into(),
            kind: "notice".into(),
            text: "Usage marker".into(),
            ..Default::default()
        };
        log.observe(&tool, false);
        log.observe(&usage, true);
        log.prepare(80);
        assert!(log.rows.is_empty());
        assert!(!log.has_work());
        let live = log
            .live(80, &ActivityClocks::default())
            .iter()
            .map(ToString::to_string)
            .collect::<Vec<_>>()
            .join("\n");
        assert!(live.find("delegate") < live.find("Usage marker"));
        tool.status = "succeeded".into();
        log.observe(&tool, true);
        log.prepare(80);
        let committed = log
            .rows
            .drain(..)
            .map(|line| line.to_string())
            .collect::<Vec<_>>()
            .join("\n");
        assert!(committed.find("delegate") < committed.find("Usage marker"));
        assert!(log.live(80, &ActivityClocks::default()).is_empty());
    }
    #[test]
    fn replay_backlog_does_not_hide_new_streaming_text() {
        let mut log = Journal::default();
        for n in 0..1000 {
            log.observe(
                &Item {
                    id: format!("old-{n}"),
                    kind: "assistant".into(),
                    text: "Historical paragraph".into(),
                    ..Default::default()
                },
                true,
            );
        }
        log.observe(
            &Item {
                id: "new".into(),
                kind: "assistant".into(),
                text: "Fresh streaming text".into(),
                ..Default::default()
            },
            false,
        );
        log.prepare(80);
        assert!(log.has_work());
        assert!(log.pending.len() > 900);
        let live: String = log
            .live(80, &ActivityClocks::default())
            .iter()
            .map(ToString::to_string)
            .collect();
        assert!(live.contains("Fresh streaming text"));
        assert!(!live.contains("Historical paragraph"));
    }
    #[test]
    fn finalization_and_identical_updates_do_not_duplicate_history() {
        let mut log = Journal::default();
        let mut item = Item {
            id: "a".into(),
            kind: "assistant".into(),
            text: "First.\n\nSecond".into(),
            ..Default::default()
        };
        log.observe(&item, false);
        log.prepare(80);
        let first: String = log.rows.drain(..).map(|l| l.to_string()).collect();
        assert!(first.contains("First."));
        item.text.push('.');
        log.observe(&item, true);
        log.prepare(40);
        let last: String = log.rows.drain(..).map(|l| l.to_string()).collect();
        assert!(last.contains("Second."));
        assert!(!last.contains("First."));
        log.observe(&item, true);
        log.prepare(80);
        assert!(log.rows.is_empty());
    }

    #[test]
    fn switching_keeps_backlogged_rows_and_exit_flushes_partial_source() {
        let mut log = Journal::default();
        for i in 0..200 {
            log.observe(
                &Item {
                    id: format!("id-{i}"),
                    kind: "user".into(),
                    text: format!("marker-{i:03}"),
                    ..Default::default()
                },
                true,
            );
        }
        log.prepare(80);
        log.reset();
        let history: String = log.rows.drain(..).map(|l| l.to_string()).collect();
        for i in 0..200 {
            assert_eq!(history.matches(&format!("marker-{i:03}")).count(), 1);
        }
        log.observe(
            &Item {
                id: "partial".into(),
                kind: "assistant".into(),
                text: "unfinished **source".into(),
                ..Default::default()
            },
            false,
        );
        log.prepare(40);
        assert!(log.rows.is_empty());
        log.finish();
        log.prepare(40);
        let history: String = log.rows.drain(..).map(|l| l.to_string()).collect();
        assert!(history.contains("unfinished **source"));
        assert!(!log.has_work());
    }

    #[test]
    fn historical_replay_is_disclosed_and_does_not_limit_new_output() {
        let mut log = Journal::default();
        assert_eq!(log.begin_replay(100_000), 99_000);
        assert!(
            log.rows
                .front()
                .unwrap()
                .to_string()
                .contains("Transcript / Export")
        );
        log.skip_replay_item = true;
        log.observe(
            &Item {
                id: "old".into(),
                text: "old".into(),
                ..Default::default()
            },
            true,
        );
        log.skip_replay_item = false;
        log.observe(
            &Item {
                id: "new".into(),
                text: "new".into(),
                ..Default::default()
            },
            true,
        );
        log.prepare(80);
        assert!(!log.emitted.contains_key("old"));
        assert!(log.emitted.contains_key("new"));
    }
}

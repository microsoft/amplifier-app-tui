use crossterm::{
    event::{
        self, DisableBracketedPaste, DisableMouseCapture, EnableBracketedPaste, EnableMouseCapture,
        Event, KeyCode, KeyEventKind, KeyModifiers, MouseEventKind,
    },
    execute,
};
use ratatui::{
    prelude::*,
    widgets::{Block, BorderType, Borders, Paragraph},
};
use ratatui_textarea::TextArea;
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::{
    collections::HashMap,
    io::{self, BufRead, Read, Write},
    process::{Child, ChildStdin, Command, Stdio},
    sync::{
        Arc,
        atomic::{AtomicBool, Ordering},
        mpsc::{self, Receiver},
    },
    time::{Duration, Instant},
};
mod code_blocks;
mod composer;
mod controls;
mod external_editor;
mod insights;
mod interaction;
mod markdown;
mod native;
mod navigation;
mod questions;
mod selection;
mod tables;
mod transcript;
mod workflow;
mod workspace;
use interaction::{Action, Interaction};

const BG: Color = Color::Rgb(20, 25, 31);
const PANEL: Color = Color::Rgb(29, 36, 45);
const INK: Color = Color::Rgb(224, 230, 236);
const MUTED: Color = Color::Rgb(162, 176, 191);
const LINE: Color = Color::Rgb(57, 70, 84);
const GREEN: Color = Color::Rgb(142, 213, 183);
const AMBER: Color = Color::Rgb(232, 193, 111);
const RED: Color = Color::Rgb(243, 163, 174);

#[derive(Clone, Default, Deserialize, Serialize)]
struct Item {
    id: String,
    kind: String,
    text: String,
    #[serde(default)]
    status: String,
    #[serde(default)]
    detail: String,
}

struct App {
    insights: insights::Insights,
    selection: selection::Selection,
    flow: workflow::Workflow,
    controls: controls::Controls,
    questions: questions::Questions,
    review_request: Option<String>,
    nav: navigation::Navigation,
    ui: Interaction,
    items: Vec<Item>,
    index: HashMap<String, usize>,
    tool_indices: Vec<usize>,
    draft: TextArea<'static>,
    title: String,
    context: String,
    mode: String,
    policy: String,
    native: native::Journal,
    status: String,
    system: Vec<String>,
    approval: Option<Value>,
    view: usize,
    scroll: [usize; 3],
    anchors: [Option<transcript::Anchor>; 2],
    layouts: Vec<Option<transcript::Layout>>,
    durable: bool,
    saved_draft: String,
    draft_changed: Instant,
    draft_pending: bool,
    expanded: bool,
    selected: usize,
    detail_scroll: usize,
    request: u64,
    pending: HashMap<String, String>,
    child: Child,
    input: ChildStdin,
    output: Receiver<Value>,
    disconnected: bool,
    rows: Vec<(u16, usize)>,
    tab_y: u16,
    body: Rect,
    copy: Option<String>,
}

fn string(v: &Value, key: &str) -> String {
    v[key].as_str().unwrap_or_default().to_owned()
}
fn safe(text: &str) -> String {
    text.chars()
        .filter(|c| !c.is_control() || *c == '\n' || *c == '\t')
        .collect::<String>()
        .replace('\t', "    ")
}
fn color(status: &str) -> Color {
    match status {
        "failed" => RED,
        "succeeded" | "completed" => GREEN,
        "waiting" | "running" => AMBER,
        _ => MUTED,
    }
}
fn icon(status: &str) -> &str {
    match status {
        "failed" => "×",
        "succeeded" => "✓",
        "waiting" | "running" => "·",
        _ => "−",
    }
}

fn editor() -> TextArea<'static> {
    let mut draft = TextArea::default();
    draft.set_style(Style::default().fg(INK).bg(BG));
    draft.set_cursor_line_style(Style::default());
    draft.set_cursor_style(Style::default().fg(BG).bg(GREEN));
    draft.set_selection_style(Style::default().fg(INK).bg(LINE));
    draft.set_placeholder_text("Ask, correct, or describe the next task…");
    draft
}

impl App {
    fn new(command: Vec<String>) -> io::Result<Self> {
        let mut child = Command::new(&command[0])
            .args(&command[1..])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()?;
        let input = child.stdin.take().unwrap();
        let stdout = child.stdout.take().unwrap();
        let (tx, output) = mpsc::sync_channel(1024);
        std::thread::spawn(move || {
            let mut reader = io::BufReader::new(stdout);
            loop {
                let mut bytes = Vec::new();
                // Bounded record read, including the large initial stress snapshot.
                let read = std::io::Read::by_ref(&mut reader)
                    .take(64 * 1024 * 1024)
                    .read_until(b'\n', &mut bytes);
                match read {
                    Ok(0) | Err(_) => break,
                    Ok(_) => match serde_json::from_slice(&bytes) {
                        Ok(value) => {
                            if tx.send(value).is_err() {
                                return;
                            }
                        }
                        Err(_) => break,
                    },
                }
            }
            let _ = tx.send(json!({"type":"disconnected"}));
        });
        let draft = editor();
        Ok(Self {
            insights: insights::Insights::default(),
            flow: workflow::Workflow::default(),
            controls: controls::Controls::default(),
            questions: questions::Questions::default(),
            selection: selection::Selection::default(),
            review_request: None,
            nav: navigation::Navigation::default(),
            ui: Interaction::default(),
            items: vec![],
            index: HashMap::new(),
            tool_indices: vec![],
            draft,
            title: "A place to do real work".into(),
            context: "Preparing session".into(),
            mode: "STARTING".into(),
            policy: "loading".into(),
            native: native::Journal::default(),
            status: "Starting · draft stays editable".into(),
            system: vec![],
            approval: None,
            view: 0,
            scroll: [0; 3],
            anchors: [None; 2],
            layouts: vec![],
            durable: false,
            saved_draft: String::new(),
            draft_changed: Instant::now(),
            draft_pending: false,
            expanded: false,
            selected: 0,
            detail_scroll: 0,
            request: 0,
            pending: HashMap::new(),
            child,
            input,
            output,
            disconnected: false,
            rows: vec![],
            tab_y: 0,
            body: Rect::default(),
            copy: None,
        })
    }
    fn upsert(&mut self, item: Item) {
        if item.kind == "outcome" {
            self.native.finish();
        }
        self.native.observe(&item, true);
        if let Some(&i) = self.index.get(&item.id) {
            if item.kind != self.items[i].kind {
                match (item.kind == "tool", self.tool_indices.binary_search(&i)) {
                    (true, Err(at)) => self.tool_indices.insert(at, i),
                    (false, Ok(at)) => {
                        self.tool_indices.remove(at);
                    }
                    _ => (),
                }
            }
            self.items[i] = item;
            self.layouts[i] = None;
        } else {
            self.index.insert(item.id.clone(), self.items.len());
            if item.kind == "tool" {
                self.selected = self.items.len();
                self.tool_indices.push(self.items.len());
            }
            self.items.push(item);
            self.layouts.push(None);
        }
    }
    fn receive(&mut self, v: Value) {
        if v["type"] != "disconnected" && v["version"] != 1 {
            self.disconnected = true;
            self.status = "Protocol mismatch · no work retried".into();
            return;
        }
        match v["type"].as_str().unwrap_or("") {
            "snapshot" => {
                if v["reset"] == true {
                    self.native.reset();
                    self.flow = workflow::Workflow::default();
                    self.controls = controls::Controls::default();
                    self.questions = questions::Questions::default();
                    self.selection = selection::Selection::default();
                    self.review_request = None;
                    self.items.clear();
                    self.index.clear();
                    self.tool_indices.clear();
                    self.layouts.clear();
                    self.ui = Interaction::default();
                    self.pending.clear();
                    self.approval = None;
                    self.view = 0;
                    self.scroll = [0; 3];
                    self.anchors = [None; 2];
                    self.expanded = false;
                    self.detail_scroll = 0;
                    self.copy = None;
                    // Undo/selection state belongs to the source conversation too.
                    self.draft = editor();
                    self.nav.lookup = None;
                    self.draft_pending = false;
                }
                self.nav.session = string(&v, "session_id");
                self.policy = "loading".into();
                self.nav.enabled = v["navigation"] == true;
                self.ui.skills = v["skills"]
                    .as_array()
                    .unwrap_or(&vec![])
                    .iter()
                    .filter_map(|s| s.as_str().map(str::to_owned))
                    .collect();
                self.durable = v["durable"] == true;
                self.insights = insights::Insights::default();
                self.insights.drafts = v["local_drafts"].as_array().cloned().unwrap_or_default();
                self.insights.error = string(&v, "local_drafts_error");
                self.saved_draft = string(&v, "draft");
                self.title = safe(&string(&v, "title"));
                self.context = safe(&string(&v, "context"));
                self.mode = string(&v, "mode");
                self.native.banner(&self.title, &self.mode);
                if self.mode == "SIMULATED" {
                    self.policy = "unavailable".into();
                }
                self.system = v["system"]
                    .as_array()
                    .unwrap_or(&vec![])
                    .iter()
                    .filter_map(|s| s.as_str().map(safe))
                    .collect();
                if self.draft.lines().join("\n").is_empty() {
                    self.draft.insert_str(string(&v, "draft"));
                }
                if let Some(items) = v["items"].as_array() {
                    let skip = self.native.begin_replay(items.len());
                    for (position, value) in items.iter().enumerate() {
                        self.native.skip_replay_item = position < skip;
                        if let Ok(item) = serde_json::from_value(value.clone()) {
                            self.upsert(item);
                        }
                    }
                    self.native.skip_replay_item = false;
                }
                self.selected = self
                    .items
                    .iter()
                    .rposition(|i| i.kind == "tool")
                    .unwrap_or(0);
                self.ui.history = self
                    .items
                    .iter()
                    .filter(|i| i.kind == "user")
                    .map(|i| i.text.clone())
                    .rev()
                    .take(1000)
                    .collect();
                self.ui.history.reverse();
            }
            "input_history" if v["session_id"] == self.nav.session => {
                self.ui.prior_history = Some(
                    v["entries"]
                        .as_array()
                        .unwrap_or(&vec![])
                        .iter()
                        .filter_map(|s| s.as_str().map(str::to_owned))
                        .collect(),
                );
                self.ui.history_partial = v["partial"] == true;
            }
            "mode_status" if v["session_id"] == self.nav.session => {
                self.policy = if v["supported"] == true {
                    v["current"]
                        .as_str()
                        .map(safe)
                        .unwrap_or_else(|| "default".into())
                } else {
                    "unavailable".into()
                };
            }
            "item" => {
                if v["kind"] == "user" && v["input_id"].is_string() {
                    self.ui.history.push(string(&v, "text"));
                    if self.ui.history.len() > 1000 {
                        self.ui.history.remove(0);
                    }
                }
                if let Ok(item) = serde_json::from_value(v) {
                    self.upsert(item);
                }
            }
            "delta" => {
                let id = string(&v, "id");
                if let Some(&i) = self.index.get(&id) {
                    self.items[i].text.push_str(&string(&v, "text"));
                    self.layouts[i] = None;
                    self.native.observe(&self.items[i], false);
                } else {
                    self.upsert(Item {
                        id,
                        kind: "assistant".into(),
                        text: string(&v, "text"),
                        ..Item::default()
                    });
                    self.native.observe(self.items.last().unwrap(), false);
                }
            }
            "system" => {
                self.controls.steer = v["steer"] == true;
                self.controls.providers = v["conversation_provider"].clone();
                self.ui.skills = v["skills"]
                    .as_array()
                    .unwrap_or(&vec![])
                    .iter()
                    .filter_map(|s| s.as_str().map(str::to_owned))
                    .collect();
                self.ui.diagnostics = v["diagnostics"]
                    .as_array()
                    .unwrap_or(&vec![])
                    .iter()
                    .filter_map(|s| s.as_str().map(safe))
                    .collect();
                self.system = v["lines"]
                    .as_array()
                    .unwrap_or(&vec![])
                    .iter()
                    .filter_map(|s| s.as_str().map(safe))
                    .collect();
            }
            "state" => {
                self.flow.busy = v["busy"] == true;
                self.controls.turn = if self.flow.busy {
                    string(&v, "turn_id")
                } else {
                    String::new()
                };
                self.status = safe(&string(&v, "status"));
                self.approval = if v["approval"].is_object() {
                    Some(v["approval"].clone())
                } else {
                    None
                };
            }
            "reply" => {
                let id = string(&v, "request_id");
                let queued = self.flow.queued_requests.remove(&id);
                if self.controls.requests.remove(&id) {
                    self.status = safe(&string(&v, "reason"));
                }
                if self
                    .flow
                    .prompt
                    .as_ref()
                    .is_some_and(|p| p.pending.as_ref() == Some(&id))
                {
                    if v["accepted"] == true {
                        self.flow.prompt = None;
                    } else {
                        self.flow.prompt.as_mut().unwrap().pending = None;
                    }
                }
                if self.nav.switching.as_ref() == Some(&id) && v["accepted"] != true {
                    self.nav.switching = None;
                }
                if let Some(sent) = self.pending.remove(&id)
                    && v["accepted"] == true
                {
                    if self.draft.lines().join("\n") == sent {
                        self.draft.select_all();
                        self.draft.insert_str("");
                    }
                    if !queued {
                        self.ui.history.push(sent);
                    }
                    self.ui.recall = composer::Recall::default();
                    self.draft_pending = true;
                    self.draft_changed = Instant::now();
                    if self.ui.history.len() > 1000 {
                        self.ui.history.remove(0);
                    }
                }
                if v["accepted"] != true {
                    if self.review_request.as_ref() == Some(&id) {
                        self.review_request = None;
                        self.ui.menu = None;
                    }
                    self.reject_lookup(&id);
                    self.status = safe(&string(&v, "reason"));
                }
            }
            "error" => self.status = safe(&string(&v, "message")),
            "title" => {
                self.title = format!(
                    "{} · {}",
                    safe(&string(&v, "text")),
                    self.nav.session.chars().take(8).collect::<String>()
                )
            }
            "followups" if v["session_id"] == self.nav.session => {
                self.flow.rows = v["rows"].as_array().cloned().unwrap_or_default();
                self.flow.paused = v["paused"] == true;
            }
            "workspace_changes" | "workspace_diff" => self.review_result(&v),
            "inspection" => self.inspection_result(v),
            "file_snapshot" => self.file_snapshot_result(v),
            "question" if v["session_id"] == self.nav.session => {
                let id = string(&v, "id");
                if v["status"] == "waiting" {
                    self.questions.pending.insert(id, v);
                } else {
                    self.questions.pending.remove(&id);
                    self.questions.answers.remove(&id);
                }
            }
            "modes" if v["session_id"] == self.nav.session => {
                self.mode_menu(&v);
            }
            "providers" if v["session_id"] == self.nav.session => {
                self.controls.providers = v.clone();
                if self
                    .controls
                    .lookup
                    .as_ref()
                    .is_some_and(|id| v["request_id"] == *id)
                {
                    self.controls.lookup = None;
                    if self
                        .ui
                        .menu
                        .as_ref()
                        .is_some_and(|m| m.title == "Conversation providers · loading")
                    {
                        self.provider_menu();
                    }
                }
            }
            "provider_observed" if v["session_id"] == self.nav.session => {
                self.controls.observed = format!(
                    "{} / {} ({})",
                    safe(&string(&v, "provider")),
                    safe(&string(&v, "model")),
                    safe(&string(&v, "basis"))
                );
            }
            "steering_ready" if v["session_id"] == self.nav.session => {
                self.controls.ready_turn = string(&v, "turn_id");
            }
            "conversations" | "completion" => self.receive_lookup(&v),
            "switch_result" => {
                if self
                    .nav
                    .switching
                    .as_ref()
                    .is_some_and(|id| v["request_id"] == *id)
                {
                    self.nav.switching = None;
                    if v["ok"] != true {
                        self.status = safe(&string(&v, "message"));
                    }
                }
            }
            "disconnected" => {
                self.disconnected = true;
                self.nav.switching = None;
                self.nav.lookup = None;
                self.approval = None;
                self.controls.lookup = None;
                self.status = "Disconnected · outcome uncertain; draft retained; no retry".into();
            }
            _ => (),
        }
    }
    fn send(&mut self, mut request: Value) {
        if self.disconnected {
            self.status = "Disconnected · draft retained; no automatic retry".into();
            return;
        }
        self.request += 1;
        let id = self.request.to_string();
        request["version"] = json!(1);
        request["request_id"] = json!(id);
        if !self.nav.session.is_empty() {
            request["session_id"] = json!(self.nav.session);
        }
        if request["op"] == "submit" || request["op"] == "queue" {
            if request["op"] == "queue" {
                self.flow.queued_requests.insert(id.clone());
            }
            self.pending.insert(id, string(&request, "text"));
        }
        if writeln!(self.input, "{request}")
            .and_then(|_| self.input.flush())
            .is_err()
        {
            self.receive(json!({"type":"disconnected"}));
        }
    }
    fn decision(&mut self, option: &str) {
        if let Some(a) = &self.approval {
            self.send(json!({"op":"decision","approval_id":a["id"],"option":option}));
        } else {
            self.status = "No pending decision".into();
        }
    }
    fn navigate(&mut self, amount: isize) {
        if self.selection.start.is_some() && self.ui.menu.is_none() {
            self.selection.scroll(amount);
        } else if self.expanded {
            self.detail_scroll = self.detail_scroll.saturating_add_signed(-amount);
        } else if self.view < 2 {
            self.scroll_lines(amount);
        } else {
            self.scroll[self.view] = self.scroll[self.view]
                .saturating_add_signed(if self.view == 2 { -amount } else { amount })
                .min(
                    if self.view == 2 {
                        let source = if self.ui.diagnostic_view {
                            &self.ui.diagnostics
                        } else {
                            &self.system
                        };
                        source
                            .iter()
                            .map(|s| wrap(s, self.body.width as usize).len())
                            .sum()
                    } else {
                        self.items.len()
                    }
                    .saturating_sub(1),
                );
        }
    }
    fn key(&mut self, key: crossterm::event::KeyEvent) -> bool {
        if key.kind == KeyEventKind::Release {
            return true;
        }
        if key.code == KeyCode::Enter && key.kind != KeyEventKind::Press {
            return true;
        }
        let ctrl = key.modifiers.contains(KeyModifiers::CONTROL);
        if self.ui.menu.is_none() && self.flow.prompt.is_none() && self.selection.start.is_some() {
            if ctrl && key.code == KeyCode::Char('c') {
                self.copy = Some(self.selection.text());
                return true;
            }
            if key.code == KeyCode::Esc {
                self.selection.start = None;
                return true;
            }
        }
        if ctrl && matches!(key.code, KeyCode::Char('q' | 'c')) {
            return false;
        }
        if self.nav.switching.is_some() {
            if key.code == KeyCode::Esc {
                self.send(json!({"op":"cancel_switch"}));
            }
            return true;
        }
        if let Some(keep_running) = self.prompt_key(key) {
            return keep_running;
        }
        if let Some(keep_running) = self.local_key(key) {
            return keep_running;
        }
        match key.code {
            KeyCode::Char('q' | 'c') if ctrl => return false,
            KeyCode::F(n @ 1..=3) => self.view = (n - 1) as usize,
            KeyCode::Char('e') if ctrl => {
                self.expanded = !self.expanded;
                self.detail_scroll = 0;
            }
            KeyCode::Char('t') if ctrl => {
                if !self.items.is_empty() {
                    for step in 1..=self.items.len() {
                        let i = (self.selected + step) % self.items.len();
                        if self.items[i].kind == "tool" {
                            self.selected = i;
                            self.detail_scroll = 0;
                            break;
                        }
                    }
                }
            }
            KeyCode::Char('p') if ctrl => {
                self.copy = self.items.get(self.selected).map(|i| i.detail.clone());
            }
            KeyCode::Char('y') if ctrl => self.decision("allow"),
            KeyCode::Char('n') if ctrl => self.decision("deny"),
            KeyCode::Char('x') if ctrl => self.send(json!({"op":"stop"})),
            KeyCode::PageUp => self.navigate(self.body.height.saturating_sub(2).max(1) as isize),
            KeyCode::PageDown => {
                self.navigate(-(self.body.height.saturating_sub(2).max(1) as isize))
            }
            KeyCode::End if ctrl && self.view < 2 => self.anchors[self.view] = None,
            KeyCode::Esc => {
                self.expanded = false;
                self.view = 0;
                self.anchors = [None; 2];
            }
            KeyCode::Enter
                if key
                    .modifiers
                    .intersects(KeyModifiers::ALT | KeyModifiers::SHIFT) =>
            {
                self.draft.insert_newline();
            }
            KeyCode::Char('j') if ctrl => {
                self.draft.insert_newline();
            }
            KeyCode::Enter => return self.submit_draft(),
            _ => {
                self.draft.input(key);
            }
        }
        true
    }
}

impl Drop for App {
    fn drop(&mut self) {
        self.retain_editor();
        if self.durable && !self.disconnected {
            self.send(json!({"op":"draft","text":self.draft.lines().join("\n")}));
        }
        let _ = writeln!(self.input, "{{\"version\":1,\"op\":\"shutdown\"}}");
        let _ = self.input.flush();
        let start = Instant::now();
        while start.elapsed() < Duration::from_secs(3) {
            if matches!(self.child.try_wait(), Ok(Some(_))) {
                return;
            }
            std::thread::sleep(Duration::from_millis(10));
        }
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

fn wrap(text: &str, width: usize) -> Vec<String> {
    use unicode_width::UnicodeWidthChar;
    if width == 0 {
        return vec![];
    }
    let mut lines = vec![];
    for source in safe(text).split('\n') {
        let mut line = String::new();
        let mut size = 0;
        for c in source.chars() {
            let w = c.width().unwrap_or(0);
            if size + w > width && !line.is_empty() {
                if let Some(space) = line.rfind(' ').filter(|&i| i >= width / 3) {
                    let tail = line.split_off(space + 1);
                    lines.push(line);
                    line = tail;
                    size = unicode_width::UnicodeWidthStr::width(line.as_str());
                } else {
                    lines.push(line);
                    line = String::new();
                    size = 0;
                }
            }
            line.push(c);
            size += w;
        }
        lines.push(line);
    }
    lines
}
fn text(f: &mut Frame, area: Rect, value: impl Into<Text<'static>>, fg: Color) {
    f.render_widget(Paragraph::new(value).style(Style::default().fg(fg)), area);
}
fn item_lines(item: &Item, width: usize, selected: bool) -> Vec<(String, Color)> {
    match item.kind.as_str() {
        "tool" => vec![(
            format!(
                "{} {}  {}",
                if selected { "›" } else { " " },
                icon(&item.status),
                item.text
            ),
            color(&item.status),
        )],
        "correction" => {
            let mut lines = vec![(
                format!("your correction · {}", item.status),
                if item.status == "applied" {
                    GREEN
                } else {
                    AMBER
                },
            )];
            lines.extend(wrap(&item.text, width).into_iter().map(|s| (s, INK)));
            if item.status == "unconfirmed" {
                lines.extend(wrap("Insertion not confirmed. Not retried or queued; inspect before sending again.", width).into_iter().map(|s| (s, AMBER)));
            }
            lines.push((String::new(), INK));
            lines
        }
        "user" | "assistant" => {
            let mut lines = vec![(
                if item.kind == "user" {
                    "you"
                } else {
                    "amplifier"
                }
                .into(),
                if item.kind == "user" { MUTED } else { GREEN },
            )];
            lines.extend(wrap(&item.text, width).into_iter().map(|s| (s, INK)));
            lines.push((String::new(), INK));
            lines
        }
        _ => wrap(&item.text, width)
            .into_iter()
            .map(|s| (s, color(&item.status)))
            .collect(),
    }
}
fn draw(f: &mut Frame, app: &mut App) {
    app.ui.buttons.clear();
    let outer = f.area();
    f.render_widget(
        Block::default().style(Style::default().bg(BG).fg(INK)),
        outer,
    );
    if outer.width < 32 || outer.height < 12 {
        text(f, outer, "Please resize to at least 32 × 12", AMBER);
        return;
    }
    let a = outer;
    let pad = if a.width >= 80 { 3 } else { 2 };
    let inner = Rect::new(a.x + pad, a.y, a.width - 2 * pad, a.height);
    text(f, Rect::new(inner.x, 1, 12, 1), "amplifier", GREEN);
    text(
        f,
        Rect::new(inner.x + 14, 1, inner.width.saturating_sub(14), 1),
        app.title.clone(),
        INK,
    );
    text(
        f,
        Rect::new(inner.x, 2, inner.width, 1),
        format!(
            "Mode: {} · Ratatui · {} · {}",
            app.policy, app.mode, app.context
        ),
        MUTED,
    );
    app.tab_y = 4;
    f.render_widget(
        Block::default()
            .borders(Borders::TOP)
            .border_style(Style::default().fg(LINE)),
        Rect::new(a.x, 3, a.width, 3),
    );
    for (i, label) in ["F1  Work", "F2  Review", "F3  System"].iter().enumerate() {
        let rect = Rect::new(
            inner.x + i as u16 * 16,
            4,
            15.min(inner.width.saturating_sub(i as u16 * 16)),
            1,
        );
        app.button(f, rect, *label, Action::View(i));
    }
    if app.view < 2 && app.anchors[app.view].is_some() && inner.width > 70 {
        app.button(
            f,
            Rect::new(inner.x + 52, 4, 18, 1),
            "[ Latest ↓ ]",
            Action::Latest,
        );
    }
    let composer_h = if a.height >= 30 { 8 } else { 6 };
    let approval_h = if app.approval.is_some() {
        if a.height >= 30 { 7 } else { 5 }
    } else {
        0
    };
    let compose_y = a.height - composer_h;
    let question_h = if !app.questions.pending.is_empty() && approval_h == 0 && a.height >= 24 {
        4
    } else {
        0
    };
    let approval_y = compose_y - approval_h - question_h;
    app.body = Rect::new(inner.x, 6, inner.width, approval_y.saturating_sub(7));
    app.rows.clear();
    if app.expanded {
        if let Some(item) = app.items.get(app.selected) {
            text(
                f,
                Rect::new(app.body.x, app.body.y, app.body.width, 1),
                format!("Evidence · {}  [Esc close]", item.text),
                color(&item.status),
            );
            let lines = wrap(&item.detail, app.body.width as usize);
            app.detail_scroll = app.detail_scroll.min(
                lines
                    .len()
                    .saturating_sub(app.body.height.saturating_sub(2) as usize),
            );
            for (i, line) in lines
                .iter()
                .skip(app.detail_scroll)
                .take(app.body.height.saturating_sub(2) as usize)
                .enumerate()
            {
                text(
                    f,
                    Rect::new(app.body.x, app.body.y + 2 + i as u16, app.body.width, 1),
                    line.clone(),
                    if line.starts_with('-') {
                        RED
                    } else if line.starts_with('+') {
                        GREEN
                    } else {
                        INK
                    },
                );
            }
        }
    } else if app.view == 2 {
        let source = if app.ui.diagnostic_view {
            &app.ui.diagnostics
        } else {
            &app.system
        };
        let lines: Vec<_> = source
            .iter()
            .flat_map(|s| wrap(s, app.body.width as usize))
            .collect();
        for (i, line) in lines
            .iter()
            .skip(app.scroll[2])
            .take(app.body.height as usize)
            .enumerate()
        {
            text(
                f,
                Rect::new(app.body.x, app.body.y + i as u16, app.body.width, 1),
                line.clone(),
                if i == 0 { GREEN } else { MUTED },
            );
        }
    } else {
        let visible = app.transcript_rows();
        app.selection.visible = visible.iter().map(|(_, line)| line.to_string()).collect();
        let used = visible.len();
        let mut y = app.body.y;
        for (index, line) in visible {
            text(f, Rect::new(app.body.x, y, app.body.width, 1), line, INK);
            if app.items[index].kind == "tool" || app.items[index].kind == "question" {
                app.rows.push((y, index));
            }
            y += 1;
        }
        if app.view == 1 && used == 0 {
            text(f, app.body, "No tool evidence yet", MUTED);
        }
    }
    if app.selection.area != app.body {
        app.selection.start = None;
    }
    app.selection.draw(f);
    if question_h > 0 {
        let (id, row) = app.questions.pending.iter().next().unwrap();
        let id = id.clone();
        let prompt = safe(&string(&row["questions"][0], "question")).replace('\n', " ");
        text(
            f,
            Rect::new(inner.x, approval_y, inner.width, 1),
            "Question waiting · your draft stays yours",
            AMBER,
        );
        text(
            f,
            Rect::new(inner.x, approval_y + 1, inner.width, 1),
            prompt,
            INK,
        );
        app.button(
            f,
            Rect::new(inner.x, approval_y + 2, inner.width.min(28), 1),
            "[ Answer question ]",
            Action::QuestionOpen(id),
        );
    }
    if let Some(approval) = app.approval.clone() {
        let area = Rect::new(inner.x, approval_y, inner.width, approval_h);
        f.render_widget(
            Block::default()
                .borders(Borders::ALL)
                .border_type(BorderType::Rounded)
                .border_style(Style::default().fg(AMBER))
                .style(Style::default().bg(Color::Rgb(56, 47, 29)))
                .title(format!(" Decision needed · {} ", string(&approval, "id"))),
            area,
        );
        let x = area.x + 2;
        let w = area.width.saturating_sub(4);
        if approval_h >= 7 {
            text(
                f,
                Rect::new(x, area.y + 1, w, 1),
                safe(&string(&approval, "prompt")),
                INK,
            );
        }
        text(
            f,
            Rect::new(x, area.y + approval_h - 4, w, 1),
            safe(&string(&approval, "command")),
            AMBER,
        );
        // Compact card is an entry point. Full question/options live in Decisions.
        app.button(
            f,
            Rect::new(x, area.y + approval_h - 2, w.min(28), 1),
            "[ Review decision ]",
            Action::Decisions,
        );
    }
    draw_footer(f, app, a, inner, compose_y, composer_h);
}

fn draw_footer(
    f: &mut Frame,
    app: &mut App,
    a: Rect,
    inner: Rect,
    compose_y: u16,
    composer_h: u16,
) {
    app.button(
        f,
        Rect::new(inner.x, compose_y, 10.min(inner.width), 1),
        "[Resume]",
        Action::Conversations,
    );
    app.button(
        f,
        Rect::new(
            inner.x + 10,
            compose_y,
            13.min(inner.width.saturating_sub(10)),
            1,
        ),
        format!(
            "[Pending {}]",
            app.flow
                .rows
                .iter()
                .filter(|r| r["state"] == "queued")
                .count()
        ),
        Action::QueueList,
    );
    if inner.width >= 30 {
        app.button(
            f,
            Rect::new(inner.x + 23, compose_y, 7, 1),
            "[Steer]",
            Action::CorrectActive,
        );
    }
    if inner.width >= 42 {
        app.button(
            f,
            Rect::new(inner.x + 31, compose_y, 11, 1),
            "[Modes]",
            Action::Modes,
        );
    }
    let composer = Rect::new(inner.x, compose_y + 1, inner.width, composer_h - 3);
    let block = Block::default()
        .borders(Borders::ALL)
        .border_type(BorderType::Rounded)
        .border_style(
            Style::default().fg(if app.ui.focus.is_none() && app.ui.menu.is_none() {
                GREEN
            } else {
                LINE
            }),
        )
        .title(if app.nav.switching.is_some() {
            " Opening conversation · editing paused; Esc cancels "
        } else {
            " Message · draft stays editable "
        });
    let edit = block.inner(composer);
    f.render_widget(block, composer);
    f.render_widget(&app.draft, edit);
    let y = a.bottom() - 2;
    app.button(
        f,
        Rect::new(inner.x, y, inner.width.min(11), 1),
        if app.nav.switching.is_some() {
            "[ Cancel ]"
        } else {
            "[ Actions ]"
        },
        if app.nav.switching.is_some() {
            Action::CancelSwitch
        } else {
            Action::Menu
        },
    );
    app.button(
        f,
        Rect::new(inner.x + 12, y, inner.width.saturating_sub(12).min(9), 1),
        if !app.questions.pending.is_empty() && inner.width <= 54 {
            "[Answer]"
        } else if app.flow.busy && app.nav.enabled {
            "[ Queue ]"
        } else {
            "[ Send ]"
        },
        if !app.questions.pending.is_empty() && inner.width <= 54 {
            Action::QuestionOpen(app.questions.pending.keys().next().unwrap().clone())
        } else {
            Action::Send
        },
    );
    if inner.width > 28 {
        app.button(
            f,
            Rect::new(inner.x + 21, y, 8, 1),
            "[ Stop ]",
            Action::Stop,
        );
    }
    let helper_x = if !app.questions.pending.is_empty() && inner.width > 54 {
        app.button(
            f,
            Rect::new(inner.x + 30, y, 23, 1),
            format!("[ Answer questions {} ]", app.questions.pending.len()),
            Action::Questions,
        );
        54
    } else {
        30
    };
    if app.selection.start.is_some() && inner.width > 52 {
        app.button(
            f,
            Rect::new(inner.x + 30, y, 22, 1),
            "[ Copy selection ]",
            Action::CopySelection,
        );
    }
    if inner.width > helper_x + 12 && app.selection.start.is_none() {
        text(
            f,
            Rect::new(inner.x + helper_x, y, inner.width - helper_x, 1),
            format!(
                "Enter {} · Tab complete/actions · {} waiting{}",
                if app.flow.busy && app.nav.enabled {
                    "queue"
                } else {
                    "send"
                },
                app.flow
                    .rows
                    .iter()
                    .filter(|r| r["state"] == "queued")
                    .count(),
                if app.flow.paused { " (paused)" } else { "" }
            ),
            MUTED,
        );
    }
    f.render_widget(
        Paragraph::new(format!(" {}", app.status)).style(
            Style::default()
                .fg(if app.disconnected { RED } else { MUTED })
                .bg(PANEL),
        ),
        Rect::new(a.x, a.bottom() - 1, a.width, 1),
    );
    app.draw_menu(f);
    app.draw_prompt(f);
}

fn main() -> io::Result<()> {
    let args: Vec<String> = std::env::args().collect();
    let command: Vec<String> = args
        .windows(2)
        .find(|x| x[0] == "--host-json")
        .and_then(|x| serde_json::from_str(&x[1]).ok())
        .filter(|v: &Vec<String>| !v.is_empty())
        .ok_or_else(|| io::Error::other("Use scripts/compare.py ratatui to launch"))?;
    let mut app = App::new(command)?;
    let stop = Arc::new(AtomicBool::new(false));
    for signal in [signal_hook::consts::SIGTERM, signal_hook::consts::SIGINT] {
        signal_hook::flag::register(signal, stop.clone())?;
    }
    let mut terminal = native::Screen::new()?;
    let result = (|| -> io::Result<()> {
        let mut dirty = true;
        let mut last = Instant::now() - Duration::from_secs(1);
        let mut edge_tick = Instant::now();
        while !stop.load(Ordering::Relaxed) {
            for _ in 0..64 {
                match app.output.try_recv() {
                    Ok(v) => {
                        app.receive(v);
                        dirty = true;
                    }
                    Err(_) => break,
                }
            }
            app.ui.merge_history();
            if app.selection.start.is_some()
                && app.selection.dragging
                && app.ui.menu.is_none()
                && edge_tick.elapsed() >= Duration::from_millis(60)
            {
                if let Some((_, y)) = app.selection.pointer {
                    if y <= app.body.y {
                        app.selection.scroll(3);
                        dirty = true;
                    } else if y >= app.body.bottom().saturating_sub(1) {
                        app.selection.scroll(-3);
                        dirty = true;
                    }
                }
                edge_tick = Instant::now();
            }
            if app.durable
                && app.nav.switching.is_none()
                && app.draft_pending
                && app.draft_changed.elapsed() >= Duration::from_millis(250)
            {
                app.retain_editor();
                let draft = app.draft.lines().join("\n");
                if draft != app.saved_draft {
                    app.send(json!({"op":"draft","text":draft}));
                    app.saved_draft = draft;
                }
                app.draft_pending = false;
            }
            if dirty && last.elapsed() >= Duration::from_millis(16) {
                terminal.paint(&mut app)?;
                dirty = app.native.has_work();
                last = Instant::now();
            }
            if event::poll(Duration::from_millis(if dirty { 1 } else { 8 }))? {
                let event = event::read()?;
                match event {
                    Event::Key(key) => {
                        if !app.key(key) {
                            break;
                        }
                    }
                    Event::Paste(s) => {
                        if app.nav.switching.is_some() {
                            continue;
                        }
                        if let Some(prompt) = &mut app.flow.prompt {
                            if prompt.pending.is_none() {
                                prompt.editor.insert_str(if prompt.identity.is_some() {
                                    safe(&s)
                                } else {
                                    safe(&s).replace('\n', " ")
                                });
                            }
                        } else if let Some(menu) = &mut app.ui.menu {
                            menu.query.push_str(&safe(&s).replace('\n', " "));
                            menu.selected = 0;
                        } else {
                            app.ui.focus = None;
                            app.draft.insert_str(safe(&s));
                        }
                    }
                    Event::Mouse(_) if app.flow.prompt.is_some() => (),
                    Event::Mouse(m) => match m.kind {
                        MouseEventKind::Drag(_) if app.selection.dragging => {
                            app.selection.extend(m.column, m.row)
                        }
                        MouseEventKind::Up(_) if app.selection.dragging => {
                            app.selection.extend(m.column, m.row);
                            app.selection.dragging = false;
                            if app.selection.text().is_empty() {
                                app.selection.start = None;
                            } else {
                                app.status =
                                    "Text selected · Copy selection / Ctrl+C · Esc clears".into();
                            }
                        }
                        MouseEventKind::ScrollUp => app.navigate(3),
                        MouseEventKind::ScrollDown => app.navigate(-3),
                        MouseEventKind::Down(_) => {
                            let position = Position::new(m.column, m.row);
                            let action = if app.ui.menu.is_some() {
                                app.ui
                                    .menu_buttons
                                    .iter()
                                    .find(|(r, _)| r.contains(position))
                                    .map(|(_, a)| a.clone())
                            } else {
                                app.ui
                                    .buttons
                                    .iter()
                                    .find(|(r, _)| r.contains(position))
                                    .map(|(_, c)| c.action.clone())
                            };
                            if let Some(action) = action {
                                if !app.activate(action) {
                                    break;
                                }
                            } else if app.ui.menu.is_none()
                                && let Some((_, i)) = app.rows.iter().find(|(r, _)| *r == m.row)
                            {
                                let item = &app.items[*i];
                                if item.kind == "question" && item.status == "waiting" {
                                    app.question_open(item.id.clone());
                                } else {
                                    app.selected = *i;
                                    app.expanded = true;
                                    app.detail_scroll = 0;
                                }
                            } else if app.ui.menu.is_none()
                                && app.view < 2
                                && !app.expanded
                                && app.body.contains(position)
                            {
                                app.begin_selection(m.column, m.row);
                            } else if app.ui.menu.is_none() {
                                app.ui.focus = None;
                            }
                        }
                        _ => (),
                    },
                    _ => (),
                }
                dirty = true;
                app.draft_changed = Instant::now();
                app.draft_pending = true;
            }
            if let Some(value) = app.copy.take() {
                // Explicit user copy only; OSC52 is ignored by terminals without support.
                use base64::Engine;
                let encoded = base64::engine::general_purpose::STANDARD.encode(value.as_bytes());
                write!(io::stdout(), "\x1b]52;c;{}\x07", encoded)?;
                io::stdout().flush()?;
                app.status = "Source copied via OSC52 (terminal permission required)".into();
                dirty = true;
            }
            if std::mem::take(&mut app.insights.external_editor) {
                terminal.external_editor(&mut app)?;
                dirty = true;
            }
        }
        Ok(())
    })();
    let retained = terminal.finish(&mut app);
    result.and(retained)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn unicode_wrap_keeps_source() {
        let s = "界e\u{301}🦀abcdef";
        assert_eq!(wrap(s, 4).concat(), s);
    }
    #[test]
    fn controls_are_not_terminal_commands() {
        assert_eq!(safe("a\x1b[31m\x07b"), "a[31mb");
    }
    #[test]
    fn failure_keeps_red() {
        assert_eq!(color("failed"), RED);
        assert_eq!(icon("failed"), "×");
    }
}

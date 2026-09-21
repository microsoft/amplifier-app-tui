use chrome as activity;
use crossterm::{
    event::{
        self, DisableBracketedPaste, DisableFocusChange, DisableMouseCapture, EnableBracketedPaste,
        EnableFocusChange, EnableMouseCapture, Event, KeyCode, KeyEventKind, KeyModifiers,
        MouseEventKind,
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
use std::os::unix::process::CommandExt;
use std::{
    collections::{HashMap, HashSet},
    io::{self, BufRead, Read, Write},
    process::{Child, Command, Stdio},
    sync::{
        Arc,
        atomic::{AtomicBool, Ordering},
        mpsc::{self, Receiver},
    },
    time::{Duration, Instant},
};
mod chrome;
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
mod syntax;
mod tables;
mod transcript;
mod workflow;
mod workspace;
use interaction::{Action, Interaction};

#[derive(Clone, Copy)]
enum SyntaxTheme {
    Plain,
    Light,
    Dark,
}

struct Palette {
    bg: Color,
    panel: Color,
    ink: Color,
    muted: Color,
    line: Color,
    green: Color,
    amber: Color,
    red: Color,
    syntax_theme: SyntaxTheme,
}

impl Palette {
    fn named(name: &str, plain: bool) -> Self {
        if plain {
            return Self {
                bg: Color::Reset,
                panel: Color::Reset,
                ink: Color::Reset,
                muted: Color::Reset,
                line: Color::Reset,
                green: Color::Reset,
                amber: Color::Reset,
                red: Color::Reset,
                syntax_theme: SyntaxTheme::Plain,
            };
        }
        match name {
            "light" => Self {
                bg: Color::Rgb(240, 246, 255),
                panel: Color::Rgb(232, 233, 238),
                ink: Color::Rgb(13, 17, 23),
                muted: Color::Rgb(74, 80, 96),
                line: Color::Rgb(142, 149, 163),
                // Darkened brand accents preserve readable contrast on light.
                green: Color::Rgb(0, 104, 120),
                amber: Color::Rgb(139, 82, 0),
                red: Color::Rgb(178, 44, 40),
                syntax_theme: SyntaxTheme::Light,
            },
            "terminal" => Self {
                bg: Color::Reset,
                panel: Color::Reset,
                ink: Color::Reset,
                muted: Color::Reset,
                line: Color::Reset,
                green: Color::Reset,
                amber: Color::Reset,
                red: Color::Reset,
                syntax_theme: SyntaxTheme::Plain,
            },
            _ => Self {
                // muxplex brand.conf / tokens.css, reference f88898e.
                bg: Color::Rgb(13, 17, 23),
                panel: Color::Rgb(26, 31, 43),
                ink: Color::Rgb(240, 246, 255),
                muted: Color::Rgb(142, 149, 163),
                line: Color::Rgb(42, 48, 64),
                green: Color::Rgb(0, 217, 245),
                amber: Color::Rgb(241, 166, 64),
                red: Color::Rgb(248, 81, 73),
                syntax_theme: SyntaxTheme::Dark,
            },
        }
    }
}

fn palette() -> &'static Palette {
    static PALETTE: std::sync::OnceLock<Palette> = std::sync::OnceLock::new();
    PALETTE.get_or_init(|| {
        Palette::named(
            &std::env::var("AMPLIFIER_TUI_THEME").unwrap_or_default(),
            std::env::var_os("NO_COLOR").is_some(),
        )
    })
}

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
    anchor_offsets: [Option<(usize, usize)>; 2],
    layouts: Vec<Option<transcript::Layout>>,
    durable: bool,
    saved_draft: String,
    draft_changed: Instant,
    draft_pending: bool,
    user_activity: UserActivity,
    expanded: bool,
    interacting: bool,
    interaction_focus: bool,
    inline_open: HashSet<String>,
    background: String,
    selected: usize,
    detail_scroll: usize,
    request: u64,
    pending: HashMap<String, String>,
    child: Child,
    input: mpsc::SyncSender<String>,
    output: Receiver<Value>,
    disconnected: bool,
    ready: bool,
    connected: bool,
    ownership: String,
    startup_failure: String,
    startup_recovery: Option<String>,
    rows: Vec<(u16, usize)>,
    tab_y: u16,
    body: Rect,
    copy: Option<String>,
}

#[derive(Default)]
struct UserActivity {
    supported: bool,
    pending: bool,
    last_sent: Option<Instant>,
    external_editor: bool,
}

impl UserActivity {
    fn observe(&mut self, event: &Event) {
        self.pending |= match event {
            Event::Key(key) => key.kind != KeyEventKind::Release,
            Event::Paste(_) | Event::Mouse(_) | Event::Resize(..) | Event::FocusGained => true,
            Event::FocusLost => false,
        };
    }

    fn due(&self, now: Instant) -> bool {
        self.pending
            && self
                .last_sent
                .is_none_or(|last| now.duration_since(last) >= Duration::from_millis(250))
    }
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
        "failed" | "error" | "interrupted" | "cancelled" | "stopping" | "stopped" => palette().red,
        "succeeded" | "completed" => palette().green,
        "waiting" | "running" | "warning" | "unknown" => palette().amber,
        _ => palette().muted,
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
    draft.set_style(Style::default().fg(palette().ink).bg(palette().panel));
    draft.set_cursor_line_style(Style::default());
    draft.set_cursor_style(Style::default().fg(palette().bg).bg(palette().green));
    draft.set_selection_style(Style::default().fg(palette().ink).bg(palette().line));
    draft.set_placeholder_text("Ask, correct, or describe the next task…");
    draft.set_wrap_mode(ratatui_textarea::WrapMode::WordOrGlyph);
    draft
}

impl App {
    fn new(command: Vec<String>) -> io::Result<Self> {
        let mut child = Command::new(&command[0])
            .args(&command[1..])
            .process_group(0)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()?;
        let mut pipe = child.stdin.take().unwrap();
        let stdout = child.stdout.take().unwrap();
        let (tx, output) = mpsc::sync_channel(1024);
        // A non-reading host must not block key handling or the exit deadline.
        // Eight bounded records plus one in-flight write; never retry partial JSON.
        let (input, writes) = mpsc::sync_channel::<String>(8);
        let failure = tx.clone();
        std::thread::spawn(move || {
            while let Ok(record) = writes.recv() {
                if writeln!(pipe, "{record}")
                    .and_then(|_| pipe.flush())
                    .is_err()
                {
                    let _ = failure.send(json!({"type":"disconnected"}));
                    return;
                }
            }
        });
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
            ownership: String::new(),
            system: vec![],
            approval: None,
            view: 0,
            scroll: [0; 3],
            anchors: [None; 2],
            anchor_offsets: [None; 2],
            layouts: vec![],
            durable: false,
            saved_draft: String::new(),
            draft_changed: Instant::now(),
            draft_pending: false,
            user_activity: UserActivity::default(),
            expanded: false,
            interacting: false,
            interaction_focus: false,
            inline_open: HashSet::new(),
            background: "Starting runtime".into(),
            selected: 0,
            detail_scroll: 0,
            request: 0,
            pending: HashMap::new(),
            child,
            input,
            output,
            disconnected: false,
            ready: false,
            connected: false,
            startup_failure: String::new(),
            startup_recovery: None,
            rows: vec![],
            tab_y: 0,
            body: Rect::default(),
            copy: None,
        })
    }
    fn upsert(&mut self, item: Item) {
        if self.flow.busy && !self.disconnected {
            self.flow.clocks.observe(&item);
        }
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
                if native::expandable(&item) && !self.interaction_focus {
                    self.selected = self.items.len();
                }
                self.tool_indices.push(self.items.len());
            }
            self.items.push(item);
            self.layouts.push(None);
        }
    }
    fn receive(&mut self, v: Value) {
        if v["type"] != "disconnected" && v["version"] != 1 {
            self.flow.clocks.freeze();
            self.disconnected = true;
            self.status = "Protocol mismatch · no work retried".into();
            return;
        }
        match v["type"].as_str().unwrap_or("") {
            "snapshot" => {
                self.connected = v["connected"] == true;
                self.ownership.clear();
                if v["reset"] == true {
                    self.startup_failure.clear();
                    self.startup_recovery = None;
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
                    // Legacy stdout/stderr belongs to the process, not the
                    // conversation being replaced. Keep its count-only badge.
                    self.ui = Interaction {
                        runtime_output_lines: self.ui.runtime_output_lines,
                        runtime_output_omitted: self.ui.runtime_output_omitted,
                        runtime_output_failed: self.ui.runtime_output_failed,
                        ..Interaction::default()
                    };
                    self.pending.clear();
                    self.approval = None;
                    self.view = 0;
                    self.scroll = [0; 3];
                    self.anchors = [None; 2];
                    self.anchor_offsets = [None; 2];
                    self.expanded = false;
                    self.interacting = false;
                    self.interaction_focus = false;
                    self.inline_open.clear();
                    self.detail_scroll = 0;
                    self.copy = None;
                    // Undo/selection state belongs to the source conversation too.
                    self.draft = editor();
                    self.nav.lookup = None;
                    self.draft_pending = false;
                    self.user_activity = UserActivity::default();
                }
                self.nav.session = string(&v, "session_id");
                self.user_activity.supported = v["user_activity"] == true;
                self.controls.auth_prompt = None;
                self.controls.goal.clear();
                // Older v1 scene adapters have no readiness field; real hosts emit it.
                self.ready = v["ready"].as_bool().unwrap_or(true);
                if self.ready {
                    self.background.clear();
                }
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
                } else if !self.saved_draft.is_empty()
                    && self.draft.lines().join("\n") != self.saved_draft
                {
                    // Keep the live editor itself: cursor, selection and undo belong to
                    // the person already typing. Back up restored text before any write.
                    let nonce = std::time::SystemTime::now()
                        .duration_since(std::time::UNIX_EPOCH)
                        .unwrap_or_default()
                        .as_nanos();
                    let id = format!("startup:{nonce}");
                    self.insights.drafts.push(json!({"id":id,"kind":"startup",
                        "source":self.nav.session,"text":self.saved_draft}));
                    self.startup_recovery = Some(id);
                    self.draft_pending = true;
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
                self.selected = self.items.iter().rposition(native::expandable).unwrap_or(0);
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
            "remote_items" if v["session_id"] == self.nav.session => {
                // Authoritative projection replacement; native committed history stays intact.
                // Changed rows reuse their identity, so snapshots never append another copy.
                let selected = self.items.get(self.selected).map(|i| i.id.clone());
                let rows = v["items"].as_array().cloned().unwrap_or_default();
                let ids: HashSet<String> = rows.iter().map(|r| string(r, "id")).collect();
                self.native.retain(&ids);
                self.items.clear();
                self.index.clear();
                self.tool_indices.clear();
                self.layouts.clear();
                for row in rows {
                    if let Ok(item) = serde_json::from_value::<Item>(row) {
                        self.upsert(item);
                    }
                }
                self.selected = selected
                    .and_then(|id| self.index.get(&id).copied())
                    .unwrap_or(0);
                self.title = safe(&string(&v, "title"));
            }
            "input_pending" if v["session_id"] == self.nav.session => {
                let id = string(&v, "request_id");
                if let Some(text) = self.pending.get(&id)
                    && self.draft.lines().join("\n") == *text
                {
                    self.draft = editor();
                    self.draft_pending = true;
                    self.draft_changed = Instant::now();
                }
            }
            "delivery_draft" if v["session_id"] == self.nav.session => {
                let text = string(&v, "text");
                if self.draft.lines().join("\n").is_empty() {
                    self.draft.insert_str(text);
                    self.draft_pending = true;
                    self.draft_changed = Instant::now();
                } else {
                    self.insights
                        .drafts
                        .push(json!({"id":"delivery-recovery","text":text,"kind":"delivery"}));
                    self.status =
                        "Current draft kept; rejected input remains in saved drafts".into();
                }
            }
            "deliveries" if v["session_id"] == self.nav.session => {
                let mut choices = vec![];
                for row in v["entries"].as_array().unwrap_or(&vec![]) {
                    let id = string(row, "id");
                    let status = string(row, "status");
                    let text = row["args"]["text"].as_str().unwrap_or("");
                    if matches!(status.as_str(), "unknown" | "failed") {
                        choices.push(interaction::Choice {
                            label: format!(
                                "Retry exact request · {status} · {}",
                                safe(text).chars().take(50).collect::<String>()
                            ),
                            action: Action::RetryDelivery(id.clone()),
                            detail: safe(&row.to_string()),
                        });
                    }
                    if status == "failed" && row["action"] == "conversation.send" {
                        choices.push(interaction::Choice {
                            label: "Edit rejected input in empty composer".into(),
                            action: Action::EditDelivery(id),
                            detail: safe(text),
                        });
                    }
                    choices.push(interaction::Choice {
                        label: format!("Copy retained input · {status}"),
                        action: Action::CopyText(text.into()),
                        detail: safe(&row.to_string()),
                    });
                }
                self.menu("Message delivery · retries keep original identity", choices);
            }
            "history_page" => self.history_page_result(v),
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
                self.ui.history_legacy = v["legacy"] == true;
                self.ui.history_replace_count =
                    (v["replace"] == true).then_some(self.ui.history.len());
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
                self.controls.mode_names = v["mode_names"]
                    .as_array()
                    .unwrap_or(&vec![])
                    .iter()
                    .filter_map(|v| v.as_str().map(str::to_owned))
                    .collect();
                self.ui.commands = v["commands"]
                    .as_array()
                    .unwrap_or(&vec![])
                    .iter()
                    .filter_map(|v| v.as_str().map(str::to_owned))
                    .collect();
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
            "commands" if v["session_id"] == self.nav.session => {
                self.ui.commands = v["commands"]
                    .as_array()
                    .unwrap_or(&vec![])
                    .iter()
                    .filter_map(|v| v.as_str().map(str::to_owned))
                    .collect();
            }
            "background" => self.background = safe(&string(&v, "phase")),
            "runtime_output_status" => {
                self.ui.runtime_output_lines = v["lines"].as_u64().unwrap_or_default();
                self.ui.runtime_output_omitted = v["omitted"].as_u64().unwrap_or_default();
                self.ui.runtime_output_failed = v["failed"] == true;
            }
            "model_activity"
                if self.flow.busy
                    && v["session_id"] == self.nav.session
                    && v["turn_id"] == self.controls.turn =>
            {
                self.flow.meter.phase = safe(&string(&v, "phase"));
            }
            "ownership" if v["session_id"] == self.nav.session => {
                self.ownership = string(&v, "status");
                if matches!(self.ownership.as_str(), "blocked" | "yielded") {
                    self.policy = "read-only".into();
                }
                self.ready = matches!(self.ownership.as_str(), "owned" | "parked");
                self.status = safe(&string(&v, "message"));
                self.startup_failure.clear();
                self.background = if matches!(
                    self.ownership.as_str(),
                    "taking-over" | "activating" | "parking"
                ) {
                    self.status.clone()
                } else {
                    String::new()
                };
            }
            "state" => {
                if let Some(ready) = v["ready"].as_bool() {
                    self.ready = ready && (self.ownership.is_empty() || self.ownership == "owned");
                }
                self.flow.busy = v["busy"] == true;
                if !self.flow.busy {
                    self.flow.clocks.freeze();
                } else if self.controls.turn != string(&v, "turn_id") {
                    self.flow.clocks = native::ActivityClocks::default();
                }
                if !self.flow.busy {
                    self.flow.cancellation.clear();
                } else if let Some(stage) = v["cancellation"].as_str() {
                    self.flow.cancellation = stage.into();
                }
                self.controls.turn = if self.flow.busy {
                    string(&v, "turn_id")
                } else {
                    String::new()
                };
                self.flow.meter.state(&self.controls.turn, self.flow.busy);
                self.status = safe(&string(&v, "status"));
                if self.ready {
                    self.background.clear();
                    self.startup_failure.clear();
                } else if self.status.starts_with("Startup failed:") {
                    self.background.clear();
                    self.startup_failure = self.status.clone();
                    self.upsert(Item {
                        id: "startup-failure".into(), kind: "notice".into(),
                        text: format!("{}\nNothing sent. Your draft remains editable; correct the startup problem and relaunch.", self.status),
                        status: "failed".into(), ..Item::default()
                    });
                }
                self.approval = if v["approval"].is_object() {
                    Some(v["approval"].clone())
                } else {
                    None
                };
            }
            "turn_metrics"
                if self.flow.busy
                    && v["session_id"] == self.nav.session
                    && v["turn_id"] == self.controls.turn =>
            {
                self.flow.meter.observe(v);
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
                    // Delayed autosave refusal after failed startup keeps
                    // admission and local-only draft state explicit.
                    self.status = if self.ready || !self.ownership.is_empty() {
                        safe(&string(&v, "reason"))
                    } else {
                        format!(
                            "Session not ready · {} · draft retained locally",
                            if self.startup_failure.is_empty() {
                                safe(&string(&v, "reason"))
                            } else {
                                self.startup_failure.clone()
                            }
                        )
                    };
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
            "workspace_changes"
            | "workspace_diff"
            | "workspace_edit_prepare"
            | "workspace_edit_apply" => self.review_result(&v),
            "inspection" => self.inspection_result(v),
            "auth_prompt" if v["session_id"] == self.nav.session => {
                if v["active"] == true {
                    self.controls.auth_prompt = Some(safe(&string(&v, "text")));
                    if let Some(menu) = self
                        .ui
                        .menu
                        .as_mut()
                        .filter(|m| m.title.starts_with("Provider login ·"))
                    {
                        menu.detail = self.controls.auth_prompt.clone().unwrap_or_default();
                    }
                    self.status = "Login instructions available: Actions → Provider login prompt · Stop cancels".into();
                } else {
                    self.controls.auth_prompt = None;
                    self.status = safe(&string(&v, "text"));
                    if self
                        .ui
                        .menu
                        .as_ref()
                        .is_some_and(|m| m.title.starts_with("Provider login ·"))
                    {
                        self.ui.menu = None;
                    }
                }
            }
            "goal_status" if v["session_id"] == self.nav.session => {
                self.controls.goal = if v["active"] == true {
                    format!(
                        " · Goal ≤{} turns",
                        v["cap"]
                            .as_u64()
                            .map(|n| n.to_string())
                            .unwrap_or_else(|| "unlimited".into())
                    )
                } else {
                    String::new()
                };
            }
            "runtime_tools" if v["session_id"] == self.nav.session => {
                if let Some(start) = self
                    .system
                    .iter()
                    .position(|s| s.starts_with("Tools (mounted"))
                {
                    let end = self
                        .system
                        .iter()
                        .enumerate()
                        .skip(start + 1)
                        .find(|(_, s)| s.is_empty())
                        .map(|(i, _)| i)
                        .unwrap_or(start + 1);
                    self.system.splice(
                        start + 1..end,
                        v["tools"]
                            .as_array()
                            .unwrap_or(&vec![])
                            .iter()
                            .filter_map(|s| s.as_str().map(|s| format!("  • {}", safe(s)))),
                    );
                }
            }
            "provider_validation" if v["session_id"] == self.nav.session => {
                self.status = safe(&string(&v, "message"));
                if self
                    .ui
                    .menu
                    .as_ref()
                    .is_some_and(|m| m.title == "Provider validation · waiting")
                {
                    self.menu("Provider validation · observed result", vec![]);
                    self.ui.menu.as_mut().unwrap().detail = self.status.clone();
                }
            }
            "model_catalog" => self.model_catalog_result(v),
            "image_snapshot" => self.image_snapshot_result(v),
            "image_draft" => {
                if v["session_id"] == self.nav.session {
                    self.insights.image = v.get("image").filter(|v| !v.is_null()).cloned();
                }
            }
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
                    } else {
                        self.status = "Ready".into();
                    }
                }
            }
            "disconnected" => {
                self.flow.clocks.freeze();
                if !self.disconnected {
                    self.upsert(Item {
                        id: "connection-failure".into(),
                        kind: "notice".into(),
                        text: if self.ready {
                            "Runtime disconnected · outstanding outcomes may be uncertain. Copy your unsent draft before exiting; new edits cannot be saved. Relaunch explicitly; nothing is retried."
                        } else {
                            "Startup disconnected before readiness · nothing sent. Copy your unsent draft before exiting; new edits cannot be saved. Relaunch explicitly."
                        }.into(),
                        status: "failed".into(),
                        ..Item::default()
                    });
                }
                self.disconnected = true;
                self.ready = false;
                self.background.clear();
                if self.policy == "loading" {
                    self.policy = "unavailable".into();
                }
                self.nav.switching = None;
                self.nav.lookup = None;
                self.approval = None;
                self.controls.lookup = None;
                self.status =
                    "Disconnected · draft is local only; copy before exiting · no retry".into();
            }
            _ => (),
        }
    }
    fn not_ready(&mut self) {
        self.status = if self.disconnected {
            "Disconnected · draft is local only; copy before exiting · no retry".into()
        } else if matches!(self.ownership.as_str(), "blocked" | "yielded") {
            "Choose Continue here · draft retained".into()
        } else if self.startup_failure.is_empty() {
            "Session not ready · draft retained; send explicitly when ready".into()
        } else {
            format!(
                "Session not ready · {} · draft retained",
                self.startup_failure
            )
        };
    }
    fn flush_user_activity(&mut self, force: bool) -> bool {
        if !self.user_activity.supported || self.disconnected || self.nav.session.is_empty() {
            return false;
        }
        let now = Instant::now();
        if !force && !self.user_activity.due(now) {
            return false;
        }
        // Leading and trailing coalescing: continuous input is bounded, and the
        // final event still renews the timer. No request ID, reply or saved receipt.
        let record = json!({"version":1,"op":"user_activity",
            "session_id":self.nav.session,
            "external_editor":self.user_activity.external_editor})
        .to_string();
        match self.input.try_send(record) {
            Ok(()) => {
                self.user_activity.pending = false;
                self.user_activity.last_sent = Some(now);
                true
            }
            Err(mpsc::TrySendError::Full(_)) => false, // Retry latest presence only.
            Err(mpsc::TrySendError::Disconnected(_)) => {
                self.receive(json!({"type":"disconnected"}));
                false
            }
        }
    }

    fn send(&mut self, mut request: Value) {
        if self.disconnected {
            self.not_ready();
            return;
        }
        if let Some(image) = &self.insights.image
            && image["state"] == "attached"
            && (request["op"] == "submit" || request["op"] == "queue")
        {
            request["image_id"] = image["id"].clone();
        }
        if !self.ready
            && !matches!(self.ownership.as_str(), "blocked" | "yielded")
            && !matches!(
                request["op"].as_str(),
                Some(
                    "draft"
                        | "editor_draft"
                        | "cancel_switch"
                        | "stop"
                        | "continue_here"
                        | "deliveries"
                        | "edit_delivery"
                )
            )
        {
            self.not_ready();
            return;
        }
        if matches!(
            request["op"].as_str(),
            Some("draft" | "submit" | "queue" | "switch")
        ) && let Some(id) = &self.startup_recovery
            && let Some(row) = self.insights.drafts.iter().find(|r| r["id"] == *id)
        {
            request["startup_backup"] = row.clone();
        }
        self.request += 1;
        let id = self.request.to_string();
        request["version"] = json!(1);
        request["request_id"] = json!(id);
        if request["op"] == "continue_here" {
            self.controls.requests.insert(id.clone());
        }
        if !self.nav.session.is_empty() {
            request["session_id"] = json!(self.nav.session);
        }
        if request["op"] == "submit" || request["op"] == "queue" {
            if request["op"] == "queue" {
                self.flow.queued_requests.insert(id.clone());
            }
            self.pending.insert(id, string(&request, "text"));
        }
        let record = request.to_string();
        if record.len() > 1024 * 1024 || self.input.try_send(record).is_err() {
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
        if ctrl
            && matches!(key.code, KeyCode::Char(c) if c.eq_ignore_ascii_case(&'c'))
            && key.kind != KeyEventKind::Press
        {
            return true;
        }
        if let Some(keep_running) = self.quit_key(key) {
            return keep_running;
        }
        if self.interacting
            && self.interaction_focus
            && self.ui.menu.is_none()
            && self.flow.prompt.is_none()
            && self.ui.focus.is_none()
        {
            match key.code {
                KeyCode::Up | KeyCode::Down => {
                    let eligible: Vec<_> = self
                        .items
                        .iter()
                        .enumerate()
                        .filter(|(_, item)| native::expandable(item))
                        .map(|(index, _)| index)
                        .collect();
                    let index = if key.code == KeyCode::Down {
                        eligible
                            .iter()
                            .find(|index| **index > self.selected)
                            .or(eligible.first())
                    } else {
                        eligible
                            .iter()
                            .rev()
                            .find(|index| **index < self.selected)
                            .or(eligible.last())
                    };
                    if let Some(index) = index {
                        self.reveal_item(*index);
                    }
                    return true;
                }
                KeyCode::Enter if key.modifiers.is_empty() => {
                    return self.activate(Action::InlineToggle);
                }
                KeyCode::Char(_) if !ctrl => self.interaction_focus = false,
                _ => (),
            }
        }
        if self.ui.menu.is_none() && self.flow.prompt.is_none() && self.selection.start.is_some() {
            if ctrl && matches!(key.code, KeyCode::Char(c) if c.eq_ignore_ascii_case(&'c')) {
                self.copy = Some(self.selection.text());
                return true;
            }
            if key.code == KeyCode::Esc {
                self.selection.start = None;
                return true;
            }
        }
        if ctrl && matches!(key.code, KeyCode::Char(c) if c.eq_ignore_ascii_case(&'c')) {
            if self.flow.busy && !self.disconnected {
                self.send(json!({"op":"stop"}));
                return true;
            }
            self.flow.quit_confirmation = Some(false);
            return true;
        }
        if ctrl && key.code == KeyCode::Char('q') {
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
            KeyCode::Char('q') if ctrl => return false,
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
                if self.interacting {
                    self.status = "Native copy · terminal/tmux owns selection".into();
                }
                self.interacting = false;
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
        let _ = self
            .input
            .try_send("{\"version\":1,\"op\":\"shutdown\"}".into());
        let start = Instant::now();
        let mut finished = None;
        while start.elapsed() < Duration::from_secs(3) {
            if let Ok(Some(status)) = self.child.try_wait() {
                finished = Some(status);
                break;
            }
            std::thread::sleep(Duration::from_millis(10));
        }
        // CommandExt created this group, never the terminal/user's group. Detached
        // descendants and remote effects are deliberately outside this claim.
        unsafe {
            libc::kill(-(self.child.id() as i32), libc::SIGKILL);
        }
        if finished.is_none() {
            // Also target the direct child if it changed its own process group.
            // Never turn a failed kill or an uninterruptible OS task into another
            // unlimited terminal wait; report lack of confirmation instead.
            let _ = self.child.kill();
            let reap = Instant::now();
            let mut reaped = false;
            while reap.elapsed() < Duration::from_millis(500) {
                if matches!(self.child.try_wait(), Ok(Some(_))) {
                    reaped = true;
                    break;
                }
                std::thread::sleep(Duration::from_millis(10));
            }
            if !reaped {
                eprintln!(
                    "Host termination could not be confirmed (owned PID {}). Inspect local processes; cleanup is incomplete.",
                    self.child.id()
                );
            }
        }
        if finished.is_none() {
            eprintln!(
                "Amplifier host forced to exit after 3 seconds. Module cleanup and outstanding effects are uncertain; nothing was retried or undone. Detached or remote work may remain."
            );
        } else if finished.is_some_and(|status| !status.success()) {
            eprintln!(
                "Amplifier host exited with an error. Cleanup/outcomes may be uncertain; inspect retained history before recovery."
            );
        }
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
fn item_lines(
    kind: &str,
    text: &str,
    status: &str,
    width: usize,
    selected: bool,
) -> Vec<(String, Color)> {
    match kind {
        "tool" => {
            let mut source = text.lines();
            let heading = format!(
                "{}{}  {} · {}",
                if selected { "› " } else { "" },
                icon(status),
                source.next().unwrap_or("Tool"),
                status
            );
            let mut rows: Vec<_> = wrap(&heading, width)
                .into_iter()
                .map(|s| (s, color(status)))
                .collect();
            for line in source.take(10) {
                rows.extend(wrap(line, width).into_iter().map(|s| {
                    (
                        s,
                        if status == "failed" {
                            palette().amber
                        } else {
                            palette().muted
                        },
                    )
                }));
            }
            rows
        }
        "correction" => {
            let mut lines = vec![(
                format!("your correction · {}", status),
                if status == "applied" {
                    palette().green
                } else {
                    palette().amber
                },
            )];
            lines.extend(wrap(text, width).into_iter().map(|s| (s, palette().ink)));
            if status == "unconfirmed" {
                lines.extend(wrap("Insertion not confirmed. Not retried or queued; inspect before sending again.", width).into_iter().map(|s| (s, palette().amber)));
            }
            lines.push((String::new(), palette().ink));
            lines
        }
        "user" | "assistant" => {
            let mut lines = vec![(
                if kind == "user" { "you" } else { "amplifier" }.into(),
                if kind == "user" {
                    palette().muted
                } else {
                    palette().green
                },
            )];
            lines.extend(wrap(text, width).into_iter().map(|s| (s, palette().ink)));
            lines.push((String::new(), palette().ink));
            lines
        }
        _ => wrap(text, width)
            .into_iter()
            .map(|s| (s, color(status)))
            .collect(),
    }
}
fn draw(f: &mut Frame, app: &mut App) {
    app.ui.buttons.clear();
    let outer = f.area();
    f.render_widget(
        Block::default().style(Style::default().bg(palette().bg).fg(palette().ink)),
        outer,
    );
    if outer.width < 32 || outer.height < 12 {
        text(
            f,
            outer,
            "Please resize to at least 32 × 12",
            palette().amber,
        );
        return;
    }
    let a = outer;
    let inner = a;
    text(
        f,
        Rect::new(inner.x, 1, 12, 1),
        "amplifier",
        palette().green,
    );
    text(
        f,
        Rect::new(inner.x + 14, 1, inner.width.saturating_sub(14), 1),
        app.title.clone(),
        palette().ink,
    );
    text(
        f,
        Rect::new(inner.x, 2, inner.width, 1),
        format!(
            "Mode: {}{} · {}",
            app.policy,
            chrome::runtime_notice(&app.mode),
            app.context
        ),
        palette().muted,
    );
    app.tab_y = 4;
    f.render_widget(
        Block::default()
            .borders(Borders::TOP)
            .border_style(Style::default().fg(palette().line)),
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
    let composer_h = if a.height >= 30 { 9 } else { 6 };
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
    app.resize_transcript(inner.width);
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
                        palette().red
                    } else if line.starts_with('+') {
                        palette().green
                    } else {
                        palette().ink
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
                if i == 0 {
                    palette().green
                } else {
                    palette().muted
                },
            );
        }
    } else {
        let visible = app.transcript_rows();
        app.selection.visible = visible.iter().map(|(_, line)| line.to_string()).collect();
        let used = visible.len();
        for (y, (index, line)) in (app.body.y..).zip(visible) {
            text(
                f,
                Rect::new(app.body.x, y, app.body.width, 1),
                line,
                palette().ink,
            );
            if app.items[index].kind == "tool" || app.items[index].kind == "question" {
                app.rows.push((y, index));
            }
        }
        if app.view == 1 && used == 0 {
            text(f, app.body, "No tool evidence yet", palette().muted);
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
            palette().amber,
        );
        text(
            f,
            Rect::new(inner.x, approval_y + 1, inner.width, 1),
            prompt,
            palette().ink,
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
                .border_style(Style::default().fg(palette().amber))
                .style(Style::default().bg(palette().panel))
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
                palette().ink,
            );
        }
        text(
            f,
            Rect::new(x, area.y + approval_h - 4, w, 1),
            safe(&string(&approval, "command")),
            palette().amber,
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
    if inner.width >= 36 {
        app.button(
            f,
            Rect::new(inner.x + 23, compose_y, 13, 1),
            "[Change task]",
            Action::CorrectActive,
        );
    }
    if inner.width >= 45 {
        app.button(
            f,
            Rect::new(inner.x + 37, compose_y, 8, 1),
            "[Modes]",
            Action::Modes,
        );
    }
    let composer = Rect::new(inner.x, compose_y + 1, inner.width, composer_h - 3);
    text(
        f,
        Rect::new(composer.x, composer.y, composer.width, 1),
        if app.nav.switching.is_some() {
            "Opening conversation · editing paused; Esc cancels"
        } else {
            "Message · draft stays editable"
        },
        palette().green,
    );
    let edit = Rect::new(
        composer.x,
        composer.y + 2,
        composer.width,
        composer.height.saturating_sub(3).max(1),
    );
    f.render_widget(
        Block::default().style(Style::default().bg(palette().panel)),
        Rect::new(
            composer.x,
            composer.y + 1,
            composer.width,
            composer.height - 1,
        ),
    );
    composer::render_fitted(&mut app.draft, edit, f.buffer_mut());
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
            palette().muted,
        );
    }
    f.render_widget(
        Paragraph::new(format!(" {}", chrome::status_label(&app.status))).style(
            Style::default()
                .fg(if app.disconnected {
                    palette().red
                } else {
                    palette().muted
                })
                .bg(palette().panel),
        ),
        Rect::new(a.x, a.bottom() - 1, a.width, 1),
    );
    app.draw_menu(f);
    app.draw_prompt(f);
    app.draw_quit_confirmation(f);
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
    let interrupt = Arc::new(AtomicBool::new(false));
    signal_hook::flag::register(signal_hook::consts::SIGTERM, stop.clone())?;
    signal_hook::flag::register(signal_hook::consts::SIGINT, interrupt.clone())?;
    let mut terminal = native::Screen::new()?;
    let result = (|| -> io::Result<()> {
        let mut dirty = true;
        let mut last = Instant::now() - Duration::from_secs(1);
        let mut edge_tick = Instant::now();
        while !stop.load(Ordering::Relaxed) {
            if interrupt.swap(false, Ordering::Relaxed) {
                app.user_activity.pending = true;
                if !app.key(crossterm::event::KeyEvent::new(
                    KeyCode::Char('c'),
                    KeyModifiers::CONTROL,
                )) {
                    break;
                }
                dirty = true;
            }
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
            app.refresh_children();
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
            // Quiet tools still owe elapsed-time feedback; repaint only the live
            // projection, never append timer ticks to terminal or saved history.
            if activity::repaint_after(&app).is_some_and(|period| last.elapsed() >= period) {
                dirty = true;
            }
            if dirty && last.elapsed() >= Duration::from_millis(16) {
                terminal.paint(&mut app)?;
                dirty = app.native.has_work();
                last = Instant::now();
            }
            if event::poll(Duration::from_millis(if dirty { 1 } else { 8 }))? {
                let event = event::read()?;
                app.user_activity.observe(&event);
                app.flush_user_activity(false);
                match event {
                    Event::Key(key) => {
                        if !app.key(key) {
                            break;
                        }
                    }
                    Event::Paste(s) => {
                        if app.nav.switching.is_some() || app.flow.quit_confirmation.is_some() {
                            continue;
                        }
                        // Large pasted intent should not wait for the typing debounce.
                        // The ordinary bounded transport still owns persistence; never Send.
                        app.draft_changed = Instant::now() - Duration::from_millis(250);
                        app.draft_pending = true;
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
                            app.interaction_focus = false;
                            app.draft.insert_str(safe(&s));
                        }
                    }
                    Event::Mouse(m) if app.flow.quit_confirmation.is_some() => {
                        if matches!(m.kind, MouseEventKind::Down(_)) {
                            let choice = app
                                .flow
                                .quit_buttons
                                .iter()
                                .find(|(area, _)| area.contains((m.column, m.row).into()))
                                .map(|(_, yes)| *yes);
                            if choice == Some(true) {
                                break;
                            }
                            if choice == Some(false) {
                                app.flow.quit_confirmation = None;
                            }
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
                                    if app.interacting {
                                        app.interaction_focus = true;
                                        app.activate(Action::InlineToggle);
                                    } else {
                                        app.expanded = true;
                                    }
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
                                app.interaction_focus = false;
                            }
                        }
                        _ => (),
                    },
                    _ => (),
                }
                dirty = true;
                // Measure from the first unsaved event, not the last keystroke.
                // Continuous typing must not postpone autosave indefinitely.
                if !app.draft_pending {
                    app.draft_changed = Instant::now();
                }
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
            app.flush_user_activity(false);
            if std::mem::take(&mut app.insights.external_editor) {
                app.user_activity.external_editor = true;
                if !app.user_activity.supported || app.flush_user_activity(true) {
                    let result = terminal.external_editor(&mut app);
                    app.user_activity.external_editor = false;
                    app.user_activity.pending = true;
                    app.flush_user_activity(true);
                    result?;
                } else {
                    app.user_activity.external_editor = false;
                    app.status = "Controls busy · try opening the editor again".into();
                }
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
    fn presence_is_coalesced_with_a_trailing_input_notification() {
        let start = Instant::now();
        let mut activity = UserActivity::default();
        assert!(!activity.due(start)); // Painting/time alone never sends presence.
        activity.observe(&Event::Key(event::KeyEvent::new(
            KeyCode::Left,
            KeyModifiers::NONE,
        )));
        assert!(activity.due(start));
        activity.pending = false;
        activity.last_sent = Some(start);
        for _ in 0..1000 {
            activity.observe(&Event::Paste("draft".into()));
        }
        assert!(!activity.due(start + Duration::from_millis(249)));
        assert!(activity.due(start + Duration::from_millis(250)));
        activity.pending = false;
        assert!(!activity.due(start + Duration::from_secs(300)));
    }

    #[test]
    fn presence_counts_navigation_mouse_resize_and_focus_return_not_focus_loss() {
        for event in [
            Event::Key(event::KeyEvent::new(KeyCode::PageUp, KeyModifiers::NONE)),
            Event::Mouse(event::MouseEvent {
                kind: MouseEventKind::ScrollUp,
                column: 10,
                row: 3,
                modifiers: KeyModifiers::NONE,
            }),
            Event::Resize(175, 50),
            Event::FocusGained,
        ] {
            let mut activity = UserActivity::default();
            activity.observe(&event);
            assert!(activity.pending);
        }
        let mut activity = UserActivity::default();
        activity.observe(&Event::FocusLost);
        activity.observe(&Event::Key(event::KeyEvent::new_with_kind(
            KeyCode::Left,
            KeyModifiers::NONE,
            KeyEventKind::Release,
        )));
        assert!(!activity.pending);
    }

    #[test]
    fn brand_text_roles_have_readable_contrast_on_both_surfaces() {
        let luminance = |c| {
            let Color::Rgb(r, g, b) = c else {
                panic!("expected RGB")
            };
            let linear = |v: u8| {
                let s = f64::from(v) / 255.0;
                if s <= 0.04045 {
                    s / 12.92
                } else {
                    ((s + 0.055) / 1.055).powf(2.4)
                }
            };
            0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b)
        };
        for name in ["dark", "light"] {
            let p = Palette::named(name, false);
            for surface in [p.bg, p.panel] {
                for foreground in [p.ink, p.muted, p.green, p.amber, p.red] {
                    let (a, b) = (luminance(surface), luminance(foreground));
                    assert!(
                        (a.max(b) + 0.05) / (a.min(b) + 0.05) >= 4.5,
                        "{name}: {foreground:?} on {surface:?}"
                    );
                }
            }
        }
    }
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
    fn bare_control_commands_reach_the_host() {
        for command in ["/config", "/provider", "/mode"] {
            assert_eq!(App::local_action(command), None);
        }
        assert_eq!(
            App::local_action("/system"),
            Some(interaction::Action::View(2))
        );
        assert_eq!(
            App::local_action("/providers"),
            Some(interaction::Action::Providers)
        );
        assert_eq!(
            App::local_action("/modes"),
            Some(interaction::Action::Modes)
        );
    }
    #[test]
    fn failure_keeps_red() {
        assert_eq!(color("failed"), palette().red);
        for status in ["interrupted", "stopping", "stopped", "cancelled"] {
            assert_eq!(color(status), palette().red);
        }
        assert_eq!(icon("failed"), "×");
    }
}

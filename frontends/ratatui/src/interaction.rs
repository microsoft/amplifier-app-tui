//! Local interaction policy. Execution still belongs to the identified host boundary.
use super::*;
use ratatui::widgets::Clear;

#[derive(Clone, Debug, PartialEq)]
pub(super) enum Action {
    Menu,
    Conversations,
    ConversationPage(usize, String),
    FindSaved,
    RecipeRequest(String),
    StopForDraft,
    StopForDraftApply(String),
    Models,
    DiscoverModels,
    Rename,
    Find,
    Replies,
    CodeBlocks,
    CodeBlock(Arc<code_blocks::CodeBlock>),
    CopyCode(Arc<code_blocks::CodeBlock>),
    Message(String),
    Jump(String),
    CopyMessage(String),
    CopyText(String),
    CopySelection,
    NativeScrollback,
    Transcript,
    Export,
    Modes,
    ModeNamed(String),
    ModeChoice(Option<String>, Option<String>),
    ModeApply(Option<String>, Option<String>),
    QueueDraft,
    QueueList,
    QueueItem(String),
    QueueEdit(String),
    QueueControl(String, String),
    QueueResolve(String),
    QueueResolveConfirm(String),
    CorrectActive,
    Corrections,
    CorrectionDraft(String),
    CorrectionDraftApply(String, String),
    Questions,
    WorkspaceChanges,
    WorkspaceDiff(String, String),
    WorkspaceEditPrepare(String, String),
    WorkspaceEdit(Arc<Value>),
    WorkspaceEditApply(Arc<Value>, String),
    WorkspaceHunks(Arc<Value>),
    WorkspaceHunk(Arc<Value>, usize),
    WorkspaceSide(Arc<Value>, usize),
    CopySource(Arc<str>),
    QuestionGroup(String),
    QuestionOpen(String),
    QuestionEdit(String, String),
    QuestionChoice(String, String, String),
    QuestionText(String, String),
    QuestionSubmit(String),
    QuestionCancel(String),
    Providers,
    ForkComposition,
    ForkCompositionApply(String),
    ProviderHistory,
    ProviderValidateChoice(String),
    ProviderValidate(String),
    ProviderChoice(Option<String>, u64, Option<String>),
    ProviderApply(Option<String>, u64, Option<String>),
    CancelSwitch,
    Switch(String),
    RecoverChoice(String),
    Recover(String),
    RecoverChild(Arc<Value>),
    RecoverChildApply(Arc<Value>, String),
    Latest,
    View(usize),
    Section(String),
    Send,
    Stop,
    Decisions,
    Decision(String, String),
    Evidence,
    NextTool,
    Copy,
    History,
    Recall(String),
    Complete(usize, usize, usize, String),
    Diagnostics,
    LocalDrafts,
    FileInput,
    ImageInput,
    ReferenceInput,
    RequestDiagnostic,
    RequestCapture,
    RequestClear,
    ClipboardImage,
    ImageDraft,
    ImageSelect(String),
    ImageRemove(String),
    ImageRemoveItem(String, String),
    InsertFile(Arc<Value>, String),
    ExternalEditor,
    Inspect(String, Option<String>),
    Observation(Value),
    LocalDraft(Value),
    RemoveDraft(String),
    Help,
    HelpTopic(String, String),
    Quit,
}

#[derive(Clone)]
pub(super) struct Choice {
    pub label: String,
    pub action: Action,
    pub detail: String,
}

pub(super) struct Menu {
    pub title: String,
    pub detail: String,
    pub detail_scroll: usize,
    pub query: String,
    pub selected: usize,
    pub choices: Vec<Choice>,
    pub diff: bool,
    pub side_by_side: bool,
    pub code: Option<Arc<code_blocks::CodeBlock>>,
    pub image: Option<Value>,
    pub detail_cache: Option<(u16, bool, String, Vec<Line<'static>>)>,
}

impl Menu {
    pub fn filtered(&self) -> Vec<Choice> {
        self.choices
            .iter()
            .filter(|c| c.label.to_lowercase().contains(&self.query.to_lowercase()))
            .cloned()
            .collect()
    }
}

#[derive(Default)]
pub(super) struct Interaction {
    pub menu: Option<Menu>,
    pub focus: Option<Action>,
    pub buttons: Vec<(Rect, Choice)>,
    pub menu_buttons: Vec<(Rect, Action)>,
    pub history: Vec<String>,
    pub prior_history: Option<Vec<String>>,
    pub history_partial: bool,
    pub history_legacy: bool,
    pub history_replace_count: Option<usize>,
    pub diagnostics: Vec<String>,
    pub diagnostic_view: bool,
    pub skills: Vec<String>,
    pub recall: composer::Recall,
}

impl Interaction {
    pub fn merge_history(&mut self) {
        if self.recall.active() {
            return;
        }
        if let Some(mut prior) = self.prior_history.take() {
            if let Some(count) = self.history_replace_count.take() {
                self.history.drain(..count.min(self.history.len()));
            }
            prior.append(&mut self.history);
            if prior.len() > 1000 {
                prior.drain(..prior.len() - 1000);
            }
            self.history = prior;
        }
    }
}

fn choice(label: impl Into<String>, action: Action) -> Choice {
    Choice {
        label: label.into(),
        action,
        detail: String::new(),
    }
}

impl App {
    pub fn menu(&mut self, title: impl Into<String>, choices: Vec<Choice>) {
        self.ui.menu = Some(Menu {
            title: title.into(),
            detail: String::new(),
            detail_scroll: 0,
            query: String::new(),
            selected: 0,
            choices,
            diff: false,
            side_by_side: false,
            code: None,
            image: None,
            detail_cache: None,
        });
    }

    pub fn activate(&mut self, action: Action) -> bool {
        if !self.ready
            && !matches!(
                action,
                Action::Menu
                    | Action::Help
                    | Action::HelpTopic(..)
                    | Action::Quit
                    | Action::LocalDrafts
                    | Action::LocalDraft(..)
                    | Action::CopyText(..)
                    | Action::CancelSwitch
            )
        {
            self.status = "Session not ready · draft retained; send explicitly when ready".into();
            return true;
        }
        if self.nav.switching.is_some() && !matches!(action, Action::CancelSwitch | Action::Quit) {
            return true;
        }
        self.ui.menu = None;
        self.ui.focus = None;
        self.review_request = None;
        match action {
            Action::Menu => self.menu(
                "Actions · type to search",
                vec![
                    choice("Getting started — Help for everyday tasks", Action::Help),
                    choice("Work — conversation", Action::View(0)),
                    choice("Latest — follow new output", Action::Latest),
                    choice("Find in conversation — search retained message text", Action::Find),
                    choice("Assistant replies — inspect / copy Markdown", Action::Replies),
                    choice("Copy selection — selected visible text", Action::CopySelection),
                    choice("Native scrollback — return to normal terminal", Action::NativeScrollback),
                    choice("Transcript — inspect, reflow and select text", Action::Transcript),
                    choice("Export conversation — private Markdown file", Action::Export),
                    choice("Modes — choose session tool policy", Action::Modes),
                    choice("Code blocks — inspect / copy without executing", Action::CodeBlocks),
                    choice("Rename conversation", Action::Rename),
                    choice("Queue current draft as a follow-up", Action::QueueDraft),
                    choice("Saved local drafts — answers and corrections", Action::LocalDrafts),
                    choice("Insert text file — preview a workspace snapshot", Action::FileInput),
                    choice("Edit in external editor — return to unsent draft", Action::ExternalEditor),
                    choice("Delegated work — inspect agents and recipe children", Action::Inspect("children".into(), None)),
                    choice("Activity evidence — tools and runtime observations", Action::Inspect("activity".into(), None)),
                    choice("Context intelligence — usage, compaction and logging", Action::Inspect("context".into(), None)),
                    choice("Stored context — inspect current module messages", Action::Inspect("stored_context".into(), None)),
                    choice("Provider request diagnostic — explicit one-shot capture", Action::RequestDiagnostic),
                    choice("Instruction sources — inspect resolved context origins", Action::Inspect("instructions".into(), None)),
                    choice("Attach image — PNG/JPEG snapshot", Action::ImageInput),
                    choice("Attach file reference — path and line range", Action::ReferenceInput),
                    choice("Paste image — read host desktop clipboard", Action::ClipboardImage),
                    choice("Attached images / references — inspect or remove", Action::ImageDraft),
                    choice("Search saved conversations — local content search", Action::FindSaved),
                    choice("Recipe activity — inspect runs and prepare a review request", Action::Inspect("recipes".into(), None)),
                    choice("Recovered work — historical child and action evidence", Action::Inspect("recovery".into(), None)),
                    choice("Change and command evidence — agent, call and source versions", Action::Inspect("changes".into(), None)),
                    choice("Model catalog — discover configured providers' model IDs", Action::Models),
                    choice("New provider composition — fork captured public context", Action::ForkComposition),
                    choice("Pending follow-ups — inspect / pause / run / remove", Action::QueueList),
                    choice("Corrections — inspect insertion status / copy text", Action::Corrections),
                    choice("Questions — answer / review / cancel clarification requests", Action::Questions),
                    choice("Workspace changes — read-only Git status / diff", Action::WorkspaceChanges),
                    choice(
                        "Skills — discovered catalog (not automatically loaded)",
                        Action::Section("Skills (".into()),
                    ),
                    choice(
                        "Conversation provider — inspect / select mounted model",
                        Action::Providers,
                    ),
                    choice("Review — tool evidence", Action::View(1)),
                    choice(
                        "System — tools, providers and capabilities",
                        Action::View(2),
                    ),
                    choice(
                        "Decisions — inspect question and choices",
                        Action::Decisions,
                    ),
                    choice("Evidence — expand selected tool", Action::Evidence),
                    choice("Next tool", Action::NextTool),
                    choice("Copy exact tool evidence", Action::Copy),
                    choice("History — recall a sent message", Action::History),
                    choice("Stop active turn (does not undo effects)", Action::Stop),
                    choice("Stop and keep replacement draft — review before sending", Action::StopForDraft),
                    choice(
                        "Composition details — diagnostic record",
                        Action::Diagnostics,
                    ),
                    choice(
                        "Correct active turn — steer (not a queued follow-up)",
                        Action::CorrectActive,
                    ),
                    choice(
                        "Resume — return to a saved conversation",
                        Action::Conversations,
                    ),
                    choice("New conversation — save this draft and start fresh", Action::Switch("new".into())),
                    choice(if self.durable { "Quit — save draft and conversation" } else { "Quit — unsent draft is not saved" }, Action::Quit),
                ],
            ),
            Action::Section(prefix) => {
                self.view = 2;
                self.expanded = false;
                self.ui.diagnostic_view = false;
                self.scroll[2] = self
                    .system
                    .iter()
                    .take_while(|s| !s.starts_with(&prefix))
                    .map(|s| wrap(s, self.body.width as usize).len())
                    .sum();
            }
            Action::Latest => {
                if self.view < 2 { self.anchors[self.view] = None; }
                self.expanded = false;
            }
            Action::Conversations => self.conversation_page(0, String::new()),
            Action::ConversationPage(offset, query) => self.conversation_page(offset, query),
            Action::FindSaved => self.prompt("Search saved conversations"),
            Action::Models => {
                self.menu("Model catalog · explicit discovery", vec![choice("Query configured providers (may contact their services)", Action::DiscoverModels)]);
                self.ui.menu.as_mut().unwrap().detail = "Queries module-reported model catalogs, not a model completion. Does not change providers, models, credentials, routing or the draft. Catalogs may be static; access is not validated.".into();
            }
            Action::DiscoverModels => {
                self.insights.lookup = Some((self.request + 1).to_string());
                self.menu("Model catalog · querying", vec![]);
                self.send(json!({"op":"discover_models"}));
            }
            Action::RecipeRequest(identity) => {
                self.draft.insert_str(format!("\nPlease inspect recipe session {} and explain its completed and unfinished steps. I am considering an explicit resume; do not resume, retry, approve, or execute anything until I confirm after your explanation.", serde_json::to_string(&identity).unwrap()));
                self.status = "Recipe review request added to draft · edit and Send explicitly".into();
            }
            Action::ImageInput => self.prompt("Attach image"),
            Action::ReferenceInput => self.prompt("Attach file reference"),
            Action::RequestDiagnostic => {
                self.menu("Provider request · private diagnostic", vec![
                    choice("Arm one-shot capture (private context in memory)", Action::RequestCapture),
                    choice("Inspect captured provider request", Action::Inspect("wire_request".into(), None)),
                    choice("Clear capture and disarm", Action::RequestClear),
                ]);
                self.ui.menu.as_mut().unwrap().detail = "Explicit diagnostic: may expose private prompts, tool schemas and source content. The next root provider request is captured only if its module exposes raw fields; this never enables provider raw logging or sends a request. Capture stays in memory, not the app journal; module-authored logging is independent. Media/auth/oversize fields omitted. Not exact wire serialization or delivery proof. Escape changes nothing.".into();
            },
            Action::RequestCapture => {
                self.send(json!({"op":"request_capture", "confirm_private_context":true}));
                self.inspect("wire_request".into(), None);
            },
            Action::RequestClear => {
                self.send(json!({"op":"request_clear"}));
                self.inspect("wire_request".into(), None);
            },
            Action::ClipboardImage => {
                self.insights.file_request = Some(((self.request + 1).to_string(), self.draft.lines().join("\n")));
                self.menu("Text file · reading", vec![]);
                self.send(json!({"op":"clipboard_image"}));
            }
            Action::ImageDraft => self.image_draft_menu(),
            Action::ImageSelect(id) => self.send(json!({"op":"image_select", "id":id})),
            Action::ImageRemove(id) => self.send(json!({"op":"image_remove", "id":id})),
            Action::ImageRemoveItem(id, item_id) => self.send(json!({"op":"image_remove", "id":id, "item_id":item_id})),
            Action::RecoverChoice(id) => {
                self.menu("Recover into a new conversation?",vec![choice("Create recovered conversation — no replay",Action::Recover(id))]);
                self.ui.menu.as_mut().unwrap().detail="The original stays unchanged. Historical transcript becomes reference context, not pending execution. No tools or queued work are replayed. Partial external effects may remain. Escape cancels.".into();
            }
            Action::RecoverChild(row) => {
                self.flow.recovery = Some(row);
                self.prompt("Continue captured child");
            }
            Action::RecoverChildApply(row, instruction) => {
                self.send(json!({"op":"recover_child", "source":row["source"], "child":row["id"], "sha256":row["source_sha256"], "text":instruction, "confirm":true}));
                self.ui.menu = None;
            }
            Action::Recover(id) => {
                self.nav.switching=Some((self.request+1).to_string());
                self.send(json!({"op":"switch","target":id,"recover":true,"draft":self.draft.lines().join("\n")}));
            }
            Action::Rename => self.prompt("Rename conversation"),
            Action::Find => self.prompt("Find in conversation"),
            Action::Replies => {
                let choices = self.items.iter().rev().filter(|i| i.kind == "assistant").take(100)
                    .map(|i| choice(safe(&i.text.chars().take(100).collect::<String>()).replace('\n', " ↵ "), Action::Message(i.id.clone()))).collect();
                self.menu("Assistant replies · latest 100 blocks", choices);
            }
            Action::CopySelection => {
                if self.selection.start.is_some() { self.copy=Some(self.selection.text()); }
                else { self.status="Drag over transcript text to select it; Export saves the whole conversation".into(); }
            }
            Action::NativeScrollback => {
                self.view = 0;
                self.anchors = [None; 2];
                self.expanded = false;
                self.selection.start = None;
                self.status = "Native terminal history · select normally; tmux prefix [ to scroll/copy".into();
            }
            Action::Transcript => {
                self.view = 0;
                self.expanded = false;
                self.anchors[0] = self.tail();
            }
            Action::Export => self.send(json!({"op":"export"})),
            Action::Modes => self.send(json!({"op":"modes"})),
            Action::ModeNamed(name) => self.send(json!({"op":"modes","select":name})),
            Action::ModeChoice(name,current) => {
                self.menu("Change mode · confirm tool policy",vec![choice(format!("Apply {}",name.as_deref().unwrap_or("default")),Action::ModeApply(name,current))]);
                self.ui.menu.as_mut().unwrap().detail="Your explicit choice changes session policy, not model instructions. Module transition restrictions still apply. Pending follow-ups are paused.".into();
            }
            Action::ModeApply(name,current) => self.send(json!({"op":"mode_select","mode":name,"current":current})),
            Action::QuestionOpen(id) => self.question_open(id),
            Action::CodeBlocks => self.code_blocks(),
            Action::CodeBlock(block) => self.code_block(block),
            Action::CopyCode(block) => self.copy = Some(block.content.clone()),
            Action::WorkspaceHunks(snapshot) => self.workspace_hunks(snapshot),
            Action::WorkspaceHunk(snapshot, at) => self.workspace_hunk(snapshot, at),
            Action::WorkspaceSide(snapshot, at) => {
                self.workspace_hunk(snapshot, at);
                if let Some(menu) = self.ui.menu.as_mut() {
                    menu.side_by_side = true;
                    menu.title = "Workspace diff · side by side (unified below 80 columns)".into();
                }
            }
            Action::CopySource(source) => self.copy = Some(source.to_string()),
            Action::Message(id) => self.message_menu(id),
            Action::Jump(id) => { if let Some(&i) = self.index.get(&id) { self.reveal_item(i); } }
            Action::CopyMessage(id) => {
                if let Some(&i) = self.index.get(&id) {
                    if self.items[i].text.len() <= 1024 * 1024 {
                        self.copy = Some(self.items[i].text.clone());
                    } else {
                        self.status = "Message exceeds 1 MiB clipboard limit; nothing truncated or copied".into();
                    }
                }
            }
            Action::CopyText(text) => self.copy = Some(text),
            Action::QueueDraft => self.send(json!({"op":"queue", "text":self.draft.lines().join("\n")})),
            Action::QueueList => self.queue_menu(),
            Action::QueueItem(id) => self.queue_item(id),
            Action::QueueEdit(id) => {
                if let Some(row) = self.flow.rows.iter().find(|r| r["id"] == id) {
                    let text = string(row, "text");
                    self.send(json!({"op":"queue_pause"}));
                    self.prompt("Edit waiting follow-up");
                    let prompt = self.flow.prompt.as_mut().unwrap();
                    prompt.identity = Some(id);
                    prompt.editor.insert_str(text);
                }
            }
            Action::QueueControl(op, id) => self.send(json!({"op":op, "id":id})),
            Action::QueueResolve(id) => {
                self.menu("Resolve uncertain follow-up · no retry", vec![choice("Acknowledge unknown effects and dismiss from execution", Action::QueueResolveConfirm(id))]);
                self.ui.menu.as_mut().unwrap().detail = "This input may or may not have run. Inspect its source and workspace first. This leaves a dismissed record, keeps the queue paused, and neither retries nor undoes anything. Escape keeps it unresolved.".into();
            }
            Action::QueueResolveConfirm(id) => self.send(json!({"op":"queue_resolve", "id":id, "acknowledge_unknown":true})),
            Action::CorrectActive => self.correct_active(),
            Action::Questions => self.question_list(),
            Action::WorkspaceChanges => self.review_lookup(None),
            Action::WorkspaceDiff(id, token) => self.review_lookup(Some((id, token))),
            Action::WorkspaceEditPrepare(id, token) => {
                self.review_request = Some((self.request + 1).to_string());
                self.menu("Conflict file · capturing proposal", vec![]);
                self.send(json!({"op":"workspace_edit_prepare","id":id,"token":token}));
            }
            Action::WorkspaceEdit(snapshot) => {
                self.ui.menu = None;
                self.prompt("Edit conflict proposal");
                let prompt = self.flow.prompt.as_mut().unwrap();
                prompt.identity = Some(string(&snapshot, "id"));
                prompt.editor.insert_str(string(&snapshot, "text"));
                self.flow.conflict = Some(snapshot);
            }
            Action::WorkspaceEditApply(snapshot, text) => {
                self.review_request = Some((self.request + 1).to_string());
                let mut retained = (*snapshot).clone();
                retained["text"] = json!(text);
                self.flow.conflict = Some(Arc::new(retained));
                self.menu("Conflict file · applying confirmed proposal", vec![]);
                self.send(json!({"op":"workspace_edit_apply","id":snapshot["id"],"text":text,"confirm_write":true}));
            }
            Action::QuestionGroup(id) => self.question_group(id),
            Action::QuestionEdit(id, qid) => self.question_edit(id, qid),
            Action::QuestionText(id, qid) => self.question_text(id, qid),
            Action::QuestionChoice(id, qid, label) => {
                if self.questions.pending.contains_key(&id) {
                    self.retain_text(format!("answer:{id}:{qid}"), "answer", label.clone());
                    self.questions.answers.entry(id.clone()).or_default().insert(qid, json!({"option":label,"text":""}));
                    self.question_group(id);
                }
            }
            Action::QuestionSubmit(ref id) | Action::QuestionCancel(ref id) => {
                if let Some(row) = self.questions.pending.get(id) {
                    let op = if matches!(action, Action::QuestionSubmit(_)) { "question_answer" } else { "question_cancel" };
                    self.send(json!({"op":op,"question_id":id,"turn_id":row["turn_id"],"answers":self.questions.answers.get(id)}));
                } else { self.status = "Question expired; no answer delivered".into(); }
            }
            Action::Corrections => {
                let choices = self.items.iter().rev().filter(|i| i.kind == "correction").take(100)
                    .map(|i| choice(format!("{} · {}", i.status, safe(&i.text.chars().take(100).collect::<String>()).replace('\n', " ↵ ")), Action::Message(i.id.clone()))).collect();
                self.menu("Corrections · latest 100 · applied means inserted, not task success", choices);
                self.ui.menu.as_mut().unwrap().detail = "Pending waits for runtime insertion. Unconfirmed means no insertion acknowledgement; never retried or queued automatically. Open to inspect / copy the original correction.".into();
            }
            Action::CorrectionDraft(id) => self.correction_draft(id, None),
            Action::CorrectionDraftApply(id, text) => self.correction_draft(id, Some(text)),
            Action::ForkComposition => self.prompt("New provider overlay"),
            Action::ForkCompositionApply(overlay) => {
                self.nav.switching = Some((self.request + 1).to_string());
                self.send(json!({"op":"switch", "target":"new", "conversion_overlay":overlay, "confirm_conversion":true, "draft":self.draft.lines().join("\n")}));
                self.ui.menu = None;
            }
            Action::Providers => {
                if self.controls.providers["supported"] != true {
                    self.provider_menu();
                } else {
                    self.controls.lookup = Some((self.request + 1).to_string());
                    self.menu("Conversation providers · loading", vec![]);
                    self.send(json!({"op":"providers"}));
                }
            }
            Action::ProviderChoice(name, revision, current) => self.provider_confirm(name, revision, current),
            Action::ProviderHistory => self.provider_history(),
            Action::ProviderValidateChoice(name) => {
                self.menu("Validate provider access?", vec![choice(format!("Send standalone probe to {}", safe(&name)), Action::ProviderValidate(name))]);
                self.ui.menu.as_mut().unwrap().detail = "This makes a remote request using the provider's configured model and credentials. Charges may apply. Sends only ‘Reply OK.’, no conversation, workspace or tools. Requests 16 output tokens; provider policy may differ. Cooperative 20-second timeout; provider retries may apply. No selection change. Escape cancels.".into();
            }
            Action::ProviderValidate(name) => {
                self.menu("Provider validation · waiting", vec![]);
                self.send(json!({"op":"validate_provider", "provider":name, "confirm_remote":true}));
            }
            Action::ProviderApply(name, revision, current) => {
                self.controls.requests.insert((self.request + 1).to_string());
                self.send(json!({"op":"provider_select", "provider":name, "revision":revision, "current":current}));
            }
            Action::CancelSwitch => self.send(json!({"op":"cancel_switch"})),
            Action::Switch(target) => self.switch_conversation(target),
            Action::View(view) => {
                self.selection.start = None;
                self.view = view;
                self.expanded = false;
                self.ui.diagnostic_view = false;
            }
            Action::Send => return self.submit_draft(),
            Action::Stop => self.send(json!({"op":"stop"})),
            Action::StopForDraft => {
                let draft = self.draft.lines().join("\n");
                if !self.flow.busy || draft.trim().is_empty() {
                    self.status = "Write a replacement draft while work is active; nothing sent".into();
                } else {
                    self.menu("Stop current work and retain this draft?", vec![choice("Stop only — keep replacement unsent", Action::StopForDraftApply(draft))]);
                    self.ui.menu.as_mut().unwrap().detail = "Stop holds waiting work and does not undo earlier effects. The draft and attachments stay here; no replacement is queued or sent. Wait for the observed ending, review effects, then Send explicitly. Uncooperative tools may require Quit, which has a separate owned-host shutdown deadline. Escape cancels.".into();
                }
            }
            Action::StopForDraftApply(expected) => {
                if expected != self.draft.lines().join("\n") || !self.flow.busy {
                    self.status = "Work or draft changed; inspect again. Nothing sent".into();
                } else {
                    self.controls.steer = false;
                    self.send(json!({"op":"stop"}));
                    self.ui.menu = None;
                    self.status = "Stop requested · replacement remains unsent · review effects before Send".into();
                }
            }
            Action::Decisions => {
                if let Some(a) = &self.approval {
                    let id = string(a, "id");
                    let title = format!("Decision · {}", id);
                    let detail = format!(
                        "{}\n{}\nOptions (exact runtime scope):\n{}",
                        safe(&string(a, "prompt")),
                        safe(&string(a, "command")),
                        a["options"]
                            .as_array()
                            .unwrap_or(&vec![])
                            .iter()
                            .filter_map(|o| o.as_str())
                            .map(safe)
                            .collect::<Vec<_>>()
                            .join("\n")
                    );
                    let choices = a["options"]
                        .as_array()
                        .unwrap_or(&vec![])
                        .iter()
                        .filter_map(|o| o.as_str())
                        .map(|o| choice(safe(o), Action::Decision(id.clone(), o.into())))
                        .collect();
                    self.menu(title, choices);
                    self.ui.menu.as_mut().unwrap().detail = detail;
                } else {
                    self.status = "No pending decision".into();
                }
            }
            Action::Decision(id, option) => {
                if self.approval.as_ref().is_some_and(|a| a["id"] == id) {
                    self.send(json!({"op":"decision","approval_id":id,"option":option}));
                } else {
                    self.status = "Decision no longer pending · no answer sent".into();
                }
            }
            Action::Evidence => {
                self.expanded = !self.expanded;
                self.detail_scroll = 0;
            }
            Action::NextTool => {
                for step in 1..=self.items.len() {
                    let index = (self.selected + step) % self.items.len();
                    if self.items[index].kind == "tool" {
                        self.selected = index;
                        self.detail_scroll = 0;
                        break;
                    }
                }
            }
            Action::Copy => {
                self.copy = self
                    .items
                    .get(self.selected)
                    .filter(|i| i.kind == "tool")
                    .map(|i| i.detail.clone())
            }
            Action::History => {
                let choices = self
                    .ui
                    .history
                    .iter()
                    .rev()
                    .map(|s| choice(safe(s).replace('\n', " ↵ "), Action::Recall(s.clone())))
                    .collect();
                self.menu(
                    if self.ui.history_partial { "Directory history · recent subset · selecting never sends" } else if self.ui.history_legacy { "Directory history · legacy rows use session activity order · text only" } else { "Directory history · chronological submissions · text only, never sends" },
                    choices,
                );
            }
            Action::Recall(value) => {
                self.draft.select_all();
                self.draft.insert_str(value);
            }
            Action::Complete(row, start, end, value) => {
                composer::replace(&mut self.draft, row, start, end, &value);
                self.status = "Completed locally · path/skill names are text, not loaded attachments".into();
            }
            Action::Diagnostics => {
                self.view = 2;
                self.expanded = false;
                self.ui.diagnostic_view = true;
                self.scroll[2] = 0;
            }
            Action::LocalDrafts => self.local_drafts(),
            Action::FileInput => self.prompt("Insert text file"),
            Action::InsertFile(value, draft) => self.insert_file(value, draft),
            Action::ExternalEditor => {
                if self.flow.busy || self.nav.switching.is_some() || (!self.flow.paused && !self.flow.rows.is_empty()) {
                    self.status = "External editing requires idle work and a paused queue".into();
                } else { self.insights.external_editor = true; }
            }
            Action::Inspect(category, child) => self.inspect(category, child),
            Action::Observation(row) => self.observation(row),
            Action::LocalDraft(row) => self.local_draft(row),
            Action::RemoveDraft(id) => {
                self.send(json!({"op":"editor_draft","remove":id}));
                self.insights.drafts.retain(|r| r["id"] != id);
                self.insights.saved.remove(&id);
                self.local_drafts();
            }
            Action::Help => self.menu(
                "Help · choose a topic · Esc keeps your draft",
                [
                    ("First conversation", "Describe one task, then Enter sends it. Alt+Enter adds a newline; paste stays text. No example here is sent automatically.\n\nLive presets can use file/shell tools and incur model charges; this is not a sandbox. A FIXTURE RUNTIME is a scripted demonstration, not an AI assistant.\n\nSystem shows mounted tools and authored definitions. An available definition is not proof that an external service is running."),
                    ("Editing and finding actions", "Tab completes ./paths, @skills and /commands; otherwise it focuses visible controls. Enter activates the focused control. Actions opens local search; Escape returns to your unchanged draft.\n\nUp/Down recalls sent messages at editor line boundaries. Returning past the newest recalled entry restores your draft. Insert text file previews captured bytes before insertion; Edit in external editor never sends them."),
                    ("Queue or steer?", "Queue stores a follow-up for a later turn. Pending follow-ups lets you pause, edit, remove or explicitly run queued work.\n\nSteer opens a separate correction for the active turn when supported. Accepted is not yet inserted: inspect Corrections for the observed status.\n\nStop requests cancellation, holds pending follow-ups, and does not undo file or command effects."),
                    ("When the assistant waits", "Review decision opens an actual permission request and its offered options. Answer question opens a clarification, where you choose or write information and explicitly submit after review. These are different controls.\n\nLook for the waiting card beside the composer. Escape preserves local intent; it does not answer or grant permission. Modes changes session policy; the mode badge stays visible."),
                    ("Copy and return later", "The normal conversation uses terminal selection and native history. In tmux, enter copy mode (normally prefix then [) and scroll. Menus and inspection temporarily own the mouse.\n\nTranscript offers reflowed source inspection; Export conversation writes private Markdown. Quit saves supported state; Resume offers a picker and never repeats old tool operations. Interrupted work may require an explicitly acknowledged historical recovery, not exact context repair."),
                    ("Understand what happened", "Delegated work shows child progress and historical receipts. Activity evidence and Review show source tool results; a completed turn does not prove every tool succeeded or tests passed.\n\nWorkspace changes is read-only Git inspection, not attribution. Context intelligence distinguishes observed usage, configured local capture and remote dispatch; unavailable is not zero."),
                    ("Setup and reporting a problem", "Outside the app, run amplifier-tui --check for local setup blockers or --getting-started for the first-run guide. Checks do not validate a key, contact a provider or load bundles.\n\nUse --support-report for path-free local diagnostic JSON. Review before sharing. --doctor, exports, screenshots and raw logs may contain private paths or conversation content. Never share keys. Include steps to reproduce and expected versus actual behavior.")
                ].into_iter().map(|(title, body)| Choice {
                    label: title.into(),
                    action: Action::HelpTopic(title.into(), body.into()),
                    detail: "Enter opens instructions only; no example is submitted.".into(),
                }).collect(),
            ),
            Action::HelpTopic(title, body) => {
                self.menu(format!("Help · {title}"), vec![choice("Back to help topics", Action::Help)]);
                self.ui.menu.as_mut().unwrap().detail = body;
            }
            Action::Quit => return false,
        }
        true
    }

    pub fn local_key(&mut self, key: crossterm::event::KeyEvent) -> Option<bool> {
        if key.code == KeyCode::Esc || (self.ui.menu.is_none() && key.code != KeyCode::Tab) {
            self.nav.lookup = None;
            self.controls.lookup = None;
            self.review_request = None;
        }
        if let Some(menu) = &mut self.ui.menu {
            let count = menu.filtered().len();
            let mut picked = None;
            match key.code {
                KeyCode::PageDown => menu.detail_scroll = menu.detail_scroll.saturating_add(3),
                KeyCode::PageUp => menu.detail_scroll = menu.detail_scroll.saturating_sub(3),
                KeyCode::Esc => {
                    self.ui.menu = None;
                    self.ui.focus = None;
                }
                KeyCode::Down => {
                    menu.selected = (menu.selected + 1) % count.max(1);
                    menu.detail_scroll = 0;
                }
                KeyCode::Tab => {
                    if let Some(c) = menu.filtered().get(menu.selected) {
                        if matches!(c.action, Action::Complete(..)) {
                            picked = Some(c.action.clone());
                        } else {
                            menu.query = c.label.clone();
                            menu.selected = 0;
                            menu.detail_scroll = 0;
                        }
                    }
                }
                KeyCode::Up | KeyCode::BackTab => {
                    menu.selected = (menu.selected + count.max(1) - 1) % count.max(1);
                    menu.detail_scroll = 0;
                }
                KeyCode::Enter if key.kind == KeyEventKind::Press => {
                    picked = if menu.title == "Actions · type to search"
                        && menu.query.starts_with("mode ")
                    {
                        Some(Action::ModeNamed(menu.query[5..].trim().into()))
                    } else {
                        menu.filtered().get(menu.selected).map(|c| c.action.clone())
                    }
                }
                KeyCode::Char(c)
                    if key.modifiers.is_empty() || key.modifiers == KeyModifiers::SHIFT =>
                {
                    menu.query.push(c);
                    menu.selected = 0;
                    menu.detail_scroll = 0;
                }
                KeyCode::Backspace => {
                    menu.query.pop();
                    menu.selected = 0;
                    menu.detail_scroll = 0;
                }
                _ => (),
            }
            return Some(picked.map(|a| self.activate(a)).unwrap_or(true));
        }
        match key.code {
            KeyCode::Up
                if self.ui.focus.is_none()
                    && key.modifiers.is_empty()
                    && composer::at_vertical_boundary(&self.draft, true) =>
            {
                self.ui
                    .recall
                    .navigate(&mut self.draft, &self.ui.history, true)
                    .then_some(true)
            }
            KeyCode::Down
                if self.ui.focus.is_none()
                    && key.modifiers.is_empty()
                    && composer::at_vertical_boundary(&self.draft, false) =>
            {
                self.ui
                    .recall
                    .navigate(&mut self.draft, &self.ui.history, false)
                    .then_some(true)
            }
            KeyCode::Esc if self.ui.focus.is_none() && self.ui.recall.cancel(&mut self.draft) => {
                Some(true)
            }
            KeyCode::Tab if self.ui.focus.is_none() && self.complete_token() => Some(true),
            KeyCode::Tab | KeyCode::BackTab => {
                let actions: Vec<_> = self
                    .ui
                    .buttons
                    .iter()
                    .map(|(_, c)| c.action.clone())
                    .collect();
                let current = self
                    .ui
                    .focus
                    .as_ref()
                    .and_then(|f| actions.iter().position(|a| a == f));
                self.ui.focus = if key.code == KeyCode::BackTab {
                    current.map_or_else(
                        || actions.last().cloned(),
                        |i| i.checked_sub(1).and_then(|j| actions.get(j).cloned()),
                    )
                } else {
                    actions.get(current.map_or(0, |i| i + 1)).cloned()
                };
                Some(true)
            }
            KeyCode::Esc if self.ui.focus.is_some() => {
                self.ui.focus = None;
                Some(true)
            }
            KeyCode::Enter if self.ui.focus.is_some() => {
                let action = self.ui.focus.clone().unwrap();
                Some(if key.kind == KeyEventKind::Press {
                    self.activate(action)
                } else {
                    true
                })
            }
            _ if self.ui.focus.is_some() => Some(true),
            KeyCode::Char('/')
                if key.modifiers.is_empty() && self.draft.lines().join("\n").is_empty() =>
            {
                Some(self.activate(Action::Menu))
            }
            KeyCode::F(4) => Some(self.activate(Action::Menu)),
            _ => None,
        }
    }

    fn complete_token(&mut self) -> bool {
        let Some((row, start, end, query)) = composer::token(&self.draft) else {
            return false;
        };
        if query.starts_with("./") {
            self.lookup(Some((row, start, end)), query);
            return true;
        }
        let values: Vec<String> = if query.starts_with('@') {
            self.ui
                .skills
                .iter()
                .map(|name| format!("@{name}"))
                .collect()
        } else {
            [
                "work",
                "agents",
                "activity",
                "context",
                "drafts",
                "attach",
                "editor",
                "review",
                "system",
                "skills",
                "providers",
                "questions",
                "code",
                "changes",
                "steer",
                "history",
                "help",
                "stop",
                "quit",
                "evidence",
                "copy",
                "resume",
                "new",
                "queue",
                "pending",
                "find",
                "rename",
                "replies",
                "modes",
                "mode",
                "export",
                "scrollback",
            ]
            .iter()
            .map(|s| format!("/{s}"))
            .collect()
        };
        let choices: Vec<_> = values
            .into_iter()
            .filter(|s| s.starts_with(&query))
            .map(|s| choice(s.clone(), Action::Complete(row, start, end, s)))
            .collect();
        match choices.len() {
            0 => {
                self.status =
                    "No local completion · @ completes discovered skills; / completes commands"
                        .into()
            }
            1 => {
                self.activate(choices[0].action.clone());
            }
            _ => self.menu(
                "Complete locally · Tab/Enter inserts; Esc keeps draft",
                choices,
            ),
        }
        true
    }

    pub fn submit_draft(&mut self) -> bool {
        if !self.ready {
            self.status = "Session not ready · draft retained; send explicitly when ready".into();
            return true;
        }
        let value = self.draft.lines().join("\n");
        let action = match value.trim() {
            v if v.starts_with("/mode ") => Some(Action::ModeNamed(v[6..].trim().into())),
            "/work" => Some(Action::View(0)),
            "/agents" => Some(Action::Inspect("children".into(), None)),
            "/activity" => Some(Action::Inspect("activity".into(), None)),
            "/context" => Some(Action::Inspect("context".into(), None)),
            "/drafts" => Some(Action::LocalDrafts),
            "/attach" => Some(Action::FileInput),
            "/editor" => Some(Action::ExternalEditor),
            "/review" => Some(Action::View(1)),
            "/system" => Some(Action::View(2)),
            "/skills" => Some(Action::Section("Skills (".into())),
            "/providers" => Some(Action::Providers),
            "/questions" => Some(Action::Questions),
            "/modes" | "/mode" => Some(Action::Modes),
            "/export" => Some(Action::Export),
            "/scrollback" => Some(Action::NativeScrollback),
            "/code" => Some(Action::CodeBlocks),
            "/changes" => Some(Action::WorkspaceChanges),
            "/steer" => Some(Action::CorrectActive),
            "/history" => Some(Action::History),
            "/help" => Some(Action::Help),
            "/stop" => Some(Action::Stop),
            "/quit" => Some(Action::Quit),
            "/evidence" => Some(Action::Evidence),
            "/copy" => Some(Action::Copy),
            "/resume" => Some(Action::Conversations),
            "/new" => Some(Action::Switch("new".into())),
            "/pending" => Some(Action::QueueList),
            "/queue" => Some(Action::QueueList),
            "/find" => Some(Action::Find),
            "/rename" => Some(Action::Rename),
            "/replies" => Some(Action::Replies),
            _ => None,
        };
        if let Some(action) = action {
            self.draft.select_all();
            self.draft.insert_str("");
            return self.activate(action);
        }
        self.send(json!({"op":if self.flow.busy && self.nav.enabled { "queue" } else { "submit" }, "text":value}));
        true
    }

    pub fn button(&mut self, f: &mut Frame, rect: Rect, label: impl Into<String>, action: Action) {
        if rect.width == 0 {
            return;
        }
        let label = label.into();
        let focused = self.ui.focus.as_ref() == Some(&action);
        let selected = action == Action::View(self.view);
        f.render_widget(
            Paragraph::new(label.clone()).style(
                Style::default()
                    .fg(if focused {
                        BG
                    } else if selected {
                        GREEN
                    } else {
                        MUTED
                    })
                    .bg(if focused {
                        GREEN
                    } else if selected {
                        PANEL
                    } else {
                        BG
                    }),
            ),
            rect,
        );
        self.ui.buttons.push((rect, choice(label, action)));
    }

    pub fn draw_menu(&mut self, f: &mut Frame) {
        self.ui.menu_buttons.clear();
        let Some(menu) = &mut self.ui.menu else {
            return;
        };
        let outer = f.area();
        let width = outer.width.saturating_sub(4).min(100);
        let choices = menu.filtered();
        let detail = choices
            .get(menu.selected)
            .filter(|c| !c.detail.is_empty())
            .map(|c| &c.detail)
            .unwrap_or(&menu.detail);
        let has_detail = !detail.is_empty();
        let content_width = width.saturating_sub(4);
        if menu
            .detail_cache
            .as_ref()
            .is_none_or(|(w, diff, source, _)| {
                *w != content_width || *diff != menu.diff || source != detail
            })
        {
            let mut lines = if let Some(code) = &menu.code {
                let mut lines = wrap(detail, content_width as usize)
                    .into_iter()
                    .map(|s| Line::styled(s, Style::default().fg(INK)))
                    .collect::<Vec<_>>();
                let preview = safe(&code.content.chars().take(12000).collect::<String>());
                let mut budget = syntax::MAX_BYTES;
                let code_lines = if syntax::eligible(&code.content) {
                    syntax::lines(&preview, &code.language, &mut budget)
                } else {
                    syntax::plain(&preview)
                };
                lines.extend(markdown::reflow(code_lines, content_width as usize));
                lines
            } else if menu.side_by_side {
                workspace::side_by_side_lines(detail, content_width as usize)
            } else if menu.diff {
                workspace::diff_lines(detail, content_width as usize)
            } else {
                wrap(detail, content_width as usize)
                    .into_iter()
                    .map(|s| Line::styled(s, Style::default().fg(INK)))
                    .collect()
            };
            if let Some(image) = &menu.image {
                let mut preview = insights::thumbnail_lines(image, content_width as usize);
                preview.append(&mut lines);
                lines = preview;
            }
            menu.detail_cache = Some((content_width, menu.diff, detail.clone(), lines));
        }
        let lines = &menu.detail_cache.as_ref().unwrap().3;
        let available = if outer.height >= 20 {
            outer.height - if outer.height >= 30 { 7 } else { 5 } - 6
        } else {
            outer.height.saturating_sub(7)
        };
        let help_topic = menu.title.starts_with("Help ·") && !menu.detail.is_empty();
        let roomy = help_topic
            || menu.image.is_some()
            || menu.title.starts_with("Questions · review")
            || menu.title.starts_with("Observed evidence")
            || menu.title.starts_with("Context intelligence")
            || menu.title.starts_with("Text file snapshot")
            || menu.title.starts_with("File reference ·")
            || menu.title.starts_with("Provider request ·")
            || menu.title.starts_with("Saved draft ·")
            || menu.title.starts_with("Code block ·")
            || menu.title.starts_with("Workspace diff")
            || menu.title.starts_with("Conflict file")
            || menu.title.starts_with("Apply conflict proposal");
        let height = if roomy {
            (lines.len() + choices.len() + 5)
                .min(available as usize)
                .max(5) as u16
        } else {
            (choices.len() as u16 + 5 + if has_detail { 9 } else { 0 })
                .min(available)
                .max(5)
                .min(outer.height.saturating_sub(7))
        };
        let area = Rect::new(
            outer.x + (outer.width - width) / 2,
            outer.y + 5,
            width,
            height,
        );
        if area.width < 8 || area.height < 5 {
            return;
        }
        f.render_widget(Clear, area);
        f.render_widget(
            Block::bordered()
                .border_type(BorderType::Rounded)
                .title(" Actions / choices ")
                .style(Style::default().fg(GREEN).bg(PANEL)),
            area,
        );
        let x = area.x + 2;
        let w = area.width.saturating_sub(4);
        text(f, Rect::new(x, area.y + 1, w, 1), safe(&menu.title), INK);
        let detail_h = if !has_detail {
            0
        } else if roomy {
            area.height.saturating_sub(5 + choices.len().min(6) as u16)
        } else {
            (area.height / 3).max(1)
        };
        text(
            f,
            Rect::new(x, area.y + 2, w, 1),
            if help_topic {
                format!("Read · {} lines · PgUp/PgDn", lines.len())
            } else {
                format!("Search: {}", menu.query)
            },
            GREEN,
        );
        if detail_h > 0 {
            menu.detail_scroll = menu
                .detail_scroll
                .min(lines.len().saturating_sub(detail_h as usize));
            for (i, line) in lines
                .iter()
                .skip(menu.detail_scroll)
                .take(detail_h as usize)
                .enumerate()
            {
                f.render_widget(
                    Paragraph::new(line.clone()),
                    Rect::new(x, area.y + 3 + i as u16, w, 1),
                );
            }
        }
        let rows = area.height.saturating_sub(5 + detail_h) as usize;
        let start = menu.selected.saturating_sub(rows.saturating_sub(1));
        for (i, c) in choices.iter().enumerate().skip(start).take(rows) {
            let rect = Rect::new(x, area.y + 3 + detail_h + (i - start) as u16, w, 1);
            f.render_widget(
                Paragraph::new(format!(
                    "{} {}",
                    if i == menu.selected { "›" } else { " " },
                    c.label
                ))
                .style(
                    Style::default()
                        .fg(if i == menu.selected { GREEN } else { INK })
                        .bg(if i == menu.selected { LINE } else { PANEL }),
                ),
                rect,
            );
            self.ui.menu_buttons.push((rect, c.action.clone()));
        }
        text(
            f,
            Rect::new(x, area.bottom() - 2, w, 1),
            if help_topic && w < 50 {
                "PgUp/PgDn scroll · Esc back"
            } else if help_topic {
                "PgUp/PgDn scroll · Enter topics · Esc back"
            } else if detail_h > 0 && menu.title.starts_with("Decision ·") {
                "↑↓ choose · Enter answer · PgUp/PgDn question · Esc back"
            } else if detail_h > 0 {
                "↑↓ choose · Enter open · PgUp/PgDn details · Esc back"
            } else {
                "↑↓ choose · Enter select · Esc back (draft kept)"
            },
            MUTED,
        );
    }
}

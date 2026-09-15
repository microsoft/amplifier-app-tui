//! Local organization and explicit follow-up controls over the host boundary.
use super::*;
use interaction::Choice;
use ratatui::widgets::Clear;

#[derive(Default)]
pub struct Workflow {
    pub queued_requests: std::collections::HashSet<String>,
    pub busy: bool,
    pub rows: Vec<Value>,
    pub paused: bool,
    pub prompt: Option<Prompt>,
}

pub struct Prompt {
    pub kind: String,
    pub editor: TextArea<'static>,
    pub identity: Option<String>,
    pub pending: Option<String>,
    pub question: Option<(String, String)>,
}

fn choice(label: impl Into<String>, action: Action, detail: impl Into<String>) -> Choice {
    Choice {
        label: label.into(),
        action,
        detail: detail.into(),
    }
}

impl App {
    pub fn prompt(&mut self, kind: &str) {
        let mut input = editor();
        input.set_placeholder_text(match kind {
            "Rename conversation" => "New name (up to 100 characters)…",
            "Insert text file" => "Workspace-relative path · UTF-8 text, at most 64 KiB…",
            "Attach image" => "Workspace-relative PNG/JPEG path · at most 2 MiB…",
            "Find in conversation" => "Find message text…",
            "Search saved conversations" => "Saved message text, title, directory or ID…",
            "Correct active turn" => "Correction for this turn only (Alt+Enter newline)…",
            "Answer question" => {
                "Your answer · Enter saves locally for review · Alt+Enter newline…"
            }
            _ => "Follow-up text…",
        });
        self.flow.prompt = Some(Prompt {
            kind: kind.into(),
            editor: input,
            identity: None,
            pending: None,
            question: None,
        });
    }

    pub fn prompt_key(&mut self, key: crossterm::event::KeyEvent) -> Option<bool> {
        if matches!(key.code, KeyCode::Esc | KeyCode::Enter) {
            self.retain_editor();
        }
        let prompt = self.flow.prompt.as_mut()?;
        // A lost acknowledgement must not trap the editor or imply a retry.
        // Keep its text copyable, allow Escape, and never resend while disconnected.
        if self.disconnected {
            match key.code {
                KeyCode::Esc => self.flow.prompt = None,
                KeyCode::F(2) => self.copy = Some(prompt.editor.lines().join("\n")),
                _ => (),
            }
            return Some(true);
        }
        if prompt.pending.is_some() {
            return Some(true);
        }
        match key.code {
            KeyCode::F(2) => self.copy = Some(prompt.editor.lines().join("\n")),
            KeyCode::Enter
                if key.modifiers.contains(KeyModifiers::ALT) && prompt.identity.is_some() =>
            {
                prompt.editor.insert_newline();
            }
            KeyCode::Esc => {
                let prompt = self.flow.prompt.take().unwrap();
                if let Some((id, qid)) = prompt.question {
                    if self.questions.pending.contains_key(&id) {
                        self.save_question_text(id, qid, prompt.editor.lines().join("\n"));
                    }
                    self.ui.menu = None;
                }
            }
            KeyCode::Enter if key.kind == KeyEventKind::Press => {
                let mut prompt = self.flow.prompt.take().unwrap();
                let value = prompt.editor.lines().join("\n");
                if prompt.kind == "Search saved conversations" {
                    self.conversation_page(0, value);
                    return Some(true);
                }
                if prompt.kind == "Insert text file" || prompt.kind == "Attach image" {
                    self.insights.file_request = Some((
                        (self.request + 1).to_string(),
                        self.draft.lines().join("\n"),
                    ));
                    self.menu("Text file · reading", vec![]);
                    self.send(json!({"op":if prompt.kind == "Attach image" {"image_snapshot"} else {"file_snapshot"},"path":value}));
                    return Some(true);
                }
                if let Some((id, _)) = &prompt.question
                    && (!self.questions.pending.contains_key(id) || value.chars().count() > 65536)
                {
                    self.status = "Question expired or answer exceeds 65536 characters. F2 copies; Esc discards; nothing sent".into();
                    self.flow.prompt = Some(prompt);
                    return Some(true);
                }
                if let Some((id, qid)) = prompt.question.take() {
                    self.save_question_text(id, qid, value);
                    return Some(true);
                }
                if prompt.kind != "Find in conversation" {
                    prompt.pending = Some((self.request + 1).to_string());
                    let op = if prompt.kind == "Correct active turn" {
                        "steer"
                    } else if prompt.identity.is_some() {
                        "queue_edit"
                    } else {
                        "rename"
                    };
                    self.send(json!({"op":op, "id":prompt.identity, "turn_id":prompt.identity, "text":value}));
                    self.flow.prompt = Some(prompt);
                } else {
                    self.find_messages(&value);
                }
            }
            _ => {
                prompt.editor.input(key);
            }
        }
        Some(true)
    }

    pub fn find_messages(&mut self, query: &str) {
        if query.trim().is_empty() {
            self.status = "Enter text to find; nothing sent".into();
            return;
        }
        let needle = query.to_lowercase();
        let mut choices = Vec::new();
        let mut budget = 16 * 1024 * 1024usize;
        let mut partial = false;
        // Explicit search only, never per stream delta or frame. Recent results
        // first; bound source work and matches and disclose a partial scan.
        for item in self.items.iter().rev() {
            if item.text.len() > budget || choices.len() >= 200 {
                partial = true;
                break;
            }
            budget -= item.text.len();
            let lower = item.text.to_lowercase();
            if let Some(at) = lower.find(&needle) {
                // Byte offsets in case-folded text are not source offsets.
                let offset = lower[..at].chars().count();
                let snippet: String = item
                    .text
                    .chars()
                    .skip(offset.saturating_sub(40))
                    .take(180)
                    .collect();
                choices.push(choice(
                    format!("{} · {}", item.kind, safe(&snippet).replace('\n', " ↵ ")),
                    Action::Message(item.id.clone()),
                    "",
                ));
            }
        }
        self.menu(format!("Conversation matches · {query}"), choices);
        self.ui.menu.as_mut().unwrap().detail = if partial {
            "Partial search: 200 matches / 16 MiB recent source limit. Narrow the query."
        } else {
            "Search finished locally. Select a message to read or copy it."
        }
        .into();
    }

    pub fn message_menu(&mut self, id: String) {
        let Some(&index) = self.index.get(&id) else {
            return;
        };
        let item = &self.items[index];
        let detail = safe(&item.text.chars().take(12000).collect::<String>());
        self.menu(
            "Message · retained source preview (up to 12000 characters)",
            vec![
                choice("Go to this message", Action::Jump(id.clone()), ""),
                choice(
                    "Copy message source / Markdown",
                    Action::CopyMessage(id),
                    "",
                ),
            ],
        );
        self.ui.menu.as_mut().unwrap().detail = detail;
    }

    pub fn queue_menu(&mut self) {
        let mut choices = vec![
            choice("Queue current draft as a follow-up", Action::QueueDraft, ""),
            choice(
                "Run pending follow-ups (explicit release)",
                Action::QueueControl("queue_run".into(), String::new()),
                "",
            ),
            choice(
                "Pause pending follow-ups (active work continues)",
                Action::QueueControl("queue_pause".into(), String::new()),
                "",
            ),
        ];
        for row in &self.flow.rows {
            let id = string(row, "id");
            let body = safe(&string(row, "text"));
            choices.push(choice(
                format!(
                    "{} · {}",
                    string(row, "state"),
                    body.chars()
                        .take(100)
                        .collect::<String>()
                        .replace('\n', " ↵ ")
                ),
                Action::QueueItem(id),
                body,
            ));
        }
        self.menu(
            format!(
                "Pending follow-ups · {}",
                if self.flow.paused {
                    "paused"
                } else {
                    "enabled"
                }
            ),
            choices,
        );
        self.ui.menu.as_mut().unwrap().detail = "Up to 20 messages. Successful turns advance an enabled queue. Stop, failure, opening and reopening pause it. Already admitted work cannot be removed here.".into();
    }

    pub fn queue_item(&mut self, id: String) {
        let Some(row) = self.flow.rows.iter().find(|r| r["id"] == id) else {
            self.status = "Follow-up already changed; no operation sent".into();
            return;
        };
        let body = string(row, "text");
        let mut choices = vec![choice(
            "Copy follow-up text",
            Action::CopyText(body.clone()),
            "",
        )];
        if row["state"] == "dispatched" && !self.flow.busy {
            choices.push(choice(
                "Resolve uncertain delivery…",
                Action::QueueResolve(id.clone()),
                "No automatic retry or rollback; requires explicit acknowledgement.",
            ));
        }
        if row["state"] == "dismissed" {
            choices.push(choice(
                "Remove dismissed record (does not undo effects)",
                Action::QueueControl("queue_remove".into(), id.clone()),
                "Text remains copyable until explicitly removed.",
            ));
        }
        if row["state"] == "queued" {
            choices.push(choice(
                "Edit waiting follow-up (pauses the queue)",
                Action::QueueEdit(id.clone()),
                "",
            ));
            choices.push(choice(
                "Remove waiting follow-up (does not stop active work)",
                Action::QueueControl("queue_remove".into(), id),
                "",
            ));
        }
        self.menu("Follow-up · inspect before changing", choices);
        self.ui.menu.as_mut().unwrap().detail = safe(&body);
    }

    pub fn draw_prompt(&mut self, f: &mut Frame) {
        let Some(prompt) = &mut self.flow.prompt else {
            return;
        };
        let outer = f.area();
        if outer.width < 12 || outer.height < 10 {
            return;
        }
        let w = outer.width.saturating_sub(4).min(100);
        let area = Rect::new((outer.width - w) / 2, 5, w, 5);
        f.render_widget(Clear, area);
        f.render_widget(
            Block::bordered()
                .title(format!(
                    " {} · {} ",
                    prompt.kind,
                    if self.disconnected {
                        "Uncertain · F2 copy text · Esc close · no retry"
                    } else if prompt.pending.is_some() {
                        "Saving…"
                    } else if prompt.question.is_some() {
                        "Enter review · Esc keep locally · F2 copy"
                    } else {
                        "Enter apply · Esc cancel"
                    }
                ))
                .style(Style::default().fg(GREEN).bg(PANEL)),
            area,
        );
        f.render_widget(
            &prompt.editor,
            Rect::new(area.x + 1, area.y + 1, area.width - 2, 3),
        );
    }
}

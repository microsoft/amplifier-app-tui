//! Local source inspection and retained editor intent; no execution authority.
use super::*;
use interaction::Choice;

#[derive(Default)]
pub struct Insights {
    pub drafts: Vec<Value>,
    pub saved: HashMap<String, String>,
    pub error: String,
    pub lookup: Option<String>,
    pub file_request: Option<(String, String)>,
    pub external_editor: bool,
}

impl App {
    pub fn file_snapshot_result(&mut self, value: Value) {
        let Some((id, draft)) = &self.insights.file_request else {
            return;
        };
        if value["session_id"] != self.nav.session || value["request_id"] != *id {
            return;
        }
        let original = draft.clone();
        self.insights.file_request = None;
        if self
            .ui
            .menu
            .as_ref()
            .is_none_or(|m| m.title != "Text file · reading")
            || self.draft.lines().join("\n") != original
        {
            return;
        }
        if let Some(error) = value["error"].as_str() {
            self.ui.menu = None;
            self.status = format!("File not inserted: {}", safe(error));
            return;
        }
        self.menu(
            "Text file snapshot · preview before inserting",
            vec![Choice {
                label: "Insert captured text into draft (does not send)".into(),
                action: Action::InsertFile(Arc::new(value.clone()), original),
                detail: String::new(),
            }],
        );
        self.ui.menu.as_mut().unwrap().detail = format!(
            "{} · {} bytes\nSHA-256: {}\nCaptured text, not a live attachment. Sending the draft shares these bytes with the configured model. Escape leaves the draft unchanged.\n\n{}",
            safe(&string(&value, "path")),
            value["bytes"],
            string(&value, "sha256"),
            safe(&string(&value, "text"))
        );
    }

    pub fn insert_file(&mut self, value: Arc<Value>, original: String) {
        if self.draft.lines().join("\n") != original {
            self.status = "Draft changed; file insertion cancelled".into();
            return;
        }
        let text = string(&value, "text");
        let fence = "`".repeat(
            text.split('\n')
                .map(|line| line.chars().take_while(|c| *c == '`').count())
                .max()
                .unwrap_or(0)
                .max(2)
                + 1,
        );
        self.draft.insert_str(format!(
            "\n\nFile snapshot: {}\nSHA-256: {}\n{}text\n{}\n{}\n",
            string(&value, "path"),
            string(&value, "sha256"),
            fence,
            text,
            fence
        ));
        self.status = "Captured file text inserted · review and Send explicitly".into();
    }

    pub fn inspect(&mut self, category: String, child: Option<String>) {
        if self.disconnected || self.mode == "SIMULATED" {
            self.status = "Observed-work inspection requires the runtime host".into();
            return;
        }
        self.insights.lookup = Some((self.request + 1).to_string());
        self.menu("Observed work · loading", vec![]);
        self.send(json!({"op":"inspect","category":category,"child":child}));
    }

    pub fn inspection_result(&mut self, value: Value) {
        if value["session_id"] != self.nav.session
            || self
                .insights
                .lookup
                .as_ref()
                .is_none_or(|id| value["request_id"] != *id)
        {
            return;
        }
        self.insights.lookup = None;
        if self
            .ui
            .menu
            .as_ref()
            .is_none_or(|m| m.title != "Observed work · loading")
        {
            return;
        }
        let category = string(&value, "category");
        let mut choices = vec![Choice {
            label: "Refresh observations".into(),
            action: Action::Inspect(category.clone(), value["child"].as_str().map(str::to_owned)),
            detail: String::new(),
        }];
        choices.extend(
            value["rows"]
                .as_array()
                .unwrap_or(&vec![])
                .iter()
                .map(|row| Choice {
                    label: format!(
                        "{} · {} · {}",
                        if row["live"] == true {
                            "live child"
                        } else {
                            "observed"
                        },
                        safe(&string(row, "status")),
                        safe(&string(row, "label"))
                    ),
                    action: Action::Observation(row.clone()),
                    detail: format!(
                        "Conversation {} · turn {} · sequence {}\n{}",
                        string(row, "source"),
                        string(row, "turn"),
                        row["sequence"],
                        safe(&string(row, "detail"))
                    ),
                }),
        );
        self.menu(
            match category.as_str() {
                "children" => "Delegated work · scoped child observations",
                "context" => "Context intelligence · observed diagnostics",
                _ => "Activity evidence · identified runtime observations",
            },
            choices,
        );
        self.ui.menu.as_mut().unwrap().detail = format!(
            "{}\n{}\nPartial index: {}\nStorage policy: {}",
            string(&value, "scope"),
            string(&value, "context_note"),
            value["partial"],
            value["storage_policy"]
        );
    }

    pub fn observation(&mut self, row: Value) {
        let text = format!(
            "Conversation: {}\nTurn: {}\nIdentity: {}\nObserved sequences: {}–{}\n\n{}",
            string(&row, "source"),
            string(&row, "turn"),
            string(&row, "id"),
            row["first_sequence"],
            row["sequence"],
            string(&row, "detail")
        );
        let mut choices = vec![Choice {
            label: "Copy observed evidence".into(),
            action: Action::CopyText(text.clone()),
            detail: String::new(),
        }];
        if let Some(child) = row["child"].as_str() {
            choices.push(Choice {
                label: "Inspect this child's tool and text observations".into(),
                action: Action::Inspect("activity".into(), Some(child.into())),
                detail: String::new(),
            });
        }
        self.menu(
            "Observed evidence · no authorship or execution implied",
            choices,
        );
        self.ui.menu.as_mut().unwrap().detail = safe(&text);
    }

    pub fn retain_editor(&mut self) {
        let Some(prompt) = &self.flow.prompt else {
            return;
        };
        let (id, kind) = if let Some((id, qid)) = &prompt.question {
            (format!("answer:{id}:{qid}"), "answer")
        } else if prompt.kind == "Correct active turn" {
            (
                format!(
                    "correction:{}",
                    prompt.identity.as_deref().unwrap_or("unknown")
                ),
                "correction",
            )
        } else {
            return;
        };
        let text = prompt.editor.lines().join("\n");
        self.retain_text(id, kind, text);
    }

    pub fn retain_text(&mut self, id: String, kind: &str, text: String) {
        if self.insights.saved.get(&id) == Some(&text) {
            return;
        }
        let row = json!({"id":id,"kind":kind,"source":self.nav.session,"text":text});
        self.insights.drafts.retain(|r| r["id"] != id);
        if !text.is_empty() {
            self.insights.drafts.push(row.clone());
        }
        self.insights.saved.insert(id, text);
        if self.durable {
            self.send(json!({"op":"editor_draft","row":row}));
        }
    }

    pub fn local_drafts(&mut self) {
        let choices = self
            .insights
            .drafts
            .iter()
            .rev()
            .map(|r| Choice {
                label: format!(
                    "{} · {}",
                    string(r, "kind"),
                    safe(&string(r, "text").chars().take(70).collect::<String>())
                        .replace('\n', " ↵ ")
                ),
                action: Action::LocalDraft(r.clone()),
                detail: format!(
                    "Source conversation: {}\nOriginal scope: {}\n\n{}",
                    string(r, "source"),
                    string(r, "id"),
                    safe(&string(r, "text"))
                ),
            })
            .collect();
        self.menu(
            "Saved local drafts · never automatically submitted",
            choices,
        );
        self.ui.menu.as_mut().unwrap().detail = format!(
            "Answers/corrections retain their original scope. Open to copy or remove; nothing is resumed or retargeted. Up to 32 drafts / 2 MiB; autosave after a 250 ms pause. {}",
            self.insights.error
        );
    }

    pub fn local_draft(&mut self, row: Value) {
        self.menu(
            "Saved draft · historical intent, not a live request",
            vec![
                Choice {
                    label: "Copy text (does not submit)".into(),
                    action: Action::CopyText(string(&row, "text")),
                    detail: String::new(),
                },
                Choice {
                    label: "Remove this saved draft".into(),
                    action: Action::RemoveDraft(string(&row, "id")),
                    detail: String::new(),
                },
            ],
        );
        self.ui.menu.as_mut().unwrap().detail = format!(
            "Source: {}\nScope: {}\n\n{}",
            string(&row, "source"),
            string(&row, "id"),
            safe(&string(&row, "text"))
        );
    }
}

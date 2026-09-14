//! Correlated local lookups and explicit view replacement, never implicit execution.
use super::*;
use interaction::Choice;

#[derive(Default)]
pub struct Navigation {
    pub enabled: bool,
    pub session: String,
    pub switching: Option<String>,
    pub lookup: Option<Lookup>,
}

pub struct Lookup {
    id: String,
    draft: String,
    cursor: (usize, usize),
    span: Option<(usize, usize, usize)>,
}

impl App {
    pub fn reject_lookup(&mut self, id: &str) {
        if self.nav.lookup.as_ref().is_some_and(|p| p.id == id)
            && self.nav.lookup.take().unwrap().span.is_none()
        {
            self.ui.menu = None;
        }
    }
    pub fn lookup(&mut self, span: Option<(usize, usize, usize)>, query: String) {
        if !self.nav.enabled || self.disconnected {
            self.status = "Local discovery unavailable in this launch".into();
            return;
        }
        let cursor = self.draft.cursor();
        self.nav.lookup = Some(Lookup {
            id: (self.request + 1).to_string(),
            draft: self.draft.lines().join("\n"),
            cursor: (cursor.0, cursor.1),
            span,
        });
        if span.is_none() {
            self.menu("Saved conversations · loading…", vec![]);
        }
        self.status = "Looking up local choices…".into();
        self.send(json!({"op": if span.is_some() { "complete_path" } else { "conversations" }, "query":query}));
    }

    pub fn receive_lookup(&mut self, value: &Value) {
        if self
            .nav
            .lookup
            .as_ref()
            .is_none_or(|p| value["request_id"] != p.id)
            || value["session_id"] != self.nav.session
        {
            return;
        }
        let pending = self.nav.lookup.take().unwrap();
        if self.draft.lines().join("\n") != pending.draft || self.draft.cursor() != pending.cursor {
            return;
        }
        if let Some(message) = value["error"].as_str() {
            self.ui.menu = None;
            self.status = safe(message);
            return;
        }
        if let Some((row, start, end)) = pending.span {
            if self.ui.menu.is_some() || self.ui.focus.is_some() {
                return;
            }
            let choices: Vec<_> = value["candidates"]
                .as_array()
                .unwrap_or(&vec![])
                .iter()
                .filter_map(|s| s.as_str())
                .map(|s| Choice {
                    label: safe(s),
                    action: Action::Complete(row, start, end, s.into()),
                    detail: String::new(),
                })
                .collect();
            match choices.len() {
                0 => {
                    self.status =
                        "No matching workspace paths; start with ./ and narrow the directory".into()
                }
                1 if value["truncated"] != true => {
                    self.activate(choices[0].action.clone());
                }
                _ => {
                    self.menu("Workspace paths · names only; Tab/Enter inserts", choices);
                    self.status =
                        "Choose a workspace path · no file content has been loaded".into();
                    if value["truncated"] == true {
                        self.ui.menu.as_mut().unwrap().detail = "Partial results (2000 names / 80 matches maximum). Narrow the path and retry.".into();
                    }
                }
            }
        } else {
            let Some(menu) = &self.ui.menu else {
                return;
            };
            let query = menu.query.clone();
            let mut choices = vec![Choice {
                label: "New conversation — same bundle and directory".into(),
                action: Action::Switch("new".into()),
                detail: String::new(),
            }];
            for entry in value["sessions"].as_array().unwrap_or(&vec![]) {
                let id = string(entry, "id");
                let label = format!(
                    "{} · {} · {}",
                    id.chars().take(8).collect::<String>(),
                    if string(entry, "status") == "current" {
                        "current"
                    } else {
                        "saved"
                    },
                    safe(&string(entry, "title"))
                );
                choices.push(Choice {
                    label,
                    detail: format!("{}\nDirectory: {}\nConversation: {}\nOpen saves the current draft. Target checkpoint is validated before switching.", safe(&string(entry,"title")), safe(&string(entry,"cwd")), id),
                    action: if string(entry,"status").starts_with("recovery required") { Action::RecoverChoice(id) } else { Action::Switch(id) },
                });
            }
            self.menu(
                "Saved conversations · choose explicitly; Esc keeps draft",
                choices,
            );
            let menu = self.ui.menu.as_mut().unwrap();
            menu.query = query;
            menu.detail = "Opening saves this draft and pauses editing. Active work must finish or be stopped first. Uncertain or incompatible targets will be refused. Up to 100 most recent conversations.".into();
            self.status =
                "Choose a saved conversation or start a new one · Esc returns to draft".into();
        }
    }

    pub fn switch_conversation(&mut self, target: String) {
        if !self.nav.enabled || self.disconnected {
            self.status = "Conversation switching unavailable".into();
            return;
        }
        self.nav.lookup = None;
        self.nav.switching = Some((self.request + 1).to_string());
        self.status = "Opening conversation · editing paused; saving source draft…".into();
        self.send(json!({"op":"switch", "target":target, "draft":self.draft.lines().join("\n")}));
    }
}

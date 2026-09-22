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
    pub fn conversation_page(&mut self, offset: usize, query: String) {
        self.lookup_page(None, query, offset);
    }
    pub fn reject_lookup(&mut self, id: &str) {
        if self.insights.lookup.as_deref() == Some(id)
            && self
                .ui
                .menu
                .as_ref()
                .is_some_and(|m| m.title == "Earlier history · loading")
        {
            self.insights.lookup = None;
            self.ui.menu = None;
        }
        if self.nav.lookup.as_ref().is_some_and(|p| p.id == id)
            && self.nav.lookup.take().unwrap().span.is_none()
        {
            self.ui.menu = None;
        }
    }
    pub fn lookup(&mut self, span: Option<(usize, usize, usize)>, query: String) {
        self.lookup_page(span, query, 0);
    }

    fn lookup_page(&mut self, span: Option<(usize, usize, usize)>, query: String, offset: usize) {
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
        let op = if span.is_none() {
            "conversations"
        } else if query.starts_with('/') {
            "complete_command"
        } else {
            "complete_path"
        };
        self.send(json!({"op": op, "query":query, "offset":offset, "cursor":cursor.1}));
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
            let arguments = value["command_arguments"] == true;
            let choices: Vec<_> = value["candidates"]
                .as_array()
                .unwrap_or(&vec![])
                .iter()
                .filter_map(|s| {
                    Some((
                        s.as_str().or_else(|| s["value"].as_str())?,
                        s["description"].as_str().unwrap_or(""),
                    ))
                })
                .map(|(s, detail)| Choice {
                    label: safe(s),
                    action: Action::Complete(row, start, end, s.into()),
                    detail: safe(detail),
                })
                .collect();
            match choices.len() {
                0 => {
                    self.status = if arguments {
                        "No matching command arguments · free-form text stays editable"
                    } else {
                        "No matching workspace paths; start with ./ and narrow the directory"
                    }
                    .into()
                }
                1 if value["truncated"] != true => {
                    self.activate(choices[0].action.clone());
                }
                _ => {
                    self.menu(
                        if arguments {
                            "Command arguments · Tab/Enter inserts; Send runs"
                        } else {
                            "Workspace paths · names only; Tab/Enter inserts"
                        },
                        choices,
                    );
                    self.status = if arguments {
                        "Cached local choices · nothing sent"
                    } else {
                        "Choose a workspace path · no file content has been loaded"
                    }
                    .into();
                    if value["truncated"] == true {
                        self.ui.menu.as_mut().unwrap().detail =
                            "Partial results (80 matches maximum). Narrow the input and retry."
                                .into();
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
            if !self.connected {
                choices.push(Choice { label: "Search saved conversation content…".into(), action: Action::FindSaved, detail: "Search saved messages in this launch directory only; does not call a model or open a conversation.".into() });
                choices.push(Choice { label: "CLI sessions — import a historical reference…".into(), action: Action::Inspect("cli_sessions".into(), None), detail: "Browse the configured CLI home's sessions in this directory. Separate from TUI resume; original sources remain unchanged.".into() });
            }
            let search = string(value, "query");
            let offset = value["offset"].as_u64().unwrap_or(0) as usize;
            if offset > 0 {
                choices.push(Choice {
                    label: "Previous page of conversations".into(),
                    action: Action::ConversationPage(offset.saturating_sub(100), search.clone()),
                    detail: String::new(),
                });
            }
            if let Some(next) = value["next_offset"].as_u64() {
                choices.push(Choice { label: "Next page of conversations".into(), action: Action::ConversationPage(next as usize, search.clone()), detail: "Continue scanning older conversations, including pages without search matches.".into() });
            }
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
                    detail: format!("{}\nDirectory: {}\nConversation: {}\n{}\nOpen saves the current draft. Target checkpoint is validated before switching.", safe(&string(entry,"title")), safe(&string(entry,"cwd")), id, safe(&string(entry,"match"))),
                    action: if string(entry,"status").starts_with("recovery required") { Action::RecoverChoice(id) } else { Action::Switch(id) },
                });
            }
            self.menu(
                "Saved conversations · this directory · Esc keeps draft",
                choices,
            );
            let menu = self.ui.menu.as_mut().unwrap();
            menu.query = query;
            menu.detail = format!(
                "Page {} · Content search: {} · Partial source scan: {}\n{}\nOpening saves this draft. Uncertain/incompatible targets require recovery or refuse execution.",
                offset / 100 + 1,
                safe(&search),
                value["partial"] == true,
                safe(&string(value, "scope"))
            );
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

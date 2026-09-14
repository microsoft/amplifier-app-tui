//! Capability-backed, scoped runtime controls. No provider or module imports.
use super::*;
use interaction::Choice;

#[derive(Default)]
pub struct Controls {
    pub steer: bool,
    pub turn: String,
    pub ready_turn: String,
    pub providers: Value,
    pub observed: String,
    pub lookup: Option<String>,
    pub requests: std::collections::HashSet<String>,
}

impl App {
    pub fn mode_menu(&mut self, data: &Value) {
        if data["supported"] != true {
            self.status = "This composition has no supported mode control".into();
            return;
        }
        let current = data["current"].as_str().map(str::to_owned);
        if let Some(name) = data["select"].as_str() {
            if name == "clear" || name == "default" || name == "off" {
                self.activate(Action::ModeChoice(None, current));
                return;
            }
            if data["choices"]
                .as_array()
                .is_some_and(|rows| rows.iter().any(|r| r["name"] == name))
            {
                self.activate(Action::ModeChoice(Some(name.into()), current));
                return;
            }
            self.status = "Unknown mode; choose from the catalog".into();
        }
        let mut choices = vec![Choice {
            label: "Default — clear active mode".into(),
            action: Action::ModeChoice(None, current.clone()),
            detail: String::new(),
        }];
        for row in data["choices"].as_array().unwrap_or(&vec![]) {
            let name = string(row, "name");
            choices.push(Choice {
                label: format!("{} · {}", name, string(row, "description")),
                action: Action::ModeChoice(Some(name), current.clone()),
                detail: String::new(),
            });
        }
        self.menu("Modes · current session policy", choices);
        self.ui.menu.as_mut().unwrap().detail = format!(
            "Current: {}. Choose then Apply. Changes require an idle turn; module policy and persistence remain active.",
            current.as_deref().unwrap_or("default")
        );
    }
    pub fn correct_active(&mut self) {
        if !self.controls.steer || !self.flow.busy || self.controls.turn.is_empty() {
            self.status =
                "Correction needs an active turn and a supported orchestrator; nothing sent".into();
            return;
        }
        if self.controls.ready_turn != self.controls.turn {
            self.status =
                "Turn is starting; correction becomes available after its first provider request"
                    .into();
            return;
        }
        self.prompt("Correct active turn");
        self.flow.prompt.as_mut().unwrap().identity = Some(self.controls.turn.clone());
    }

    pub fn provider_menu(&mut self) {
        let data = &self.controls.providers;
        if data["supported"] != true {
            self.ui.menu = None;
            self.status =
                "Conversation-provider selection is unavailable in this orchestrator".into();
            return;
        }
        let revision = data["revision"].as_u64().unwrap_or(0);
        let current = data["current"].as_str().map(str::to_owned);
        let mut choices = vec![Choice {
            label: "Automatic — use the orchestrator's priority selection".into(),
            action: Action::ProviderChoice(None, revision, current.clone()),
            detail: String::new(),
        }];
        for row in data["choices"].as_array().unwrap_or(&vec![]) {
            let name = string(row, "name");
            choices.push(Choice {
                label: format!(
                    "{} · {} · {}{}",
                    safe(&name),
                    safe(&string(row, "model")),
                    safe(&string(row, "vendor")),
                    if current.as_ref() == Some(&name) {
                        " · selected"
                    } else {
                        ""
                    }
                ),
                action: Action::ProviderChoice(Some(name), revision, current.clone()),
                detail: String::new(),
            });
        }
        choices.push(Choice {
            label: "Selection history — inspect / copy local change records".into(),
            action: Action::ProviderHistory,
            detail: String::new(),
        });
        let detail = format!(
            "Current: {}. {}\nSelection {}. Apply while idle; this pauses pending follow-ups. Configured model labels are provider-reported defaults, not live model discovery. Retained changes: {} (limit 1000).",
            current.as_deref().unwrap_or("automatic / priority"),
            string(data, "scope"),
            if data["durable"] == true {
                "is retained on resume"
            } else {
                "is session-only (no store)"
            },
            revision
        );
        self.menu("Conversation provider · choose then confirm", choices);
        self.ui.menu.as_mut().unwrap().detail = format!(
            "{}\nLast observed selection in this engine: {}",
            detail,
            if self.controls.observed.is_empty() {
                "none yet"
            } else {
                &self.controls.observed
            }
        );
    }

    pub fn provider_history(&mut self) {
        let choices = self.controls.providers["changes"]
            .as_array()
            .unwrap_or(&vec![])
            .iter()
            .enumerate()
            .rev()
            .take(100)
            .map(|(index, row)| {
                let label = format!(
                    "{} · {} → {}",
                    index + 1,
                    row["from"].as_str().unwrap_or("automatic"),
                    row["to"].as_str().unwrap_or("automatic")
                );
                Choice {
                    label: safe(&label),
                    action: Action::CopyText(format!(
                        "{}\nRequest: {}",
                        label,
                        string(row, "request_id")
                    )),
                    detail: String::new(),
                }
            })
            .collect();
        self.menu("Provider selections · latest 100 changes", choices);
        self.ui.menu.as_mut().unwrap().detail = "Local control records, not model calls. Enter copies the selected change. Runtime selection is observed separately when work starts.".into();
    }

    pub fn provider_confirm(
        &mut self,
        name: Option<String>,
        revision: u64,
        current: Option<String>,
    ) {
        let label = name
            .as_deref()
            .unwrap_or("automatic / priority")
            .to_string();
        self.menu(
            "Apply conversation provider?",
            vec![Choice {
                label: format!("Apply {} to this conversation", safe(&label)),
                action: Action::ProviderApply(name, revision, current),
                detail: String::new(),
            }],
        );
        self.ui.menu.as_mut().unwrap().detail = format!(
            "{}\nRequires an idle turn. Pending follow-ups will be paused. Escape cancels; the composer is unchanged.",
            string(&self.controls.providers, "scope")
        );
    }
}

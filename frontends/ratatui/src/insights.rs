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
    pub image: Option<Value>,
    pub watching: Option<(String, Option<String>, Instant)>,
    pub activity_offset: usize,
}

pub fn thumbnail_lines(value: &Value, width: usize) -> Vec<Line<'static>> {
    let w = value["width"].as_u64().unwrap_or(0) as usize;
    let h = value["height"].as_u64().unwrap_or(0) as usize;
    let Some(pixels) = value["pixels"].as_array() else {
        return vec![];
    };
    if w == 0 || h == 0 || w > 32 || h > 16 || pixels.len() != w * h {
        return vec![];
    }
    let Some(rgb): Option<Vec<[u8; 3]>> = pixels
        .iter()
        .map(|pixel| {
            let values = pixel.as_array()?;
            if values.len() != 3 {
                return None;
            }
            Some([
                u8::try_from(values[0].as_u64()?).ok()?,
                u8::try_from(values[1].as_u64()?).ok()?,
                u8::try_from(values[2].as_u64()?).ok()?,
            ])
        })
        .collect()
    else {
        return vec![];
    };
    let mut lines = Vec::new();
    for y in (0..h).step_by(2) {
        let mut spans = Vec::new();
        for x in 0..w.min(width) {
            let a = rgb[y * w + x];
            let b = rgb[y.saturating_add(1).min(h - 1) * w + x];
            if std::env::var_os("NO_COLOR").is_some() {
                let light = (u32::from(a[0]) * 3 + u32::from(a[1]) * 6 + u32::from(a[2])) / 10;
                spans.push(Span::raw(
                    [" ", "░", "▒", "▓", "█"][(light * 4 / 255) as usize],
                ));
            } else {
                spans.push(Span::styled(
                    "▀",
                    Style::default()
                        .fg(Color::Rgb(a[0], a[1], a[2]))
                        .bg(Color::Rgb(b[0], b[1], b[2])),
                ));
            }
        }
        lines.push(Line::from(spans));
    }
    lines
}

impl App {
    pub fn model_catalog_result(&mut self, value: Value) {
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
            .is_none_or(|m| m.title != "Model catalog · querying")
        {
            return;
        }
        let choices = value["rows"]
            .as_array()
            .unwrap_or(&vec![])
            .iter()
            .map(|row| Choice {
                label: format!(
                    "{} · {} · {}",
                    safe(&string(row, "provider")),
                    safe(&string(row, "model")),
                    safe(&string(row, "status"))
                ),
                action: if string(row, "model").is_empty() {
                    Action::HelpTopic("Model catalog unavailable".into(), string(row, "status"))
                } else {
                    Action::CopyText(string(row, "model"))
                },
                detail: format!(
                    "Provider-reported context window: {} tokens\nMaximum output: {} tokens\nAdvertised capabilities: {}\nThese catalog limits are not current occupancy or remaining request capacity. Module reserves/instructions/tools still apply. Enter copies only the model ID; no configuration change.",
                    row["limits"]["context_window"].as_u64().map(|n| n.to_string()).unwrap_or("unknown".into()),
                    row["limits"]["max_output_tokens"].as_u64().map(|n| n.to_string()).unwrap_or("unknown".into()),
                    row["capabilities"],
                ),
            })
            .collect();
        self.menu("Model catalog · advisory IDs", choices);
        self.ui.menu.as_mut().unwrap().detail =
            format!("{}\nPartial: {}", string(&value, "scope"), value["partial"]);
    }
    pub fn image_snapshot_result(&mut self, value: Value) {
        let Some((id, draft)) = &self.insights.file_request else {
            return;
        };
        if value["session_id"] != self.nav.session || value["request_id"] != *id {
            return;
        }
        if self.draft.lines().join("\n") != *draft
            || self
                .ui
                .menu
                .as_ref()
                .is_none_or(|m| m.title != "Text file · reading")
        {
            return;
        }
        self.insights.file_request = None;
        if let Some(error) = value["error"].as_str() {
            self.ui.menu = None;
            self.status = format!("Attachment not added: {}", safe(error));
            return;
        }
        let reference = value["media_type"] == "text/plain";
        self.menu(
            if reference {
                "File reference · confirm attachment"
            } else {
                "Image snapshot · confirm attachment"
            },
            vec![Choice {
                label: if reference {
                    "Add captured reference to draft (up to four attachments)"
                } else {
                    "Add captured image to draft (up to four)"
                }
                .into(),
                action: Action::ImageSelect(string(&value, "id")),
                detail: String::new(),
            }],
        );
        self.ui.menu.as_mut().unwrap().detail = format!(
            "{} · {} · {} bytes\nSHA-256: {}\nCoarse thumbnail; original captured bytes are sent, not this preview. Up to four images per Send or queued message. Sending shares images with the configured provider. Escape leaves current attachments unchanged.",
            safe(&string(&value, "path")),
            string(&value, "media_type"),
            value["bytes"],
            string(&value, "sha256")
        );
        self.ui.menu.as_mut().unwrap().image = value.get("thumbnail").cloned();
        if reference {
            self.ui.menu.as_mut().unwrap().detail = format!(
                "{}:{}-{} · {} bytes\nSource SHA-256: {}\nExcerpt SHA-256: {}\nCaptured source data; Send or Queue shares this version, never a later file reread. Escape leaves attachments unchanged.\n\n{}",
                safe(&string(&value, "path")),
                value["start_line"],
                value["end_line"],
                value["bytes"],
                string(&value, "source_sha256"),
                string(&value, "sha256"),
                safe(&string(&value, "preview_text"))
            );
        }
    }

    pub fn image_draft_menu(&mut self) {
        let Some(image) = self.insights.image.clone() else {
            self.status = "No attachment".into();
            return;
        };
        self.menu(
            "Attachment draft · inspect before removing",
            vec![Choice {
                label: "Remove attachment set (never undo or retry)".into(),
                action: Action::ImageRemove(string(&image, "id")),
                detail: String::new(),
            }],
        );
        self.ui.menu.as_mut().unwrap().detail = format!(
            "{}\nState: {}\nSHA-256: {}\nDispatched means admission was recorded, not proof the provider saw it. A dispatched attachment never becomes unsent after restart.",
            attachment_location(&image),
            string(&image, "state"),
            string(&image, "sha256")
        );
        if image["source_sha256"].is_string() {
            self.ui.menu.as_mut().unwrap().detail.push_str(&format!(
                "\nSource SHA-256: {}",
                string(&image, "source_sha256")
            ));
        }
        if image["state"] == "attached" {
            for item in image["images"].as_array().unwrap_or(&vec![]) {
                self.ui.menu.as_mut().unwrap().choices.push(Choice {
                    label: format!("Remove {}", attachment_location(item)),
                    action: Action::ImageRemoveItem(string(&image, "id"), string(item, "id")),
                    detail: format!(
                        "{} bytes · SHA-256 {}{}",
                        item["bytes"],
                        string(item, "sha256"),
                        if item["source_sha256"].is_string() {
                            format!("\nSource SHA-256: {}", string(item, "source_sha256"))
                        } else {
                            String::new()
                        }
                    ),
                });
            }
        }
    }

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
        self.insights.activity_offset = 0;
        if self.disconnected || self.mode == "SIMULATED" {
            self.status = "Observed-work inspection requires the runtime host".into();
            return;
        }
        self.insights.lookup = Some((self.request + 1).to_string());
        self.insights.watching = Some((category.clone(), child.clone(), Instant::now()));
        self.menu("Observed work · loading", vec![]);
        self.send(json!({"op":"inspect","category":category,"child":child}));
    }

    pub fn inspect_page(&mut self, child: Option<String>, offset: usize) {
        self.insights.activity_offset = offset;
        self.insights.lookup = Some((self.request + 1).to_string());
        self.insights.watching = Some(("activity_tree".into(), child.clone(), Instant::now()));
        self.menu("Observed work · loading", vec![]);
        self.send(json!({"op":"inspect","category":"activity_tree","child":child,"offset":offset}));
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
        if self.ui.menu.as_ref().is_none_or(|m| {
            m.title != "Observed work · loading"
                && !m.title.starts_with("Delegated work · scoped")
                && !m.title.starts_with("Activity ·")
        }) {
            return;
        }
        let category = string(&value, "category");
        if category == "activity_tree" {
            self.activity_result(value);
            return;
        }
        let prior = self.ui.menu.as_ref().map(|menu| {
            let id = menu
                .filtered()
                .get(menu.selected)
                .and_then(|choice| match &choice.action {
                    Action::Observation(row) => row["id"].as_str().map(str::to_owned),
                    _ => None,
                });
            (menu.query.clone(), id, menu.detail_scroll)
        });
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
                        if row["recipe_file"].is_string() {
                            "local filename"
                        } else if row["live"] == true {
                            "live child"
                        } else {
                            "observed"
                        },
                        safe(&string(row, "status")),
                        safe(&string(row, "label"))
                    ),
                    action: if let Some(path) = row["recipe_file"].as_str() {
                        Action::RecipeFile(path.into())
                    } else if let Some(id) = row["cli_import"].as_str() {
                        Action::CliImport(id.into())
                    } else {
                        Action::Observation(row.clone())
                    },
                    detail: if row["cli_import"].is_string()
                        || row["recipe_file"].is_string()
                        || category == "runtime_output"
                    {
                        safe(&string(row, "detail"))
                    } else {
                        format!(
                            "Conversation {} · turn {} · sequence {}\n{}",
                            string(row, "source"),
                            string(row, "turn"),
                            row["sequence"],
                            safe(&string(row, "detail"))
                        )
                    },
                }),
        );
        self.menu(
            match category.as_str() {
                "children" => "Delegated work · scoped child observations",
                "context" => "Context intelligence · observed diagnostics",
                "stored_context" => "Stored context · module snapshot, not wire request",
                "wire_request" => "Provider request · memory-only projection",
                "runtime_output" => "Runtime output · private diagnostics",
                "instructions" => "Instruction sources · last observed resolution",
                "recipes" => "Recipe activity · observed tool calls",
                "recipe_files" => "Recipe files · local candidates, not active sessions",
                "recovery" => "Recovered work · inspect before adopting",
                "cli_sessions" => "CLI sessions · import historical reference",
                "changes" => "Change and command evidence · tool-correlated source versions",
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
        if category == "wire_request" {
            self.ui.menu.as_mut().unwrap().detail = format!(
                "{}\n{}\nProjection limited: {}",
                string(&value, "scope"),
                string(&value, "context_note"),
                value["partial"]
            );
        }
        if category == "runtime_output" {
            self.ui.menu.as_mut().unwrap().detail = format!(
                "{}\n{}\nPartial capture: {}",
                string(&value, "scope"),
                string(&value, "context_note"),
                value["partial"]
            );
        }
        if category == "cli_sessions" || category == "recipe_files" {
            self.ui.menu.as_mut().unwrap().detail = format!(
                "Partial catalog: {}\n{}",
                value["partial"],
                string(&value, "scope")
            );
        }
        if let Some((query, id, scroll)) = prior {
            let menu = self.ui.menu.as_mut().unwrap();
            menu.query = query;
            menu.detail_scroll = scroll;
            if let Some(id) = id {
                menu.selected = menu.filtered().iter().position(|choice| matches!(&choice.action, Action::Observation(row) if row["id"] == id)).unwrap_or(0);
            }
        }
    }

    pub fn refresh_children(&mut self) {
        if self.disconnected
            || self.insights.lookup.is_some()
            || self.flow.prompt.is_some()
            || self.ui.menu.as_ref().is_none_or(|m| {
                !m.title.starts_with("Delegated work · scoped")
                    && !m.title.starts_with("Activity ·")
            })
        {
            return;
        }
        let Some((category, child, last)) = &mut self.insights.watching else {
            return;
        };
        if last.elapsed() < Duration::from_secs(1) {
            return;
        }
        *last = Instant::now();
        let (category, child) = (category.clone(), child.clone());
        self.insights.lookup = Some((self.request + 1).to_string());
        self.send(json!({"op":"inspect", "category":category, "child":child,"offset":self.insights.activity_offset}));
    }

    pub fn activity_result(&mut self, value: Value) {
        let prior = self.ui.menu.as_ref().map(|m| {
            (
                m.query.clone(),
                m.filtered().get(m.selected).map(|c| c.action.clone()),
                m.detail_scroll,
            )
        });
        let mut choices = vec![];
        let offset = value["offset"].as_u64().unwrap_or(0) as usize;
        let node = value["node"].as_str().map(str::to_owned);
        if offset > 0 {
            choices.push(Choice {
                label: "‹ Earlier activity".into(),
                action: Action::ActivityPage(node.clone(), offset.saturating_sub(100)),
                detail: String::new(),
            });
        }
        if let Some(next) = value["next_offset"].as_u64() {
            choices.push(Choice {
                label: "More activity ›".into(),
                action: Action::ActivityPage(node, next as usize),
                detail: String::new(),
            });
        }
        if value["node"].is_string() {
            choices.push(Choice {
                label: "‹ Back one level".into(),
                action: Action::Inspect(
                    "activity_tree".into(),
                    value["parent"].as_str().map(str::to_owned),
                ),
                detail: String::new(),
            });
        }
        let focus = &value["focus"];
        if focus.is_object() {
            choices.push(Choice {
                label: "Preview · observed content".into(),
                action: Action::ActivityPreview(focus.clone()),
                detail: string(focus, "preview"),
            });
            choices.push(Choice {
                label: if focus["partial"] == true {
                    "Observed arguments / result · excerpt…"
                } else {
                    "Exact observed arguments / result…"
                }
                .into(),
                action: Action::Observation(focus.clone()),
                detail: "Read-only source evidence; partial excerpts are labelled. No tool is run."
                    .into(),
            });
        }
        for row in value["rows"].as_array().unwrap_or(&vec![]) {
            choices.push(Choice {
                label: format!(
                    "▸ {}{} · {}{}{}",
                    match row["status"].as_str() {
                        Some("waiting_capacity") => "waiting".into(),
                        _ => string(row, "status"),
                    },
                    if row["partial"] == true {
                        " (excerpt)"
                    } else {
                        ""
                    },
                    native::one_line(&string(row, "label"), 64),
                    if row["summary"].as_str().unwrap_or("").is_empty() {
                        ""
                    } else {
                        " · "
                    },
                    string(row, "summary")
                ),
                action: Action::Inspect("activity_tree".into(), Some(string(row, "id"))),
                detail: format!(
                    "{}\n{}\n{} observed children · Enter/click to open",
                    string(row, "label"),
                    native::one_line(&string(row, "preview"), 220),
                    row["children"]
                ),
            });
        }
        self.menu(
            format!(
                "Activity · {}{}",
                if value["partial"] == true {
                    "limited index · "
                } else {
                    ""
                },
                if value["node"].is_string() {
                    native::one_line(&string(&value, "breadcrumb"), 80)
                } else {
                    "tools and thinking".into()
                }
            ),
            choices,
        );
        let menu = self.ui.menu.as_mut().unwrap();
        menu.detail = format!(
            "{}\nPartial index: {}",
            string(&value, "scope"),
            value["partial"]
        );
        if focus.is_object() {
            menu.selected = menu
                .choices
                .iter()
                .position(|c| matches!(c.action, Action::ActivityPreview(_)))
                .unwrap_or(0);
        }
        if let Some((query, Some(action), scroll)) = prior {
            // Keep focus by identity, not a shifting row number, during updates.
            menu.query = query;
            if let Some(index) = menu
                .filtered()
                .iter()
                .position(|c| match (&c.action, &action) {
                    (Action::ActivityPreview(a), Action::ActivityPreview(b))
                    | (Action::Observation(a), Action::Observation(b)) => a["id"] == b["id"],
                    _ => c.action == action,
                })
            {
                menu.selected = index;
                menu.detail_scroll = scroll;
            }
        }
    }

    pub fn activity_preview(&mut self, row: Value) {
        self.menu(
            format!("Preview · {}", string(&row, "label")),
            vec![
                Choice {
                    label: "‹ Back to activity".into(),
                    action: Action::Inspect("activity_tree".into(), Some(string(&row, "id"))),
                    detail: String::new(),
                },
                Choice {
                    label: "Copy observed source text".into(),
                    action: Action::CopyText(string(&row, "preview")),
                    detail: String::new(),
                },
            ],
        );
        let menu = self.ui.menu.as_mut().unwrap();
        menu.detail = string(&row, "preview");
        menu.prose = row["markdown"] == true;
        menu.secondary = row["thinking"] == true;
    }

    pub fn observation(&mut self, row: Value) {
        if row["kind"] == "runtime_output" {
            let text = format!(
                "Received {}\n{}",
                string(&row, "status"),
                string(&row, "detail")
            );
            self.menu(
                "Runtime output · private diagnostic",
                vec![
                    Choice {
                        label: "Copy private diagnostic".into(),
                        action: Action::CopyText(text.clone()),
                        detail: String::new(),
                    },
                    Choice {
                        label: "Back to runtime output".into(),
                        action: Action::Inspect("runtime_output".into(), None),
                        detail: String::new(),
                    },
                ],
            );
            self.ui.menu.as_mut().unwrap().detail = safe(&text);
            return;
        }
        if row["id"] == "context-policy" {
            let text = format!(
                "Conversation: {}\n\n{}",
                string(&row, "source"),
                string(&row, "detail")
            );
            self.menu(
                "Context intelligence · configuration snapshot",
                vec![Choice {
                    label: "Copy configuration snapshot".into(),
                    action: Action::CopyText(text.clone()),
                    detail: String::new(),
                }],
            );
            self.ui.menu.as_mut().unwrap().detail = safe(&text);
            return;
        }
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
        if self
            .insights
            .watching
            .as_ref()
            .is_some_and(|(category, _, _)| category == "activity_tree")
        {
            choices.insert(
                0,
                Choice {
                    label: "‹ Back to activity".into(),
                    action: Action::Inspect("activity_tree".into(), Some(string(&row, "id"))),
                    detail: String::new(),
                },
            );
        }
        if let Some(id) = row["cli_import"].as_str() {
            choices.push(Choice {
                label: "Import this CLI history into a NEW conversation…".into(),
                action: Action::CliImport(id.into()),
                detail: "Historical reference only; confirmation required; no tool replay.".into(),
            });
        }
        if row["recover_child"] == true && row["source_sha256"].is_string() {
            choices.push(Choice {
                label: "Continue captured child under a NEW identity…".into(),
                action: Action::RecoverChild(Arc::new(row.clone())),
                detail: "Explicit new instruction and confirmation required; unknown tool effects are not replayed".into(),
            });
        }
        if let Some(child) = row["child"].as_str() {
            choices.push(Choice {
                label: "Inspect this child's tool and text observations".into(),
                action: Action::Inspect("activity".into(), Some(child.into())),
                detail: String::new(),
            });
        }
        for identity in row["recipe_ids"].as_array().unwrap_or(&vec![]) {
            if let Some(identity) = identity.as_str() {
                choices.push(Choice {
                    label: format!("Prepare recipe review request · {}", safe(identity)),
                    action: Action::RecipeRequest(identity.into()),
                    detail: "Adds a request to your draft, not a recipe operation or permission grant. Send explicitly. Resume can retry unfinished steps with partial effects; completed steps belong to the runner's checkpoint.".into(),
                });
            }
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
            (
                format!(
                    "dialog:{}:{}",
                    prompt.kind,
                    prompt.identity.as_deref().unwrap_or("local")
                ),
                "dialog",
            )
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
            "Answers, corrections, dialog editors and startup-conflict drafts retain their original scope. Open to copy or remove; nothing is resumed or retargeted. Up to 32 drafts / 2 MiB; autosave after a 250 ms pause. Unflushed keystrokes are not crash-durable. {}",
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

pub fn attachment_location(value: &Value) -> String {
    let path = safe(&string(value, "path"));
    if value["media_type"] == "text/plain" {
        format!("{path}:{}-{}", value["start_line"], value["end_line"])
    } else {
        path
    }
}

#[cfg(test)]
mod thumbnail_tests {
    use super::*;
    #[test]
    fn reference_location_disambiguates_same_file_ranges() {
        let first =
            json!({"path":"src/界.rs", "media_type":"text/plain", "start_line":7, "end_line":9});
        let mut second = first.clone();
        second["start_line"] = json!(12);
        second["end_line"] = json!(12);
        assert_eq!(attachment_location(&first), "src/界.rs:7-9");
        assert_eq!(attachment_location(&second), "src/界.rs:12-12");
        assert_eq!(
            attachment_location(&json!({"path":"image.png", "media_type":"image/png"})),
            "image.png"
        );
    }
    #[test]
    fn bounded_thumbnail_rejects_invalid_channels_and_respects_width() {
        let value =
            json!({"width":2, "height":2, "pixels":[[255,0,0],[0,0,255],[255,0,0],[0,0,255]]});
        assert_eq!(thumbnail_lines(&value, 1)[0].width(), 1);
        assert_eq!(thumbnail_lines(&value, 80).len(), 1);
        assert!(
            thumbnail_lines(&json!({"width":1,"height":1,"pixels":[[999,0,0]]}), 80).is_empty()
        );
    }
}

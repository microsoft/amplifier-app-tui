//! Content-sized primary-screen controls. Execution remains behind identified requests.
use super::*;
use unicode_segmentation::UnicodeSegmentation;
use unicode_width::UnicodeWidthChar;
use unicode_width::UnicodeWidthStr;

fn title_preview(value: &str, width: u16) -> String {
    let limit = usize::from(width / 2).min(56);
    if value.width() <= limit {
        return value.into();
    }
    let mut preview = String::new();
    let mut used = 0;
    for glyph in value.graphemes(true) {
        if used + glyph.width() >= limit {
            break;
        }
        preview.push_str(glyph);
        used += glyph.width();
    }
    preview.push('…');
    preview
}

/// Keep simulations/fixtures explicit without branding every ordinary live frame.
pub fn runtime_notice(mode: &str) -> String {
    if mode == "LIVE RUNTIME" || mode.is_empty() {
        String::new()
    } else {
        format!(" · {}", safe(mode))
    }
}

pub fn status_label(status: &str) -> &str {
    match status {
        "Ready · real modules mounted" => "Ready",
        _ => status,
    }
}

/// Match the editor's glyph wrapping, stopping as soon as the visible budget is full.
/// Never lay out the whole of an enormous paste merely to size the live region.
pub fn draft_rows(lines: &[String], width: u16, limit: u16) -> u16 {
    let width = usize::from(width.max(1));
    let mut rows = 0;
    for line in lines {
        rows += 1;
        let mut col = 0;
        for glyph in line.graphemes(true) {
            let cells: usize = glyph
                .chars()
                .map(|c| if c == '\t' { 4 } else { c.width().unwrap_or(0) })
                .sum();
            if col > 0 && col + cells > width {
                rows += 1;
                col = 0;
            }
            if rows >= limit {
                return limit.max(1);
            }
            col += cells;
        }
        if rows >= limit {
            return limit.max(1);
        }
    }
    rows.max(1)
}

pub struct Chrome {
    pub height: u16,
    edit_rows: u16,
    buttons: Vec<(u16, u16, String, Action)>,
    hint: Option<(u16, u16, String)>,
}

impl Chrome {
    pub fn new(app: &App, width: u16, height: u16) -> Self {
        let mut choices = vec![("[ Actions ]".into(), Action::Menu)];
        if app.ready {
            choices.push((
                if app.flow.busy && app.nav.enabled {
                    "[ Queue ]"
                } else {
                    "[ Send ]"
                }
                .into(),
                Action::Send,
            ));
            if app.flow.busy {
                choices.push(("[Steer]".into(), Action::CorrectActive));
                choices.push(("[ Stop ]".into(), Action::Stop));
            }
            let pending = app
                .flow
                .rows
                .iter()
                .filter(|r| r["state"] == "queued")
                .count();
            if pending > 0 || app.flow.paused {
                choices.push((
                    format!(
                        "[Pending {pending}]{}",
                        if app.flow.paused { " (paused)" } else { "" }
                    ),
                    Action::QueueList,
                ));
            }
            if !app.questions.pending.is_empty() {
                choices.push((
                    format!("[ Answer questions {} ]", app.questions.pending.len()),
                    Action::Questions,
                ));
            }
            choices.push(("[Resume]".into(), Action::Conversations));
            choices.push(("[Modes]".into(), Action::Modes));
        }
        if app.startup_recovery.is_some() {
            choices.push(("[Saved draft]".into(), Action::LocalDrafts));
        }
        if app
            .insights
            .image
            .as_ref()
            .is_some_and(|image| image["state"] == "attached")
        {
            let media = app.insights.image.as_ref().unwrap();
            let references = media["media_type"] == "text/plain"
                || media["images"].as_array().is_some_and(|items| {
                    items.iter().any(|item| item["media_type"] == "text/plain")
                });
            choices.push((
                if references {
                    "[References attached]"
                } else {
                    "[Image attached]"
                }
                .into(),
                Action::ImageDraft,
            ));
        }
        let mut buttons = Vec::new();
        let (mut x, mut y) = (0, 0);
        for (label, action) in choices {
            let len = label.chars().count() as u16;
            if x > 0 && x + len > width {
                x = 0;
                y += 1;
            }
            buttons.push((x, y, label, action));
            x += len + 1;
        }
        let hint = if app.nav.switching.is_some() {
            "Opening conversation · input paused".into()
        } else if app.ready {
            format!(
                "Enter {} · Tab complete/actions",
                if app.flow.busy && app.nav.enabled {
                    "queue"
                } else {
                    "send"
                }
            )
        } else {
            "Starting · type now, send when ready".into()
        };
        let hint = (x + hint.chars().count() as u16 <= width).then_some((x, y, hint));
        let controls = y + 1;
        let limit = height.saturating_sub(controls + 3).clamp(1, 6);
        let edit_rows = draft_rows(app.draft.lines(), width, limit);
        Self {
            height: edit_rows + 3 + controls,
            edit_rows,
            buttons,
            hint,
        }
    }

    pub fn draw(&self, f: &mut Frame, app: &mut App, area: Rect) {
        let composer = Rect::new(area.x, area.y, area.width, self.edit_rows + 2);
        text(
            f,
            Rect::new(area.x, area.y, area.width, 1),
            format!(
                "Message · Mode: {}{}",
                app.policy,
                runtime_notice(&app.mode)
            ),
            if app.ui.focus.is_none() { GREEN } else { MUTED },
        );
        let title = title_preview(&app.title, area.width);
        let heading_width = format!(
            "Message · Mode: {}{}",
            app.policy,
            runtime_notice(&app.mode)
        )
        .width();
        if area.width >= 74 && heading_width + title.width() + 2 <= area.width as usize {
            text(
                f,
                Rect::new(
                    area.right() - title.width() as u16,
                    area.y,
                    title.width() as u16,
                    1,
                ),
                title,
                MUTED,
            );
        }
        // No prompt or border beside any input row: terminal selection copies words.
        let edit = Rect::new(area.x, area.y + 1, area.width, self.edit_rows);
        composer::render_fitted(&mut app.draft, edit, f.buffer_mut());
        let controls_y = composer.bottom();
        for (x, y, label, action) in &self.buttons {
            app.button(
                f,
                Rect::new(
                    area.x + x,
                    controls_y + y,
                    (label.chars().count() as u16).min(area.width.saturating_sub(*x)),
                    1,
                ),
                label.clone(),
                action.clone(),
            );
        }
        if let Some((x, y, hint)) = &self.hint {
            text(
                f,
                Rect::new(area.x + x, controls_y + y, area.width - x, 1),
                hint.clone(),
                MUTED,
            );
        }
        text(
            f,
            Rect::new(area.x, area.y + self.height - 1, area.width, 1),
            if app.nav.switching.is_some() {
                "Opening conversation · input paused; draft retained".into()
            } else {
                status_label(&app.status).to_owned()
            },
            if app.disconnected { RED } else { MUTED },
        );
        // A contextual control disappearing must not leave an invisible Enter target.
        if app
            .ui
            .focus
            .as_ref()
            .is_some_and(|focus| !app.ui.buttons.iter().any(|(_, c)| &c.action == focus))
        {
            app.ui.focus = None;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn live_branding_is_quiet_but_non_live_modes_are_explicit() {
        assert_eq!(runtime_notice("LIVE RUNTIME"), "");
        assert_eq!(runtime_notice("SIMULATED"), " · SIMULATED");
        assert_eq!(runtime_notice("FIXTURE RUNTIME"), " · FIXTURE RUNTIME");
    }

    #[test]
    fn conversation_title_is_bounded_without_splitting_graphemes() {
        assert_eq!(title_preview("Orchard work", 100), "Orchard work");
        let title = title_preview(&"界e\u{301}".repeat(40), 80);
        assert!(title.width() <= 40 && title.ends_with('…'));
    }

    #[test]
    fn grows_with_lines_wraps_unicode_and_caps_pastes() {
        assert_eq!(draft_rows(&["".into()], 100, 6), 1);
        assert_eq!(draft_rows(&["one".into(), "two".into()], 100, 6), 2);
        assert_eq!(draft_rows(&["界界界".into()], 4, 6), 2);
        assert_eq!(draft_rows(&["e\u{301}e\u{301}e\u{301}".into()], 2, 6), 2);
        assert_eq!(draft_rows(&["x".repeat(100_000)], 80, 6), 6);
    }
}

//! Content-sized primary-screen controls. Execution remains behind identified requests.
use super::*;

// Paint-only activity: no text mutation, history records or runtime timers.
use std::sync::OnceLock;
pub const TICK: Duration = Duration::from_millis(80);

pub fn motion() -> bool {
    static ENABLED: OnceLock<bool> = OnceLock::new();
    *ENABLED.get_or_init(|| {
        !matches!(palette().syntax_theme, SyntaxTheme::Plain)
            && !std::env::var("AMPLIFIER_TUI_REDUCED_MOTION")
                .is_ok_and(|s| matches!(s.to_ascii_lowercase().as_str(), "1" | "true" | "yes"))
    })
}

pub fn running(app: &App) -> bool {
    !app.disconnected
        && (!app.background.is_empty() || app.flow.busy)
        && app.approval.is_none()
        && app.questions.pending.is_empty()
}

pub fn repaint_after(app: &App) -> Option<Duration> {
    if app.disconnected {
        None // Observations are stale; never animate a lost runtime as live work.
    } else if running(app) && motion() {
        Some(TICK)
    } else if app.flow.busy {
        Some(Duration::from_secs(1)) // elapsed time still advances without motion
    } else {
        None
    }
}

pub fn line(text: &str, active: bool) -> Line<'static> {
    static START: OnceLock<Instant> = OnceLock::new();
    let phase = START.get_or_init(Instant::now).elapsed().as_millis() / TICK.as_millis();
    line_at(text, phase as usize, active && motion(), palette())
}

/// Apply motion at paint time, never cache animated styles in retained layouts.
/// Only an observed running tool is eligible; completed thinking is historical.
pub fn tool_line(mut row: Line<'static>, active: bool) -> Line<'static> {
    // Structured action rows own the fourth span as their state. Do not infer
    // liveness from a command/title containing the word "running" or flatten
    // cyan actions and red child errors back into a single style.
    if active
        && row.spans.first().is_some_and(|s| s.content == "▸ ")
        && row.spans.get(3).is_some_and(|s| s.content == "running")
    {
        row.spans.splice(3..4, line("running", true).spans);
    }
    row
}

fn line_at(text: &str, phase: usize, animate: bool, colours: &Palette) -> Line<'static> {
    // Only the named state sweeps. Measures retain stable muted colour and text.
    let (label, rest) = text.split_once(" · ").unwrap_or((text, ""));
    if !label.starts_with('●') && !label.starts_with('↑') && label != "running" {
        return Line::styled(
            text.to_owned(),
            Style::default().fg(if stopping(text) {
                colours.red
            } else {
                colours.muted
            }),
        );
    }
    let negative = label.ends_with(" Stopping");
    let accent = if negative { colours.red } else { colours.amber };
    let length: usize = label.chars().map(|c| c.width().unwrap_or(0)).sum();
    let head = (phase % (length + 12)) as isize - 6;
    let mut column = 0;
    let mut spans = Vec::new();
    for ch in label.chars() {
        let distance = (column as isize - head).unsigned_abs();
        let amount = if animate {
            4usize
                .saturating_sub(distance)
                .min(if negative { 2 } else { 4 })
        } else {
            0
        };
        let foreground = match (accent, colours.ink) {
            (Color::Rgb(r, g, b), Color::Rgb(x, y, z)) => {
                let blend = |a: u8, b: u8| {
                    ((usize::from(a) * (5 - amount) + usize::from(b) * amount) / 5) as u8
                };
                Color::Rgb(blend(r, x), blend(g, y), blend(b, z))
            }
            _ => accent,
        };
        spans.push(Span::styled(
            ch.to_string(),
            Style::default().fg(foreground),
        ));
        column += ch.width().unwrap_or(0);
    }
    if !rest.is_empty() {
        spans.push(Span::styled(
            format!(" · {rest}"),
            Style::default().fg(colours.muted),
        ));
    }
    Line::from(spans)
}

#[cfg(test)]
mod activity_tests {
    use super::*;

    #[test]
    fn live_tool_motion_preserves_semantic_spans_and_ignores_word_matches() {
        let row = Line::from(vec![
            Span::raw("▸ "),
            Span::styled(
                "Review running processes",
                Style::default()
                    .fg(palette().green)
                    .add_modifier(Modifier::BOLD),
            ),
            Span::raw(" · "),
            Span::styled("running", Style::default().fg(palette().amber)),
            Span::styled(" · 2 tool errors", Style::default().fg(palette().red)),
            Span::styled(" · $0.12", Style::default().fg(palette().muted)),
        ]);
        let painted = tool_line(row.clone(), true);
        assert_eq!(painted.to_string(), row.to_string());
        assert_eq!(painted.spans[1], row.spans[1]);
        assert_eq!(painted.spans.last(), row.spans.last());
        assert_eq!(painted.spans[painted.spans.len() - 2], row.spans[4]);
        assert_eq!(tool_line(row.clone(), false), row);
        let mut done = row;
        done.spans[3] = Span::raw("done");
        assert_eq!(tool_line(done.clone(), true), done);
        let ordinary = Line::raw("▸ running in plain historical prose");
        assert_eq!(tool_line(ordinary.clone(), true), ordinary);
    }

    #[test]
    fn stopping_uses_negative_accent_with_static_explanation_and_muted_measures() {
        for theme in ["dark", "light", "terminal"] {
            let p = Palette::named(theme, false);
            let source = "● Stopping · 1h 02m 03s · Turn $1.23";
            let row = line_at(source, 0, false, &p);
            assert_eq!(row.to_string(), source);
            assert_eq!(row.spans[0].style.fg, Some(p.red));
            assert_eq!(row.spans.last().unwrap().style.fg, Some(p.muted));
            for hint in [
                "Finishing current calls · Ctrl-C again to force stop",
                "Ctrl-C again: force stop",
                "Stopping now · partial effects may remain",
            ] {
                let a = line_at(hint, 0, true, &p);
                assert_eq!(a, line_at(hint, 8, true, &p));
                assert_eq!(a.style.fg, Some(p.red));
            }
        }
        assert!(stopping("Stopped; partial effects may remain"));
        assert!(!stopping("Ready"));
    }

    #[test]
    fn sweep_moves_without_changing_text_width_or_accounting_colours() {
        let source = "● Working · 2m 05s · 8 calls · Turn usage: 1.23M tokens";
        for theme in ["dark", "light"] {
            let p = Palette::named(theme, false);
            let a = line_at(source, 7, true, &p);
            let b = line_at(source, 11, true, &p);
            assert_ne!(a, b);
            assert_eq!(a.to_string(), source);
            assert_eq!(b.to_string(), source);
            assert_eq!(a.width(), b.width());
            assert_eq!(a.spans.last(), b.spans.last());
            assert_eq!(
                line_at(source, 7, false, &p),
                line_at(source, 11, false, &p)
            );
        }
        let p = Palette::named("dark", true);
        assert_eq!(line_at(source, 7, true, &p), line_at(source, 11, true, &p));
    }
}
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
    if status.starts_with("Completed") {
        return "Ready";
    }
    match status {
        "Ready · real modules mounted" => "Ready",
        _ => status,
    }
}

pub fn stopping(status: &str) -> bool {
    status.starts_with("Finishing current calls")
        || status.starts_with("Ctrl-C again")
        || status.starts_with("Stopping")
        || status.starts_with("Stopped")
        || status.starts_with("Interrupted")
        || status.starts_with("Cancelled")
}

/// Match TextArea's WordOrGlyph ranges (Unicode word boundaries, then graphemes).
/// Never lay out the whole of an enormous paste merely to size the live region.
pub fn draft_rows(lines: &[String], width: u16, limit: u16) -> u16 {
    let width = usize::from(width.max(1));
    let limit = limit.max(1);
    let cells = |s: &str, start: usize| {
        let mut col = start;
        for c in s.chars() {
            col += if c == '\t' {
                4 - col % 4
            } else {
                c.width().unwrap_or(0)
            };
            if col > width {
                break;
            }
        }
        col
    };
    let mut rows = 0u16;
    for line in lines {
        let mut col = 0;
        let mut occupied = false;
        for word in line.split_word_bounds() {
            if occupied && cells(word, col) > width {
                rows += 1;
                col = 0;
            }
            if rows >= limit {
                return limit;
            }
            let end = cells(word, col);
            if end <= width {
                col = end;
                occupied = true;
                continue;
            }
            // The editor emits all fallback fragments as independent rows, even
            // when the final fragment could share space with the following word.
            let mut fragment = false;
            for glyph in word.graphemes(true) {
                let end = cells(glyph, col);
                if fragment && end > width {
                    rows += 1;
                    col = 0;
                }
                if rows >= limit {
                    return limit;
                }
                col = cells(glyph, col);
                fragment = true;
            }
            rows += u16::from(fragment);
            col = 0;
            occupied = false;
            if rows >= limit {
                return limit;
            }
        }
        rows += u16::from(occupied || line.is_empty());
        if rows >= limit {
            return limit;
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
        choices.push((
            if app.interacting {
                "[Copy mode]"
            } else {
                "[Interact]"
            }
            .into(),
            Action::Interact,
        ));
        choices.push((
            "[Activity]".into(),
            Action::Inspect("activity_tree".into(), None),
        ));
        if matches!(app.ownership.as_str(), "blocked" | "yielded") {
            choices.push(("[Continue here]".into(), Action::ContinueHere));
            choices.push(("[Resume]".into(), Action::Conversations));
        }
        if app.ownership == "yielding" && app.flow.busy {
            choices.push(("[Force stop]".into(), Action::Stop));
        }
        if app.ready {
            choices.push((
                if app.flow.busy && app.nav.enabled && !app.connected {
                    "[ Queue ]"
                } else {
                    "[ Send ]"
                }
                .into(),
                Action::Send,
            ));
            if app.flow.busy {
                if !app.connected {
                    choices.push(("[Change task]".into(), Action::CorrectActive));
                }
                choices.push((
                    if app.flow.cancellation == "graceful" {
                        if width < 60 {
                            "[Force]"
                        } else {
                            "[Force stop]"
                        }
                    } else {
                        "[ Stop ]"
                    }
                    .into(),
                    Action::Stop,
                ));
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
        if height < 15 {
            // Small terminals retain the primary controls; all other actions
            // remain discoverable in Actions, not additional footer rows.
            choices.retain(|(_, action)| {
                matches!(
                    action,
                    Action::Menu
                        | Action::Send
                        | Action::ContinueHere
                        | Action::Stop
                        | Action::Inspect(_, _)
                )
            });
        }
        if height < 7 {
            // Make room for a narrow meter plus a pending decision. Activity is
            // still reachable through Actions; keep Send/Stop and editable input.
            choices.retain(|(_, action)| !matches!(action, Action::Inspect(_, _)));
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
        let hint = if app.disconnected {
            "Disconnected · copy draft before exit".into()
        } else if !app.startup_failure.is_empty() {
            "Startup failed · draft stays editable".into()
        } else if app.nav.switching.is_some() {
            "Opening conversation · input paused".into()
        } else if matches!(app.ownership.as_str(), "blocked" | "yielded") {
            "Read-only · draft stays editable".into()
        } else if !app.ownership.is_empty() && !app.ready {
            app.status.clone()
        } else if app.ready {
            format!(
                "Enter {} · Tab complete/actions",
                if app.flow.busy && app.nav.enabled && !app.connected {
                    "queue"
                } else {
                    "send"
                }
            )
        } else {
            "Starting · type now, send when ready".into()
        };
        let hint = if x + hint.chars().count() as u16 <= width {
            Some((x, y, hint))
        } else if width >= 80 && x + 11 <= width && app.ready {
            Some((
                x,
                y,
                if app.flow.busy && app.nav.enabled && !app.connected {
                    "Enter queue"
                } else {
                    "Enter send"
                }
                .into(),
            ))
        } else {
            None
        };
        let controls = y + 1;
        let limit = height.saturating_sub(controls + 4).clamp(1, 6);
        let edit_rows = draft_rows(app.draft.lines(), width, limit);
        Self {
            height: edit_rows + 4 + controls,
            edit_rows,
            buttons,
            hint,
        }
    }

    pub fn draw(&self, f: &mut Frame, app: &mut App, area: Rect) {
        let composer = Rect::new(area.x, area.y + 1, area.width, self.edit_rows + 2);
        f.render_widget(
            Block::default().style(Style::default().bg(palette().panel)),
            composer,
        );
        text(
            f,
            Rect::new(area.x, area.y, area.width, 1),
            format!(
                "Message · Mode: {}{}{}",
                app.policy,
                runtime_notice(&app.mode),
                app.controls.goal
            ),
            if app.ui.focus.is_none() {
                palette().green
            } else {
                palette().muted
            },
        );
        let title = title_preview(&app.title, area.width);
        let heading_width = format!(
            "Message · Mode: {}{}{}",
            app.policy,
            runtime_notice(&app.mode),
            app.controls.goal
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
                palette().muted,
            );
        }
        // No prompt or border beside any input row: terminal selection copies words.
        let edit = Rect::new(area.x, area.y + 2, area.width, self.edit_rows);
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
                palette().muted,
            );
        }
        text(
            f,
            Rect::new(area.x, area.y + self.height - 1, area.width, 1),
            if app.nav.switching.is_some() {
                "Opening conversation · input paused; draft retained".into()
            } else if app.flow.busy && app.status.starts_with("Working") {
                String::new() // The live tail owns the ordinary working indicator.
            } else {
                status_label(&app.status).to_owned()
            },
            if app.disconnected || stopping(&app.status) {
                palette().red
            } else {
                palette().muted
            },
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

    #[test]
    fn word_wrap_height_matches_the_actual_editors_visual_cursor() {
        for source in [
            "alpha beta gamma delta",
            "small extraordinary word",
            "one  two   three",
            "\talpha\tbeta",
            "first\n\nlast",
            "界面 e\u{301}lan 👩‍💻 words",
            "word     ",
            "punctuation/path/to/file.rs",
            "non\u{a0}breaking text",
        ] {
            for width in 2..40 {
                let mut draft = editor();
                draft.insert_str(source);
                let area = Rect::new(0, 0, width, 100);
                composer::render_fitted(&mut draft, area, &mut Buffer::empty(area));
                assert_eq!(
                    draft_rows(draft.lines(), width, 100) as usize,
                    draft.screen_cursor().row + 1,
                    "{source:?} at {width}"
                );
                assert_eq!(draft.lines().join("\n"), source);
            }
        }
    }
}

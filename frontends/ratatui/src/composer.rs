//! Local editing helpers; neither completion nor recall invokes execution.
use super::*;

/// The editor retains its old scroll origin when its viewport grows. If all
/// text fits, prime origin zero through its public renderer, then restore the
/// exact cursor/selection before the visible render. Never clone/reset the draft.
pub fn render_fitted(draft: &mut TextArea<'static>, area: Rect, buffer: &mut Buffer) {
    use ratatui::widgets::Widget;
    use ratatui_textarea::CursorMove;
    let cursor = draft.cursor();
    if area.height > 0
        && chrome::draft_rows(draft.lines(), area.width, area.height + 1) <= area.height
        && cursor.0 <= u16::MAX as usize
        && cursor.1 <= u16::MAX as usize
    {
        draft.move_cursor(CursorMove::Top);
        (&*draft).render(area, buffer);
        draft.move_cursor(CursorMove::Jump(cursor.0 as u16, cursor.1 as u16));
    }
    (&*draft).render(area, buffer);
}
use ratatui_textarea::CursorMove;

pub fn at_vertical_boundary(draft: &TextArea<'_>, up: bool) -> bool {
    // Ask the editor itself, including its current soft-wrap geometry. Probe a
    // clone so a history check cannot mutate the person's cursor or selection.
    let row = draft.screen_cursor().row;
    let mut probe = draft.clone();
    probe.cancel_selection();
    probe.move_cursor(if up { CursorMove::Up } else { CursorMove::Down });
    probe.screen_cursor().row == row
}

#[derive(Default)]
pub struct Recall {
    saved: Option<TextArea<'static>>,
    index: usize,
}

impl Recall {
    pub fn active(&self) -> bool {
        self.saved.is_some()
    }
    pub fn navigate(
        &mut self,
        draft: &mut TextArea<'static>,
        history: &[String],
        up: bool,
    ) -> bool {
        if history.is_empty() || (!up && self.saved.is_none()) {
            return false;
        }
        if self.saved.is_none() {
            self.saved = Some(draft.clone());
            self.index = history.len();
        }
        if up {
            self.index = self.index.saturating_sub(1);
        } else {
            self.index = (self.index + 1).min(history.len());
        }
        if self.index == history.len() {
            *draft = self.saved.take().unwrap();
        } else {
            draft.select_all();
            draft.insert_str(&history[self.index]);
            draft.move_cursor(if up {
                CursorMove::Top
            } else {
                CursorMove::Bottom
            });
            draft.move_cursor(CursorMove::End);
        }
        true
    }

    pub fn cancel(&mut self, draft: &mut TextArea<'static>) -> bool {
        if let Some(saved) = self.saved.take() {
            *draft = saved;
            true
        } else {
            false
        }
    }
}

pub fn token(draft: &TextArea<'_>) -> Option<(usize, usize, usize, String)> {
    let cursor = draft.cursor();
    let chars: Vec<_> = draft.lines()[cursor.0].chars().collect();
    let (mut start, mut quoted, mut escaped) = (0, false, false);
    let mut spans = Vec::new();
    for (i, c) in chars.iter().enumerate() {
        if escaped {
            escaped = false;
            continue;
        }
        if *c == '\\' && quoted {
            escaped = true;
        } else if *c == '"' {
            quoted = !quoted;
        } else if c.is_whitespace() && !quoted {
            spans.push((start, i));
            start = i + 1;
        }
    }
    spans.push((start, chars.len()));
    let (start, end) = spans
        .into_iter()
        .find(|(a, b)| *a <= cursor.1 && cursor.1 <= *b)?;
    let raw: String = chars[start..cursor.1].iter().collect();
    let query: String = if raw.starts_with('"') {
        serde_json::from_str(&raw)
            .or_else(|_| serde_json::from_str(&format!("{raw}\"")))
            .ok()?
    } else {
        raw
    };
    if cursor.0 > u16::MAX as usize || end > u16::MAX as usize {
        return None;
    }
    if query.starts_with('@') || query.starts_with('/') || query.starts_with("./") {
        Some((cursor.0, start, end, query))
    } else {
        None
    }
}

pub fn replace(draft: &mut TextArea<'static>, row: usize, start: usize, end: usize, value: &str) {
    let (Ok(row), Ok(start), Ok(end)) =
        (u16::try_from(row), u16::try_from(start), u16::try_from(end))
    else {
        return;
    };
    draft.move_cursor(CursorMove::Jump(row, start));
    draft.start_selection();
    draft.move_cursor(CursorMove::Jump(row, end));
    draft.insert_str(value);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fitting_editor_growth_restores_top_without_changing_intent() {
        use ratatui::widgets::Widget;
        use ratatui_textarea::CursorMove;
        let mut draft = editor();
        draft.insert_str("first\nsecond\nthird");
        draft.move_cursor(CursorMove::Jump(2, 5));
        draft.start_selection();
        draft.move_cursor(CursorMove::Back);
        let cursor = draft.cursor();
        let selection = draft.selection_range();
        let small = Rect::new(0, 0, 30, 1);
        (&draft).render(small, &mut Buffer::empty(small));
        let grown = Rect::new(0, 0, 30, 3);
        let mut buffer = Buffer::empty(grown);
        render_fitted(&mut draft, grown, &mut buffer);
        let rows = buffer
            .content
            .chunks(30)
            .map(|row| {
                row.iter()
                    .map(|cell| cell.symbol())
                    .collect::<String>()
                    .trim_end()
                    .to_owned()
            })
            .collect::<Vec<_>>();
        assert_eq!(rows, ["first", "second", "third"]);
        assert_eq!(draft.cursor(), cursor);
        assert_eq!(draft.selection_range(), selection);
        assert!(draft.undo());
        assert!(draft.is_empty());
    }
    #[test]
    fn history_boundaries_follow_wrapped_visual_rows_without_moving_selection() {
        let mut draft = editor();
        draft.insert_str("abcdefghijklmnop");
        let area = Rect::new(0, 0, 6, 4);
        let mut buffer = Buffer::empty(area);
        (&draft).render(area, &mut buffer);
        assert!(at_vertical_boundary(&draft, false));
        assert!(!at_vertical_boundary(&draft, true));
        draft.move_cursor(CursorMove::Up);
        draft.start_selection();
        draft.move_cursor(CursorMove::Back);
        let before = (draft.cursor(), draft.selection_range());
        assert!(!at_vertical_boundary(&draft, false));
        assert!(!at_vertical_boundary(&draft, true));
        assert_eq!((draft.cursor(), draft.selection_range()), before);
        draft.cancel_selection();
        draft.move_cursor(CursorMove::Jump(0, 0));
        assert!(at_vertical_boundary(&draft, true));
    }
    #[test]
    fn delayed_directory_history_does_not_retarget_active_recall() {
        let mut ui = Interaction {
            history: vec!["current".into()],
            ..Default::default()
        };
        let mut draft = editor();
        draft.insert_str("unsent");
        ui.recall.navigate(&mut draft, &ui.history, true);
        ui.prior_history = Some(vec!["previous session".into()]);
        ui.merge_history();
        assert_eq!(ui.history, vec!["current"]);
        ui.recall.navigate(&mut draft, &ui.history, false);
        ui.merge_history();
        assert_eq!(draft.lines(), &["unsent"]);
        assert_eq!(ui.history, vec!["previous session", "current"]);
    }
    #[test]
    fn history_round_trip_restores_cursor_and_original_draft() {
        let mut draft = TextArea::from(["original", "second"]);
        draft.move_cursor(CursorMove::Jump(0, 3));
        let mut recall = Recall::default();
        let history = vec!["oldest".into(), "newest".into()];
        assert!(recall.navigate(&mut draft, &history, true));
        assert_eq!(draft.lines(), ["newest"]);
        recall.navigate(&mut draft, &history, true);
        assert_eq!(draft.lines(), ["oldest"]);
        recall.navigate(&mut draft, &history, false);
        recall.navigate(&mut draft, &history, false);
        assert_eq!(draft.lines(), ["original", "second"]);
        assert_eq!(draft.cursor(), (0, 3));
    }
    #[test]
    fn completion_preserves_unicode_neighbors_and_suffix() {
        let mut draft = TextArea::from(["界 @skxx trailing"]);
        draft.move_cursor(CursorMove::Jump(0, 5));
        let (row, start, end, query) = token(&draft).unwrap();
        assert_eq!(query, "@sk");
        replace(&mut draft, row, start, end, "@skill");
        assert_eq!(draft.lines(), ["界 @skill trailing"]);
    }
}

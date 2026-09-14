//! Local editing helpers; neither completion nor recall invokes execution.
use super::*;
use ratatui_textarea::CursorMove;

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

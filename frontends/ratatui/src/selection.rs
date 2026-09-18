//! Explicit visible-cell snapshots: later streaming cannot change selected text.
use super::*;
use unicode_segmentation::UnicodeSegmentation;
use unicode_width::UnicodeWidthStr;

#[derive(Default)]
pub struct Selection {
    pub visible: Vec<String>,
    pub snapshot: Vec<String>,
    pub area: Rect,
    pub start: Option<(usize, usize)>,
    pub end: (usize, usize),
    pub offset: usize,
    pub pointer: Option<(u16, u16)>,
    pub dragging: bool,
}

impl Selection {
    pub fn begin(&mut self, x: u16, y: u16, area: Rect) {
        self.area = area;
        self.snapshot = self.visible.clone();
        self.start = Some((
            y.saturating_sub(area.y) as usize + self.offset,
            x.saturating_sub(area.x) as usize,
        ));
        self.end = self.start.unwrap();
        self.dragging = true;
    }
    pub fn extend(&mut self, x: u16, y: u16) {
        self.pointer = Some((x, y));
        self.end = (
            y.saturating_sub(self.area.y)
                .min(self.area.height.saturating_sub(1)) as usize
                + self.offset,
            x.saturating_sub(self.area.x).min(self.area.width) as usize,
        );
    }
    pub fn scroll(&mut self, amount: isize) {
        self.offset = self.offset.saturating_add_signed(-amount).min(
            self.snapshot
                .len()
                .saturating_sub(self.area.height as usize),
        );
        if self.dragging
            && let Some((x, y)) = self.pointer
        {
            self.extend(x, y);
        }
    }
    pub fn bounds(&self, row: usize) -> Option<(usize, usize)> {
        let start = self.start?;
        let (a, b) = if start <= self.end {
            (start, self.end)
        } else {
            (self.end, start)
        };
        if row < a.0 || row > b.0 {
            return None;
        }
        Some((
            if row == a.0 { a.1 } else { 0 },
            if row == b.0 {
                b.1
            } else {
                self.area.width as usize
            },
        ))
    }
    pub fn text(&self) -> String {
        self.snapshot
            .iter()
            .enumerate()
            .filter_map(|(i, line)| {
                let (a, b) = self.bounds(i)?;
                let mut x = 0;
                let text: String = line
                    .graphemes(true)
                    .filter(|g| {
                        let left = x;
                        x += g.width();
                        left < b && x > a
                    })
                    .collect();
                Some(text.trim_end().to_string())
            })
            .collect::<Vec<_>>()
            .join("\n")
    }
    pub fn draw(&self, f: &mut Frame) {
        if self.start.is_none() {
            return;
        }
        f.render_widget(ratatui::widgets::Clear, self.area);
        f.render_widget(
            Block::default().style(Style::default().bg(palette().bg)),
            self.area,
        );
        for (i, line) in self
            .snapshot
            .iter()
            .enumerate()
            .skip(self.offset)
            .take(self.area.height as usize)
        {
            let bounds = self.bounds(i);
            let mut x = 0;
            let spans: Vec<_> = line
                .graphemes(true)
                .map(|g| {
                    let selected = bounds.is_some_and(|(a, b)| x < b && x + g.width() > a);
                    x += g.width();
                    Span::styled(
                        g.to_string(),
                        Style::default()
                            .fg(if selected {
                                palette().bg
                            } else {
                                palette().ink
                            })
                            .bg(if selected {
                                palette().green
                            } else {
                                palette().bg
                            }),
                    )
                })
                .collect();
            f.render_widget(
                Paragraph::new(Line::from(spans)),
                Rect::new(
                    self.area.x,
                    self.area.y + (i - self.offset) as u16,
                    self.area.width,
                    1,
                ),
            );
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn wheel_extends_selection_across_pages_and_frozen_source() {
        let mut s = Selection {
            visible: vec!["first".into(), "second".into()],
            ..Default::default()
        };
        s.begin(1, 0, Rect::new(0, 0, 20, 2));
        s.snapshot.extend(["third".into(), "fourth".into()]);
        s.extend(4, 1);
        s.scroll(-2);
        assert_eq!(s.offset, 2);
        assert_eq!(s.text(), "irst\nsecond\nthird\nfour");
        s.visible.clear();
        s.scroll(1);
        assert_eq!(s.text(), "irst\nsecond\nthir");
    }
    #[test]
    fn unicode_and_reverse_selection_are_stable() {
        let mut s = Selection {
            visible: vec!["a界é!".into(), "next".into()],
            ..Default::default()
        };
        s.begin(1, 0, Rect::new(0, 0, 20, 2));
        s.extend(4, 0);
        assert_eq!(s.text(), "界é");
        s.visible[0] = "changed".into();
        assert_eq!(s.text(), "界é");
        s.start = Some((1, 2));
        s.end = (0, 1);
        assert_eq!(s.text(), "界é!\nne");
    }
}

//! Lazy item layout plus an exclusive bottom-row anchor. None means follow tail.
//! Source items are never replaced by rendered fragments; streaming invalidates
//! only the changed item. A pinned reader keeps the same item/visual row.
use super::*;

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Anchor {
    pub item: usize,
    pub row: usize,
}

pub struct Layout {
    width: usize,
    selected: bool,
    lines: Vec<Line<'static>>,
}

impl App {
    pub fn begin_selection(&mut self, x: u16, y: u16) {
        let Some(mut end) = self.anchors[self.view].or_else(|| self.tail()) else {
            return;
        };
        end.row = end.row.min(self.layout(end.item).len()).max(1);
        let mut anchor = end;
        let mut rows = Vec::new();
        let mut bytes = 0;
        loop {
            let line = self.layout(anchor.item)[anchor.row.saturating_sub(1)].to_string();
            bytes += line.len();
            if bytes > 1024 * 1024 || rows.len() >= 10000 {
                break;
            }
            rows.push(line);
            let Some(previous) = self.previous(anchor) else {
                break;
            };
            anchor = previous;
        }
        rows.reverse();
        let offset = rows.len().saturating_sub(self.body.height as usize);
        anchor = end;
        while let Some(next) = self.following(anchor) {
            let line = self.layout(next.item)[next.row - 1].to_string();
            bytes += line.len();
            if bytes > 2 * 1024 * 1024 || rows.len() >= 20000 {
                break;
            }
            rows.push(line);
            anchor = next;
        }
        self.selection.offset = offset;
        self.selection.begin(x, y, self.body);
        self.selection.snapshot = rows;
        self.selection.pointer = Some((x, y));
        self.status = "Select with drag + wheel/edge scroll · snapshot capped at 20k lines/2 MiB · Native scrollback for terminal/tmux".into();
    }
    pub fn reveal_item(&mut self, item: usize) {
        self.view = 0;
        self.expanded = false;
        self.selected = item;
        let mut anchor = Anchor { item, row: 1 };
        for _ in 1..self.body.height {
            let Some(next) = self.following(anchor) else {
                break;
            };
            anchor = next;
        }
        self.anchors[0] = Some(anchor);
    }
    fn layout(&mut self, index: usize) -> &Vec<Line<'static>> {
        let width = self.body.width as usize;
        let selected = index == self.selected;
        if self.layouts[index]
            .as_ref()
            .is_none_or(|l| l.width != width || l.selected != selected)
        {
            let item = &self.items[index];
            let lines = if item.kind == "assistant" {
                let mut lines = vec![Line::styled("amplifier", Style::default().fg(GREEN))];
                lines.extend(markdown::render(&item.text, width));
                lines.push(Line::default());
                lines
            } else {
                item_lines(item, width, selected)
                    .into_iter()
                    .map(|(s, c)| Line::styled(safe(&s), Style::default().fg(c)))
                    .collect()
            };
            self.layouts[index] = Some(Layout {
                width,
                selected,
                lines,
            });
        }
        &self.layouts[index].as_ref().unwrap().lines
    }

    fn preceding_item(&self, end: usize) -> Option<usize> {
        if self.view == 0 {
            return end.checked_sub(1);
        }
        let at = self.tool_indices.partition_point(|&i| i < end);
        at.checked_sub(1).map(|i| self.tool_indices[i])
    }

    fn following_item(&self, start: usize) -> Option<usize> {
        if self.view == 0 {
            return (start < self.items.len()).then_some(start);
        }
        self.tool_indices
            .get(self.tool_indices.partition_point(|&i| i < start))
            .copied()
    }

    pub fn tail(&mut self) -> Option<Anchor> {
        let item = self.preceding_item(self.items.len())?;
        Some(Anchor {
            item,
            row: self.layout(item).len(),
        })
    }

    fn previous(&mut self, anchor: Anchor) -> Option<Anchor> {
        if anchor.row > 1 {
            return Some(Anchor {
                row: anchor.row - 1,
                ..anchor
            });
        }
        let item = self.preceding_item(anchor.item)?;
        Some(Anchor {
            item,
            row: self.layout(item).len(),
        })
    }

    fn following(&mut self, anchor: Anchor) -> Option<Anchor> {
        if anchor.row < self.layout(anchor.item).len() {
            return Some(Anchor {
                row: anchor.row + 1,
                ..anchor
            });
        }
        let item = self.following_item(anchor.item + 1)?;
        Some(Anchor { item, row: 1 })
    }

    pub fn scroll_lines(&mut self, amount: isize) {
        let Some(mut anchor) = self.anchors[self.view].or_else(|| self.tail()) else {
            return;
        };
        anchor.row = anchor.row.min(self.layout(anchor.item).len()).max(1);
        for _ in 0..amount.unsigned_abs() {
            let next = if amount > 0 {
                self.previous(anchor)
            } else {
                self.following(anchor)
            };
            let Some(next) = next else {
                break;
            };
            anchor = next;
        }
        // The earliest viewport is a full first page, not a single first row
        // floating above empty space. Compute only that page, never all history.
        if amount > 0
            && let Some(item) = self.following_item(0)
        {
            let mut first_page = Anchor { item, row: 1 };
            for _ in 1..self.body.height {
                let Some(next) = self.following(first_page) else {
                    break;
                };
                first_page = next;
            }
            if (anchor.item, anchor.row) < (first_page.item, first_page.row) {
                anchor = first_page;
            }
        }
        self.anchors[self.view] = if Some(anchor) == self.tail() {
            None
        } else {
            Some(anchor)
        };
    }

    pub fn transcript_rows(&mut self) -> Vec<(usize, Line<'static>)> {
        let Some(mut anchor) = self.anchors[self.view].or_else(|| self.tail()) else {
            return vec![];
        };
        anchor.row = anchor.row.min(self.layout(anchor.item).len()).max(1);
        let mut rows = Vec::new();
        for _ in 0..self.body.height {
            if let Some(line) = self.layout(anchor.item).get(anchor.row - 1) {
                rows.push((anchor.item, line.clone()));
            }
            let Some(previous) = self.previous(anchor) else {
                break;
            };
            anchor = previous;
        }
        rows.reverse();
        rows
    }
}

//! Width-aware tables. Narrow terminals retain column labels instead of clipping cells.
use super::*;
use pulldown_cmark::Alignment;

pub struct Table {
    pub alignments: Vec<Alignment>,
    pub rows: Vec<Vec<Line<'static>>>,
}

impl Table {
    pub fn render(self, width: usize) -> Vec<Line<'static>> {
        let n = self.alignments.len();
        if n == 0 || self.rows.is_empty() {
            return vec![];
        }
        if width < n.saturating_mul(8).saturating_add(1) {
            let mut lines = vec![Line::styled(
                "Table · stacked for this width",
                Style::default().fg(palette().muted),
            )];
            for (i, row) in self.rows.iter().enumerate().skip(1) {
                lines.push(Line::styled(
                    format!("Row {i}"),
                    Style::default().fg(palette().green),
                ));
                for (j, cell) in row.iter().enumerate() {
                    let header = self.rows[0]
                        .get(j)
                        .map(ToString::to_string)
                        .unwrap_or_default();
                    lines.push(Line::styled(
                        format!(
                            "{}:",
                            if header.is_empty() {
                                format!("Column {}", j + 1)
                            } else {
                                header
                            }
                        ),
                        Style::default()
                            .fg(palette().green)
                            .add_modifier(Modifier::BOLD),
                    ));
                    lines.push(cell.clone());
                }
            }
            if self.rows.len() == 1 {
                lines.extend(self.rows[0].clone());
            }
            return markdown::reflow(lines, width);
        }
        let mut widths: Vec<usize> = (0..n)
            .map(|j| {
                self.rows
                    .iter()
                    .filter_map(|r| r.get(j))
                    .map(Line::width)
                    .max()
                    .unwrap_or(1)
                    .max(1)
                    .min(width)
            })
            .collect();
        let budget = width.saturating_sub(3 * n + 1);
        while widths.iter().sum::<usize>() > budget {
            let j = (0..n).max_by_key(|&j| widths[j]).unwrap();
            widths[j] -= 1;
        }
        let edge = Style::default().fg(palette().muted);
        let border = |left: &str, join: &str, right: &str| {
            Line::styled(
                format!(
                    "{left}{}{right}",
                    widths
                        .iter()
                        .map(|w| "─".repeat(w + 2))
                        .collect::<Vec<_>>()
                        .join(join)
                ),
                edge,
            )
        };
        let mut lines = vec![border("┌", "┬", "┐")];
        for (i, row) in self.rows.iter().enumerate() {
            let cells: Vec<_> = (0..n)
                .map(|j| markdown::reflow(vec![row.get(j).cloned().unwrap_or_default()], widths[j]))
                .collect();
            let height = cells.iter().map(Vec::len).max().unwrap_or(1);
            for k in 0..height {
                let mut spans = vec![Span::styled("│ ", edge)];
                for j in 0..n {
                    let cell = cells[j].get(k).cloned().unwrap_or_default();
                    let gap = widths[j].saturating_sub(cell.width());
                    let left = match self.alignments[j] {
                        Alignment::Right => gap,
                        Alignment::Center => gap / 2,
                        _ => 0,
                    };
                    spans.push(Span::raw(" ".repeat(left)));
                    spans.extend(cell.spans);
                    spans.push(Span::raw(" ".repeat(gap - left)));
                    spans.push(Span::styled(if j + 1 == n { " │" } else { " │ " }, edge));
                }
                lines.push(Line::from(spans));
            }
            if i == 0 {
                lines.push(border("├", "┼", "┤"));
            }
        }
        lines.push(border("└", "┴", "┘"));
        lines
    }
}

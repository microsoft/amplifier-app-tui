//! Normal-screen output ownership. The runtime and retained source remain independent.
//! Committed rows are never repainted. Only a small live region is cursor-addressed.
use super::*;
use crossterm::{cursor, queue, style::ResetColor, terminal as tty};
use ratatui::{TerminalOptions, Viewport, backend::CrosstermBackend, widgets::Widget};
use std::collections::{BTreeSet, VecDeque};
use std::hash::{Hash, Hasher};
const MAX_REPLAY_ITEMS: usize = 1000;

struct Pending {
    item: Item,
    offset: usize,
    heading: bool,
    complete: bool,
}

#[derive(Default)]
pub struct Journal {
    pending: HashMap<String, Pending>,
    order: Vec<String>,
    dirty: BTreeSet<usize>,
    indices: HashMap<String, usize>,
    emitted: HashMap<String, u64>,
    rows: VecDeque<Line<'static>>,
    banner: bool,
    active: BTreeSet<usize>,
    pub skip_replay_item: bool,
}

fn fingerprint(item: &Item) -> u64 {
    let mut h = std::collections::hash_map::DefaultHasher::new();
    (&item.kind, &item.text, &item.status).hash(&mut h);
    h.finish()
}

/// Only completed top-level Markdown blocks are immutable while streaming.
/// Blank lines inside fenced code, lists or tables are not independent blocks.
fn stable_end(source: &str) -> usize {
    use pulldown_cmark::{Options, Parser};
    let mut depth = 0usize;
    let mut end = 0;
    for (event, range) in Parser::new_ext(source, Options::all()).into_offset_iter() {
        match event {
            pulldown_cmark::Event::Start(_) => depth += 1,
            pulldown_cmark::Event::End(_) => {
                depth = depth.saturating_sub(1);
                if depth == 0 && source[range.end..].starts_with('\n') {
                    end = range.end;
                }
            }
            _ => (),
        }
    }
    end
}

impl Journal {
    pub fn begin_replay(&mut self, count: usize) -> usize {
        let skip = count.saturating_sub(MAX_REPLAY_ITEMS);
        if skip > 0 {
            self.rows.push_back(Line::styled(
                format!("Showing latest {MAX_REPLAY_ITEMS} of {count} historical items. Transcript / Export retains full source."),
                Style::default().fg(AMBER),
            ));
        }
        skip
    }
    pub fn banner(&mut self, title: &str, mode: &str) {
        if !self.banner {
            self.rows.push_back(Line::styled(
                format!(
                    "amplifier · {}{}",
                    safe(title),
                    chrome::runtime_notice(mode)
                ),
                Style::default().fg(GREEN),
            ));
            self.rows.push_back(Line::default());
            self.banner = true;
        }
    }

    pub fn reset(&mut self) {
        // Switching is idle-only. Preserve any queued output from the prior identity.
        self.finish();
        let mut rows = std::mem::take(&mut self.rows);
        while !self.dirty.is_empty() {
            self.prepare(80);
            rows.append(&mut self.rows);
        }
        self.rows = rows;
        self.pending.clear();
        self.order.clear();
        self.dirty.clear();
        self.indices.clear();
        self.emitted.clear();
        self.active.clear();
        self.banner = false;
    }

    pub fn observe(&mut self, item: &Item, complete: bool) {
        if self.skip_replay_item {
            return;
        }
        let signature = fingerprint(item);
        if self.emitted.get(&item.id) == Some(&signature) {
            return;
        }
        let index = *self.indices.entry(item.id.clone()).or_insert_with(|| {
            self.order.push(item.id.clone());
            self.order.len() - 1
        });
        let entry = self
            .pending
            .entry(item.id.clone())
            .or_insert_with(|| Pending {
                item: item.clone(),
                offset: 0,
                heading: false,
                complete,
            });
        if !item.text.starts_with(&entry.item.text[..entry.offset]) {
            // A genuine source revision cannot rewrite terminal history. Label it.
            self.rows.push_back(Line::styled(
                "Updated source follows",
                Style::default().fg(AMBER),
            ));
            entry.offset = 0;
            entry.heading = false;
        }
        entry.item = item.clone();
        entry.complete =
            complete && !matches!(item.status.as_str(), "running" | "waiting" | "pending");
        if entry.complete {
            self.active.remove(&index);
        } else {
            self.active.insert(index);
        }
        self.dirty.insert(index);
    }

    pub fn finish(&mut self) {
        for entry in self.pending.values_mut() {
            entry.complete = true;
        }
        self.dirty
            .extend(self.pending.keys().map(|id| self.indices[id]));
        self.active.clear();
    }

    pub fn prepare(&mut self, width: usize) {
        // Bounded dirty-item work, not a full-history walk on every key/token.
        for _ in 0..32 {
            if self.rows.len() >= 128 {
                break;
            }
            let Some(index) = self.dirty.pop_first() else {
                break;
            };
            let id = &self.order[index];
            let Some(entry) = self.pending.get_mut(id) else {
                continue;
            };
            let item = &entry.item;
            if item.kind == "assistant" {
                let rest = &item.text[entry.offset..];
                let end = if entry.complete {
                    rest.len()
                } else {
                    stable_end(rest)
                };
                if end == 0 && !entry.complete {
                    continue;
                }
                if !item.text.is_empty() && !entry.heading {
                    self.rows
                        .push_back(Line::styled("amplifier", Style::default().fg(GREEN)));
                    entry.heading = true;
                }
                self.rows.extend(markdown::render(&rest[..end], width));
                entry.offset += end;
                if !entry.complete {
                    continue;
                }
            } else if entry.complete {
                self.rows.extend(
                    item_lines(item, width, false)
                        .into_iter()
                        .map(|(s, c)| Line::styled(safe(&s), Style::default().fg(c))),
                );
            } else {
                continue;
            }
            self.emitted.insert(id.clone(), fingerprint(item));
            self.pending.remove(id);
        }
    }

    fn live(&self, width: usize) -> Vec<Line<'static>> {
        let mut lines = Vec::new();
        // Active items only. Completed history is owned by the terminal.
        for index in &self.active {
            let Some(p) = self.pending.get(&self.order[*index]) else {
                continue;
            };
            if p.complete {
                continue;
            }
            if p.item.kind == "assistant" {
                if !p.heading {
                    lines.push(Line::styled("amplifier", Style::default().fg(GREEN)));
                }
                lines.extend(markdown::render_live(&p.item.text[p.offset..], width));
            } else {
                lines.extend(
                    item_lines(&p.item, width, false)
                        .into_iter()
                        .map(|(s, c)| Line::styled(safe(&s), Style::default().fg(c))),
                );
            }
        }
        while lines
            .last()
            .is_some_and(|l| l.to_string().trim().is_empty())
        {
            lines.pop();
        }
        lines
    }

    pub fn has_work(&self) -> bool {
        !self.rows.is_empty() || !self.dirty.is_empty()
    }
}

type Tty = Terminal<CrosstermBackend<io::Stdout>>;
static ALTERNATE_OWNED: AtomicBool = AtomicBool::new(false);

fn cursor_row_or_fresh_page(height: u16) -> io::Result<u16> {
    match bounded_cursor_row()? {
        Some(row) => Ok(row),
        None => {
            // A silent terminal gets a fresh page by scrolling, NEVER CSI 3 J.
            for _ in 0..height {
                write!(io::stdout(), "\r\n")?;
            }
            execute!(io::stdout(), cursor::MoveTo(0, 0))?;
            Ok(0)
        }
    }
}

// Called only on the UI/input thread, outside Crossterm polling. All bytes go
// back through its parser (including partial Unicode/paste and internal CPRs).
#[cfg(unix)]
fn bounded_cursor_row() -> io::Result<Option<u16>> {
    use std::fs::OpenOptions;
    use std::io::Read;
    use std::os::fd::AsRawFd;
    use std::os::unix::fs::OpenOptionsExt;
    static SILENT: AtomicBool = AtomicBool::new(false);
    if SILENT.load(Ordering::Relaxed) {
        return Ok(None);
    }
    let mut input = OpenOptions::new()
        .read(true)
        .custom_flags(libc::O_NONBLOCK | libc::O_NOCTTY)
        .open("/dev/tty")?;
    write!(io::stdout(), "\x1b[6n")?;
    io::stdout().flush()?;
    let deadline = Instant::now() + Duration::from_millis(100);
    let mut bytes = Vec::new();
    let result = (|| -> io::Result<Option<u16>> {
        loop {
            if let Some(row) = reported_cursor_row(&bytes) {
                return Ok(Some(row));
            }
            if Instant::now() >= deadline || bytes.len() >= 65536 {
                return Ok(None);
            }
            let mut fd = libc::pollfd {
                fd: input.as_raw_fd(),
                events: libc::POLLIN,
                revents: 0,
            };
            let timeout = deadline
                .saturating_duration_since(Instant::now())
                .as_millis()
                .max(1) as i32;
            // SAFETY: fd points to one live pollfd for this call; input owns the descriptor.
            let ready = unsafe { libc::poll(&mut fd, 1, timeout) };
            if ready < 0 {
                let error = io::Error::last_os_error();
                if error.kind() == io::ErrorKind::Interrupted {
                    continue;
                }
                return Err(error);
            }
            if ready == 0 {
                return Ok(None);
            }
            let mut chunk = [0; 4096];
            match input.read(&mut chunk) {
                Ok(0) => return Ok(None),
                Ok(n) => bytes.extend_from_slice(&chunk[..n]),
                Err(error)
                    if matches!(
                        error.kind(),
                        io::ErrorKind::WouldBlock | io::ErrorKind::Interrupted
                    ) =>
                {
                    continue;
                }
                Err(error) => return Err(error),
            }
        }
    })();
    event::buffer_input(&bytes)?;
    if matches!(result, Ok(None)) {
        // Do not mistake a late response for a later query's anchor.
        SILENT.store(true, Ordering::Relaxed);
    }
    result
}

#[cfg(not(unix))]
fn bounded_cursor_row() -> io::Result<Option<u16>> {
    cursor::position().map(|(_, row)| Some(row))
}

fn reported_cursor_row(bytes: &[u8]) -> Option<u16> {
    let mut paste = false;
    for at in 0..bytes.len() {
        let suffix = &bytes[at..];
        if suffix.starts_with(b"\x1b[200~") {
            paste = true;
        }
        if suffix.starts_with(b"\x1b[201~") {
            paste = false;
        }
        if paste || !suffix.starts_with(b"\x1b[") {
            continue;
        }
        let end = suffix[2..]
            .iter()
            .position(|c| !c.is_ascii_digit() && *c != b';')?
            + 2;
        if suffix[end] != b'R' {
            continue;
        }
        let text = std::str::from_utf8(&suffix[2..end]).ok()?;
        let Some((row, col)) = text.split_once(';') else {
            continue;
        };
        if let (Ok(row), Ok(col)) = (row.parse::<u16>(), col.parse::<u16>())
            && row > 0
            && col > 0
        {
            return Some(row - 1);
        }
    }
    None
}

pub struct Screen {
    terminal: Tty,
    area: Rect,
    size: (u16, u16),
    alternate: bool,
    primary_size: (u16, u16),
}

impl Screen {
    pub fn new() -> io::Result<Self> {
        tty::enable_raw_mode()?;
        // Install cleanup before any fallible terminal initialization.
        let old = std::panic::take_hook();
        std::panic::set_hook(Box::new(move |info| {
            restore();
            old(info);
        }));
        let result = (|| {
            execute!(io::stdout(), EnableBracketedPaste, DisableMouseCapture)?;
            let size = tty::size()?;
            // Preserve the whole preceding screen, including rows below the shell
            // cursor. A fresh page needs no cursor query or startup CPR timeout.
            execute!(
                io::stdout(),
                ResetColor,
                cursor::MoveTo(0, size.1.saturating_sub(1))
            )?;
            for _ in 0..size.1 {
                write!(io::stdout(), "\r\n")?;
            }
            execute!(io::stdout(), cursor::MoveTo(0, 0))?;
            let area = Rect::new(0, 0, size.0, 1);
            let terminal = Terminal::with_options(
                CrosstermBackend::new(io::stdout()),
                TerminalOptions {
                    viewport: Viewport::Fixed(area),
                },
            )?;
            Ok(Self {
                terminal,
                area,
                size,
                alternate: false,
                primary_size: size,
            })
        })();
        if result.is_err() {
            restore();
        }
        result
    }

    fn clear_live(&mut self) -> io::Result<()> {
        // tmux can archive a whole screen when ED starts at row zero. Erase
        // individual owned lines so a provisional full-height frame isn't history.
        let mut out = io::stdout();
        queue!(out, ResetColor)?;
        for y in self.area.y..self.size.1 {
            queue!(
                out,
                cursor::MoveTo(0, y),
                tty::Clear(tty::ClearType::CurrentLine)
            )?;
        }
        execute!(out, cursor::MoveTo(0, self.area.y))
    }

    fn resize(&mut self) -> io::Result<()> {
        let size = tty::size()?;
        if size != self.size {
            if !self.alternate {
                // Cursor is parked at the live region's origin after every frame.
                // Ask the terminal where resize/reflow moved it; never clear history.
                let y = cursor_row_or_fresh_page(size.1)?;
                // tmux can pull history onto a growing screen without moving
                // the reported cursor. Never clear those newly exposed rows.
                // This guard applies only to growth with an unmoved cursor.
                // Applying the old origin as a floor on shrink (or overriding
                // a genuinely moved cursor) scrolls stale chrome into history.
                let floor = if size.1 > self.size.1
                    && self.area.bottom() >= self.size.1
                    && y <= self.area.y
                {
                    self.area.y + size.1.saturating_sub(self.size.1)
                } else {
                    0
                };
                self.area.y = y.max(floor).min(size.1.saturating_sub(1));
            }
            self.size = size;
        }
        Ok(())
    }

    pub fn paint(&mut self, app: &mut App) -> io::Result<()> {
        self.resize()?;
        let inspect = app.view != 0
            || app.expanded
            || app.ui.menu.is_some()
            || app.flow.prompt.is_some()
            || app.anchors[0].is_some()
            || app.selection.start.is_some();
        if inspect && !self.alternate {
            self.primary_size = self.size;
            ALTERNATE_OWNED.store(true, Ordering::SeqCst);
            execute!(io::stdout(), tty::EnterAlternateScreen, EnableMouseCapture)?;
            self.alternate = true;
            self.terminal = Terminal::new(CrosstermBackend::new(io::stdout()))?;
            self.terminal.clear()?;
        } else if !inspect && self.alternate {
            self.leave_inspection()?;
        }
        if self.alternate {
            self.terminal.draw(|f| draw(f, app))?;
            return Ok(());
        }
        let width = self.size.0.max(1);
        app.native.prepare(width as usize);
        execute!(io::stdout(), tty::BeginSynchronizedUpdate)?;
        let result = self.paint_inline(app, width);
        let end = execute!(io::stdout(), tty::EndSynchronizedUpdate);
        result.and(end)
    }

    fn append(&mut self, rows: impl Iterator<Item = Line<'static>>) -> io::Result<()> {
        self.clear_live()?;
        let width = self.size.0.max(1);
        for line in rows {
            // Reflow queued rows after a resize; never re-emit committed rows.
            for line in markdown::reflow(vec![line], width as usize) {
                let rect = Rect::new(0, self.area.y, self.size.0, 1);
                let mut buffer = Buffer::empty(rect);
                Paragraph::new(line).render(Rect::new(0, rect.y, width, 1), &mut buffer);
                let empty = Buffer::empty(rect);
                self.terminal
                    .backend_mut()
                    .draw(empty.diff(&buffer).into_iter())?;
                execute!(io::stdout(), ResetColor, cursor::MoveTo(0, rect.y))?;
                write!(io::stdout(), "\r\n")?;
                self.area.y = (self.area.y + 1).min(self.size.1.saturating_sub(1));
            }
        }
        Ok(())
    }

    fn paint_inline(&mut self, app: &mut App, width: u16) -> io::Result<()> {
        let appended = !app.native.rows.is_empty();
        if !app.native.rows.is_empty() {
            let n = app.native.rows.len().min(128);
            self.append(app.native.rows.drain(..n))?;
        }
        let live = app.native.live(width as usize);
        let decision = app.approval.is_some() || !app.questions.pending.is_empty();
        let extra = if decision { 3 } else { 0 };
        let chrome = chrome::Chrome::new(app, width, self.size.1.saturating_sub(extra + 1));
        let live_h = live
            .len()
            .min(8)
            .min(self.size.1.saturating_sub(chrome.height + extra + 1) as usize)
            as u16;
        let height = (chrome.height + extra + live_h + 1)
            .max(self.size.1.saturating_sub(self.area.y))
            .min(self.size.1)
            .max(1);
        if self.area.height != height || self.area.width != self.size.0 {
            self.clear_live()?;
        }
        let scroll = (self.area.y + height).saturating_sub(self.size.1);
        if scroll > 0 {
            self.clear_live()?;
            execute!(
                io::stdout(),
                cursor::MoveTo(0, self.size.1.saturating_sub(1))
            )?;
            for _ in 0..scroll {
                write!(io::stdout(), "\r\n")?;
            }
            self.area.y = self.area.y.saturating_sub(scroll);
        }
        self.area.width = self.size.0;
        self.area.height = height;
        if appended || self.terminal.get_frame().area() != self.area {
            self.terminal = Terminal::with_options(
                CrosstermBackend::new(io::stdout()),
                TerminalOptions {
                    viewport: Viewport::Fixed(self.area),
                },
            )?;
        }
        self.terminal.draw(|f| {
            let a = f.area();
            app.ui.buttons.clear();
            app.rows.clear();
            if a.width < 32 || a.height < chrome.height + extra + 1 {
                text(f, a, "Please resize to at least 32 × 12", AMBER);
                return;
            }
            // Park on a genuinely empty separator, not a wide border that tmux
            // can reflow onto a continuation row. This row is live, not history.
            f.render_widget(
                Block::default().style(Style::default().bg(BG).fg(INK)),
                Rect::new(
                    0,
                    a.bottom().saturating_sub(chrome.height + extra),
                    width,
                    chrome.height + extra,
                ),
            );
            app.body = Rect::new(0, a.y + 1, width, live_h);
            for (row, line) in live
                .iter()
                .rev()
                .take(live_h as usize)
                .collect::<Vec<_>>()
                .into_iter()
                .rev()
                .enumerate()
            {
                text(
                    f,
                    Rect::new(0, a.y + 1 + row as u16, width, 1),
                    line.clone(),
                    INK,
                );
            }
            let base = a.bottom().saturating_sub(chrome.height + extra);
            if decision {
                let (label, prompt, action) = if let Some(approval) = &app.approval {
                    (
                        "[ Review decision ]",
                        safe(&string(approval, "command")),
                        Action::Decisions,
                    )
                } else {
                    let (id, q) = app.questions.pending.iter().next().unwrap();
                    (
                        "[ Answer question ]",
                        safe(&string(&q["questions"][0], "question")),
                        Action::QuestionOpen(id.clone()),
                    )
                };
                text(
                    f,
                    Rect::new(0, base, width, 1),
                    "Waiting for you · draft stays yours",
                    AMBER,
                );
                text(f, Rect::new(0, base + 1, width, 1), prompt, INK);
                app.button(f, Rect::new(0, base + 2, width.min(28), 1), label, action);
            }
            let base = base + extra;
            app.tab_y = u16::MAX;
            chrome.draw(f, app, Rect::new(0, base, width, chrome.height));
            if decision {
                // Tab starts at Actions; the explicit decision remains reachable.
                app.ui.buttons.rotate_left(1);
            }
        })?;
        // A stable cursor anchor lets the terminal tell us where reflow moved the live region.
        execute!(io::stdout(), cursor::MoveTo(0, self.area.y), cursor::Hide)?;
        io::stdout().flush()
    }

    fn leave_inspection(&mut self) -> io::Result<()> {
        execute!(io::stdout(), DisableMouseCapture, tty::LeaveAlternateScreen)?;
        ALTERNATE_OWNED.store(false, Ordering::SeqCst);
        self.alternate = false;
        // DEC 1049 restores primary output. A changed size needs the actual
        // restored anchor: subtracting the old (possibly full-height) live area
        // can clear committed short replies. Ordinary return/exit needs no query.
        if self.size != self.primary_size {
            self.size = self.primary_size;
            self.resize()?;
        }
        self.terminal = Terminal::with_options(
            CrosstermBackend::new(io::stdout()),
            TerminalOptions {
                viewport: Viewport::Fixed(self.area),
            },
        )?;
        Ok(())
    }

    pub fn finish(&mut self, app: &mut App) -> io::Result<()> {
        if self.alternate {
            self.leave_inspection()?;
        }
        self.resize()?;
        app.native.finish();
        while app.native.has_work() {
            app.native.prepare(self.size.0.max(1) as usize);
            let rows = std::mem::take(&mut app.native.rows);
            self.append(rows.into_iter())?;
        }
        self.clear_live()?;
        io::stdout().flush()
    }

    pub fn external_editor(&mut self, app: &mut App) -> io::Result<()> {
        if self.alternate {
            self.leave_inspection()?;
        }
        self.primary_size = self.size;
        ALTERNATE_OWNED.store(true, Ordering::SeqCst);
        execute!(
            io::stdout(),
            tty::EnterAlternateScreen,
            DisableBracketedPaste,
            DisableMouseCapture,
            cursor::Show
        )?;
        self.alternate = true;
        tty::disable_raw_mode()?;
        let result = crate::external_editor::edit(&app.draft.lines().join("\n"));
        tty::enable_raw_mode()?;
        execute!(io::stdout(), EnableBracketedPaste)?;
        self.size = tty::size()?;
        self.leave_inspection()?;
        match result {
            Ok(value) => {
                app.draft.select_all();
                app.draft.insert_str(value);
                app.draft_pending = true;
                app.draft_changed = Instant::now();
                app.status = "Editor returned · draft remains unsent".into();
            }
            Err(error) => app.status = format!("External editor: {error}; original draft retained"),
        }
        Ok(())
    }
}

fn restore() {
    if ALTERNATE_OWNED.swap(false, Ordering::SeqCst) {
        let _ = execute!(io::stdout(), tty::LeaveAlternateScreen);
    }
    let _ = execute!(
        io::stdout(),
        tty::EndSynchronizedUpdate,
        DisableBracketedPaste,
        DisableMouseCapture,
        ResetColor,
        cursor::Show
    );
    let _ = tty::disable_raw_mode();
}

impl Drop for Screen {
    fn drop(&mut self) {
        restore();
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn cursor_response_parser_ignores_paste_and_handles_fragments() {
        assert_eq!(reported_cursor_row(b"\x1b[12;"), None);
        assert_eq!(reported_cursor_row(b"typed\x1b[12;3Rmore"), Some(11));
        assert_eq!(reported_cursor_row(b"\x1b[200~\x1b[99;3R\x1b[201~"), None);
        assert_eq!(
            reported_cursor_row(b"\x1b[200~\x1b[99;3R\x1b[201~\x1b[2;1R"),
            Some(1)
        );
        assert_eq!(reported_cursor_row(b"\x1b[0;1R"), None);
    }
    #[test]
    fn stable_markdown_blocks_wait_for_real_boundaries() {
        assert_eq!(stable_end("Hello **world"), 0);
        assert_eq!(stable_end("```rs\nfirst\n\nsecond\n"), 0);
        assert!(stable_end("First paragraph.\n\nSecond") > 0);
        assert_eq!(stable_end("| A | B |\n|---|---|\n|x|y|"), 0);
    }
    #[test]
    fn finalization_and_identical_updates_do_not_duplicate_history() {
        let mut log = Journal::default();
        let mut item = Item {
            id: "a".into(),
            kind: "assistant".into(),
            text: "First.\n\nSecond".into(),
            ..Default::default()
        };
        log.observe(&item, false);
        log.prepare(80);
        let first: String = log.rows.drain(..).map(|l| l.to_string()).collect();
        assert!(first.contains("First."));
        item.text.push_str(".");
        log.observe(&item, true);
        log.prepare(40);
        let last: String = log.rows.drain(..).map(|l| l.to_string()).collect();
        assert!(last.contains("Second."));
        assert!(!last.contains("First."));
        log.observe(&item, true);
        log.prepare(80);
        assert!(log.rows.is_empty());
    }

    #[test]
    fn switching_keeps_backlogged_rows_and_exit_flushes_partial_source() {
        let mut log = Journal::default();
        for i in 0..200 {
            log.observe(
                &Item {
                    id: format!("id-{i}"),
                    kind: "user".into(),
                    text: format!("marker-{i:03}"),
                    ..Default::default()
                },
                true,
            );
        }
        log.prepare(80);
        log.reset();
        let history: String = log.rows.drain(..).map(|l| l.to_string()).collect();
        for i in 0..200 {
            assert_eq!(history.matches(&format!("marker-{i:03}")).count(), 1);
        }
        log.observe(
            &Item {
                id: "partial".into(),
                kind: "assistant".into(),
                text: "unfinished **source".into(),
                ..Default::default()
            },
            false,
        );
        log.prepare(40);
        assert!(log.rows.is_empty());
        log.finish();
        log.prepare(40);
        let history: String = log.rows.drain(..).map(|l| l.to_string()).collect();
        assert!(history.contains("unfinished **source"));
        assert!(!log.has_work());
    }

    #[test]
    fn historical_replay_is_disclosed_and_does_not_limit_new_output() {
        let mut log = Journal::default();
        assert_eq!(log.begin_replay(100_000), 99_000);
        assert!(
            log.rows
                .front()
                .unwrap()
                .to_string()
                .contains("Transcript / Export")
        );
        log.skip_replay_item = true;
        log.observe(
            &Item {
                id: "old".into(),
                text: "old".into(),
                ..Default::default()
            },
            true,
        );
        log.skip_replay_item = false;
        log.observe(
            &Item {
                id: "new".into(),
                text: "new".into(),
                ..Default::default()
            },
            true,
        );
        log.prepare(80);
        assert!(!log.emitted.contains_key("old"));
        assert!(log.emitted.contains_key("new"));
    }
}

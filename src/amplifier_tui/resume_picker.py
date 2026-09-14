"""Terminal-only startup chooser, before a runtime is mounted or state is written."""

import curses
import sys


def choose(state_dir):
    from amplifier_tui.navigation import session_choices

    rows = session_choices(state_dir, None)
    if not rows["sessions"]:
        raise ValueError("No saved conversations in this state directory")
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise ValueError("Resume picker needs a terminal; use --resume ID or --resume latest")
    return curses.wrapper(picker, rows)


def picker(screen, catalog):
    screen.keypad(True)
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    query, selected, recovery = "", 0, None
    while True:
        screen.erase()
        height, width = screen.getmaxyx()

        def line(y, value, highlight=False):
            value = " ".join(str(value).split())
            if 0 <= y < height - 1 and width > 4:
                try:
                    screen.addnstr(y, 2, value, width - 4, curses.A_REVERSE if highlight else 0)
                except curses.error:
                    pass

        rows = [
            row
            for row in catalog["sessions"]
            if query.casefold() in f"{row['title']} {row['cwd']} {row['id']}".casefold()
        ]
        selected = min(selected, max(0, len(rows) - 1))
        line(1, "Amplifier · Resume conversation")
        line(2, "Type to search · Up/Down choose · Enter open · Esc cancel")
        line(
            3,
            "Most recent 100 · more available by ID"
            if catalog["truncated"]
            else "Saved conversations · no work starts until selection",
        )
        line(5, f"Search: {query}")
        count = max(1, height - 12)
        offset = max(0, selected - count + 1)
        for index, row in enumerate(rows[offset : offset + count], offset):
            line(7 + index - offset, f"{row['id'][:8]}  {row['title']}", index == selected)
        if rows:
            row = rows[selected]
            line(height - 4, row["cwd"])
            line(height - 3, row["status"])
        else:
            line(7, "No matching conversations")
        if recovery:
            line(
                height - 6,
                "Recovery creates a NEW conversation; original unchanged; no tools replayed.",
            )
            line(
                height - 5,
                "Partial external effects may remain. Press Y to recover; any other key cancels.",
            )
        screen.refresh()
        key = screen.get_wch()
        if recovery:
            if key in ("y", "Y"):
                return recovery, True
            recovery = None
        elif key in ("\x1b", "\x03", "\x11"):
            return None
        elif key == curses.KEY_UP:
            selected = max(0, selected - 1)
        elif key == curses.KEY_DOWN:
            selected = min(len(rows) - 1, selected + 1)
        elif key in ("\n", "\r", curses.KEY_ENTER) and rows:
            row = rows[selected]
            if row["status"].startswith("recovery required"):
                recovery = row["id"]
            elif not row["status"].startswith("unavailable"):
                return row["id"], False
        elif key in (curses.KEY_BACKSPACE, "\x7f", "\b"):
            query, selected = query[:-1], 0
        elif isinstance(key, str) and key.isprintable() and len(query) < 256:
            query, selected = query + key, 0

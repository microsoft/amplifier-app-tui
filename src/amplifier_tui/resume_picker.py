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
    return curses.wrapper(
        picker,
        rows,
        lambda offset, query="": session_choices(state_dir, None, offset=offset, query=query),
    )


def picker(screen, catalog, load_page=None):
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
            if query == catalog.get("query")
            or query.casefold()
            in f"{row['title']} {row['cwd']} {row['id']} {row.get('match', '')}".casefold()
        ]
        selected = min(selected, max(0, len(rows) - 1))
        line(1, "Amplifier · Resume conversation")
        line(2, "Type to filter · F3 search all saved messages · Enter open · Esc cancel")
        line(
            3,
            f"Page {catalog.get('offset', 0) // 100 + 1} · PgUp/PgDn pages · no work starts until selection",
        )
        line(5, f"Search: {query}")
        if catalog.get("partial"):
            line(4, "Partial search index · F3 continues indexing · not all messages searched")
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
        elif key == curses.KEY_F3 and load_page:
            catalog = load_page(0, query)
            selected = 0
        elif key in (curses.KEY_NPAGE, curses.KEY_PPAGE) and load_page:
            offset = (
                catalog.get("next_offset")
                if key == curses.KEY_NPAGE
                else max(0, catalog.get("offset", 0) - 100)
            )
            if offset is not None and offset != catalog.get("offset", 0):
                catalog = (
                    load_page(offset, catalog["query"])
                    if catalog.get("query")
                    else load_page(offset)
                )
                selected = 0
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

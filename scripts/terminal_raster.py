"""Reference-font rasterization of observed terminal cells, not desktop pixels.

Requires Pillow and all four DejaVu Sans Mono faces. Missing faces fail explicitly
instead of silently passing a regular-font image off as typography evidence.
"""

import json
import math
from functools import lru_cache
from pathlib import Path

NAMED = {
    "black": "000000",
    "red": "cd3131",
    "green": "0dbc79",
    "brown": "e5e510",
    "yellow": "e5e510",
    "blue": "2472c8",
    "magenta": "bc3fbc",
    "cyan": "11a8cd",
    "white": "e5e5e5",
    "brightblack": "666666",
    "brightred": "f14c4c",
    "brightgreen": "23d18b",
    "brightyellow": "f5f543",
    "brightblue": "3b8eea",
    "brightmagenta": "d670d6",
    "brightcyan": "29b8db",
    "brightwhite": "ffffff",
}


@lru_cache(maxsize=4)
def reference_fonts(size):
    from PIL import ImageFont

    try:
        return {
            (bold, italic): ImageFont.truetype(f"DejaVuSansMono{suffix}.ttf", size)
            for bold, italic, suffix in [
                (False, False, ""),
                (True, False, "-Bold"),
                (False, True, "-Oblique"),
                (True, True, "-BoldOblique"),
            ]
        }
    except OSError as error:
        raise RuntimeError("Terminal captures require all DejaVu Sans Mono font faces") from error


def colour(value, fallback):
    value = NAMED.get(value, value)
    if len(value) == 6 and all(c in "0123456789abcdefABCDEF" for c in value):
        return "#" + value
    return fallback


def render_terminal(display, path, font_size=None):
    from PIL import Image, ImageDraw

    size = font_size or display.font_size
    fonts = reference_fonts(size)
    regular = fonts[False, False]
    width = math.ceil(regular.getlength("M"))
    ascent, descent = regular.getmetrics()
    height = ascent + descent + 2
    foreground, background = "#f0f6ff", "#0d1117"
    image = Image.new("RGB", (display.cols * width, display.rows * height), background)
    draw = ImageDraw.Draw(image)
    cells = []
    for y in range(display.rows):
        for x in range(display.cols):
            cell = display.screen.buffer[y][x]
            fg, bg = colour(cell.fg, foreground), colour(cell.bg, background)
            if cell.reverse:
                fg, bg = bg, fg
            # Paint all backgrounds first: a wide glyph spans continuation cells.
            draw.rectangle(
                (x * width, y * height, (x + 1) * width - 1, (y + 1) * height - 1), fill=bg
            )
            cells.append((x, y, cell, fg))
    for x, y, cell, fg in cells:
        draw.text(
            (x * width, y * height + 1), cell.data, font=fonts[cell.bold, cell.italics], fill=fg
        )
        if cell.underscore:
            baseline = y * height + ascent + 2
            draw.line((x * width, baseline, (x + 1) * width - 1, baseline), fill=fg)
        if cell.strikethrough:
            midline = y * height + height // 2
            draw.line((x * width, midline, (x + 1) * width - 1, midline), fill=fg)
    cursor = display.screen.cursor
    if not cursor.hidden and 0 <= cursor.x < display.cols and 0 <= cursor.y < display.rows:
        draw.rectangle(
            (
                cursor.x * width,
                cursor.y * height,
                (cursor.x + 1) * width - 1,
                (cursor.y + 1) * height - 1,
            ),
            outline="#8e95a3",
        )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "PNG")
    path.with_suffix(".capture.json").write_text(
        json.dumps(
            {
                "kind": "terminal-cell reconstruction",
                "fonts": [font.getname() for font in fonts.values()],
                "font_size": size,
                "columns": display.cols,
                "rows": display.rows,
                "cell_pixels": [width, height],
                "limitations": "Reference fonts/ANSI defaults, not the user's terminal pixels; "
                "no blink animation or font fallback for unsupported glyphs.",
            },
            indent=2,
        )
        + "\n"
    )

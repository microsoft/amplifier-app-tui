"""The capture observer must not erase the attributes under visual review."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

pyte = pytest.importorskip("pyte")
Image = pytest.importorskip("PIL.Image")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from terminal_raster import reference_fonts, render_terminal  # noqa: E402


def test_reference_capture_reproduces_attributes_without_changing_cells(tmp_path):
    try:
        reference_fonts(16)
    except RuntimeError:
        pytest.skip("Install all DejaVu Sans Mono faces for capture verification")
    screen = pyte.Screen(12, 7)
    pyte.Stream(screen).feed(
        "Heading\r\n\x1b[1mHeading\r\n\x1b[0;3mHeading\r\n"
        "\x1b[0;4mHeading\r\n\x1b[0;9mHeading\r\n"
        "\x1b[0;7mHeading\r\n\x1b[0mHeading\x1b[?25l"
    )
    # Buffer insertion order must not change the rendered row order.
    row = screen.buffer.pop(0)
    screen.buffer[0] = row
    before = list(screen.display)
    display = SimpleNamespace(screen=screen, cols=12, rows=7, font_size=16)
    path = tmp_path / "attributes.png"
    render_terminal(display, path)
    metadata = json.loads(path.with_suffix(".capture.json").read_text())
    assert metadata["kind"] == "terminal-cell reconstruction"
    assert len({tuple(font) for font in metadata["fonts"]}) == 4
    image = Image.open(path)
    width, height = metadata["cell_pixels"]
    rows = [image.crop((0, y * height, 7 * width, (y + 1) * height)).tobytes() for y in range(7)]
    assert len(set(rows[:6])) == 6  # Bold is not just a recolouring of regular.
    assert rows[0] == rows[6]
    assert screen.display == before and screen.cursor.hidden
    screen.cursor.hidden = False
    render_terminal(display, tmp_path / "cursor.png")
    assert Image.open(tmp_path / "cursor.png").tobytes() != image.tobytes()

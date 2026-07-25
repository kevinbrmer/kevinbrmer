"""Liest Glyphenpfade und Vorschubbreiten aus einer woff2-Schriftdatei."""
from __future__ import annotations

from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont


def load_font(path: Path) -> TTFont:
    """Oeffnet die Schrift. Benoetigt das Paket brotli fuer woff2."""
    return TTFont(str(path))


def _glyph_names(font: TTFont, text: str) -> list[str]:
    cmap = font.getBestCmap()
    names = []
    for char in text:
        name = cmap.get(ord(char))
        if name is None:
            raise KeyError(f"Zeichen {char!r} fehlt in der Schrift")
        names.append(name)
    return names


def advance_widths(font: TTFont, text: str, size: float) -> list[float]:
    """Kumulierte x-Positionen nach jedem Zeichen, beginnend mit 0.0."""
    upem = font["head"].unitsPerEm
    hmtx = font["hmtx"]
    scale = size / upem
    positions = [0.0]
    cursor = 0.0
    for name in _glyph_names(font, text):
        cursor += hmtx[name][0] * scale
        positions.append(cursor)
    return positions


def text_width(font: TTFont, text: str, size: float) -> float:
    """Gesamtbreite des gesetzten Textes."""
    return advance_widths(font, text, size)[-1]


def text_top(font: TTFont, text: str, size: float) -> float:
    """Hoehe der obersten Kontur ueber der Grundlinie.

    Massgeblich ist die tatsaechliche Oberkante der gezeichneten Glyphen, nicht
    die Versalhoehe: In "I help" ragt die Oberlaenge des h ueber das I hinaus.
    """
    glyph_set = font.getGlyphSet()
    scale = size / font["head"].unitsPerEm
    highest = 0.0
    for name in _glyph_names(font, text):
        pen = BoundsPen(glyph_set)
        glyph_set[name].draw(pen)
        if pen.bounds:
            highest = max(highest, pen.bounds[3])
    return highest * scale


def text_to_path(font: TTFont, text: str, size: float) -> str:
    """Setzt den Text als Folge positionierter SVG-Gruppen, Grundlinie bei y=0.

    Zeichen ohne Kontur, etwa das Leerzeichen, erzeugen keine Gruppe,
    verschieben den Cursor aber trotzdem.
    """
    upem = font["head"].unitsPerEm
    scale = size / upem
    glyph_set = font.getGlyphSet()
    hmtx = font["hmtx"]
    parts: list[str] = []
    cursor = 0.0
    for name in _glyph_names(font, text):
        pen = SVGPathPen(glyph_set)
        glyph_set[name].draw(pen)
        commands = pen.getCommands()
        if commands:
            # y wird gespiegelt, da SVG nach unten waechst, die Schrift nach oben
            parts.append(
                f'<g transform="translate({cursor:.2f} 0) scale({scale:.6f} {-scale:.6f})">'
                f'<path d="{commands}"/></g>'
            )
        cursor += hmtx[name][0] * scale
    return "".join(parts)

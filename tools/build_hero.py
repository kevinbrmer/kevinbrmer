"""Baut die SVG-Bausteine fuer das Profil-README.

Erzeugt zwei getrennte Grafiken je Farbschema:

* `headline-*.svg` — die animierte Textzeile, nichts sonst
* `portrait-*.svg` — Rahmen und freigestelltes Portrait

Die Trennung ist Absicht. Im README floatet das Portrait nach rechts,
waehrend Headline und die anklickbare Icon-Reihe links direkt untereinander
stehen. Laege beides in einer Grafik, saessen die Icons zwangslaeufig unter
dem gesamten Bild und damit weit unter der Headline.

Die Bewegung entsteht ueber SMIL, weil GitHub CSS und JavaScript aus READMEs
entfernt. Der Rotator ahmt den Typewriter von kevin-brammer.de nach.
"""
from __future__ import annotations

import base64
from pathlib import Path

from PIL import Image

from glyphs import (
    advance_widths,
    load_font,
    text_depth,
    text_to_path,
    text_top,
    text_width,
)

FONT_PATH = Path(
    r"C:\Users\KB\.claude\kevin-brammer-de\output\site\public\fonts"
    r"\cabinet-grotesk\cabinet-grotesk-700.woff2"
)
ASSETS = Path(__file__).resolve().parent.parent / "assets"

HEADLINE_SIZE = 58.0
LINE_HEIGHT = 67.0
HEADLINE_LINES = ["I help", "companies with"]
TEXT_X = 2.0
CARET_WIDTH = 5.0

# Darstellungsbreiten im README, als Anteil der Containerbreite. Sie bestimmen
# zugleich die wahrgenommene Schriftgroesse und die vertikale Ausrichtung und
# muessen deshalb mit den width-Angaben in README.md uebereinstimmen.
README_HEADLINE_W = 0.44
README_PORTRAIT_W = 0.34
HEADLINE_PAD_BOTTOM = 26.0
CARET_GAP = 5.0
DOT_GAP = 4.0

WORDS = ["digitalization", "automation", "process optimization", "data analytics"]
TYPE_MS, HOLD_MS, ERASE_MS, PAUSE_MS = 90, 1800, 50, 380

FRAME_W, FRAME_H = 380.0, 475.0
FRAME_RADIUS = 22.0
FRAME_STROKE = 3.5
PORTRAIT_SCALE = 1.15
PORTRAIT_DROP = 29.5
PORTRAIT_PAD = 2.0
# Luft unter dem Rahmen, damit das Portrait im README nicht am unteren Rand
# des Kastens klebt.
PORTRAIT_PAD_BOTTOM = 44.0

THEMES = {
    # Marken-Violett aus tokens.css, Kontrast auf hellem Grund rund 5:1
    "light": {"ink": "#0a0a0a", "accent": "#8c52ff"},
    # Aufgehelltes Violett, damit der Kontrast auf #0d1117 traegt
    "dark": {"ink": "#f0f6fc", "accent": "#a482ff"},
}

HEADLINE_LABEL = (
    "I help companies with digitalization, automation, "
    "process optimization and data analytics."
)
PORTRAIT_LABEL = "Kevin Brammer"


def word_timeline() -> list[dict]:
    """Start- und Endzeit jedes Wortes in Millisekunden, luecken- und ueberlappungsfrei."""
    segments = []
    cursor = 0
    for word in WORDS:
        typing = len(word) * TYPE_MS
        erasing = len(word) * ERASE_MS
        segments.append(
            {
                "word": word,
                "start": cursor,
                "hold_end": cursor + typing + HOLD_MS,
                "erase_end": cursor + typing + HOLD_MS + erasing,
                "end": cursor + typing + HOLD_MS + erasing + PAUSE_MS,
            }
        )
        cursor = segments[-1]["end"]
    return segments


TOTAL_MS = word_timeline()[-1]["end"]


def _word_points(segment: dict, widths: list[float]) -> list[tuple[int, float]]:
    """Cursorposition ueber die Lebensdauer eines Wortes als (Zeit, Breite)."""
    last = len(widths) - 1
    points: list[tuple[int, float]] = [(segment["start"], 0.0)]
    for index in range(1, last + 1):
        points.append((segment["start"] + index * TYPE_MS, widths[index]))
    points.append((segment["hold_end"], widths[last]))
    for step in range(1, last + 1):
        points.append((segment["hold_end"] + step * ERASE_MS, widths[last - step]))
    points.append((segment["end"], 0.0))
    return points


def _serialize(points: list[tuple[int, float]], offset: float = 0.0) -> tuple[str, str]:
    """Formt (Zeit, Wert)-Punkte in die SMIL-Attribute values und keyTimes um."""
    values = ";".join(f"{value + offset:.2f}" for _, value in points)
    times = ";".join(f"{time / TOTAL_MS:.6f}" for time, _ in points)
    return values, times


def caret_track(font) -> list[tuple[int, float]]:
    """Cursorkurve ueber den gesamten Loop, fuer Caret und Punkt."""
    points: list[tuple[int, float]] = []
    for segment in word_timeline():
        widths = advance_widths(font, segment["word"], HEADLINE_SIZE)
        for point in _word_points(segment, widths):
            if points and points[-1][0] == point[0]:
                continue
            points.append(point)
    if points[0][0] != 0:
        points.insert(0, (0, 0.0))
    if points[-1][0] != TOTAL_MS:
        points.append((TOTAL_MS, 0.0))
    return points


def _reveal_points(segment: dict, widths: list[float]) -> list[tuple[int, float]]:
    """Maskenbreite eines Wortes: folgt dem Cursor im eigenen Fenster, sonst null."""
    points: list[tuple[int, float]] = []
    if segment["start"] > 0:
        points.append((0, 0.0))
    points.extend(_word_points(segment, widths))
    if points[-1][0] != TOTAL_MS:
        points.append((TOTAL_MS, 0.0))
    return points


def _animate(attribute: str, values: str, times: str) -> str:
    return (
        f'<animate attributeName="{attribute}" values="{values}" keyTimes="{times}" '
        f'dur="{TOTAL_MS}ms" repeatCount="indefinite" calcMode="discrete" />'
    )


def _deepest_descender(font) -> float:
    """Tiefste Unterlaenge, die die Rotator-Zeile erreichen kann."""
    return max(text_depth(font, word, HEADLINE_SIZE) for word in WORDS)


def _headline_width(font) -> float:
    longest = max(text_width(font, word, HEADLINE_SIZE) for word in WORDS)
    return (
        TEXT_X
        + longest
        + CARET_GAP
        + CARET_WIDTH
        + DOT_GAP
        + text_width(font, ".", HEADLINE_SIZE)
        + 6
    )


def _pad_top(font) -> float:
    """Leerraum ueber der ersten Zeile.

    Der Textblock soll im README auf halber Hoehe des rechts daneben
    stehenden Portraits sitzen. Beide Grafiken werden an derselben
    Containerbreite skaliert, ihr Groessenverhaeltnis ist deshalb von der
    tatsaechlichen Breite unabhaengig und laesst sich hier fest ausrechnen.
    """
    geometry = portrait_geometry()
    portrait_ratio = geometry["height"] / geometry["width"]
    # Mitte des Portraits, gemessen in Anteilen der Containerbreite
    portrait_middle = README_PORTRAIT_W * portrait_ratio / 2
    # dieselbe Hoehe, umgerechnet in Koordinaten der Headline-Grafik
    target = portrait_middle * _headline_width(font) / README_HEADLINE_W

    block = (
        text_top(font, HEADLINE_LINES[0], HEADLINE_SIZE)
        + 2 * LINE_HEIGHT
        + _deepest_descender(font)
    )
    return max(0.0, target - block / 2)


def headline_size(font) -> tuple[float, float, float]:
    """Breite, Hoehe und erste Grundlinie der Headline-Grafik."""
    pad_top = _pad_top(font)
    over = text_top(font, HEADLINE_LINES[0], HEADLINE_SIZE)
    height = (
        pad_top
        + over
        + 2 * LINE_HEIGHT
        + _deepest_descender(font)
        + HEADLINE_PAD_BOTTOM
    )
    return _headline_width(font), height, pad_top + over


def _rotator_markup(font, theme: dict, baseline: float) -> str:
    top = baseline - HEADLINE_SIZE
    box_height = HEADLINE_SIZE * 1.4
    parts: list[str] = []

    for index, segment in enumerate(word_timeline()):
        widths = advance_widths(font, segment["word"], HEADLINE_SIZE)
        values, times = _serialize(_reveal_points(segment, widths))
        # Das erste Wort startet auf voller Breite, damit die Zeile auch dann
        # lesbar bleibt, wenn eine Umgebung SMIL ignoriert.
        initial = widths[-1] if index == 0 else 0.0
        parts.append(
            f"""
  <clipPath id="reveal{index}">
    <rect x="{TEXT_X:.2f}" y="{top:.2f}" width="{initial:.2f}" height="{box_height:.2f}">
      {_animate("width", values, times)}
    </rect>
  </clipPath>
  <g clip-path="url(#reveal{index})">
    <g transform="translate({TEXT_X:.2f} {baseline:.2f})" fill="{theme['accent']}">
      {text_to_path(font, segment["word"], HEADLINE_SIZE)}
    </g>
  </g>"""
        )

    points = caret_track(font)
    caret_values, caret_times = _serialize(points, offset=TEXT_X + CARET_GAP)
    dot_offset = TEXT_X + CARET_GAP + CARET_WIDTH + DOT_GAP
    dot_values, dot_times = _serialize(points, offset=dot_offset)

    parts.append(
        f"""
  <rect x="{TEXT_X + CARET_GAP:.2f}" y="{baseline - HEADLINE_SIZE * 0.78:.2f}"
        width="{CARET_WIDTH}" height="{HEADLINE_SIZE * 0.78:.2f}" fill="{theme['ink']}">
    {_animate("x", caret_values, caret_times)}
    <animate attributeName="opacity" values="1;0" keyTimes="0;0.5" dur="1s"
             repeatCount="indefinite" calcMode="discrete" />
  </rect>
  <g fill="{theme['ink']}" transform="translate(0 {baseline:.2f})">
    <g transform="translate({dot_offset:.2f} 0)">
      {text_to_path(font, ".", HEADLINE_SIZE)}
      <animateTransform attributeName="transform" type="translate"
                        values="{';'.join(f'{v} 0' for v in dot_values.split(';'))}"
                        keyTimes="{dot_times}" dur="{TOTAL_MS}ms"
                        repeatCount="indefinite" calcMode="discrete" />
    </g>
  </g>"""
    )
    return "".join(parts)


def build_headline_svg(theme_name: str) -> str:
    theme = THEMES[theme_name]
    font = load_font(FONT_PATH)
    width, height, baseline = headline_size(font)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {height:.0f}" \
width="{width:.0f}" height="{height:.0f}" role="img" aria-label="{HEADLINE_LABEL}">
  <g fill="{theme['ink']}" transform="translate({TEXT_X:.2f} {baseline:.2f})">\
{text_to_path(font, HEADLINE_LINES[0], HEADLINE_SIZE)}</g>
  <g fill="{theme['ink']}" transform="translate({TEXT_X:.2f} {baseline + LINE_HEIGHT:.2f})">\
{text_to_path(font, HEADLINE_LINES[1], HEADLINE_SIZE)}</g>
{_rotator_markup(font, theme, baseline + 2 * LINE_HEIGHT)}
</svg>
"""


def portrait_geometry() -> dict:
    """Masse der Portraitgrafik, gerechnet vom Scheitel aus.

    Das Portrait beginnt am oberen Bildrand und ragt seitlich ueber den
    Rahmen hinaus. Unten endet es buendig an dessen Innenkante.
    """
    with Image.open(ASSETS / "portrait.png") as image:
        ratio = image.height / image.width
    portrait_w = FRAME_W * PORTRAIT_SCALE
    portrait_h = portrait_w * ratio
    frame_y = portrait_h - FRAME_H - PORTRAIT_DROP
    return {
        "portrait_x": PORTRAIT_PAD,
        "portrait_y": PORTRAIT_PAD,
        "portrait_w": portrait_w,
        "portrait_h": portrait_h,
        "frame_x": PORTRAIT_PAD + (portrait_w - FRAME_W) / 2,
        "frame_y": PORTRAIT_PAD + frame_y,
        "floor": PORTRAIT_PAD + frame_y + FRAME_H - FRAME_STROKE / 2,
        "width": portrait_w + 2 * PORTRAIT_PAD,
        "height": PORTRAIT_PAD + frame_y + FRAME_H + PORTRAIT_PAD_BOTTOM,
    }


def build_portrait_svg(theme_name: str) -> str:
    theme = THEMES[theme_name]
    geometry = portrait_geometry()
    encoded = base64.b64encode((ASSETS / "portrait.png").read_bytes()).decode()

    return f"""<svg xmlns="http://www.w3.org/2000/svg" \
viewBox="0 0 {geometry['width']:.0f} {geometry['height']:.0f}" \
width="{geometry['width']:.0f}" height="{geometry['height']:.0f}" \
role="img" aria-label="{PORTRAIT_LABEL}">
  <defs>
    <clipPath id="portraitFloor">
      <rect x="0" y="0" width="{geometry['width']:.2f}" height="{geometry['floor']:.2f}" />
    </clipPath>
  </defs>
  <rect x="{geometry['frame_x']:.2f}" y="{geometry['frame_y']:.2f}"
        width="{FRAME_W}" height="{FRAME_H}" rx="{FRAME_RADIUS}"
        fill="none" stroke="{theme['ink']}" stroke-width="{FRAME_STROKE}" />
  <image href="data:image/png;base64,{encoded}" clip-path="url(#portraitFloor)"
         x="{geometry['portrait_x']:.2f}" y="{geometry['portrait_y']:.2f}"
         width="{geometry['portrait_w']:.2f}" height="{geometry['portrait_h']:.2f}" />
</svg>
"""


def main() -> None:
    for theme_name in THEMES:
        for stem, markup in (
            (f"headline-{theme_name}", build_headline_svg(theme_name)),
            (f"portrait-{theme_name}", build_portrait_svg(theme_name)),
        ):
            target = ASSETS / f"{stem}.svg"
            target.write_text(markup, encoding="utf-8")
            print(f"{target.name}: {target.stat().st_size / 1024:.1f} KB")
    font = load_font(FONT_PATH)
    width, height, _ = headline_size(font)
    geometry = portrait_geometry()
    print(f"Headline {width:.0f} x {height:.0f}, Portrait "
          f"{geometry['width']:.0f} x {geometry['height']:.0f}, Loop {TOTAL_MS} ms")


if __name__ == "__main__":
    main()

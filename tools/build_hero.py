"""Baut die animierten Hero-SVG fuer das Profil-README.

Der Rotator ahmt den Typewriter der Startseite von kevin-brammer.de nach.
Da GitHub kein CSS und kein JavaScript in READMEs zulaesst, geschieht die
Bewegung ueber SMIL: Je Wort gibt eine clipPath-Maske zeichenweise mehr
Flaeche frei, waehrend Caret und Punkt auf derselben Zeitachse mitwandern.
"""
from __future__ import annotations

import base64
from pathlib import Path

from PIL import Image

from glyphs import advance_widths, load_font, text_to_path, text_top, text_width

FONT_PATH = Path(
    r"C:\Users\KB\.claude\kevin-brammer-de\output\site\public\fonts"
    r"\cabinet-grotesk\cabinet-grotesk-700.woff2"
)
ASSETS = Path(__file__).resolve().parent.parent / "assets"

WIDTH = 1200
HEADLINE_SIZE = 62.0
LINE_HEIGHT = 72.0
TEXT_X = 64.0
HEADLINE_LINES = ["I help", "companies with"]
CARET_WIDTH = 5.0
CARET_GAP = 5.0
DOT_GAP = 4.0

WORDS = ["digitalization", "automation", "process optimization", "data analytics"]
TYPE_MS, HOLD_MS, ERASE_MS, PAUSE_MS = 90, 1800, 50, 380

# Bewusst flaches Bannerformat: Steht die Headline oben buendig zum Scheitel,
# waere sie bei einem hohen Portrait nur im oberen Drittel und darunter bliebe
# eine leere Flaeche, die im README die Headline vom Untertitel wegdrueckt.
FRAME_X, FRAME_Y, FRAME_W, FRAME_H = 820.0, 90.0, 300.0, 375.0
FRAME_RADIUS = 22.0
FRAME_STROKE = 3.5
PORTRAIT_SCALE = 1.15
PORTRAIT_DROP = 29.5

# Die Zeichenflaeche endet kurz unter dem Rahmen. Weiter unten steht nichts
# mehr, und ueberzaehlige Hoehe waere im README nur leerer Abstand.
HEIGHT = round(FRAME_Y + FRAME_H + 12)

# Das SVG bleibt vollstaendig transparent, damit GitHub seinen eigenen
# Seitenhintergrund durchscheinen laesst. Eine gesetzte Flaeche wuerde in
# jedem Theme leicht neben dem Seitenton liegen und als Kasten auffallen.
THEMES = {
    # Marken-Violett aus tokens.css, Kontrast auf hellem Grund rund 5:1
    "light": {"ink": "#0a0a0a", "accent": "#8c52ff"},
    # Aufgehelltes Violett, damit der Kontrast auf #0d1117 traegt
    "dark": {"ink": "#f0f6fc", "accent": "#a482ff"},
}

ARIA_LABEL = (
    "Kevin Brammer - I help companies with digitalization, automation, "
    "process optimization and data analytics."
)


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
                "type_end": cursor + typing,
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


def _widths_for(font, word: str) -> list[float]:
    return advance_widths(font, word, HEADLINE_SIZE)


def _serialize(points: list[tuple[int, float]], offset: float = 0.0) -> tuple[str, str]:
    """Formt (Zeit, Wert)-Punkte in SMIL-Attribute values und keyTimes um."""
    values = ";".join(f"{value + offset:.2f}" for _, value in points)
    times = ";".join(f"{time / TOTAL_MS:.6f}" for time, _ in points)
    return values, times


def caret_track(font=None) -> tuple[list[float], list[float]]:
    """Globale Cursorkurve ueber den gesamten Loop, als (Breiten, normierte Zeiten)."""
    font = font or load_font(FONT_PATH)
    points: list[tuple[int, float]] = []
    for segment in word_timeline():
        for point in _word_points(segment, _widths_for(font, segment["word"])):
            if points and points[-1][0] == point[0]:
                continue
            points.append(point)
    if points[0][0] != 0:
        points.insert(0, (0, 0.0))
    if points[-1][0] != TOTAL_MS:
        points.append((TOTAL_MS, 0.0))
    return [value for _, value in points], [time / TOTAL_MS for time, _ in points]


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


def _rotator_markup(font, theme: dict, first_baseline: float) -> str:
    baseline = first_baseline + len(HEADLINE_LINES) * LINE_HEIGHT
    top = baseline - HEADLINE_SIZE
    box_height = HEADLINE_SIZE * 1.4
    parts: list[str] = []

    for index, segment in enumerate(word_timeline()):
        widths = _widths_for(font, segment["word"])
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

    track_values, track_times = caret_track(font)
    points = list(zip((int(t * TOTAL_MS) for t in track_times), track_values))
    caret_values, caret_times = _serialize(points, offset=TEXT_X + CARET_GAP)
    dot_values, dot_times = _serialize(
        points, offset=TEXT_X + CARET_GAP + CARET_WIDTH + DOT_GAP
    )

    parts.append(
        f"""
  <rect y="{baseline - HEADLINE_SIZE * 0.78:.2f}" width="{CARET_WIDTH}" height="{HEADLINE_SIZE * 0.78:.2f}"
        fill="{theme['ink']}" x="{TEXT_X + CARET_GAP:.2f}">
    {_animate("x", caret_values, caret_times)}
    <animate attributeName="opacity" values="1;0" keyTimes="0;0.5" dur="1s"
             repeatCount="indefinite" calcMode="discrete" />
  </rect>
  <g fill="{theme['ink']}" transform="translate(0 {baseline:.2f})">
    <g transform="translate({TEXT_X + CARET_GAP + CARET_WIDTH + DOT_GAP:.2f} 0)">
      {text_to_path(font, ".", HEADLINE_SIZE)}
      <animateTransform attributeName="transform" type="translate"
                        values="{';'.join(f'{v} 0' for v in dot_values.split(';'))}"
                        keyTimes="{dot_times}" dur="{TOTAL_MS}ms"
                        repeatCount="indefinite" calcMode="discrete" />
    </g>
  </g>"""
    )
    return "".join(parts)


def first_baseline(font) -> float:
    """Grundlinie der ersten Headline-Zeile.

    Die Oberkante der Schrift liegt buendig mit dem Scheitel des Portraits.
    Das PNG ist auf seinen sichtbaren Inhalt zugeschnitten, seine obere
    Bildkante ist damit zugleich die Oberkante der Silhouette.
    """
    _, portrait_y, _, _ = _portrait_geometry()
    return portrait_y + text_top(font, HEADLINE_LINES[0], HEADLINE_SIZE)


def _portrait_geometry() -> tuple[float, float, float, float]:
    with Image.open(ASSETS / "portrait.png") as image:
        ratio = image.height / image.width
    width = FRAME_W * PORTRAIT_SCALE
    height = width * ratio
    x = FRAME_X + FRAME_W / 2 - width / 2
    y = FRAME_Y + FRAME_H + PORTRAIT_DROP - height
    return x, y, width, height


def build_svg(theme_name: str) -> str:
    theme = THEMES[theme_name]
    font = load_font(FONT_PATH)
    portrait_b64 = base64.b64encode((ASSETS / "portrait.png").read_bytes()).decode()
    px, py, pw, ph = _portrait_geometry()
    base = first_baseline(font)

    # Das Portrait ragt oben und seitlich ueber den Rahmen hinaus, endet unten
    # aber buendig an dessen Innenkante, statt darunter weiterzulaufen.
    portrait_floor = FRAME_Y + FRAME_H - FRAME_STROKE / 2

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" \
width="{WIDTH}" height="{HEIGHT}" role="img" aria-label="{ARIA_LABEL}">
  <defs>
    <clipPath id="portraitFloor">
      <rect x="0" y="0" width="{WIDTH}" height="{portrait_floor:.2f}" />
    </clipPath>
  </defs>

  <g fill="{theme['ink']}" transform="translate({TEXT_X:.2f} {base:.2f})">\
{text_to_path(font, HEADLINE_LINES[0], HEADLINE_SIZE)}</g>
  <g fill="{theme['ink']}" transform="translate({TEXT_X:.2f} {base + LINE_HEIGHT:.2f})">\
{text_to_path(font, HEADLINE_LINES[1], HEADLINE_SIZE)}</g>
{_rotator_markup(font, theme, base)}

  <rect x="{FRAME_X}" y="{FRAME_Y}" width="{FRAME_W}" height="{FRAME_H}" rx="{FRAME_RADIUS}"
        fill="none" stroke="{theme['ink']}" stroke-width="{FRAME_STROKE}" />
  <image href="data:image/png;base64,{portrait_b64}" clip-path="url(#portraitFloor)"
         x="{px:.2f}" y="{py:.2f}" width="{pw:.2f}" height="{ph:.2f}" />
</svg>
"""


def main() -> None:
    for theme_name in THEMES:
        target = ASSETS / f"hero-{theme_name}.svg"
        target.write_text(build_svg(theme_name), encoding="utf-8")
        print(f"{target.name}: {target.stat().st_size / 1024:.1f} KB")
    print(f"Loop: {TOTAL_MS} ms")


if __name__ == "__main__":
    main()

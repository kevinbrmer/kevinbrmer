import xml.etree.ElementTree as ET

import pytest

from build_hero import (
    FONT_PATH,
    FRAME_H,
    FRAME_STROKE,
    HEADLINE_LINES,
    HEADLINE_SIZE,
    LINE_HEIGHT,
    THEMES,
    TOTAL_MS,
    WORDS,
    build_headline_svg,
    build_portrait_svg,
    caret_track,
    headline_size,
    portrait_geometry,
    word_timeline,
)
from glyphs import load_font, text_depth, text_top

NS = "{http://www.w3.org/2000/svg}"
THEME_NAMES = ["light", "dark"]


# --- Zeitachse ---------------------------------------------------------------


def test_timeline_total_is_16840_ms():
    assert word_timeline()[-1]["end"] == 16840
    assert TOTAL_MS == 16840


def test_timeline_covers_every_word():
    assert len(word_timeline()) == len(WORDS)


def test_timeline_segments_are_contiguous():
    timeline = word_timeline()
    for previous, current in zip(timeline, timeline[1:]):
        assert current["start"] == previous["end"]


def test_caret_track_starts_and_ends_at_origin():
    points = caret_track(load_font(FONT_PATH))
    assert points[0] == (0, 0.0)
    assert points[-1] == (TOTAL_MS, 0.0)


def test_caret_track_is_monotonic_in_time():
    points = caret_track(load_font(FONT_PATH))
    assert all(b[0] >= a[0] for a, b in zip(points, points[1:]))


# --- Headline-Grafik ---------------------------------------------------------


@pytest.mark.parametrize("theme", THEME_NAMES)
def test_headline_is_wellformed_and_labelled(theme):
    root = ET.fromstring(build_headline_svg(theme))
    assert root.attrib["role"] == "img"
    assert "digitalization" in root.attrib["aria-label"]


@pytest.mark.parametrize("theme", THEME_NAMES)
def test_headline_animates_every_word(theme):
    assert build_headline_svg(theme).count("<animate") >= len(WORDS)


@pytest.mark.parametrize("theme", THEME_NAMES)
def test_first_word_stays_visible_without_smil(theme):
    """Ignoriert eine Umgebung SMIL, muss die Rotator-Zeile trotzdem lesbar sein."""
    root = ET.fromstring(build_headline_svg(theme))
    rect = root.find(f".//{NS}clipPath[@id='reveal0']/{NS}rect")
    assert rect is not None
    assert float(rect.attrib["width"]) > 0


@pytest.mark.parametrize("theme", THEME_NAMES)
def test_clipped_groups_carry_no_transform(theme):
    """SVG wendet transform vor clip-path an. Traegt dasselbe Element beides,
    verschiebt sich die Maske mit und schneidet den Text komplett weg."""
    root = ET.fromstring(build_headline_svg(theme))
    clipped = [g for g in root.iter(f"{NS}g") if "clip-path" in g.attrib]
    assert len(clipped) == len(WORDS)
    for group in clipped:
        assert "transform" not in group.attrib


@pytest.mark.parametrize("theme", THEME_NAMES)
def test_rotator_words_use_the_theme_accent(theme):
    root = ET.fromstring(build_headline_svg(theme))
    clipped = [g for g in root.iter(f"{NS}g") if "clip-path" in g.attrib]
    for group in clipped:
        assert group.find(f"{NS}g").attrib["fill"] == THEMES[theme]["accent"]


@pytest.mark.parametrize("theme", THEME_NAMES)
def test_headline_carries_no_portrait(theme):
    """Portrait und Headline sind getrennte Dateien, damit im README das Bild
    nach rechts floaten kann und die Icons direkt unter den Text ruecken."""
    assert "data:image/png;base64," not in build_headline_svg(theme)


@pytest.mark.parametrize("theme", THEME_NAMES)
def test_headline_box_encloses_all_three_lines(theme):
    """Keine Zeile darf oben oder unten aus der Zeichenflaeche ragen."""
    font = load_font(FONT_PATH)
    width, height, baseline = headline_size(font)
    assert baseline - text_top(font, HEADLINE_LINES[0], HEADLINE_SIZE) >= 0
    last = baseline + 2 * LINE_HEIGHT
    assert last + max(text_depth(font, w, HEADLINE_SIZE) for w in WORDS) <= height

    root = ET.fromstring(build_headline_svg(theme))
    assert root.attrib["viewBox"] == f"0 0 {width:.0f} {height:.0f}"


# --- Portrait-Grafik ---------------------------------------------------------


@pytest.mark.parametrize("theme", THEME_NAMES)
def test_portrait_is_wellformed_and_embeds_the_image(theme):
    markup = build_portrait_svg(theme)
    root = ET.fromstring(markup)
    assert root.attrib["role"] == "img"
    assert "data:image/png;base64," in markup


@pytest.mark.parametrize("theme", THEME_NAMES)
def test_portrait_starts_at_the_top_edge(theme):
    """Der Scheitel sitzt am oberen Bildrand, damit im README kein toter
    Rand ueber dem Portrait entsteht."""
    geometry = portrait_geometry()
    assert geometry["portrait_y"] <= 2.0


@pytest.mark.parametrize("theme", THEME_NAMES)
def test_portrait_is_cut_at_the_frame_floor(theme):
    """Das Portrait endet an der Innenkante der unteren Rahmenlinie."""
    geometry = portrait_geometry()
    root = ET.fromstring(build_portrait_svg(theme))
    image = root.find(f"{NS}image")
    assert image.attrib["clip-path"] == "url(#portraitFloor)"

    rect = root.find(f".//{NS}clipPath[@id='portraitFloor']/{NS}rect")
    expected = geometry["frame_y"] + FRAME_H - FRAME_STROKE / 2
    assert float(rect.attrib["height"]) == pytest.approx(expected)
    # Ohne Beschnitt liefe das Bild tiefer, sonst waere der Test blind.
    assert geometry["portrait_y"] + geometry["portrait_h"] > expected


@pytest.mark.parametrize("theme", THEME_NAMES)
def test_frame_is_outline_only(theme):
    root = ET.fromstring(build_portrait_svg(theme))
    frames = [r for r in root.findall(f"{NS}rect") if "stroke" in r.attrib]
    assert len(frames) == 1
    assert frames[0].attrib["fill"] == "none"


@pytest.mark.parametrize("theme", THEME_NAMES)
def test_both_svgs_stay_transparent(theme):
    """Kein gefuelltes Hintergrundrechteck, damit GitHubs Seitenton durchscheint."""
    for markup in (build_headline_svg(theme), build_portrait_svg(theme)):
        root = ET.fromstring(markup)
        backgrounds = [
            rect
            for rect in root.findall(f"{NS}rect")
            if rect.attrib.get("fill") not in (None, "none")
            and float(rect.attrib.get("width", 0)) > 300
        ]
        assert backgrounds == []

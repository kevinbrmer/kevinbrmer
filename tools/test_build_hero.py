import re
import xml.etree.ElementTree as ET

import pytest

from build_hero import HEIGHT, TOTAL_MS, WIDTH, WORDS, build_svg, caret_track, word_timeline

NS = "{http://www.w3.org/2000/svg}"


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
    values, times = caret_track()
    assert values[0] == 0.0
    assert values[-1] == 0.0
    assert times[0] == 0.0
    assert times[-1] == 1.0


def test_caret_track_is_monotonic_in_time():
    _, times = caret_track()
    assert all(b >= a for a, b in zip(times, times[1:]))


def test_caret_track_pairs_values_with_times():
    values, times = caret_track()
    assert len(values) == len(times)


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_build_svg_is_wellformed_and_sized(theme):
    root = ET.fromstring(build_svg(theme))
    assert root.attrib["viewBox"] == f"0 0 {WIDTH} {HEIGHT}"


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_build_svg_animates_every_word(theme):
    markup = build_svg(theme)
    assert markup.count("<animate") >= len(WORDS)


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_first_word_stays_visible_without_smil(theme):
    """Ignoriert eine Umgebung SMIL, muss die Rotator-Zeile trotzdem lesbar sein."""
    root = ET.fromstring(build_svg(theme))
    rect = root.find(f".//{NS}clipPath[@id='reveal0']/{NS}rect")
    assert rect is not None
    assert float(rect.attrib["width"]) > 0


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_clipped_groups_carry_no_transform(theme):
    """SVG wendet transform vor clip-path an. Traegt dasselbe Element beides,
    verschiebt sich die Maske mit und schneidet den Text komplett weg."""
    root = ET.fromstring(build_svg(theme))
    clipped = [g for g in root.iter(f"{NS}g") if "clip-path" in g.attrib]
    assert len(clipped) == len(WORDS)
    for group in clipped:
        assert "transform" not in group.attrib


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_rotator_words_use_the_theme_accent(theme):
    """Die Rotator-Zeile ist einfarbig in der Akzentfarbe des jeweiligen Themes."""
    from build_hero import THEMES

    root = ET.fromstring(build_svg(theme))
    clipped = [g for g in root.iter(f"{NS}g") if "clip-path" in g.attrib]
    assert len(clipped) == len(WORDS)
    for group in clipped:
        inner = group.find(f"{NS}g")
        assert inner.attrib["fill"] == THEMES[theme]["accent"]


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_build_svg_embeds_portrait(theme):
    markup = build_svg(theme)
    assert "data:image/png;base64," in markup


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_headline_block_is_centered_on_the_portrait(theme):
    """Die Mitte des Textblocks liegt auf der Mitte des sichtbaren Portraits."""
    from build_hero import (
        FONT_PATH,
        FRAME_H,
        FRAME_STROKE,
        FRAME_Y,
        HEADLINE_LINES,
        HEADLINE_SIZE,
        LINE_HEIGHT,
    )
    from glyphs import load_font, text_depth, text_top

    root = ET.fromstring(build_svg(theme))
    image = root.find(f"{NS}image")
    groups = [g for g in root.findall(f"{NS}g") if "transform" in g.attrib]
    baseline_y = float(groups[0].attrib["transform"].split()[-1].rstrip(")"))

    from build_hero import ICON_SIZE, ICON_TOP_GAP

    font = load_font(FONT_PATH)
    over = text_top(font, HEADLINE_LINES[0], HEADLINE_SIZE)
    under = max(text_depth(font, word, HEADLINE_SIZE) for word in WORDS)
    block_top = baseline_y - over
    block_bottom = (
        baseline_y
        + len(HEADLINE_LINES) * LINE_HEIGHT
        + under
        + ICON_TOP_GAP
        + ICON_SIZE
    )

    portrait_top = float(image.attrib["y"])
    portrait_bottom = min(
        portrait_top + float(image.attrib["height"]),
        FRAME_Y + FRAME_H - FRAME_STROKE / 2,
    )
    assert (block_top + block_bottom) / 2 == pytest.approx(
        (portrait_top + portrait_bottom) / 2, abs=0.5
    )


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_icons_are_left_aligned_with_the_headline(theme):
    """Alle Icons sitzen in einer Reihe, das erste buendig zur Textkante."""
    from build_hero import ICON_GAP, ICON_NAMES, ICON_SIZE, TEXT_X

    markup = build_svg(theme)
    # Nur die Icon-Gruppen: ihr scale hat einen einzigen Faktor, waehrend die
    # Buchstabengruppen mit "scale(x -y)" die y-Achse spiegeln.
    xs, ys = [], []
    for match in re.finditer(r"translate\(([\d.]+) ([\d.]+)\) scale\([\d.]+\)", markup):
        xs.append(float(match.group(1)))
        ys.append(float(match.group(2)))

    assert len(xs) == len(ICON_NAMES)
    assert xs[0] == pytest.approx(TEXT_X)
    assert len(set(round(y, 2) for y in ys)) == 1
    for left, right in zip(xs, xs[1:]):
        assert right - left == pytest.approx(ICON_SIZE + ICON_GAP)


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_outline_icons_keep_their_fill_none(theme):
    """Konturen-Icons brauchen das geerbte fill="none".

    Fehlt es, fallen rect, circle und path auf den schwarzen Standard-Fill
    zurueck und aus den Umrissen werden gefuellte Kloetze.
    """
    root = ET.fromstring(build_svg(theme))
    stroked = [g for g in root.iter(f"{NS}g") if "stroke" in g.attrib]
    assert stroked, "keine Kontur-Icons im SVG gefunden"
    for group in stroked:
        assert group.attrib.get("fill") == "none"


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_icons_stay_more_muted_than_the_headline(theme):
    """Die Kontaktreihe traegt ein gedaempftes Grau, nicht die Textfarbe."""
    from build_hero import THEMES

    root = ET.fromstring(build_svg(theme))
    stroked = [g for g in root.iter(f"{NS}g") if "stroke" in g.attrib]
    assert stroked
    for group in stroked:
        assert group.attrib["stroke"] == THEMES[theme]["icon"]
    assert THEMES[theme]["icon"] != THEMES[theme]["ink"]


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_svg_stays_transparent(theme):
    """Kein gefuelltes Hintergrundrechteck, damit GitHubs Seitenton durchscheint."""
    root = ET.fromstring(build_svg(theme))
    full_width = [
        rect
        for rect in root.findall(f"{NS}rect")
        if rect.attrib.get("width") == str(WIDTH)
    ]
    assert full_width == []


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_frame_is_outline_only(theme):
    """Der Rahmen ist eine reine Kontur, seine Flaeche bleibt durchsichtig."""
    root = ET.fromstring(build_svg(theme))
    frames = [r for r in root.findall(f"{NS}rect") if "stroke" in r.attrib]
    assert len(frames) == 1
    assert frames[0].attrib["fill"] == "none"


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_portrait_is_cut_at_the_frame_floor(theme):
    """Das Portrait endet an der Innenkante der unteren Rahmenlinie."""
    from build_hero import FRAME_H, FRAME_STROKE, FRAME_Y

    root = ET.fromstring(build_svg(theme))
    image = root.find(f"{NS}image")
    assert image.attrib["clip-path"] == "url(#portraitFloor)"

    rect = root.find(f".//{NS}clipPath[@id='portraitFloor']/{NS}rect")
    expected = FRAME_Y + FRAME_H - FRAME_STROKE / 2
    assert float(rect.attrib["height"]) == pytest.approx(expected)
    # Ohne Beschnitt liefe das Bild tatsaechlich tiefer, sonst waere der Test blind.
    assert float(image.attrib["y"]) + float(image.attrib["height"]) > expected


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_build_svg_has_accessible_label(theme):
    root = ET.fromstring(build_svg(theme))
    assert root.attrib["role"] == "img"
    assert "Kevin Brammer" in root.attrib["aria-label"]

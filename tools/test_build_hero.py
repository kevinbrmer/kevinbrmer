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

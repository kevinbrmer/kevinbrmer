from pathlib import Path

import pytest

from glyphs import advance_widths, load_font, text_to_path

FONT = Path(
    r"C:\Users\KB\.claude\kevin-brammer-de\output\site\public\fonts"
    r"\cabinet-grotesk\cabinet-grotesk-700.woff2"
)


@pytest.fixture(scope="module")
def font():
    return load_font(FONT)


def test_advance_widths_start_at_zero(font):
    widths = advance_widths(font, "automation", 64.0)
    assert widths[0] == 0.0


def test_advance_widths_has_one_entry_per_character_plus_start(font):
    text = "automation"
    widths = advance_widths(font, text, 64.0)
    assert len(widths) == len(text) + 1


def test_advance_widths_are_monotonic(font):
    widths = advance_widths(font, "process optimization", 64.0)
    assert all(b > a for a, b in zip(widths, widths[1:]))


def test_text_to_path_returns_positioned_groups(font):
    markup = text_to_path(font, "automation", 64.0)
    assert markup.count("<g transform=") == len("automation")
    assert "scale(" in markup


def test_space_produces_no_group_but_advances(font):
    """Das Leerzeichen zeichnet nichts, verschiebt den Cursor aber."""
    markup = text_to_path(font, "a b", 64.0)
    assert markup.count("<g transform=") == 2
    widths = advance_widths(font, "a b", 64.0)
    assert widths[2] > widths[1]

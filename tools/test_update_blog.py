import pytest

from update_blog import parse_feed, render_block, replace_block

FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item>
    <title>Workload-Routing</title>
    <link>https://kevin-brammer.de/blog/wr/</link>
    <pubDate>Fri, 25 Jul 2026 08:00:00 GMT</pubDate>
  </item>
  <item>
    <title>J-Space</title>
    <link>https://kevin-brammer.de/blog/js/</link>
    <pubDate>Fri, 18 Jul 2026 08:00:00 GMT</pubDate>
  </item>
</channel></rss>"""


def test_parse_feed_reads_all_items():
    items = parse_feed(FEED, limit=4)
    assert len(items) == 2
    assert items[0]["title"] == "Workload-Routing"
    assert items[0]["link"] == "https://kevin-brammer.de/blog/wr/"


def test_parse_feed_honors_limit():
    assert len(parse_feed(FEED, limit=1)) == 1


def test_parse_feed_formats_date_as_iso():
    assert parse_feed(FEED, limit=1)[0]["date"] == "2026-07-25"


def test_render_block_creates_one_line_per_item():
    block = render_block(parse_feed(FEED, limit=4))
    assert block.count("- [") == 2
    assert "https://kevin-brammer.de/blog/wr/" in block


def test_render_block_handles_empty_feed():
    assert render_block([]) == "_No posts yet._"


def test_replace_block_keeps_markers():
    readme = "intro\n<!-- BLOG:START -->\nold\n<!-- BLOG:END -->\noutro"
    result = replace_block(readme, "new")
    assert "<!-- BLOG:START -->" in result
    assert "<!-- BLOG:END -->" in result
    assert "old" not in result
    assert "new" in result
    assert result.startswith("intro")
    assert result.endswith("outro")


def test_replace_block_is_idempotent():
    readme = "intro\n<!-- BLOG:START -->\n<!-- BLOG:END -->\noutro"
    once = replace_block(readme, "block")
    assert replace_block(once, "block") == once


def test_replace_block_raises_when_markers_missing():
    with pytest.raises(ValueError):
        replace_block("no markers here", "new")


def test_replace_block_raises_when_markers_are_swapped():
    readme = "<!-- BLOG:END -->\n<!-- BLOG:START -->"
    with pytest.raises(ValueError):
        replace_block(readme, "new")

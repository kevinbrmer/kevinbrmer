"""Aktualisiert den Blog-Abschnitt im Profil-README aus dem RSS-Feed."""
from __future__ import annotations

import sys
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path

FEED_URL = "https://kevin-brammer.de/rss.xml"
README = Path(__file__).resolve().parent.parent / "README.md"
START = "<!-- BLOG:START -->"
END = "<!-- BLOG:END -->"
LIMIT = 4


def parse_feed(xml_text: str, limit: int = LIMIT) -> list[dict]:
    root = ET.fromstring(xml_text)
    items = []
    for item in root.findall("./channel/item")[:limit]:
        published = item.findtext("pubDate", default="")
        items.append(
            {
                "title": (item.findtext("title") or "").strip(),
                "link": (item.findtext("link") or "").strip(),
                "date": parsedate_to_datetime(published).strftime("%Y-%m-%d")
                if published
                else "",
            }
        )
    return items


def fetch_items(url: str = FEED_URL, limit: int = LIMIT) -> list[dict]:
    request = urllib.request.Request(url, headers={"User-Agent": "kevinbrmer-readme"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return parse_feed(response.read().decode("utf-8"), limit=limit)


def render_block(items: list[dict]) -> str:
    if not items:
        return "_No posts yet._"
    return "\n".join(f"- [{i['title']}]({i['link']}) — {i['date']}" for i in items)


def replace_block(readme: str, block: str) -> str:
    start = readme.find(START)
    end = readme.find(END)
    if start == -1 or end == -1 or end < start:
        raise ValueError("Marker BLOG:START / BLOG:END nicht gefunden oder vertauscht")
    return readme[: start + len(START)] + "\n" + block + "\n" + readme[end:]


def main() -> int:
    try:
        items = fetch_items()
    except Exception as error:  # Netzwerkfehler darf keinen leeren Block committen
        print(f"Feed nicht erreichbar: {error}", file=sys.stderr)
        return 1
    if not items:
        print("Feed lieferte keine Eintraege, README bleibt unveraendert", file=sys.stderr)
        return 1
    current = README.read_text(encoding="utf-8")
    updated = replace_block(current, render_block(items))
    if updated == current:
        print("Keine Aenderung")
        return 0
    README.write_text(updated, encoding="utf-8")
    print(f"{len(items)} Beitraege geschrieben")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

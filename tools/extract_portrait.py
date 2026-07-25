"""Baut aus me-website.svg ein freigestelltes Portrait-PNG.

Das Quell-SVG enthaelt zwei eingebettete Rasterbilder: das Foto und eine
Luminanz-Maske, die ueber ein <mask>-Element den Freisteller erzeugt. Beide
werden hier zu einem PNG mit Alphakanal zusammengefuehrt.
"""
from __future__ import annotations

import base64
import io
import re
from pathlib import Path

from PIL import Image

SRC = Path(r"C:\Users\KB\.claude\kevin-brammer-de\output\site\public\me-website.svg")
DST = Path(__file__).resolve().parent.parent / "assets" / "portrait.png"
TARGET_WIDTH = 480

IMAGE_PATTERN = re.compile(r'(?:xlink:)?href="data:image/(\w+);base64,([^"]+)"')


def _decode(payload: str) -> Image.Image:
    return Image.open(io.BytesIO(base64.b64decode(payload)))


def split_photo_and_mask(svg_text: str) -> tuple[Image.Image, Image.Image]:
    """Trennt Foto und Maske anhand ihrer Position relativ zum <mask>-Block."""
    matches = list(IMAGE_PATTERN.finditer(svg_text))
    if len(matches) != 2:
        raise ValueError(f"Erwartet wurden 2 eingebettete Bilder, gefunden: {len(matches)}")

    mask_start = svg_text.find("<mask")
    mask_end = svg_text.find("</mask>")
    if mask_start == -1 or mask_end == -1:
        raise ValueError("Kein <mask>-Block im SVG gefunden")

    inside = [m for m in matches if mask_start < m.start() < mask_end]
    outside = [m for m in matches if not (mask_start < m.start() < mask_end)]
    if len(inside) != 1 or len(outside) != 1:
        raise ValueError("Zuordnung von Foto und Maske ist nicht eindeutig")

    photo = _decode(outside[0].group(2)).convert("RGB")
    mask = _decode(inside[0].group(2)).convert("L")
    return photo, mask


def main() -> None:
    photo, mask = split_photo_and_mask(SRC.read_text(encoding="utf-8"))
    print(f"Foto:  {photo.width}x{photo.height}")
    print(f"Maske: {mask.width}x{mask.height}")

    if mask.size != photo.size:
        mask = mask.resize(photo.size, Image.LANCZOS)
        print(f"Maske auf Fotogroesse skaliert: {mask.width}x{mask.height}")

    cutout = photo.convert("RGBA")
    cutout.putalpha(mask)

    # Auf die tatsaechlich sichtbaren Pixel zuschneiden, damit im Hero-SVG
    # keine leeren Raender mitgerechnet werden.
    bbox = cutout.getbbox()
    if bbox:
        cutout = cutout.crop(bbox)
        print(f"Auf Inhalt zugeschnitten: {cutout.width}x{cutout.height}")

    ratio = TARGET_WIDTH / cutout.width
    resized = cutout.resize((TARGET_WIDTH, round(cutout.height * ratio)), Image.LANCZOS)
    DST.parent.mkdir(parents=True, exist_ok=True)
    resized.save(DST, format="PNG", optimize=True)

    kb = DST.stat().st_size / 1024
    print(f"{DST.name}: {resized.width}x{resized.height}, {kb:.1f} KB")
    if kb > 250:
        raise SystemExit(f"Portrait zu gross: {kb:.1f} KB (Ziel unter 250 KB)")


if __name__ == "__main__":
    main()

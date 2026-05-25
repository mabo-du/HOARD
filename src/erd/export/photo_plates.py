"""photo_plates.py — rectpack-driven photo plate layout.

Scans the project assets directory for images, packs them into A4-sized
photo plates using a 2D bin-packing algorithm (rectpack), and produces
Markdown-formatted plates suitable for inclusion in the final report.

Each plate:
    - Fills an A4 page (210 x 297 mm at 200 dpi approx 1654 x 2339 px usable)
    - Has a unique plate number and optional caption per image
    - Images are downscaled to fit the grid but never upscaled
    - Margins and gutters are configurable

exports: write_photo_plates(assets_dir, config) -> str
used_by: erd.phases.phase5  -> assemble_report()
rules:   No GPU. Uses Pillow for image dimension queries.
license: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image


# -- Plate geometry (A4 at 200 dpi, portrait) ---------------------------------

# A4 = 210 x 297 mm
# 200 DPI -> approx 1654 x 2339 px
# Subtract margins: 15 mm each side -> approx 1847 px usable height, 1417 px width
_SHEET_W = 1417  # px (210mm - 30mm margins at 200dpi)
_SHEET_H = 1847  # px (297mm - 30mm margins at 200dpi)
_GUTTER = 12     # px between images
_CAPTION_H = 30  # px reserved per caption row


def write_photo_plates(
    assets_dir: Path,
    captions: dict[str, str] | None = None,
    spatial_dir: Path | None = None,
) -> str:
    """Generate Markdown photo plates from images in assets_dir.

    Only includes images that have a corresponding Phase 2 caption JSON
    in spatial_dir (if provided), so context sheets and other non-photo
    images are excluded.

    Args:
        assets_dir: Directory to scan recursively for images.
        captions: Optional dict mapping image filename stems to captions.
        spatial_dir: Optional Phase 2 output dir. If provided, only images
                     with a matching {stem}.json caption file are included.

    Returns:
        Markdown string containing all photo plates, or empty string if no
        images found.
    """
    images = _collect_images(assets_dir, captions or {})

    # Filter to only images processed by Phase 2 (have caption JSON in spatial_dir)
    if spatial_dir and spatial_dir.is_dir():
        processed_stems = {f.stem for f in spatial_dir.glob("*.json")}
        images = [img for img in images if img.path.stem in processed_stems]

    if not images:
        return ""

    plates = _pack_plates(images)
    return _plates_to_markdown(plates)


# --- Internal helpers --------------------------------------------------------


class _ImageEntry:
    """Metadata for a single image on a photo plate."""

    def __init__(self, path: Path, caption: str, width: int, height: int):
        self.path = path
        self.caption = caption
        self.width = width
        self.height = height


def _collect_images(
    assets_dir: Path,
    captions: dict[str, str],
) -> list[_ImageEntry]:
    """Scan assets_dir for images and return _ImageEntry list."""
    entries: list[_ImageEntry] = []
    extensions = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".gif", ".webp"}

    for path in sorted(assets_dir.rglob("*")):
        if path.suffix.lower() not in extensions:
            continue
        try:
            with Image.open(path) as img:
                w, h = img.size
        except Exception:
            continue  # skip corrupt files

        stem = path.stem
        caption = captions.get(stem, captions.get(path.name, stem.replace("_", " ").title()))
        entries.append(_ImageEntry(path, caption, w, h))

    return entries


def _pack_plates(images: list[_ImageEntry]) -> list[list[_ImageEntry]]:
    """Pack images into A4 plates using rectpack algorithm.

    Returns list of plates, each plate being a list of _ImageEntry.
    """
    from rectpack import newPacker, PackingMode

    if not images:
        return []

    packer = newPacker(mode=PackingMode.Offline)

    # Add each image as a rectangle
    for idx, img in enumerate(images):
        # Scale to fit within plate width while maintaining aspect ratio
        scale = min(1.0, (_SHEET_W - _GUTTER) / img.width)
        pw = int(img.width * scale)
        ph = int(img.height * scale) + _CAPTION_H
        packer.add_rect(pw, ph, rid=idx)

    # Add enough bins (one per image maximum - actual count determined by packer)
    packer.add_bin(_SHEET_W, _SHEET_H, count=len(images))
    packer.pack()

    # Group results by bin using rect_list()
    # rect_list() returns list of (bin_id, x, y, w, h, rid)
    bin_index: dict[int, list[_ImageEntry]] = {}

    for entry in packer.rect_list():
        bin_id, _x, _y, _w, _h, rid = entry
        if rid < 0 or rid >= len(images):
            continue
        if bin_id not in bin_index:
            bin_index[bin_id] = []
        bin_index[bin_id].append(images[rid])

    plates: list[list[_ImageEntry]] = []
    for bin_id in sorted(bin_index.keys()):
        if bin_index[bin_id]:
            plates.append(bin_index[bin_id])

    # Fallback: if nothing was packed (e.g. images too large), put each in own plate
    if not plates and images:
        plates.append(list(images))

    return plates


def _plates_to_markdown(plates: list[list[_ImageEntry]]) -> str:
    """Convert packed plates into a Markdown string suitable for the report."""
    sections: list[str] = []

    for plate_num, images in enumerate(plates, start=1):
        sections.append(f"\n### Photo Plate {plate_num}\n")

        # Markdown table with 2 columns for images
        row_count = (len(images) + 1) // 2
        table_rows: list[str] = []

        for row_idx in range(row_count):
            left = images[row_idx * 2]
            right = images[row_idx * 2 + 1] if (row_idx * 2 + 1) < len(images) else None

            left_md = f"![{left.caption}]({left.path.resolve()})"
            right_md = f"![{right.caption}]({right.path.resolve()})" if right else ""

            left_cap = left.caption
            right_cap = right.caption if right else ""

            table_rows.append(f"| {left_md} | {right_md} |")
            table_rows.append(f"| **{left_cap}** | **{right_cap}** |")
            table_rows.append(f"|---|")

        sections.append("\n".join(table_rows))
        sections.append("")

    return "\n".join(sections).strip()

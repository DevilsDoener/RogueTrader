"""Render original-pixel checkbox calibration overlays and contact sheets.

The checked-in JSON is the calibration authority.  This tool deliberately
does not read geometry from the production schemas: it combines the fixed
pixel rectangles with the source artwork so reviewers can inspect every
printed marking surface independently of the responsive implementation.
"""
from __future__ import annotations

import json
import hashlib
from collections import OrderedDict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_PATH = ROOT / "tests" / "fixtures" / "checkbox-rectangles.json"
MANIFEST_PATH = ROOT / "tests" / "fixtures" / "checkbox-calibration-manifest.json"
IMAGE_DIR = ROOT / "sheets" / "static" / "sheets" / "images"
OUTPUT_DIR = ROOT / "tests" / "visual" / "checkbox-contacts"

CONTEXT_X = 42
CONTEXT_Y = 32
LABEL_HEIGHT = 22
CELL_WIDTH = 190
CELL_HEIGHT = 132
CONTACT_COLUMNS = 6
MAX_ITEMS_PER_CONTACT = 60


def _group_name(page_id: str, field_id: str) -> str:
    if page_id == "character-page-1":
        return "advances" if "_adv_" in field_id else "skills"
    if page_id == "character-page-2":
        return "advances"
    if field_id.startswith(("ship_space_", "ship_power_", "ship_weapon_capacity_")):
        return "capacity"
    return "weapon-locations"


def _font():
    return ImageFont.load_default()


def _verify_calibration_inputs():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    artifacts = [manifest["rectangle_reference"], *manifest["sources"].values()]
    for artifact in artifacts:
        path = ROOT / artifact["path"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != artifact["sha256"]:
            raise SystemExit(f"calibration input changed: {artifact['path']}")


def _render_full_overlay(page_id: str, source: Image.Image, rectangles: dict[str, list[int]]):
    overlay = source.convert("RGB")
    draw = ImageDraw.Draw(overlay)
    for rect in rectangles.values():
        left, top, right, bottom = rect
        draw.rectangle((left, top, right - 1, bottom - 1), outline=(220, 20, 20), width=2)
    overlay.save(OUTPUT_DIR / f"{page_id}-all-rectangles.png", optimize=True)


def _render_contact(
    page_id: str,
    group_name: str,
    part: int,
    source: Image.Image,
    items: list[tuple[str, list[int]]],
):
    rows = (len(items) + CONTACT_COLUMNS - 1) // CONTACT_COLUMNS
    contact = Image.new(
        "RGB",
        (CONTACT_COLUMNS * CELL_WIDTH, rows * CELL_HEIGHT),
        "white",
    )
    font = _font()

    for index, (field_id, rect) in enumerate(items):
        left, top, right, bottom = rect
        crop_box = (
            max(0, left - CONTEXT_X),
            max(0, top - CONTEXT_Y),
            min(source.width, right + CONTEXT_X),
            min(source.height, bottom + CONTEXT_Y),
        )
        crop = source.crop(crop_box).convert("RGB")
        crop_draw = ImageDraw.Draw(crop)
        crop_draw.rectangle(
            (
                left - crop_box[0],
                top - crop_box[1],
                right - crop_box[0] - 1,
                bottom - crop_box[1] - 1,
            ),
            outline=(220, 20, 20),
            width=2,
        )

        column = index % CONTACT_COLUMNS
        row = index // CONTACT_COLUMNS
        cell_left = column * CELL_WIDTH
        cell_top = row * CELL_HEIGHT
        paste_left = cell_left + (CELL_WIDTH - crop.width) // 2
        paste_top = cell_top + LABEL_HEIGHT
        contact.paste(crop, (paste_left, paste_top))
        draw = ImageDraw.Draw(contact)
        draw.text((cell_left + 4, cell_top + 4), field_id, fill="black", font=font)
        draw.rectangle(
            (cell_left, cell_top, cell_left + CELL_WIDTH - 1, cell_top + CELL_HEIGHT - 1),
            outline=(180, 180, 180),
        )

    suffix = f"-{part:02d}" if part > 1 else ""
    contact.save(OUTPUT_DIR / f"{page_id}-{group_name}{suffix}.png", optimize=True)


def main():
    _verify_calibration_inputs()
    reference = json.loads(
        REFERENCE_PATH.read_text(encoding="utf-8"),
        object_pairs_hook=OrderedDict,
    )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    rendered = 0
    for page_id, rectangles in reference.items():
        source = Image.open(IMAGE_DIR / f"{page_id}.webp").convert("RGB")
        _render_full_overlay(page_id, source, rectangles)

        groups: OrderedDict[str, list[tuple[str, list[int]]]] = OrderedDict()
        for field_id, rect in rectangles.items():
            assert 0 <= rect[0] < rect[2] <= source.width
            assert 0 <= rect[1] < rect[3] <= source.height
            groups.setdefault(_group_name(page_id, field_id), []).append((field_id, rect))
            rendered += 1

        for group_name, items in groups.items():
            for offset in range(0, len(items), MAX_ITEMS_PER_CONTACT):
                _render_contact(
                    page_id,
                    group_name,
                    offset // MAX_ITEMS_PER_CONTACT + 1,
                    source,
                    items[offset : offset + MAX_ITEMS_PER_CONTACT],
                )

    if rendered != 424:
        raise SystemExit(f"expected 424 checkbox crops, rendered {rendered}")
    print(f"Rendered {rendered} checkbox crops to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

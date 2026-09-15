"""Field-vs-artwork calibration checks.

Complements ``test_schema.py`` (structural schema validation) and
``test_assets.py`` (image sanity) with checks tying specific field rects to
the actual pixels of the background artwork they sit on top of. These guard
against calibration-drift failure modes found in manual review: a field
starting on top of its own printed label, and a characteristic value field
narrowing back off the full printed box (owner wants the value box to span
the whole box, matching WS/BS, per ``docs/charakterbogen-feld-anforderungen.md``).
"""
from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from sheets.schema import load_schema

IMAGES_DIR = Path(__file__).resolve().parent.parent / "static" / "sheets" / "images"

DARK_THRESHOLD = 130

# Fields whose printed label sits immediately to the left of (or, before
# calibration, underneath) the field's own start -- regression-tested by
# asserting no label ink remains just left of the field's current x.
LABEL_ADJACENT_FIELDS = (
    ("character-page-1", "c1_character_name"),
    ("character-page-1", "c1_description_line_1"),
)

# Characteristic value fields whose printed box contains a bonus circle in
# its left half. Both character pages now widen these to span the FULL printed
# box (matching WS/BS), deliberately covering the circle -- owner request
# (page 1: 2026-08-26; page 2: 2026-08-27). The guard below asserts they stay
# widened rather than narrowing back off the box.
FULL_BOX_VALUE_FIELDS = (
    ("character-page-2", "c2_s_value"),
    ("character-page-2", "c2_t_value"),
    ("character-page-2", "c2_ag_value"),
    ("character-page-2", "c2_int_value"),
    ("character-page-2", "c2_per_value"),
    ("character-page-2", "c2_wp_value"),
    ("character-page-2", "c2_fel_value"),
)


def _field(page_id, field_id):
    schema = load_schema(page_id)
    return next(f for f in schema.fields if f.id == field_id)


def _open_grayscale(page_id):
    return Image.open(IMAGES_DIR / f"{page_id}.webp").convert("L")


@pytest.mark.parametrize("page_id, field_id", LABEL_ADJACENT_FIELDS)
def test_field_does_not_start_on_top_of_its_own_label(page_id, field_id):
    field = _field(page_id, field_id)
    im = _open_grayscale(page_id)
    w, h = im.size

    x_px = int(w * float(field.x) / 100.0)
    y_px = h * float(field.y) / 100.0
    h_px = h * float(field.height) / 100.0
    # The label glyph body sits above the field's own baseline rule --
    # exclude the bottom 30% (the printed rule line, which is expected to
    # be dark across the field's full width) and a little above the top.
    y0 = max(0, int(y_px - h_px * 0.9))
    y1 = int(y_px + h_px * 0.7)

    margin_px = 4  # matches the .sheet-text padding-left inset
    dark_columns = [
        x
        for x in range(max(0, x_px - margin_px), x_px)
        if any(im.getpixel((x, y)) < DARK_THRESHOLD for y in range(y0, y1))
    ]
    assert not dark_columns, (
        f"{field_id}: label ink found within {margin_px}px left of field.x "
        f"({field.x}%) -- field start overlaps its own printed label"
    )


@pytest.mark.parametrize("page_id, field_id", FULL_BOX_VALUE_FIELDS)
def test_characteristic_value_field_covers_full_box(page_id, field_id):
    field = _field(page_id, field_id)
    reference = _field(page_id, "c2_ws_value")

    # WS has no bonus circle, so its value box is the reference "full box"
    # width. The circle-bearing characteristics must span essentially the same
    # width (owner request) rather than the old ~half-box, clear-of-circle
    # layout. Allow a small tolerance for the per-box printed-border spacing.
    assert float(field.width) >= float(reference.width) - 0.3, (
        f"{field_id}: width {field.width}% is narrower than the full "
        f"characteristic box (WS reference {reference.width}%) -- the value "
        f"box no longer spans the whole printed box"
    )

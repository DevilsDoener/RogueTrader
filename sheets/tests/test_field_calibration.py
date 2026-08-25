"""Field-vs-artwork calibration checks.

Complements ``test_schema.py`` (structural schema validation) and
``test_assets.py`` (image sanity) with checks tying specific field rects to
the actual pixels of the background artwork they sit on top of. These guard
against the two calibration-drift failure modes found in a manual review:
a field starting on top of its own printed label, and a characteristic
value field extending underneath its bonus circle graphic.
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

# Characteristic value fields with a printed bonus circle occupying the
# right half of their historical (pre-fix) box width.
CIRCLE_VALUE_FIELDS = (
    ("character-page-1", "c1_s_value"),
    ("character-page-1", "c1_t_value"),
    ("character-page-1", "c1_ag_value"),
    ("character-page-1", "c1_int_value"),
    ("character-page-1", "c1_per_value"),
    ("character-page-1", "c1_wp_value"),
    ("character-page-1", "c1_fel_value"),
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


@pytest.mark.parametrize("page_id, field_id", CIRCLE_VALUE_FIELDS)
def test_characteristic_value_field_stays_clear_of_bonus_circle(page_id, field_id):
    field = _field(page_id, field_id)
    im = _open_grayscale(page_id)
    w, h = im.size

    # The circle sits to the right of the field; probe a generous box
    # spanning from the field's right edge out to well past where the
    # circle is known to start, and confirm the field's own right edge
    # is comfortably left of that circle's leftmost dark boundary pixel.
    right_edge_px = w * (float(field.x) + float(field.width)) / 100.0
    y_px = int(h * (float(field.y) + float(field.height) / 2) / 100.0)
    probe_start_px = int(w * float(field.x) / 100.0)
    probe_end_px = min(w - 1, int(right_edge_px) + 80)

    circle_edge_px = None
    prev = None
    for x in range(probe_start_px, probe_end_px + 1):
        value = im.getpixel((x, y_px))
        if prev is not None and abs(value - prev) > 15 and x > probe_start_px + 5:
            circle_edge_px = x
            break
        prev = value

    assert circle_edge_px is not None, f"{field_id}: could not locate the bonus circle boundary"
    assert right_edge_px <= circle_edge_px, (
        f"{field_id}: field right edge ({right_edge_px:.1f}px) extends past the "
        f"bonus circle boundary ({circle_edge_px}px) -- typed digits would render "
        f"underneath the circle graphic"
    )

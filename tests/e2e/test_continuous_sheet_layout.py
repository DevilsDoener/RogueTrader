"""Browser contracts for the continuous, pixel-calibrated sheet viewer."""
from __future__ import annotations

import io
import json
import statistics
from pathlib import Path
from urllib.parse import unquote

import pytest
from PIL import Image, ImageChops

from sheets.schema import load_schema

from .conftest import (
    DESKTOP_VIEWPORTS,
    VIEWPORT_MINIMUM,
    VIEWPORT_WIDE,
    all_text_metrics,
    open_character,
    open_ship,
    text_metrics,
    wait_for_fit,
)

pytestmark = pytest.mark.django_db(transaction=True)

FONT_CALIBRATION = json.loads(
    (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "font-calibration.json"
    ).read_text(encoding="utf-8")
)
FONT_TARGET_RATIO = statistics.median(
    reference["glyph_height"] / reference["source_width"]
    for reference in FONT_CALIBRATION["references"]
)
SOURCE_WIDTHS = {
    reference["page_id"]: reference["source_width"]
    for reference in FONT_CALIBRATION["references"]
}


def _line_text_field_count(*page_ids):
    """Text fields rendered as bottom-anchored line text (not centred value boxes)."""
    return sum(
        1
        for page_id in page_ids
        for field in load_schema(page_id).fields
        if field.kind == "text" and field.text_style == "line"
    )


def _rendered_glyph_height_in_source_pixels(page, field_id, source_width):
    input_locator = page.locator(f'[data-field-id="{field_id}"]')
    input_locator.evaluate(
        """(input) => {
          input.closest('.sheet-canvas').style.zoom = '2';
          input.value = 'Calibration';
          input.classList.add('has-value');
        }"""
    )
    filled = Image.open(io.BytesIO(input_locator.screenshot())).convert("RGB")
    input_locator.evaluate(
        """(input) => {
          input.value = '';
          input.classList.remove('has-value');
        }"""
    )
    blank = Image.open(io.BytesIO(input_locator.screenshot())).convert("RGB")
    diff = ImageChops.difference(filled, blank).convert("L")
    mask = diff.point(lambda value: 255 if value >= 5 else 0)
    bbox = mask.getbbox()
    assert bbox is not None, field_id
    rendered_height = bbox[3] - bbox[1]
    canvas_width = input_locator.evaluate(
        "input => input.closest('.sheet-canvas').getBoundingClientRect().width"
    )
    return rendered_height / canvas_width * source_width


@pytest.mark.parametrize("viewport", DESKTOP_VIEWPORTS)
def test_character_pages_form_one_continuous_scrollable_document(
    page, live_server, owner, character_factory, viewport
):
    page.set_viewport_size(viewport)
    open_character(page, live_server, owner, character_factory)

    pages = page.locator('.sheet-page[data-page-id^="character-page-"]')
    assert pages.count() == 2
    assert pages.nth(0).is_visible()
    assert pages.nth(1).is_visible()
    assert page.locator("#sheet-page-tabs, .sheet-page-tab").count() == 0

    geometry = pages.evaluate_all(
        """(items) => {
          const first = items[0].getBoundingClientRect();
          const second = items[1].getBoundingClientRect();
          return {
            gap: second.top - first.bottom,
            page2BelowPage1: second.top >= first.bottom,
            page2StartsBelowFold: second.top > window.innerHeight,
            documentScrollable: document.documentElement.scrollHeight > window.innerHeight,
          };
        }"""
    )
    assert geometry["page2BelowPage1"]
    assert geometry["gap"] > 0
    assert geometry["page2StartsBelowFold"]
    assert geometry["documentScrollable"]

    pages.nth(1).scroll_into_view_if_needed()
    assert page.evaluate("window.scrollY") > 0
    assert pages.nth(1).is_visible()


def test_tab_order_crosses_from_character_page_1_to_page_2(
    page, live_server, owner, character_factory
):
    open_character(page, live_server, owner, character_factory)
    page_1_inputs = page.locator(
        '.sheet-page[data-page-id="character-page-1"] .sheet-input'
    )
    page_2_inputs = page.locator(
        '.sheet-page[data-page-id="character-page-2"] .sheet-input'
    )
    last_page_1 = page_1_inputs.last.get_attribute("data-field-id")
    first_page_2 = page_2_inputs.first.get_attribute("data-field-id")

    page.focus(f'[data-field-id="{last_page_1}"]')
    page.keyboard.press("Tab")

    assert page.evaluate("document.activeElement.dataset.fieldId") == first_page_2


@pytest.mark.parametrize("viewport", DESKTOP_VIEWPORTS)
def test_every_text_input_is_bottom_aligned_and_uses_the_shared_size(
    page, live_server, owner, character_factory, ship_sheet, viewport
):
    page.set_viewport_size(viewport)
    open_character(page, live_server, owner, character_factory)
    character_metrics = all_text_metrics(page)
    # Every text field except the centred value boxes (their text_style is not
    # "line") is bottom-anchored; the count follows the schema, not a literal.
    assert len(character_metrics) == _line_text_field_count(
        "character-page-1", "character-page-2"
    )

    page.goto(f"{live_server.url}/ships/{ship_sheet.id}/")
    page.wait_for_selector('[data-field-id="ship_name"]')
    ship_metrics = all_text_metrics(page)
    assert len(ship_metrics) == _line_text_field_count("ship-page")

    all_metrics = character_metrics + ship_metrics
    normalized_sizes = [item["fontSize"] / item["canvasWidth"] for item in all_metrics]
    assert max(normalized_sizes) - min(normalized_sizes) <= 0.00005

    for item in all_metrics:
        assert item["bottomDelta"] <= 0.5, item["id"]
        assert item["fontFamily"].split(",")[0].strip(' "') == "Times New Roman", item["id"]
        assert item["inputHeight"] <= item["fontSize"] * 1.5, item["id"]


@pytest.mark.parametrize(
    ("sheet", "field_id", "value"),
    (
        ("character", "c1_rank", "R9"),
        ("character", "c2_wounds_critical_damage", "99"),
        ("ship", "ship_weapon_1_damage", "9"),
    ),
)
def test_filled_text_line_box_scales_and_fits_at_desktop_widths(
    page, live_server, owner, character_factory, ship_sheet, sheet, field_id, value
):
    if sheet == "character":
        open_character(
            page, live_server, owner, character_factory, values={field_id: value}
        )
    else:
        open_ship(page, live_server, owner, ship_sheet, values={field_id: value})

    measurements = {}
    for viewport in DESKTOP_VIEWPORTS:
        page.set_viewport_size(viewport)
        wait_for_fit(page)
        measurements[viewport["width"]] = text_metrics(page, field_id)

    for viewport_width, metrics in measurements.items():
        context = f"{field_id} at desktop width {viewport_width}px"
        assert metrics["value"] == value, context
        assert metrics["color"] != "rgba(0, 0, 0, 0)", context
        # Text fits inside its box (rendered space).
        assert metrics["renderedLineHeight"] <= metrics["contentHeight"] + 0.5, context
        assert metrics["scrollHeight"] <= metrics["clientHeight"] + 1, context

    narrow = measurements[VIEWPORT_MINIMUM["width"]]
    wide = measurements[VIEWPORT_WIDE["width"]]
    # The single canvas transform scales the rendered text with the sheet:
    # a wider rendered canvas renders proportionally larger text.
    assert narrow["fontSize"] < wide["fontSize"], field_id
    assert wide["fontSize"] / narrow["fontSize"] == pytest.approx(
        wide["canvasWidth"] / narrow["canvasWidth"], rel=0.15
    ), field_id


@pytest.mark.parametrize(
    ("page_id", "field_id"),
    (
        ("character-page-1", "c1_character_name"),
        ("character-page-2", "c2_weapon_1_name"),
        ("ship-page", "ship_name"),
    ),
)
def test_rendered_times_glyph_height_matches_the_normalized_source_median(
    page,
    live_server,
    owner,
    character_factory,
    ship_sheet,
    page_id,
    field_id,
):
    page.set_viewport_size(VIEWPORT_WIDE)
    if page_id == "ship-page":
        open_ship(page, live_server, owner, ship_sheet)
    else:
        open_character(page, live_server, owner, character_factory)
    page.wait_for_selector(f'[data-field-id="{field_id}"]')

    source_width = SOURCE_WIDTHS[page_id]
    actual_source_pixels = _rendered_glyph_height_in_source_pixels(
        page, field_id, source_width
    )
    expected_source_pixels = FONT_TARGET_RATIO * source_width
    assert actual_source_pixels == pytest.approx(expected_source_pixels, abs=2), (
        page_id,
        actual_source_pixels,
        expected_source_pixels,
    )


def test_checked_checkbox_renders_an_inset_x(page, live_server, owner, character_factory):
    # A square cell. The "Adv. Taken" pips (c1_ws_adv_1 etc.) are round and fill
    # their box -- covered by the round-fill test below. Page 2 has only pip
    # checkboxes, so it is not in this square-cell contract.
    field_id = "c1_skill_acrobatics_basic"
    page.set_viewport_size(VIEWPORT_WIDE)
    open_character(page, live_server, owner, character_factory, values={field_id: True})

    checkbox = page.locator(f'[data-field-id="{field_id}"]')
    assert checkbox.is_visible()
    checkbox.scroll_into_view_if_needed()
    style = checkbox.evaluate(
        """(input) => {
          const style = getComputedStyle(input);
          return {
            appearance: style.appearance,
            backgroundColor: style.backgroundColor,
            backgroundImage: style.backgroundImage,
            backgroundPosition: style.backgroundPosition,
            backgroundSize: style.backgroundSize,
          };
        }"""
    )
    assert checkbox.is_checked()
    assert style["appearance"] == "none"
    assert style["backgroundColor"] in ("rgba(0, 0, 0, 0)", "transparent")
    assert "M2 2L18 18M18 2L2 18" in unquote(style["backgroundImage"])
    assert "%3Crect" not in style["backgroundImage"]
    assert style["backgroundPosition"] == "50% 50%"
    assert style["backgroundSize"] == "70% 70%"

    checked = Image.open(io.BytesIO(checkbox.screenshot())).convert("RGB")
    checkbox.evaluate("input => { input.checked = false; }")
    unchecked = Image.open(io.BytesIO(checkbox.screenshot())).convert("RGB")
    delta = ImageChops.difference(checked, unchecked)
    delta_mask = delta.convert("L").point(lambda value: 255 if value >= 5 else 0)
    delta_bbox = delta_mask.getbbox()
    assert delta_bbox is not None, field_id

    left, top, right, bottom = delta_bbox
    assert left >= 1 and top >= 1, field_id
    assert right <= checked.width - 1 and bottom <= checked.height - 1, field_id
    delta_center = ((left + right) / 2, (top + bottom) / 2)
    checkbox_center = (checked.width / 2, checked.height / 2)
    assert abs(delta_center[0] - checkbox_center[0]) <= checked.width * 0.15, field_id
    assert abs(delta_center[1] - checkbox_center[1]) <= checked.height * 0.15, field_id

    border_mask = Image.new("L", checked.size, 0)
    for x in range(checked.width):
        border_mask.putpixel((x, 0), 255)
        border_mask.putpixel((x, checked.height - 1), 255)
    for y in range(checked.height):
        border_mask.putpixel((0, y), 255)
        border_mask.putpixel((checked.width - 1, y), 255)
    assert ImageChops.multiply(delta_mask, border_mask).getbbox() is None, field_id

    black_pixels = [
        (x, y)
        for y in range(checked.height)
        for x in range(checked.width)
        if (lambda rgb: max(rgb) <= 40)(checked.getpixel((x, y)))
    ]
    assert black_pixels, field_id
    assert min(x for x, _y in black_pixels) >= 1, field_id
    assert min(y for _x, y in black_pixels) >= 1, field_id
    assert max(x for x, _y in black_pixels) <= checked.width - 2, field_id
    assert max(y for _x, y in black_pixels) <= checked.height - 2, field_id


@pytest.mark.parametrize(
    ("page_id", "field_id"),
    (
        ("character-page-1", "c1_ws_adv_1"),
        ("character-page-2", "c2_ws_adv_1"),
    ),
)
def test_checked_advancement_pip_renders_a_round_fill(
    page, live_server, owner, character_factory, page_id, field_id
):
    page.set_viewport_size(VIEWPORT_WIDE)
    open_character(page, live_server, owner, character_factory, values={field_id: True})

    pip = page.locator(f'[data-field-id="{field_id}"]')
    assert pip.is_visible(), page_id
    pip.scroll_into_view_if_needed()
    style = pip.evaluate(
        """(el) => {
          const s = getComputedStyle(el);
          const image = decodeURIComponent(s.backgroundImage);
          return {
            appearance: s.appearance,
            backgroundSize: s.backgroundSize,
            diagonalCross: image.includes('M2 2L18 18M18 2L2 18'),
            filledCircle: image.includes('<circle')
          };
        }"""
    )
    assert pip.is_checked()
    assert style["appearance"] == "none"
    assert style["backgroundSize"] == "100% 100%"
    assert style["diagonalCross"] is False
    assert style["filledCircle"] is True

    checked = Image.open(io.BytesIO(pip.screenshot())).convert("RGB")
    pip.evaluate("el => { el.checked = false; }")
    unchecked = Image.open(io.BytesIO(pip.screenshot())).convert("RGB")
    delta_bbox = (
        ImageChops.difference(checked, unchecked)
        .convert("L")
        .point(lambda v: 255 if v >= 5 else 0)
        .getbbox()
    )
    assert delta_bbox is not None, field_id
    left, top, right, bottom = delta_bbox
    w, h = checked.width, checked.height
    # A round fill spans the printed circle but leaves its corners clear.
    assert (right - left) + 1 >= w * 0.85 and (bottom - top) + 1 >= h * 0.85, field_id
    for corner in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        assert max(checked.getpixel(corner)) > 60, (field_id, corner)

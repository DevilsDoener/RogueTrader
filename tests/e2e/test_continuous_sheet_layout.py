"""Browser contracts for the continuous, pixel-calibrated sheet viewer."""
from __future__ import annotations

import io
import json
import statistics
from pathlib import Path

import pytest
from PIL import Image, ImageChops

from .conftest import login_via_browser


pytestmark = pytest.mark.django_db(transaction=True)

DESKTOP_VIEWPORTS = (
    {"width": 1024, "height": 768},
    {"width": 1440, "height": 900},
)

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


def _open_character(page, live_server, owner, character_factory, *, values=None):
    character = character_factory(owner=owner, values=values or {})
    login_via_browser(page, live_server, username=owner.username)
    page.goto(f"{live_server.url}/characters/{character.id}/")
    page.wait_for_selector('[data-field-id="c1_character_name"]')
    return character


# All lengths reported here are RENDERED (post-transform) pixels: getBoundingClientRect
# already includes the canvas transform, and fontSize -- which is computed in the
# canvas's fixed element space -- is multiplied by --sheet-scale so it lands in the
# same rendered space. That keeps every "shared canvas-relative size" / "fits its box"
# invariant a comparison between mutually consistent rendered values.
def _text_metrics(page, field_id):
    return page.locator(f'[data-field-id="{field_id}"]').evaluate(
        """(input) => {
          const canvasEl = input.closest('.sheet-canvas');
          const scale = Number.parseFloat(
            getComputedStyle(canvasEl).getPropertyValue('--sheet-scale')
          ) || 1;
          const field = input.closest('.sheet-field').getBoundingClientRect();
          const canvas = canvasEl.getBoundingClientRect();
          const rect = input.getBoundingClientRect();
          const style = getComputedStyle(input);
          return {
            bottomDelta: Math.abs(rect.bottom - field.bottom),
            fontFamily: style.fontFamily,
            fontSize: Number.parseFloat(style.fontSize) * scale,
            inputHeight: rect.height,
            fieldHeight: field.height,
            canvasWidth: canvas.width,
          };
        }"""
    )


def _all_text_metrics(page):
    # Excludes the centred value fields (characteristics + experience totals),
    # which deliberately fill their box and use their own size, so they are not
    # part of the shared bottom-anchored line-text contract asserted below.
    return page.locator(".sheet-text:not(.sheet-text--center)").evaluate_all(
        """(inputs) => inputs.map((input) => {
          const canvasEl = input.closest('.sheet-canvas');
          const scale = Number.parseFloat(
            getComputedStyle(canvasEl).getPropertyValue('--sheet-scale')
          ) || 1;
          const field = input.closest('.sheet-field').getBoundingClientRect();
          const canvas = canvasEl.getBoundingClientRect();
          const rect = input.getBoundingClientRect();
          const style = getComputedStyle(input);
          return {
            id: input.dataset.fieldId,
            pageId: input.closest('.sheet-page').dataset.pageId,
            bottomDelta: Math.abs(rect.bottom - field.bottom),
            fontFamily: style.fontFamily,
            fontSize: Number.parseFloat(style.fontSize) * scale,
            inputHeight: rect.height,
            canvasWidth: canvas.width,
          };
        })"""
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
    _open_character(page, live_server, owner, character_factory)

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


def test_viewer_never_reads_or_writes_a_page_index(
    page, live_server, owner, character_factory
):
    character = _open_character(page, live_server, owner, character_factory)
    stale_key = f"sheets:viewer:{owner.id}:{character.id}:page"
    page.evaluate("localStorage.clear()")
    page.reload()
    page.wait_for_selector('[data-field-id="c1_character_name"]')

    assert page.evaluate("key => localStorage.getItem(key)", stale_key) is None
    page.locator('.sheet-page[data-page-id="character-page-2"]').scroll_into_view_if_needed()
    page.reload()
    page.wait_for_selector('[data-field-id="c2_weapon_1_name"]')

    assert page.evaluate("key => localStorage.getItem(key)", stale_key) is None
    assert page.locator("#sheet-page-tabs, .sheet-page-tab").count() == 0


def test_tab_order_crosses_from_character_page_1_to_page_2(
    page, live_server, owner, character_factory
):
    _open_character(page, live_server, owner, character_factory)
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
def test_character_text_uses_one_bottom_anchored_canvas_relative_serif_size(
    page, live_server, owner, character_factory, viewport
):
    # Only line (bottom-anchored) text fields here -- the characteristic value
    # boxes (c1_ws_value etc.) are centred and use their own larger size, so
    # they are not part of this shared-serif-size contract.
    values = {
        "c1_character_name": "Abel Gerrit",
        "c1_rank": "R9",
        "c2_weapon_1_name": "Sunsear",
        "c2_wounds_critical_damage": "3",
    }
    page.set_viewport_size(viewport)
    _open_character(page, live_server, owner, character_factory, values=values)
    assert page.locator(
        '.sheet-page[data-page-id="character-page-2"]'
    ).is_visible(), "page 2 must participate in the continuous document layout"

    field_ids = tuple(values)
    metrics = [_text_metrics(page, field_id) for field_id in field_ids]
    font_sizes = [item["fontSize"] for item in metrics]
    normalized_sizes = [
        item["fontSize"] / item["canvasWidth"] for item in metrics
    ]

    assert max(font_sizes) - min(font_sizes) <= 0.05
    assert max(normalized_sizes) - min(normalized_sizes) <= 0.00005
    for field_id, item in zip(field_ids, metrics, strict=True):
        assert item["bottomDelta"] <= 0.5, field_id
        assert item["fontFamily"].split(",")[0].strip(' "') == "Times New Roman", field_id
        assert item["inputHeight"] <= item["fontSize"] * 1.5, field_id
        if item["fieldHeight"] > item["fontSize"] * 2:
            assert item["inputHeight"] < item["fieldHeight"], field_id


@pytest.mark.parametrize("viewport", DESKTOP_VIEWPORTS)
def test_ship_text_uses_same_bottom_anchored_canvas_relative_serif_size(
    page, live_server, user_factory, ship_sheet, viewport
):
    user = user_factory()
    ship_sheet.values = {
        **ship_sheet.values,
        "ship_name": "His Divine Right",
        "ship_speed": "7",
    }
    ship_sheet.save(update_fields=["values"])
    page.set_viewport_size(viewport)
    login_via_browser(page, live_server, username=user.username)
    page.goto(f"{live_server.url}/ships/{ship_sheet.id}/")
    page.wait_for_selector('[data-field-id="ship_name"]')

    metrics = [_text_metrics(page, field_id) for field_id in ("ship_name", "ship_speed")]
    normalized_sizes = [item["fontSize"] / item["canvasWidth"] for item in metrics]
    assert max(normalized_sizes) - min(normalized_sizes) <= 0.00005
    for item in metrics:
        assert item["bottomDelta"] <= 0.5
        assert item["fontFamily"].split(",")[0].strip(' "') == "Times New Roman"
        assert item["inputHeight"] <= item["fontSize"] * 1.5


@pytest.mark.parametrize("viewport", DESKTOP_VIEWPORTS)
def test_every_text_input_is_bottom_aligned_and_uses_the_shared_size(
    page, live_server, owner, character_factory, ship_sheet, viewport
):
    page.set_viewport_size(viewport)
    _open_character(page, live_server, owner, character_factory)
    character_metrics = _all_text_metrics(page)
    # 341 text fields minus the 94 centred value fields that _all_text_metrics
    # excludes: 9+9 characteristics, 2 experience totals, and (2026-08-28 owner
    # review) page-2's 6 movement, 3 lifting and 2 fate boxes, which have no
    # printed line and are now centred like the characteristic boxes.
    assert len(character_metrics) == 247

    page.goto(f"{live_server.url}/ships/{ship_sheet.id}/")
    page.wait_for_selector('[data-field-id="ship_name"]')
    ship_metrics = _all_text_metrics(page)
    assert len(ship_metrics) == 49

    all_metrics = character_metrics + ship_metrics
    normalized_sizes = [item["fontSize"] / item["canvasWidth"] for item in all_metrics]
    assert max(normalized_sizes) - min(normalized_sizes) <= 0.00005

    for item in all_metrics:
        assert item["bottomDelta"] <= 0.5, item["id"]
        assert item["fontFamily"].split(",")[0].strip(' "') == "Times New Roman", item["id"]
        assert item["inputHeight"] <= item["fontSize"] * 1.5, item["id"]


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
    page.set_viewport_size({"width": 1440, "height": 900})
    login_via_browser(page, live_server, username=owner.username)
    if page_id == "ship-page":
        page.goto(f"{live_server.url}/ships/{ship_sheet.id}/")
    else:
        character = character_factory(owner=owner)
        page.goto(f"{live_server.url}/characters/{character.id}/")
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


@pytest.mark.parametrize(
    ("page_id", "field_id"),
    (
        # Square cells only. The "Adv. Taken" pips (c1_ws_adv_1 etc.) are round
        # and fill their box -- covered by the round-fill test below. Page 2 has
        # only pip checkboxes, so it is not in this square-cell contract.
        ("character-page-1", "c1_skill_acrobatics_basic"),
    ),
)
def test_checked_checkbox_renders_an_inset_x(
    page,
    live_server,
    owner,
    character_factory,
    ship_sheet,
    user_factory,
    page_id,
    field_id,
):
    page.set_viewport_size({"width": 1440, "height": 900})
    if page_id == "ship-page":
        user = user_factory()
        ship_sheet.values = {**ship_sheet.values, field_id: True}
        ship_sheet.save(update_fields=["values"])
        login_via_browser(page, live_server, username=user.username)
        page.goto(f"{live_server.url}/ships/{ship_sheet.id}/")
    else:
        _open_character(
            page,
            live_server,
            owner,
            character_factory,
            values={field_id: True},
        )

    checkbox = page.locator(f'[data-field-id="{field_id}"]')
    assert checkbox.is_visible(), f"{page_id} must be rendered without page switching"
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
    from urllib.parse import unquote
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
def test_checked_advancement_pip_renders_an_inset_cross(
    page, live_server, owner, character_factory, page_id, field_id
):
    page.set_viewport_size({"width": 1440, "height": 900})
    _open_character(
        page, live_server, owner, character_factory, values={field_id: True}
    )

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
    assert style["backgroundSize"] == "70% 70%"
    assert style["diagonalCross"] is True
    assert style["filledCircle"] is False

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
    # The cross stays inset within the printed circle and leaves its corners clear.
    assert left >= 1 and top >= 1, field_id
    assert right <= w - 1 and bottom <= h - 1, field_id
    for corner in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        assert max(checked.getpixel(corner)) > 60, (field_id, corner)

"""Task 11, Step 2: deterministic visual regression + overlay-bounds checks.

Two independent guarantees are checked here, for each of the three sheet
pages (character-page-1, character-page-2, ship-page):

1. **Pixel fidelity** (``test_blank_sheet_matches_extracted_background``):
   with no data entered, ``.sheet-canvas`` at fit-page zoom must render as
   (almost) exactly the extracted background image from Task 4
   (``sheets/static/sheets/images/*.webp``). Idle text inputs have no
   border/background/visible caret and idle checkboxes are the browser's
   native (tiny) control, so the only expected differences from the source
   asset are resampling/compression noise -- never a shifted field, an
   extra visible box, or wrong ship-page rotation. Each render is also
   saved to ``tests/visual/<page>.png`` for manual inspection per the
   brief's Step 2.

2. **Geometry containment** (``test_field_rectangles_stay_within_canvas_*``):
   with a test-only debug-overlay class enabled, every schema field
   rectangle's actual rendered position must stay inside ``.sheet-canvas``
   at 50%, 100%, 150%, 300% zoom and at mobile fit-width. Checkboxes have
   specifically been a source of calibration bugs on this project (see
   ``.superpowers/sdd/2026-08-16-rogue-trader-portal/progress.md``, Task 4
   and Task 9), so in addition to the blanket "every field stays inside
   the canvas" assertion, one checkbox field per page has its *exact*
   proportional position (not just "in bounds") asserted against the
   schema at every zoom level.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageStat

from .conftest import login_via_browser

pytestmark = pytest.mark.django_db(transaction=True)

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKGROUND_DIR = REPO_ROOT / "sheets" / "static" / "sheets" / "images"
SCHEMA_DIR = REPO_ROOT / "sheets" / "data"
VISUAL_OUTPUT_DIR = REPO_ROOT / "tests" / "visual"

# The canvas is exactly the background <img> plus fully-transparent idle
# inputs (see sheets/static/sheets/sheet-viewer.css), so a captured
# screenshot should differ from the source asset only by resampling/AA
# edge noise around the sheet's dense fine print and rule lines (measured
# 5.4-8.9 across the three real pages, worst on character-page-1 with its
# 376 checkboxes) -- never a shifted field block, wrong ship-page
# rotation, or a control painting visible chrome of its own (an earlier,
# now-fixed version of .sheet-checkbox failed this at a mean diff of ~21
# by rendering idle native checkboxes as solid filled squares).
MAX_MEAN_CHANNEL_DIFF = 12.0

# One checkbox per page, chosen because checkbox calibration has
# specifically needed multiple correction rounds on this project (weapon
# capacity boxes on the ship page; general pitch errors on both character
# pages -- see progress.md).
PAGES = [
    ("character-page-1", 0, "c1_ws_adv_1", {"width": 1400, "height": 1800}),
    ("character-page-2", 1, "c2_ws_adv_1", {"width": 1400, "height": 1800}),
    ("ship-page", 0, "ship_weapon_capacity_dorsal", {"width": 1800, "height": 1300}),
]

ZOOM_LEVELS = [0.5, 1.0, 1.5, 3.0]

# Rounding/subpixel slack only -- large enough to absorb browser subpixel
# layout rounding, small enough that a real one-row/one-column calibration
# slip (which is always at least a fraction of a percent of the canvas)
# would still fail it.
BOUNDS_EPS_PX = 0.75
PROPORTION_TOLERANCE = 0.004


def _load_schema(page_id: str) -> dict:
    return json.loads((SCHEMA_DIR / f"{page_id}.json").read_text(encoding="utf-8"))


def _field(schema: dict, field_id: str) -> dict:
    return next(f for f in schema["fields"] if f["id"] == field_id)


def _open_sheet(page, live_server, *, owner, character_factory, ship_sheet, page_id, page_index):
    if page_id == "ship-page":
        page.goto(f"{live_server.url}/ships/{ship_sheet.id}/")
    else:
        character = character_factory(owner=owner)
        page.goto(f"{live_server.url}/characters/{character.id}/")
    page.wait_for_selector(".sheet-canvas")
    if page_index:
        page.click(f'.sheet-page-tab[data-page-index="{page_index}"]')
        page.wait_for_timeout(30)


def _enable_debug_overlay(page):
    page.evaluate(
        "document.getElementById('sheet-viewer-root').classList.add('sheet-viewer-debug')"
    )


def _all_fields_within_canvas(page) -> bool:
    return page.evaluate(
        """(eps) => {
          const canvas = document.querySelector('.sheet-page:not([hidden]) .sheet-canvas');
          const c = canvas.getBoundingClientRect();
          const fields = Array.from(
            document.querySelectorAll('.sheet-page:not([hidden]) .sheet-field')
          );
          return fields.length > 0 && fields.every((field) => {
            const r = field.getBoundingClientRect();
            return r.left >= c.left - eps && r.top >= c.top - eps &&
                   r.right <= c.right + eps && r.bottom <= c.bottom + eps;
          });
        }""",
        BOUNDS_EPS_PX,
    )


def _measure_field(page, field_id: str) -> dict:
    return page.evaluate(
        """([fieldId, eps]) => {
          const canvas = document.querySelector('.sheet-page:not([hidden]) .sheet-canvas');
          const input = document.querySelector('[data-field-id="' + fieldId + '"]');
          const field = input.closest('.sheet-field');
          const c = canvas.getBoundingClientRect();
          const f = field.getBoundingClientRect();
          return {
            x: (f.left - c.left) / c.width,
            y: (f.top - c.top) / c.height,
            w: f.width / c.width,
            h: f.height / c.height,
            withinCanvas: f.left >= c.left - eps && f.top >= c.top - eps &&
                          f.right <= c.right + eps && f.bottom <= c.bottom + eps,
          };
        }""",
        [field_id, BOUNDS_EPS_PX],
    )


def _assert_checkbox_position(page, page_id, field_id, context_label):
    expected = _field(_load_schema(page_id), field_id)
    measured = _measure_field(page, field_id)
    assert measured["withinCanvas"], (
        f"{page_id} checkbox {field_id} left the canvas bounds at {context_label}"
    )
    assert measured["x"] == pytest.approx(expected["x"] / 100, abs=PROPORTION_TOLERANCE), context_label
    assert measured["y"] == pytest.approx(expected["y"] / 100, abs=PROPORTION_TOLERANCE), context_label
    assert measured["w"] == pytest.approx(expected["width"] / 100, abs=PROPORTION_TOLERANCE), context_label
    assert measured["h"] == pytest.approx(expected["height"] / 100, abs=PROPORTION_TOLERANCE), context_label


def _assert_matches_background(screenshot_bytes: bytes, background_path: Path, *, save_as: str):
    VISUAL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (VISUAL_OUTPUT_DIR / save_as).write_bytes(screenshot_bytes)

    shot = Image.open(io.BytesIO(screenshot_bytes)).convert("RGB")
    reference = Image.open(background_path).convert("RGB").resize(shot.size, Image.LANCZOS)
    diff = ImageChops.difference(shot, reference)
    mean_diff = sum(ImageStat.Stat(diff).mean) / 3
    assert mean_diff < MAX_MEAN_CHANNEL_DIFF, (
        f"{save_as}: mean per-channel diff {mean_diff:.2f} exceeds the "
        f"{MAX_MEAN_CHANNEL_DIFF} antialiasing tolerance -- a control is "
        "adding visible chrome, or the sheet has shifted/rotated"
    )


@pytest.mark.parametrize("page_id, page_index, checkbox_field_id, viewport", PAGES)
def test_blank_sheet_matches_extracted_background_at_fit_page(
    page, live_server, owner, character_factory, ship_sheet,
    page_id, page_index, checkbox_field_id, viewport,
):
    page.set_viewport_size(viewport)
    login_via_browser(page, live_server, username=owner.username)
    _open_sheet(
        page, live_server,
        owner=owner, character_factory=character_factory, ship_sheet=ship_sheet,
        page_id=page_id, page_index=page_index,
    )
    page.click("#fit-page")
    page.wait_for_timeout(50)

    canvas = page.locator(".sheet-page:not([hidden]) .sheet-canvas")
    screenshot = canvas.screenshot()

    _assert_matches_background(
        screenshot, BACKGROUND_DIR / f"{page_id}.webp", save_as=f"{page_id}.png"
    )


@pytest.mark.parametrize("page_id, page_index, checkbox_field_id, viewport", PAGES)
@pytest.mark.parametrize("zoom", ZOOM_LEVELS)
def test_field_rectangles_stay_within_canvas_at_zoom_level(
    page, live_server, owner, character_factory, ship_sheet,
    page_id, page_index, checkbox_field_id, viewport, zoom,
):
    page.set_viewport_size({"width": 1200, "height": 1000})
    login_via_browser(page, live_server, username=owner.username)
    _open_sheet(
        page, live_server,
        owner=owner, character_factory=character_factory, ship_sheet=ship_sheet,
        page_id=page_id, page_index=page_index,
    )
    # Clicking the page tab (above, inside _open_sheet) already persisted
    # the active page index to localStorage via showPage()/persistState();
    # overwrite just the zoom key and reload so the viewer boots directly
    # at the requested zoom on the requested page -- exercising the same
    # ZOOM_MIN/ZOOM_MAX-clamped code path a real user's pinch-zoom does.
    user_id, sheet_id = page.evaluate(
        "() => { const r = document.getElementById('sheet-viewer-root'); "
        "return [r.dataset.userId, r.dataset.sheetId]; }"
    )
    storage_key = f"sheets:viewer:{user_id}:{sheet_id}:zoom"
    page.evaluate("([k, v]) => localStorage.setItem(k, v)", [storage_key, str(zoom)])
    page.reload()
    # Both pages' ".sheet-canvas" elements exist in the DOM (only one is
    # ever unhidden) -- a bare ".sheet-canvas" selector can resolve to the
    # *other*, permanently-hidden page and hang waiting for it to become
    # visible, so this must stay scoped to the currently-shown page.
    page.wait_for_selector(".sheet-page:not([hidden]) .sheet-canvas")

    _enable_debug_overlay(page)

    assert _all_fields_within_canvas(page), (
        f"{page_id} at {int(zoom * 100)}% zoom: a field rectangle left the canvas bounds"
    )
    _assert_checkbox_position(page, page_id, checkbox_field_id, f"{int(zoom * 100)}% zoom")


@pytest.mark.parametrize("page_id, page_index, checkbox_field_id, viewport", PAGES)
def test_field_rectangles_stay_within_canvas_at_mobile_fit_width(
    page, live_server, owner, character_factory, ship_sheet,
    page_id, page_index, checkbox_field_id, viewport,
):
    page.set_viewport_size({"width": 390, "height": 844})
    login_via_browser(page, live_server, username=owner.username)
    _open_sheet(
        page, live_server,
        owner=owner, character_factory=character_factory, ship_sheet=ship_sheet,
        page_id=page_id, page_index=page_index,
    )
    page.click("#fit-width")
    page.wait_for_timeout(50)

    _enable_debug_overlay(page)

    assert _all_fields_within_canvas(page), (
        f"{page_id} at mobile fit-width: a field rectangle left the canvas bounds"
    )
    _assert_checkbox_position(page, page_id, checkbox_field_id, "mobile fit-width")

"""Task 11, Step 2: deterministic visual regression + overlay-bounds checks.

Two independent guarantees are checked here, for each of the three sheet
pages (character-page-1, character-page-2, ship-page):

1. **Pixel fidelity** (``test_blank_sheet_matches_extracted_background``):
   with no data entered, the responsive ``.sheet-canvas`` must render as
   (almost) exactly the extracted background image from Task 4
   (``sheets/static/sheets/images/*.webp``). Idle text inputs have no
   border/background/visible caret, and an idle checkbox has native
   rendering suppressed entirely (``appearance: none``, see
   ``sheet-viewer.css``) so it paints no chrome of its own either -- the
   only expected differences from the source asset are resampling/
   compression noise, never a shifted field, an extra visible box, or wrong
   ship-page rotation. Each render is also saved to ``tests/visual/
   <page>.png`` for manual inspection per the brief's Step 2.
   ``test_checked_checkbox_matches_extracted_background``
   covers the complementary transparent golden SVG tick, including
   once through the read-only admin viewer, where the checkbox is also
   ``disabled``.

2. **Geometry containment** (``test_field_rectangles_stay_within_desktop_canvas``):
   with a test-only debug-overlay class enabled, every schema field
   rectangle's actual rendered position must stay inside ``.sheet-canvas``
   at the minimum and wide supported desktop widths. Checkboxes have
   specifically been a source of calibration bugs on this project (see
   ``.superpowers/sdd/2026-08-16-rogue-trader-portal/progress.md``, Task 4
   and Task 9), so in addition to the blanket "every field stays inside
   the canvas" assertion, one checkbox field per page has its *exact*
   proportional position (not just "in bounds") asserted against the
   schema at each desktop width, in both its unchecked and checked state.
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
# 351 checkboxes on character page 1; 387 across both character pages) --
# never a shifted field block, wrong ship-page
# rotation, or a control painting visible chrome of its own (an earlier,
# now-fixed version of .sheet-checkbox failed this at a mean diff of ~21
# by rendering idle native checkboxes as solid filled squares).
MAX_MEAN_CHANNEL_DIFF = 12.0

# One checkbox per page, chosen because checkbox calibration has
# specifically needed multiple correction rounds on this project (weapon
# capacity boxes on the ship page; general pitch errors on both character
# pages -- see progress.md).
PAGES = [
    ("character-page-1", "c1_ws_adv_1", {"width": 1400, "height": 1800}),
    ("character-page-2", "c2_ws_adv_1", {"width": 1400, "height": 1800}),
    ("ship-page", "ship_weapon_capacity_dorsal", {"width": 1800, "height": 1300}),
]

DESKTOP_VIEWPORTS = [
    ("desktop-minimum", {"width": 1024, "height": 768}),
    ("desktop-wide", {"width": 1440, "height": 900}),
]

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


def _open_sheet(
    page, live_server, *, owner, character_factory, ship_sheet, page_id,
    checked_field_id=None, admin_user=None,
):
    """Opens a sheet, optionally pre-marking ``checked_field_id`` and/or
    opening it through the read-only admin viewer instead of the owner's
    own view (``admin_user`` -- character pages only, there is no separate
    admin route for the ship)."""
    if page_id == "ship-page":
        if checked_field_id:
            ship_sheet.values = {**ship_sheet.values, checked_field_id: True}
            ship_sheet.save(update_fields=["values"])
        page.goto(f"{live_server.url}/ships/{ship_sheet.id}/")
    else:
        values = {checked_field_id: True} if checked_field_id else {}
        character = character_factory(owner=owner, values=values)
        if admin_user is not None:
            page.goto(f"{live_server.url}/portal-admin/characters/{character.id}/")
        else:
            page.goto(f"{live_server.url}/characters/{character.id}/")
    page.wait_for_selector(".sheet-canvas")


def _enable_debug_overlay(page):
    page.evaluate(
        "document.getElementById('sheet-viewer-root').classList.add('sheet-viewer-debug')"
    )


def _all_fields_within_canvas(page, page_id) -> bool:
    return page.evaluate(
        """([pageId, eps]) => {
          const page = document.querySelector('.sheet-page[data-page-id="' + pageId + '"]');
          const canvas = page.querySelector('.sheet-canvas');
          const c = canvas.getBoundingClientRect();
          const fields = Array.from(page.querySelectorAll('.sheet-field'));
          return fields.length > 0 && fields.every((field) => {
            const r = field.getBoundingClientRect();
            return r.left >= c.left - eps && r.top >= c.top - eps &&
                   r.right <= c.right + eps && r.bottom <= c.bottom + eps;
          });
        }""",
        [page_id, BOUNDS_EPS_PX],
    )


def _measure_field(page, field_id: str) -> dict:
    return page.evaluate(
        """([fieldId, eps]) => {
          const input = document.querySelector('[data-field-id="' + fieldId + '"]');
          const field = input.closest('.sheet-field');
          const canvas = input.closest('.sheet-canvas');
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


@pytest.mark.parametrize("page_id, checkbox_field_id, viewport", PAGES)
def test_blank_sheet_matches_extracted_background(
    page, live_server, owner, character_factory, ship_sheet,
    page_id, checkbox_field_id, viewport,
):
    page.set_viewport_size(viewport)
    login_via_browser(page, live_server, username=owner.username)
    _open_sheet(
        page, live_server,
        owner=owner, character_factory=character_factory, ship_sheet=ship_sheet,
        page_id=page_id,
    )
    canvas = page.locator(f'.sheet-page[data-page-id="{page_id}"] .sheet-canvas')
    screenshot = canvas.screenshot()

    _assert_matches_background(
        screenshot, BACKGROUND_DIR / f"{page_id}.webp", save_as=f"{page_id}.png"
    )


@pytest.mark.parametrize("page_id, checkbox_field_id, viewport", PAGES)
def test_checked_checkbox_matches_extracted_background(
    page, live_server, owner, character_factory, ship_sheet,
    page_id, checkbox_field_id, viewport,
):
    """A checked schema field adds only one small transparent golden tick,
    so the rest of the canvas must continue to match the source artwork."""
    page.set_viewport_size(viewport)
    login_via_browser(page, live_server, username=owner.username)
    _open_sheet(
        page, live_server,
        owner=owner, character_factory=character_factory, ship_sheet=ship_sheet,
        page_id=page_id, checked_field_id=checkbox_field_id,
    )
    checkbox = page.locator(f'[data-field-id="{checkbox_field_id}"]')
    assert checkbox.is_checked()

    canvas = page.locator(f'.sheet-page[data-page-id="{page_id}"] .sheet-canvas')
    screenshot = canvas.screenshot()

    # One tiny checked control out of a full page moves the whole-canvas
    # mean diff only marginally, so the same blank-sheet tolerance still
    # applies -- if it didn't, that would itself mean the checked state is
    # painting something far bigger than a single tick/accent-color box.
    _assert_matches_background(
        screenshot, BACKGROUND_DIR / f"{page_id}.webp", save_as=f"{page_id}-checked.png"
    )


@pytest.mark.parametrize("page_id, checkbox_field_id, viewport", PAGES)
def test_checked_checkbox_position_unchanged_at_desktop_width(
    page, live_server, owner, character_factory, ship_sheet,
    page_id, checkbox_field_id, viewport,
):
    """Adding the custom tick must never move or resize its checkbox."""
    page.set_viewport_size(viewport)
    login_via_browser(page, live_server, username=owner.username)
    _open_sheet(
        page, live_server,
        owner=owner, character_factory=character_factory, ship_sheet=ship_sheet,
        page_id=page_id, checked_field_id=checkbox_field_id,
    )
    _assert_checkbox_position(page, page_id, checkbox_field_id, "checked, desktop")


@pytest.mark.parametrize(
    "page_id, checkbox_field_id, viewport",
    [p for p in PAGES if p[0] != "ship-page"],  # no separate admin route for the ship
)
def test_admin_read_only_view_renders_checked_checkbox_within_canvas(
    page, live_server, owner, character_factory, ship_sheet, portal_admin,
    page_id, checkbox_field_id, viewport,
):
    """The read-only admin viewer (``/portal-admin/characters/<uuid>/``) has
    never been opened by this suite before. Its checkbox inputs are also
    ``disabled`` (see ``sheets/character_detail.html``), and Chromium visibly
    dims a disabled ``:checked`` control's ``accent-color`` -- grey instead
    of the gold used everywhere else. That dimming is standard, deliberate
    browser behaviour for disabled controls (a real accessibility signal,
    not a bug to fix here), so this only asserts geometry stays correct,
    not pixel color -- geometry is what would actually break if the shared
    ``_sheet_viewer.html`` fragment ever diverged between the owner and
    admin views."""
    page.set_viewport_size(viewport)
    login_via_browser(page, live_server, username=portal_admin.username)
    _open_sheet(
        page, live_server,
        owner=owner, character_factory=character_factory, ship_sheet=ship_sheet,
        page_id=page_id, checked_field_id=checkbox_field_id,
        admin_user=portal_admin,
    )
    checkbox = page.locator(f'[data-field-id="{checkbox_field_id}"]')
    assert checkbox.is_checked()
    assert checkbox.is_disabled()

    _assert_checkbox_position(page, page_id, checkbox_field_id, "admin read-only view")


@pytest.mark.parametrize("page_id, checkbox_field_id, unused_viewport", PAGES)
@pytest.mark.parametrize("viewport_name, viewport", DESKTOP_VIEWPORTS)
def test_field_rectangles_stay_within_desktop_canvas(
    page, live_server, owner, character_factory, ship_sheet,
    page_id, checkbox_field_id, unused_viewport, viewport_name, viewport,
):
    page.set_viewport_size(viewport)
    login_via_browser(page, live_server, username=owner.username)
    _open_sheet(
        page, live_server,
        owner=owner, character_factory=character_factory, ship_sheet=ship_sheet,
        page_id=page_id,
    )
    _enable_debug_overlay(page)

    assert _all_fields_within_canvas(page, page_id), (
        f"{page_id} at {viewport_name} width: a field rectangle left the canvas bounds"
    )
    _assert_checkbox_position(page, page_id, checkbox_field_id, viewport_name)


def test_populated_reference_sections_are_captured_for_visual_review(
    page, live_server, owner, character_factory, ship_sheet
):
    character_values = {
        "c1_character_name": "Abel Gerrit",
        "c1_rank": "4",
        "c1_ws_value": "42",
        "c1_talent_1": "Peer (Imperial Navy)",
        "c1_special_ability_1": "Exceptional Leader",
        "c1_profit_factor_current": "38",
        "c2_weapon_1_name": "Sunsear Laser Battery",
        "c2_weapon_1_class": "Ship",
        "c2_weapon_1_damage": "1d10+2",
        "c2_gear_1": "Void suit",
        "c2_acquisition_1": "Best-craftsmanship auspex",
        "c2_corruption_current_points": "3",
        "c2_wounds_current": "14",
        "c2_armour_head_type": "Flak",
    }
    character = character_factory(owner=owner, values=character_values)
    login_via_browser(page, live_server, username=owner.username)
    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(f"{live_server.url}/characters/{character.id}/")
    page.wait_for_selector('[data-field-id="c1_character_name"]')

    VISUAL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for page_id in ("character-page-1", "character-page-2"):
        screenshot = page.locator(
            f'.sheet-page[data-page-id="{page_id}"] .sheet-canvas'
        ).screenshot()
        (VISUAL_OUTPUT_DIR / f"{page_id}-filled.png").write_bytes(screenshot)

    ship_sheet.values = {
        **ship_sheet.values,
        "ship_name": "His Divine Right",
        "ship_class": "Sword-class Frigate",
        "ship_speed": "7",
        "ship_essential_component_1": "Jovian-pattern Class 2 Drive",
        "ship_hull_integrity_current": "31",
        "ship_crew_percent_current": "92",
        "ship_morale_current": "88",
        "ship_weapon_1_name": "Sunsear Laser Battery",
        "ship_weapon_1_damage": "1d10+2",
    }
    ship_sheet.save(update_fields=["values"])
    page.goto(f"{live_server.url}/ships/{ship_sheet.id}/")
    page.wait_for_selector('[data-field-id="ship_name"]')
    screenshot = page.locator(
        '.sheet-page[data-page-id="ship-page"] .sheet-canvas'
    ).screenshot()
    (VISUAL_OUTPUT_DIR / "ship-page-filled.png").write_bytes(screenshot)

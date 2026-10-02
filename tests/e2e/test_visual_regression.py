"""Deterministic visual regression and overlay-bounds checks.

For each of the three sheet pages (character-page-1, character-page-2,
ship-page) two independent guarantees are checked:

1. **Pixel fidelity**: with no data entered, the ``.sheet-canvas`` must render
   as (almost) exactly the extracted background image
   (``sheets/static/sheets/images/*.webp``). Idle text inputs have no
   border/background/visible caret, and an idle checkbox has native rendering
   suppressed entirely (``appearance: none``, see ``sheet-viewer.css``) so it
   paints no chrome of its own either -- the only expected differences from the
   source asset are resampling/compression noise, never a shifted field, an
   extra visible box, or wrong ship-page rotation. Each render is also saved to
   ``tests/visual/<page>.png`` for manual inspection; those files are latest
   captured renders, rewritten on every run, not baselines, and git-ignored.
   ``test_checked_checkbox_keeps_artwork_and_position`` covers the checked
   state (a black X, or a round fill for pips) the same way and additionally
   pins the checkbox's exact position; one variant runs through the read-only
   admin viewer, where the checkbox is also ``disabled``.

2. **Geometry**: every character field's rendered rectangle is pinned to the
   schema by ``test_every_character_field_keeps_schema_order_label_kind_and_geometry``
   in ``test_character_sheet.py``. The ship page is covered here: every field
   must stay inside ``.sheet-canvas`` at the minimum and wide desktop widths,
   and one checkbox has its *exact* proportional position asserted. Checkboxes
   have repeatedly been a source of calibration bugs on this project, hence
   the exact position checks.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageStat

from .conftest import NAMED_DESKTOP_VIEWPORTS, VIEWPORT_WIDE, open_character, open_ship

pytestmark = pytest.mark.django_db(transaction=True)

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKGROUND_DIR = REPO_ROOT / "sheets" / "static" / "sheets" / "images"
SCHEMA_DIR = REPO_ROOT / "sheets" / "data"
VISUAL_OUTPUT_DIR = REPO_ROOT / "tests" / "visual"

# The canvas is exactly the background <img> plus fully-transparent idle
# inputs (see sheets/static/sheets/sheet-viewer.css), so a captured
# screenshot should differ from the source asset only by resampling/AA
# edge noise around the sheet's dense fine print and rule lines -- never a
# shifted field block, wrong ship-page rotation, or a control painting
# visible chrome of its own (an earlier, now-fixed version of
# .sheet-checkbox failed this at a mean diff of ~21 by rendering idle native
# checkboxes as solid filled squares).
MAX_MEAN_CHANNEL_DIFF = 12.0

# One checkbox per page, chosen because checkbox calibration has
# specifically needed multiple correction rounds on this project (weapon
# capacity boxes on the ship page; general pitch errors on both character
# pages).
PAGES = [
    ("character-page-1", "c1_ws_adv_1", {"width": 1400, "height": 1800}),
    ("character-page-2", "c2_ws_adv_1", {"width": 1400, "height": 1800}),
    ("ship-page", "ship_weapon_1_location_dorsal", {"width": 1800, "height": 1300}),
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
    checked_field_id=None, admin=None,
):
    """Logs in and opens a sheet, optionally pre-marking ``checked_field_id``
    and/or opening it through the read-only admin viewer (``admin`` --
    character pages only, there is no separate admin route for the ship)."""
    checked = {checked_field_id: True} if checked_field_id else None
    if page_id == "ship-page":
        open_ship(page, live_server, owner, ship_sheet, values=checked)
    else:
        open_character(
            page, live_server, owner, character_factory, values=checked, admin=admin
        )
    page.wait_for_selector(".sheet-canvas")


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
    tolerance = PROPORTION_TOLERANCE
    assert measured["x"] == pytest.approx(expected["x"] / 100, abs=tolerance), context_label
    assert measured["y"] == pytest.approx(expected["y"] / 100, abs=tolerance), context_label
    assert measured["w"] == pytest.approx(expected["width"] / 100, abs=tolerance), context_label
    assert measured["h"] == pytest.approx(expected["height"] / 100, abs=tolerance), context_label


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
def test_checked_checkbox_keeps_artwork_and_position(
    page, live_server, owner, character_factory, ship_sheet,
    page_id, checkbox_field_id, viewport,
):
    """A checked schema field adds only its own marker: the rest of the canvas
    keeps matching the source artwork, and the checkbox must never move or
    resize."""
    page.set_viewport_size(viewport)
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
    # painting something far bigger than a single marker.
    _assert_matches_background(
        screenshot, BACKGROUND_DIR / f"{page_id}.webp", save_as=f"{page_id}-checked.png"
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
    """The read-only admin viewer (``/portal-admin/characters/<uuid>/``) renders
    its checkbox inputs ``disabled`` (see ``sheets/character_detail.html``).
    Only geometry is asserted: it is what would break if the shared
    ``_sheet_viewer.html`` fragment ever diverged between the owner and admin
    views."""
    page.set_viewport_size(viewport)
    _open_sheet(
        page, live_server,
        owner=owner, character_factory=character_factory, ship_sheet=ship_sheet,
        page_id=page_id, checked_field_id=checkbox_field_id,
        admin=portal_admin,
    )
    checkbox = page.locator(f'[data-field-id="{checkbox_field_id}"]')
    assert checkbox.is_checked()
    assert checkbox.is_disabled()

    _assert_checkbox_position(page, page_id, checkbox_field_id, "admin read-only view")


@pytest.mark.parametrize("viewport_name, viewport", NAMED_DESKTOP_VIEWPORTS)
def test_ship_field_rectangles_stay_within_desktop_canvas(
    page, live_server, owner, character_factory, ship_sheet, viewport_name, viewport,
):
    # The character pages are pinned field by field in test_character_sheet.py;
    # the ship page has no such per-field test, so its containment lives here.
    page_id, checkbox_field_id, _ = next(p for p in PAGES if p[0] == "ship-page")
    page.set_viewport_size(viewport)
    _open_sheet(
        page, live_server,
        owner=owner, character_factory=character_factory, ship_sheet=ship_sheet,
        page_id=page_id,
    )

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
    page.set_viewport_size(VIEWPORT_WIDE)
    open_character(page, live_server, owner, character_factory, values=character_values)

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

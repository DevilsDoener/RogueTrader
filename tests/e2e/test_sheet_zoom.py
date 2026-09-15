"""Browser contracts for the sheet viewer's zoom control."""
from __future__ import annotations

import pytest

from .conftest import login_via_browser

pytestmark = pytest.mark.django_db(transaction=True)


def _open_character(page, live_server, owner, character_factory):
    character = character_factory(owner=owner, values={})
    login_via_browser(page, live_server, username=owner.username)
    page.goto(f"{live_server.url}/characters/{character.id}/")
    page.wait_for_selector('[data-field-id="c1_character_name"]')
    return character


# The viewer scales via a single transform on .sheet-canvas (not a wrapper
# width). The effective zoom is therefore the rendered canvas width as a
# fraction of the available column width: canvasWidth = wrapperWidth * zoom/100.
def _rendered_zoom_percent(page):
    return page.evaluate(
        """() => {
          const wrapper = document.getElementById('sheet-canvas-wrapper');
          const canvas = document.querySelector('.sheet-page .sheet-canvas');
          return Math.round(canvas.getBoundingClientRect().width / wrapper.clientWidth * 100);
        }"""
    )


def _rendered_canvas_width(page):
    return page.evaluate(
        "() => document.querySelector('.sheet-page .sheet-canvas').getBoundingClientRect().width"
    )


def test_zoom_out_button_shrinks_canvas_and_updates_label(
    page, live_server, owner, character_factory
):
    _open_character(page, live_server, owner, character_factory)

    assert page.locator("#sheet-zoom-level").inner_text() == "100%"
    before = _rendered_canvas_width(page)

    page.click(".sheet-zoom-out")

    assert page.locator("#sheet-zoom-level").inner_text() == "90%"
    after = _rendered_canvas_width(page)
    assert after < before
    assert _rendered_zoom_percent(page) == 90


def _checkbox_position_in_canvas(page, field_id):
    # Where the checkbox sits as a fraction of the canvas box. Uses
    # getBoundingClientRect for both, so the ratio is what the user actually
    # sees on screen at the current zoom.
    return page.locator(f'[data-field-id="{field_id}"]').evaluate(
        """(input) => {
          const canvas = input.closest('.sheet-canvas').getBoundingClientRect();
          const box = input.getBoundingClientRect();
          return {
            x: (box.left - canvas.left) / canvas.width,
            y: (box.top - canvas.top) / canvas.height,
            w: box.width / canvas.width,
            h: box.height / canvas.height,
          };
        }"""
    )


def test_checkbox_stays_locked_to_artwork_across_zoom(
    page, live_server, owner, character_factory
):
    # Direct regression for the reported bug: "when you change the zoom the
    # checkboxes shift". Because one transform scales the whole calibrated
    # layer as a unit, a checkbox's position relative to the artwork must be
    # identical at every zoom level, not merely close.
    _open_character(page, live_server, owner, character_factory)

    at_100 = _checkbox_position_in_canvas(page, "c1_ws_adv_1")

    for _ in range(5):  # 100% -> 50%
        page.click(".sheet-zoom-out")
    assert page.locator("#sheet-zoom-level").inner_text() == "50%"
    at_50 = _checkbox_position_in_canvas(page, "c1_ws_adv_1")

    for axis in ("x", "y", "w", "h"):
        assert at_50[axis] == pytest.approx(at_100[axis], abs=0.0005), axis


def test_zoom_cannot_go_below_30_or_above_100_percent(
    page, live_server, owner, character_factory
):
    _open_character(page, live_server, owner, character_factory)

    for _ in range(7):  # 100% down to 30% in 10% steps
        page.click(".sheet-zoom-out")
    assert page.locator("#sheet-zoom-level").inner_text() == "30%"
    assert page.locator(".sheet-zoom-out").is_disabled()

    for _ in range(7):  # 30% back up to 100% in 10% steps
        page.click(".sheet-zoom-in")
    assert page.locator("#sheet-zoom-level").inner_text() == "100%"
    assert page.locator(".sheet-zoom-in").is_disabled()


def test_ctrl_minus_and_ctrl_zero_shortcuts_control_zoom(
    page, live_server, owner, character_factory
):
    _open_character(page, live_server, owner, character_factory)

    page.keyboard.press("Control+-")
    assert page.locator("#sheet-zoom-level").inner_text() == "90%"

    page.keyboard.press("Control+-")
    assert page.locator("#sheet-zoom-level").inner_text() == "80%"

    page.keyboard.press("Control+0")
    assert page.locator("#sheet-zoom-level").inner_text() == "100%"


def test_zoom_level_persists_across_reload(page, live_server, owner, character_factory):
    _open_character(page, live_server, owner, character_factory)

    page.click(".sheet-zoom-out")
    page.click(".sheet-zoom-out")
    assert page.locator("#sheet-zoom-level").inner_text() == "80%"

    page.reload()
    page.wait_for_selector('[data-field-id="c1_character_name"]')

    assert page.locator("#sheet-zoom-level").inner_text() == "80%"
    assert _rendered_zoom_percent(page) == 80


def test_zoom_control_is_present_on_read_only_admin_view(
    page, live_server, portal_admin, owner, character_factory
):
    character = character_factory(owner=owner, values={})
    login_via_browser(page, live_server, username=portal_admin.username)
    page.goto(f"{live_server.url}/portal-admin/characters/{character.id}/")
    page.wait_for_selector('[data-field-id="c1_character_name"]')

    assert page.locator("#sheet-zoom-level").inner_text() == "100%"
    page.click(".sheet-zoom-out")
    assert page.locator("#sheet-zoom-level").inner_text() == "90%"

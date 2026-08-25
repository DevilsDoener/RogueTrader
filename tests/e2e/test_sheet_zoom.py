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


def _wrapper_zoom_percent(page):
    return page.locator("#sheet-canvas-wrapper").evaluate(
        "el => Math.round(parseFloat(getComputedStyle(el).getPropertyValue('--sheet-zoom')) * 100)"
    )


def test_zoom_out_button_shrinks_canvas_and_updates_label(
    page, live_server, owner, character_factory
):
    _open_character(page, live_server, owner, character_factory)

    assert page.locator("#sheet-zoom-level").inner_text() == "100%"
    before = page.locator("#sheet-canvas-wrapper").bounding_box()["width"]

    page.click(".sheet-zoom-out")

    assert page.locator("#sheet-zoom-level").inner_text() == "90%"
    after = page.locator("#sheet-canvas-wrapper").bounding_box()["width"]
    assert after < before
    assert _wrapper_zoom_percent(page) == 90


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
    assert _wrapper_zoom_percent(page) == 80


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

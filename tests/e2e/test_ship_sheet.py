"""Playwright end-to-end concurrency tests for the shared ship sheet.

Unlike the character sheet (owned by a single user), the ship is mutated by
every authenticated user, so these tests drive two independent browser
contexts (``page``/``second_page`` -- see ``tests/e2e/conftest.py``) logged
in as two different users against the same ``ShipSheet`` row, matching how
the feature is actually used at the table.
"""
from __future__ import annotations

import pytest

from .conftest import login_via_browser

pytestmark = pytest.mark.django_db(transaction=True)

DESKTOP_TEXT_VIEWPORTS = [
    {"width": 1024, "height": 768},
    {"width": 1440, "height": 900},
]


def _wait_saved(page):
    page.wait_for_function(
        "document.getElementById('sheet-save-status').textContent === 'Gespeichert'",
        timeout=5000,
    )


def test_ship_viewer_has_no_zoom_controls_or_transform(
    page, live_server, user_factory, ship_sheet
):
    user = user_factory()
    login_via_browser(page, live_server, username=user.username)
    page.evaluate("localStorage.clear()")
    page.goto(f"{live_server.url}/ships/{ship_sheet.id}/")
    page.wait_for_selector('[data-field-id="ship_name"]')

    assert page.locator(".sheet-toolbar-zoom").count() == 0
    assert page.locator("#zoom-in, #zoom-out, #fit-width, #fit-page").count() == 0
    assert page.evaluate(
        "getComputedStyle(document.querySelector('.sheet-canvas-wrapper')).transform"
    ) == "none"

    zoom_key = f"sheets:viewer:{user.id}:{ship_sheet.id}:zoom"
    assert page.evaluate("key => localStorage.getItem(key)", zoom_key) is None


def test_filled_ship_text_line_box_scales_and_fits_at_desktop_widths(
    page, live_server, user_factory, ship_sheet
):
    user = user_factory()
    ship_sheet.values = {"ship_weapon_1_damage": "9"}
    ship_sheet.save(update_fields=["values"])
    login_via_browser(page, live_server, username=user.username)
    page.goto(f"{live_server.url}/ships/{ship_sheet.id}/")

    measurements = {}
    for viewport in DESKTOP_TEXT_VIEWPORTS:
        page.set_viewport_size(viewport)
        measurements[viewport["width"]] = page.locator(
            '[data-field-id="ship_weapon_1_damage"]'
        ).evaluate(
            """(input) => {
              const style = getComputedStyle(input);
              const rect = input.getBoundingClientRect();
              const px = (value) => Number.parseFloat(value) || 0;
              return {
                value: input.value,
                color: style.color,
                fontSize: px(style.fontSize),
                lineHeight: px(style.lineHeight),
                contentHeight: rect.height
                  - px(style.paddingTop) - px(style.paddingBottom)
                  - px(style.borderTopWidth) - px(style.borderBottomWidth),
                clientHeight: input.clientHeight,
                scrollHeight: input.scrollHeight,
                canvasWidth: input.closest('.sheet-canvas').getBoundingClientRect().width,
              };
            }"""
        )

    for viewport_width, metrics in measurements.items():
        context = f"ship_weapon_1_damage at desktop width {viewport_width}px"
        assert metrics["value"] == "9", context
        assert metrics["color"] != "rgba(0, 0, 0, 0)", context
        assert metrics["lineHeight"] <= metrics["contentHeight"] + 0.5, context
        assert metrics["scrollHeight"] <= metrics["clientHeight"] + 1, context

    narrow = measurements[1024]
    wide = measurements[1440]
    assert narrow["fontSize"] < wide["fontSize"]
    assert wide["fontSize"] / narrow["fontSize"] == pytest.approx(
        wide["canvasWidth"] / narrow["canvasWidth"], rel=0.15
    )


def test_different_field_edits_from_two_browsers_merge(
    page, second_page, live_server, user_factory, ship_sheet
):
    first_user = user_factory()
    second_user = user_factory()

    login_via_browser(page, live_server, username=first_user.username)
    page.goto(f"{live_server.url}/ships/{ship_sheet.id}/")
    page.wait_for_selector('[data-field-id="ship_name"]')

    login_via_browser(second_page, live_server, username=second_user.username)
    second_page.goto(f"{live_server.url}/ships/{ship_sheet.id}/")
    second_page.wait_for_selector('[data-field-id="ship_speed"]')

    name_field = page.locator('[data-field-id="ship_name"]')
    name_field.fill("Rosinante")
    name_field.blur()
    _wait_saved(page)

    speed_field = second_page.locator('[data-field-id="ship_speed"]')
    speed_field.fill("7")
    speed_field.blur()
    _wait_saved(second_page)

    # Both edits must have gone through even though they raced against each
    # other on different fields of the same shared sheet.
    page.reload()
    page.wait_for_selector('[data-field-id="ship_name"]')
    assert page.input_value('[data-field-id="ship_name"]') == "Rosinante"
    assert page.input_value('[data-field-id="ship_speed"]') == "7"


def test_same_field_conflict_shown_to_second_saver_and_reload_shows_accepted_value(
    page, second_page, live_server, user_factory, ship_sheet
):
    first_user = user_factory()
    second_user = user_factory()

    login_via_browser(page, live_server, username=first_user.username)
    page.goto(f"{live_server.url}/ships/{ship_sheet.id}/")
    page.wait_for_selector('[data-field-id="ship_class"]')

    login_via_browser(second_page, live_server, username=second_user.username)
    second_page.goto(f"{live_server.url}/ships/{ship_sheet.id}/")
    second_page.wait_for_selector('[data-field-id="ship_class"]')

    # Both browsers loaded the field at base_version 0. The first browser
    # saves first and wins outright.
    first_field = page.locator('[data-field-id="ship_class"]')
    first_field.fill("Frigate")
    first_field.blur()
    _wait_saved(page)

    # The second browser still thinks base_version is 0, so its save on the
    # same field must conflict rather than silently overwrite the winner.
    second_field = second_page.locator('[data-field-id="ship_class"]')
    second_field.fill("Cruiser")
    second_field.blur()

    panel = second_page.locator(".sheet-conflict-panel")
    panel.wait_for(timeout=5000)
    assert panel.locator("text=Aktuellen Wert übernehmen").count() == 1
    assert panel.locator("text=Meinen Wert erneut speichern").count() == 1

    panel.locator("text=Aktuellen Wert übernehmen").click()
    assert second_page.input_value('[data-field-id="ship_class"]') == "Frigate"

    # A reload on either browser must show the value that actually won.
    page.reload()
    page.wait_for_selector('[data-field-id="ship_class"]')
    assert page.input_value('[data-field-id="ship_class"]') == "Frigate"

    second_page.reload()
    second_page.wait_for_selector('[data-field-id="ship_class"]')
    assert second_page.input_value('[data-field-id="ship_class"]') == "Frigate"


def test_history_attributes_each_edit_to_the_correct_actor(
    page, second_page, live_server, user_factory, ship_sheet
):
    first_user = user_factory()
    second_user = user_factory()

    login_via_browser(page, live_server, username=first_user.username)
    page.goto(f"{live_server.url}/ships/{ship_sheet.id}/")
    page.wait_for_selector('[data-field-id="ship_name"]')
    name_field = page.locator('[data-field-id="ship_name"]')
    name_field.fill("Rosinante")
    name_field.blur()
    _wait_saved(page)

    login_via_browser(second_page, live_server, username=second_user.username)
    second_page.goto(f"{live_server.url}/ships/{ship_sheet.id}/")
    second_page.wait_for_selector('[data-field-id="ship_speed"]')
    speed_field = second_page.locator('[data-field-id="ship_speed"]')
    speed_field.fill("7")
    speed_field.blur()
    _wait_saved(second_page)

    page.goto(f"{live_server.url}/ships/{ship_sheet.id}/history/")
    page.wait_for_selector("#ship-history-table")
    history_text = page.content()
    assert first_user.username in history_text
    assert second_user.username in history_text
    # Neither value is present until a row is expanded.
    assert "Rosinante" not in history_text

    row = page.locator(f'tr[data-change-id]:has-text("{second_user.username}")').first
    row.locator(".ship-history-expand").click()
    page.wait_for_function(
        "el => el.nextElementSibling && !el.nextElementSibling.hidden "
        "&& el.nextElementSibling.innerText.includes('Nachher')",
        arg=row.element_handle(),
        timeout=5000,
    )
    detail_text = row.evaluate("row => row.nextElementSibling.innerText")
    assert "7" in detail_text

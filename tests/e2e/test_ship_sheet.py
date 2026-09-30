"""Playwright end-to-end tests for the shared ship sheet.

Unlike the character sheet (owned by a single user), the ship is mutated by
every authenticated user, so the concurrency tests drive two independent
browser contexts (``page``/``second_page`` -- see ``tests/e2e/conftest.py``)
logged in as two different users against the same ``ShipSheet`` row, matching
how the feature is actually used at the table.
"""
from __future__ import annotations

import pytest

from .conftest import login_via_browser, open_ship, wait_saved

pytestmark = pytest.mark.django_db(transaction=True)

# True while the rendered text of a ship field fits the printed area, the same
# check the viewer's own shrink-to-fit applies.
_TEXT_FITS_JS = """id => {
  const el = document.querySelector('[data-field-id="' + id + '"]');
  const style = getComputedStyle(el);
  const context = document.createElement('canvas').getContext('2d');
  context.font = style.font;
  return context.measureText(el.value).width
    <= el.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight) + 1;
}"""


def test_ship_viewer_scrolls_with_the_document(page, live_server, user_factory, ship_sheet):
    open_ship(page, live_server, user_factory(), ship_sheet)

    assert page.evaluate(
        "getComputedStyle(document.querySelector('.sheet-canvas-wrapper')).transform"
    ) == "none"


@pytest.mark.parametrize("width", [1024, 1440])
def test_ship_values_fit_and_enlarged_markers_save(
    page, live_server, user_factory, ship_sheet, width
):
    damage_ids = [f"ship_weapon_{n}_damage" for n in range(1, 5)]
    page.set_viewport_size({"width": width, "height": 1000})
    open_ship(
        page,
        live_server,
        user_factory(),
        ship_sheet,
        values={damage_id: "1d10+2" for damage_id in damage_ids},
    )
    for damage_id in damage_ids:
        page.locator(f'[data-field-id="{damage_id}"]').scroll_into_view_if_needed()
        page.wait_for_function(_TEXT_FITS_JS, arg=damage_id, timeout=3000)

    resource_ids = (
        "ship_space_available",
        "ship_space_used",
        "ship_power_available",
        "ship_power_used",
        *(
            f"ship_weapon_capacity_{side}"
            for side in ("dorsal", "prow", "keel", "port", "starboard")
        ),
    )
    for field_id in resource_ids:
        field = page.locator(f'[data-field-id="{field_id}"]')
        field.fill("12")
        field.blur()
        wait_saved(page)

    # Clicking the printed label, away from the small dot, toggles only this marker.
    page.locator('label[for="field-ship_weapon_1_type_macro_battery"]').click(
        position={"x": 3, "y": 2}
    )
    wait_saved(page)
    assert page.locator('[data-field-id="ship_weapon_1_type_macro_battery"]').is_checked()
    assert not page.locator('[data-field-id="ship_weapon_1_type_lance"]').is_checked()

    # Every enlarged region must resolve to its own marker, including row edges.
    for hit_label in page.locator(".sheet-pip-hit").all():
        hit_label.scroll_into_view_if_needed()
        assert hit_label.evaluate(
            """label => {
              const r = label.getBoundingClientRect();
              return [[0.15, 0.5], [0.85, 0.5]].every(([x, y]) => {
                const el = document.elementFromPoint(r.left + r.width * x, r.top + r.height * y);
                return el === label || el.id === label.htmlFor;
              });
            }"""
        )

    damage = page.locator('[data-field-id="ship_weapon_1_damage"]')
    damage.fill("2d10+12")
    damage.blur()
    wait_saved(page)

    page.reload()
    assert page.locator('[data-field-id="ship_weapon_1_damage"]').input_value() == "2d10+12"
    assert page.locator('[data-field-id="ship_space_available"]').input_value() == "12"
    assert page.locator('[data-field-id="ship_weapon_capacity_dorsal"]').input_value() == "12"
    assert page.locator('[data-field-id="ship_weapon_1_type_macro_battery"]').is_checked()
    page.wait_for_function(_TEXT_FITS_JS, arg="ship_weapon_1_damage")


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
    wait_saved(page)

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


def test_different_field_edits_merge_and_history_attributes_each_to_its_actor(
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
    wait_saved(page)

    speed_field = second_page.locator('[data-field-id="ship_speed"]')
    speed_field.fill("7")
    speed_field.blur()
    wait_saved(second_page)

    # Both edits must have gone through even though they raced against each
    # other on different fields of the same shared sheet.
    page.reload()
    page.wait_for_selector('[data-field-id="ship_name"]')
    assert page.input_value('[data-field-id="ship_name"]') == "Rosinante"
    assert page.input_value('[data-field-id="ship_speed"]') == "7"

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

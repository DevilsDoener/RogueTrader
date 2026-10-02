import pytest

from .conftest import open_character, open_ship, wait_saved

pytestmark = pytest.mark.django_db(transaction=True)


def test_characteristics_and_advances_sync_live_and_survive_reload(
    page, live_server, owner, character_factory
):
    open_character(
        page,
        live_server,
        owner,
        character_factory,
        values={
            "c1_ws_value": "35",
            "c2_ws_value": "35",
            "c1_ws_adv_3": False,
            "c2_ws_adv_3": False,
        },
    )

    first_value = page.locator('[data-field-id="c1_ws_value"]')
    second_value = page.locator('[data-field-id="c2_ws_value"]')
    assert first_value.get_attribute("maxlength") == "2"
    assert second_value.get_attribute("maxlength") == "2"

    first_value.fill("47")
    assert second_value.input_value() == "47"
    first_value.blur()
    wait_saved(page)

    second_advance = page.locator('[data-field-id="c2_ws_adv_3"]')
    first_advance = page.locator('[data-field-id="c1_ws_adv_3"]')
    second_advance.check()
    assert first_advance.is_checked()
    wait_saved(page)

    page.reload()
    assert page.locator('[data-field-id="c1_ws_value"]').input_value() == "47"
    assert page.locator('[data-field-id="c2_ws_value"]').input_value() == "47"
    assert page.locator('[data-field-id="c1_ws_adv_3"]').is_checked()
    assert page.locator('[data-field-id="c2_ws_adv_3"]').is_checked()


def _checked_marker_kind(locator):
    return locator.evaluate(
        """element => {
            const image = decodeURIComponent(getComputedStyle(element).backgroundImage);
            return {
                diagonalCross: image.includes('M2 2L18 18M18 2L2 18'),
                filledCircle: image.includes('<circle')
            };
        }"""
    )


def test_ship_circle_keeps_its_round_checked_marker(page, live_server, owner, ship_sheet):
    field_id = "ship_weapon_1_location_dorsal"
    open_ship(page, live_server, owner, ship_sheet, values={field_id: True})

    marker = page.locator(f'[data-field-id="{field_id}"]')
    assert marker.is_checked()
    assert _checked_marker_kind(marker) == {
        "diagonalCross": False,
        "filledCircle": True,
    }

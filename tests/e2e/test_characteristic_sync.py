import pytest

from .conftest import login_via_browser


pytestmark = pytest.mark.django_db(transaction=True)


def test_characteristics_and_advances_sync_live_and_survive_reload(
    page, live_server, owner, character_factory
):
    character = character_factory(
        owner=owner,
        values={
            "c1_ws_value": "35",
            "c2_ws_value": "35",
            "c1_ws_adv_3": False,
            "c2_ws_adv_3": False,
        },
    )
    login_via_browser(page, live_server, username=owner.username)
    page.goto(f"{live_server.url}/characters/{character.pk}/")

    first_value = page.locator('[data-field-id="c1_ws_value"]')
    second_value = page.locator('[data-field-id="c2_ws_value"]')
    assert first_value.get_attribute("maxlength") == "2"
    assert second_value.get_attribute("maxlength") == "2"

    first_value.fill("47")
    assert second_value.input_value() == "47"
    first_value.blur()
    page.wait_for_function(
        "document.getElementById('sheet-save-status').textContent==='Gespeichert'"
    )

    second_advance = page.locator('[data-field-id="c2_ws_adv_3"]')
    first_advance = page.locator('[data-field-id="c1_ws_adv_3"]')
    second_advance.check()
    assert first_advance.is_checked()
    page.wait_for_function(
        "document.getElementById('sheet-save-status').textContent==='Gespeichert'"
    )

    page.reload()
    assert page.locator('[data-field-id="c1_ws_value"]').input_value() == "47"
    assert page.locator('[data-field-id="c2_ws_value"]').input_value() == "47"
    assert page.locator('[data-field-id="c1_ws_adv_3"]').is_checked()
    assert page.locator('[data-field-id="c2_ws_adv_3"]').is_checked()

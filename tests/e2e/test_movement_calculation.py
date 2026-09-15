import pytest
from .conftest import login_via_browser
from sheets.services import patch_character_field

pytestmark=pytest.mark.django_db(transaction=True)

def test_movement_updates_live_and_survives_reload(page,live_server,owner,character_factory):
    character=character_factory(owner=owner,values={"c2_movement_half_move":"4"})
    login_via_browser(page,live_server,username=owner.username)
    page.goto(f"{live_server.url}/characters/{character.pk}/")
    base=page.locator('[data-field-id="c2_movement_half_move"]')
    base.fill("5")
    for field,value in [("full_move","10"),("charge","15"),("run","30")]:
        el=page.locator(f'[data-field-id="c2_movement_{field}"]')
        assert el.input_value()==value
        assert not el.is_editable()
    base.blur()
    page.wait_for_function("document.getElementById('sheet-save-status').textContent==='Gespeichert'")
    page.reload()
    assert page.locator('[data-field-id="c2_movement_run"]').input_value()=="30"
    base.fill("");base.blur()
    page.wait_for_function("document.getElementById('sheet-save-status').textContent==='Gespeichert'")
    page.reload()
    assert page.locator('[data-field-id="c2_movement_run"]').input_value()==""

def test_conflict_resolution_refreshes_calculated_fields(page,live_server,owner,character_factory):
    character=character_factory(owner=owner,values={"c2_movement_half_move":"4"})
    login_via_browser(page,live_server,username=owner.username)
    page.goto(f"{live_server.url}/characters/{character.pk}/")
    patch_character_field(sheet_id=character.pk,actor=owner,field_id="c2_movement_half_move",value="6",base_version=0)
    base=page.locator('[data-field-id="c2_movement_half_move"]')
    base.fill("5");base.blur()
    page.locator('.sheet-conflict-take-current').click()
    assert base.input_value()=="6"
    assert page.locator('[data-field-id="c2_movement_run"]').input_value()=="36"
    base.fill("7");base.blur()
    page.wait_for_function("document.getElementById('sheet-save-status').textContent==='Gespeichert'")
    page.reload()
    assert page.locator('[data-field-id="c2_movement_run"]').input_value()=="42"

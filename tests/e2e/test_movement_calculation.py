"""Browser contracts for the computed movement fields on character page 2."""
from __future__ import annotations

import pytest

from sheets.services import patch_character_field

from .conftest import open_character, wait_saved

pytestmark = pytest.mark.django_db(transaction=True)


def test_movement_updates_live_and_survives_reload(page, live_server, owner, character_factory):
    open_character(
        page, live_server, owner, character_factory, values={"c2_movement_half_move": "4"}
    )
    base = page.locator('[data-field-id="c2_movement_half_move"]')
    base.fill("5")
    for field, value in [("full_move", "10"), ("charge", "15"), ("run", "30")]:
        result = page.locator(f'[data-field-id="c2_movement_{field}"]')
        assert result.input_value() == value
        assert not result.is_editable()
    base.blur()
    wait_saved(page)

    page.reload()
    assert page.locator('[data-field-id="c2_movement_run"]').input_value() == "30"

    base.fill("")
    base.blur()
    wait_saved(page)
    page.reload()
    assert page.locator('[data-field-id="c2_movement_run"]').input_value() == ""


def test_conflict_resolution_refreshes_calculated_fields(
    page, live_server, owner, character_factory
):
    character = open_character(
        page, live_server, owner, character_factory, values={"c2_movement_half_move": "4"}
    )
    patch_character_field(
        sheet_id=character.pk,
        actor=owner,
        field_id="c2_movement_half_move",
        value="6",
        base_version=0,
    )
    base = page.locator('[data-field-id="c2_movement_half_move"]')
    base.fill("5")
    base.blur()
    page.locator(".sheet-conflict-take-current").click()
    assert base.input_value() == "6"
    assert page.locator('[data-field-id="c2_movement_run"]').input_value() == "36"

    base.fill("7")
    base.blur()
    wait_saved(page)
    page.reload()
    assert page.locator('[data-field-id="c2_movement_run"]').input_value() == "42"

import importlib
from types import SimpleNamespace

import pytest
from django.apps import apps
from django.db import connection

from sheets import schema
from sheets.services import FieldConflict, FieldValidationError, patch_character_field


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("field_id", "value", "counterpart"),
    [
        ("c1_ws_value", "42", "c2_ws_value"),
        ("c2_fel_adv_4", True, "c1_fel_adv_4"),
    ],
)
def test_characteristics_and_advances_sync_in_both_directions(
    character_sheet, owner, field_id, value, counterpart
):
    result = patch_character_field(
        sheet_id=character_sheet.pk,
        actor=owner,
        field_id=field_id,
        value=value,
        base_version=0,
    )

    character_sheet.refresh_from_db()
    assert character_sheet.values[field_id] == value
    assert character_sheet.values[counterpart] == value
    assert character_sheet.field_versions[field_id] == result.version
    assert character_sheet.field_versions[counterpart] == result.version
    assert result.calculated_fields[counterpart] == {
        "value": value,
        "version": result.version,
    }
    assert character_sheet.changes.get(field_id=counterpart).new_value == value


@pytest.mark.django_db
def test_sync_updates_counterpart_version_so_stale_other_page_conflicts(
    character_sheet, owner
):
    patch_character_field(
        sheet_id=character_sheet.pk,
        actor=owner,
        field_id="c2_ag_value",
        value="38",
        base_version=0,
    )

    with pytest.raises(FieldConflict):
        patch_character_field(
            sheet_id=character_sheet.pk,
            actor=owner,
            field_id="c1_ag_value",
            value="41",
            base_version=0,
        )


@pytest.mark.django_db
@pytest.mark.parametrize("field_id", ["c1_int_value", "c2_int_value"])
def test_characteristic_values_accept_only_zero_to_two_digits(
    character_sheet, owner, field_id
):
    for value in ("", "0", "00", "99"):
        character_sheet.refresh_from_db()
        base_version = character_sheet.field_versions.get(field_id, 0)
        patch_character_field(
            sheet_id=character_sheet.pk,
            actor=owner,
            field_id=field_id,
            value=value,
            base_version=base_version,
        )

    character_sheet.refresh_from_db()
    with pytest.raises(FieldValidationError):
        patch_character_field(
            sheet_id=character_sheet.pk,
            actor=owner,
            field_id=field_id,
            value="100",
            base_version=character_sheet.field_versions[field_id],
        )

    spec = next(
        field
        for page_id in ("character-page-1", "character-page-2")
        for field in schema.load_schema(page_id).fields
        if field.id == field_id
    )
    assert spec.max_length == 2
    assert spec.input_mode == "numeric"


@pytest.mark.django_db
def test_existing_characteristics_are_reconciled_from_page_one(character_factory):
    migration = importlib.import_module(
        "sheets.migrations.0006_sync_characteristics_between_pages"
    )
    character = character_factory(
        values={
            "c1_ws_value": "44",
            "c2_ws_value": "31",
            "c1_ws_adv_1": True,
            "c2_ws_adv_1": False,
            "c2_bs_value": "52",
        }
    )

    migration.sync_existing(apps, SimpleNamespace(connection=connection))
    character.refresh_from_db()

    assert character.values["c2_ws_value"] == "44"
    assert character.values["c2_ws_adv_1"] is True
    assert character.values["c1_bs_value"] == "52"
    assert character.changes.get(field_id="c2_ws_value").old_value == "31"
    assert character.changes.get(field_id="c1_bs_value").old_value is None

    change_count = character.changes.count()
    migration.sync_existing(apps, SimpleNamespace(connection=connection))
    assert character.changes.count() == change_count

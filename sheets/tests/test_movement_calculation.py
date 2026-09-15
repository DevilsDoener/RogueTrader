import pytest
from sheets.services import patch_character_field, FieldConflict, FieldValidationError

SOURCE="c2_movement_half_move"
TARGETS={"c2_movement_full_move":2,"c2_movement_charge":3,"c2_movement_run":6}

@pytest.mark.django_db
def test_half_move_saves_all_results_atomically(character_sheet,owner):
    result=patch_character_field(sheet_id=character_sheet.pk,actor=owner,field_id=SOURCE,value="5",base_version=0)
    character_sheet.refresh_from_db()
    for field,factor in TARGETS.items():
        assert character_sheet.values[field]==str(5*factor)
        assert character_sheet.field_versions[field]==result.version
        assert character_sheet.changes.get(field_id=field).new_value==str(5*factor)
    before=dict(character_sheet.values)
    with pytest.raises(FieldConflict):
        patch_character_field(sheet_id=character_sheet.pk,actor=owner,field_id=SOURCE,value="9",base_version=0)
    character_sheet.refresh_from_db()
    assert character_sheet.values==before

@pytest.mark.django_db
@pytest.mark.parametrize("value", ["0", "", "999999"])
def test_zero_empty_and_maximum_movement(character_sheet,owner,value):
    patch_character_field(sheet_id=character_sheet.pk,actor=owner,field_id=SOURCE,value=value,base_version=0)
    character_sheet.refresh_from_db()
    for field,factor in TARGETS.items():
        assert character_sheet.values[field] == (str(int(value)*factor) if value else "")

@pytest.mark.django_db
def test_direct_result_edits_and_invalid_base_are_rejected(character_sheet,owner):
    for field,value in [(SOURCE,"abc"),(SOURCE,"-1"),(SOURCE,"1.5"),*[(field,"99") for field in TARGETS]]:
        with pytest.raises(FieldValidationError):
            patch_character_field(sheet_id=character_sheet.pk,actor=owner,field_id=field,value=value,base_version=0)
    assert character_sheet.changes.count()==0


@pytest.mark.django_db
def test_existing_values_recalculated_and_archived(character_factory):
    import importlib
    from django.apps import apps
    from django.db import connection
    from types import SimpleNamespace
    migration=importlib.import_module("sheets.migrations.0005_calculate_character_movement")
    character=character_factory(values={SOURCE:"4", "c2_movement_run":"4", "c1_character_name":"Keep"})
    invalid=character_factory(values={SOURCE:"custom", "c2_movement_run":"old"})
    migration.calculate_existing(apps,SimpleNamespace(connection=connection))
    character.refresh_from_db();invalid.refresh_from_db()
    assert character.values["c2_movement_run"]=="24"
    assert character.values["c1_character_name"]=="Keep"
    assert character.changes.get(field_id="c2_movement_run").old_value=="4"
    assert invalid.values["c2_movement_run"]=="old"
    migration.calculate_existing(apps,SimpleNamespace(connection=connection))
    assert character.changes.count()==3

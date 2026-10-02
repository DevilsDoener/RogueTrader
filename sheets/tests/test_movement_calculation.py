import pytest

from sheets import movement
from sheets.schema import load_schema
from sheets.services import FieldConflict, FieldValidationError, patch_character_field
from sheets.tests.helpers import load_migration, run_migration_step

SOURCE = "c2_movement_half_move"
TARGETS = {"c2_movement_full_move": 2, "c2_movement_charge": 3, "c2_movement_run": 6}


@pytest.mark.django_db
def test_half_move_saves_all_results_atomically(character_sheet, owner):
    result = patch_character_field(
        sheet_id=character_sheet.pk, actor=owner, field_id=SOURCE, value="5", base_version=0
    )
    character_sheet.refresh_from_db()
    for field, factor in TARGETS.items():
        assert character_sheet.values[field] == str(5 * factor)
        assert character_sheet.field_versions[field] == result.version
        assert character_sheet.changes.get(field_id=field).new_value == str(5 * factor)
    before = dict(character_sheet.values)
    with pytest.raises(FieldConflict):
        patch_character_field(
            sheet_id=character_sheet.pk, actor=owner, field_id=SOURCE, value="9", base_version=0
        )
    character_sheet.refresh_from_db()
    assert character_sheet.values == before


@pytest.mark.django_db
@pytest.mark.parametrize("value", ["0", "", "999999"])
def test_zero_empty_and_maximum_movement(character_sheet, owner, value):
    patch_character_field(
        sheet_id=character_sheet.pk, actor=owner, field_id=SOURCE, value=value, base_version=0
    )
    character_sheet.refresh_from_db()
    for field, factor in TARGETS.items():
        assert character_sheet.values[field] == (str(int(value) * factor) if value else "")


@pytest.mark.django_db
def test_direct_result_edits_and_invalid_base_are_rejected(character_sheet, owner):
    invalid_writes = [(SOURCE, "abc"), (SOURCE, "-1"), (SOURCE, "1.5")]
    invalid_writes += [(field, "99") for field in TARGETS]
    for field, value in invalid_writes:
        with pytest.raises(FieldValidationError):
            patch_character_field(
                sheet_id=character_sheet.pk,
                actor=owner,
                field_id=field,
                value=value,
                base_version=0,
            )
    assert character_sheet.changes.count() == 0


def test_calculation_digit_limit_matches_the_half_move_schema_field():
    # movement.calculate() rejects inputs longer than MAX_DIGITS; the schema
    # validation that runs first must never let a longer value through.
    assert movement.SOURCE == SOURCE
    assert load_schema("character-page-2").field_by_id(SOURCE).max_length == movement.MAX_DIGITS


@pytest.mark.django_db
def test_existing_values_recalculated_and_archived(character_factory):
    migration = load_migration("0005_calculate_character_movement")
    character = character_factory(
        values={SOURCE: "4", "c2_movement_run": "4", "c1_character_name": "Keep"}
    )
    invalid = character_factory(values={SOURCE: "custom", "c2_movement_run": "old"})
    run_migration_step(migration.calculate_existing)
    character.refresh_from_db()
    invalid.refresh_from_db()
    assert character.values["c2_movement_run"] == "24"
    assert character.values["c1_character_name"] == "Keep"
    assert character.changes.get(field_id="c2_movement_run").old_value == "4"
    assert invalid.values["c2_movement_run"] == "old"
    run_migration_step(migration.calculate_existing)
    assert character.changes.count() == 3


@pytest.mark.django_db
def test_rewriting_half_move_with_a_drifted_result_resyncs_it(character_sheet, owner):
    result = patch_character_field(
        sheet_id=character_sheet.pk, actor=owner, field_id=SOURCE, value="5", base_version=0
    )
    character_sheet.refresh_from_db()
    character_sheet.values["c2_movement_charge"] = "1"  # drifted out of band
    character_sheet.save()

    again = patch_character_field(
        sheet_id=character_sheet.pk,
        actor=owner,
        field_id=SOURCE,
        value="5",
        base_version=result.version,
    )

    character_sheet.refresh_from_db()
    assert character_sheet.values["c2_movement_charge"] == "15"
    assert again.version == result.version + 1
    assert again.calculated_fields["c2_movement_charge"]["value"] == "15"


@pytest.mark.django_db
def test_rewriting_half_move_when_the_results_are_in_sync_stays_a_noop(character_sheet, owner):
    result = patch_character_field(
        sheet_id=character_sheet.pk, actor=owner, field_id=SOURCE, value="5", base_version=0
    )
    changes = character_sheet.changes.count()

    again = patch_character_field(
        sheet_id=character_sheet.pk,
        actor=owner,
        field_id=SOURCE,
        value="5",
        base_version=result.version,
    )

    assert again.version == result.version
    assert character_sheet.changes.count() == changes


@pytest.mark.django_db
def test_rewriting_a_characteristic_with_a_drifted_counterpart_resyncs_it(character_sheet, owner):
    result = patch_character_field(
        sheet_id=character_sheet.pk, actor=owner, field_id="c1_ws_value", value="40", base_version=0
    )
    character_sheet.refresh_from_db()
    character_sheet.values["c2_ws_value"] = "7"
    character_sheet.save()

    again = patch_character_field(
        sheet_id=character_sheet.pk,
        actor=owner,
        field_id="c1_ws_value",
        value="40",
        base_version=result.version,
    )

    character_sheet.refresh_from_db()
    assert character_sheet.values["c2_ws_value"] == "40"
    assert again.version == result.version + 1

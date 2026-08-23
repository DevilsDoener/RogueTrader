import uuid

import pytest

from sheets.models import SheetChange
from sheets.services import (
    FieldConflict,
    FieldValidationError,
    PatchResult,
    SheetNotFound,
    patch_character_field,
    patch_ship_field,
)


@pytest.mark.django_db(transaction=True)
def test_patch_character_field_raises_sheet_not_found_for_nonexistent_id(owner):
    with pytest.raises(SheetNotFound):
        patch_character_field(
            sheet_id=uuid.uuid4(),
            actor=owner,
            field_id="c1_character_name",
            value="Lucian",
            base_version=0,
        )


@pytest.mark.django_db(transaction=True)
def test_patch_ship_field_raises_sheet_not_found_for_nonexistent_id(owner):
    with pytest.raises(SheetNotFound):
        patch_ship_field(
            sheet_id=uuid.uuid4(),
            actor=owner,
            field_id="ship_name",
            value="The Emissary",
            base_version=0,
        )


@pytest.mark.django_db(transaction=True)
def test_different_fields_merge_from_same_base(character_sheet, owner):
    first = patch_character_field(
        sheet_id=character_sheet.id,
        actor=owner,
        field_id="c1_character_name",
        value="Lucian",
        base_version=0,
    )
    second = patch_character_field(
        sheet_id=character_sheet.id,
        actor=owner,
        field_id="c1_player_name",
        value="Nikolas",
        base_version=0,
    )
    assert first.version == 1
    assert second.version == 2
    assert isinstance(first, PatchResult)
    assert first.field_id == "c1_character_name"
    assert first.value == "Lucian"


@pytest.mark.django_db(transaction=True)
def test_same_field_conflict_never_overwrites(character_sheet, owner):
    patch_character_field(
        sheet_id=character_sheet.id,
        actor=owner,
        field_id="c1_character_name",
        value="Lucian",
        base_version=0,
    )
    with pytest.raises(FieldConflict) as error:
        patch_character_field(
            sheet_id=character_sheet.id,
            actor=owner,
            field_id="c1_character_name",
            value="Voss",
            base_version=0,
        )
    assert error.value.current_value == "Lucian"
    assert error.value.current_version == 1
    assert error.value.field_id == "c1_character_name"
    assert error.value.submitted_value == "Voss"

    # The stored value was not overwritten by the losing write.
    character_sheet.refresh_from_db()
    assert character_sheet.values["c1_character_name"] == "Lucian"


@pytest.mark.django_db(transaction=True)
def test_conflict_resolved_by_retrying_with_current_version(character_sheet, owner):
    patch_character_field(
        sheet_id=character_sheet.id,
        actor=owner,
        field_id="c1_character_name",
        value="Lucian",
        base_version=0,
    )
    result = patch_character_field(
        sheet_id=character_sheet.id,
        actor=owner,
        field_id="c1_character_name",
        value="Voss",
        base_version=1,
    )
    assert result.value == "Voss"
    assert result.version == 2


@pytest.mark.django_db(transaction=True)
def test_updating_character_name_syncs_display_name(character_sheet, owner):
    patch_character_field(
        sheet_id=character_sheet.id,
        actor=owner,
        field_id="c1_character_name",
        value="Lucian",
        base_version=0,
    )
    character_sheet.refresh_from_db()
    assert character_sheet.display_name == "Lucian"


@pytest.mark.django_db(transaction=True)
def test_unknown_field_id_fails_validation(character_sheet, owner):
    with pytest.raises(FieldValidationError):
        patch_character_field(
            sheet_id=character_sheet.id,
            actor=owner,
            field_id="not_a_real_field",
            value="whatever",
            base_version=0,
        )


@pytest.mark.django_db(transaction=True)
def test_wrong_type_fails_validation(character_sheet, owner):
    with pytest.raises(FieldValidationError):
        patch_character_field(
            sheet_id=character_sheet.id,
            actor=owner,
            field_id="c1_ws_adv_1",  # checkbox field
            value="not-a-bool",
            base_version=0,
        )


@pytest.mark.django_db(transaction=True)
def test_field_from_page_two_is_reachable(character_sheet, owner):
    result = patch_character_field(
        sheet_id=character_sheet.id,
        actor=owner,
        field_id="c2_movement_half_move",
        value="4",
        base_version=0,
    )
    assert result.version == 1


@pytest.mark.django_db(transaction=True)
def test_any_authenticated_user_can_patch_ship(ship_sheet, owner, other_user):
    first = patch_ship_field(
        sheet_id=ship_sheet.id,
        actor=owner,
        field_id="ship_name",
        value="The Emissary",
        base_version=0,
    )
    second = patch_ship_field(
        sheet_id=ship_sheet.id,
        actor=other_user,
        field_id="ship_class",
        value="Frigate",
        base_version=0,
    )
    assert first.version == 1
    assert second.version == 2


@pytest.mark.django_db(transaction=True)
def test_ship_field_conflict_never_overwrites(ship_sheet, owner, other_user):
    patch_ship_field(
        sheet_id=ship_sheet.id,
        actor=owner,
        field_id="ship_name",
        value="The Emissary",
        base_version=0,
    )
    with pytest.raises(FieldConflict) as error:
        patch_ship_field(
            sheet_id=ship_sheet.id,
            actor=other_user,
            field_id="ship_name",
            value="Retribution's Claw",
            base_version=0,
        )
    assert error.value.current_value == "The Emissary"


@pytest.mark.django_db(transaction=True)
def test_ship_change_creates_audit_record_with_actor_old_new(ship_sheet, owner):
    patch_ship_field(
        sheet_id=ship_sheet.id,
        actor=owner,
        field_id="ship_name",
        value="The Emissary",
        base_version=0,
    )
    change = SheetChange.objects.get(ship=ship_sheet, field_id="ship_name")
    assert change.character is None
    assert change.actor == owner
    assert change.old_value is None
    assert change.new_value == "The Emissary"
    assert change.resulting_version == 1


@pytest.mark.django_db(transaction=True)
def test_character_change_creates_audit_record(character_sheet, owner):
    patch_character_field(
        sheet_id=character_sheet.id,
        actor=owner,
        field_id="c1_character_name",
        value="Lucian",
        base_version=0,
    )
    change = SheetChange.objects.get(character=character_sheet, field_id="c1_character_name")
    assert change.ship is None
    assert change.actor == owner
    assert change.old_value is None
    assert change.new_value == "Lucian"
    assert change.resulting_version == 1

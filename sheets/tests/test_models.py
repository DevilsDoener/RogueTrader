import uuid

import pytest
from django.db import IntegrityError, transaction

from sheets.models import CharacterSheet, ShipSheet, SheetChange


@pytest.mark.django_db
def test_character_sheet_defaults(owner):
    sheet = CharacterSheet.objects.create(owner=owner, display_name="")
    assert isinstance(sheet.id, uuid.UUID)
    assert sheet.values == {}
    assert sheet.field_versions == {}
    assert sheet.version == 0
    assert sheet.created_at is not None
    assert sheet.updated_at is not None


@pytest.mark.django_db
def test_ship_sheet_defaults():
    sheet = ShipSheet.objects.create()
    assert isinstance(sheet.id, uuid.UUID)
    assert sheet.display_name == "Gemeinsames Schiff"
    assert sheet.values == {}
    assert sheet.field_versions == {}
    assert sheet.version == 0
    assert sheet.is_active is True


@pytest.mark.django_db
def test_sheet_change_requires_exactly_one_target(character_sheet, ship_sheet, owner):
    # Neither target set.
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            SheetChange.objects.create(
                character=None,
                ship=None,
                actor=owner,
                field_id="c1_character_name",
                old_value=None,
                new_value="Lucian",
                resulting_version=1,
            )

    # Both targets set.
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            SheetChange.objects.create(
                character=character_sheet,
                ship=ship_sheet,
                actor=owner,
                field_id="c1_character_name",
                old_value=None,
                new_value="Lucian",
                resulting_version=1,
            )

    # Exactly one target set is fine.
    change = SheetChange.objects.create(
        character=character_sheet,
        ship=None,
        actor=owner,
        field_id="c1_character_name",
        old_value=None,
        new_value="Lucian",
        resulting_version=1,
    )
    assert change.pk is not None

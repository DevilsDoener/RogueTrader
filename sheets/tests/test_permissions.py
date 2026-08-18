import pytest

from sheets.models import CharacterSheet
from sheets.permissions import can_mutate_character, can_view_character, visible_characters
from sheets.services import (
    SheetNotFound,
    delete_character,
    get_character_for_view,
    patch_character_field,
    patch_ship_field,
)


@pytest.mark.django_db(transaction=True)
def test_normal_user_gets_sheet_not_found_for_others_character(character_sheet, other_user):
    with pytest.raises(SheetNotFound):
        patch_character_field(
            sheet_id=character_sheet.id,
            actor=other_user,
            field_id="c1_character_name",
            value="Voss",
            base_version=0,
        )
    with pytest.raises(SheetNotFound):
        get_character_for_view(sheet_id=character_sheet.id, actor=other_user)


@pytest.mark.django_db(transaction=True)
def test_admin_can_read_but_not_patch_or_delete_others_character(character_sheet, portal_admin):
    # Admin can read.
    sheet = get_character_for_view(sheet_id=character_sheet.id, actor=portal_admin)
    assert sheet.id == character_sheet.id

    # Admin cannot patch -- indistinguishable from the sheet not existing.
    with pytest.raises(SheetNotFound):
        patch_character_field(
            sheet_id=character_sheet.id,
            actor=portal_admin,
            field_id="c1_character_name",
            value="Voss",
            base_version=0,
        )

    # Admin cannot delete.
    with pytest.raises(SheetNotFound):
        delete_character(sheet_id=character_sheet.id, actor=portal_admin)

    assert CharacterSheet.objects.filter(pk=character_sheet.id).exists()


@pytest.mark.django_db(transaction=True)
def test_owner_can_read_and_mutate_own_character(character_sheet, owner):
    sheet = get_character_for_view(sheet_id=character_sheet.id, actor=owner)
    assert can_view_character(owner, sheet)
    assert can_mutate_character(owner, sheet)

    result = patch_character_field(
        sheet_id=character_sheet.id,
        actor=owner,
        field_id="c1_character_name",
        value="Lucian",
        base_version=0,
    )
    assert result.value == "Lucian"


@pytest.mark.django_db(transaction=True)
def test_owner_can_delete_own_character(character_sheet, owner):
    delete_character(sheet_id=character_sheet.id, actor=owner)
    assert not CharacterSheet.objects.filter(pk=character_sheet.id).exists()


@pytest.mark.django_db(transaction=True)
def test_every_user_can_patch_the_shared_ship(ship_sheet, owner, other_user, portal_admin):
    for index, actor in enumerate((owner, other_user, portal_admin)):
        result = patch_ship_field(
            sheet_id=ship_sheet.id,
            actor=actor,
            field_id="ship_name",
            value=f"Name-{index}",
            base_version=index,
        )
        assert result.version == index + 1


@pytest.mark.django_db
def test_visible_characters_filters_by_ownership(owner, other_user, portal_admin):
    mine = CharacterSheet.objects.create(owner=owner, display_name="Mine")
    theirs = CharacterSheet.objects.create(owner=other_user, display_name="Theirs")

    owner_visible = set(visible_characters(owner, CharacterSheet.objects.all()))
    assert owner_visible == {mine}

    admin_visible = set(visible_characters(portal_admin, CharacterSheet.objects.all()))
    assert admin_visible == {mine, theirs}

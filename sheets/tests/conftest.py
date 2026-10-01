import pytest

from sheets.models import CharacterSheet


@pytest.fixture
def character_sheet(owner):
    return CharacterSheet.objects.create(owner=owner, display_name="")

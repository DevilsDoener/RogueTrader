import pytest
from django.contrib.auth import get_user_model

from sheets.models import CharacterSheet, ShipSheet


@pytest.fixture
def user_factory(db):
    def create_user(**attributes):
        password = attributes.pop("password", "Valid-Password-42!")
        attributes.setdefault("must_change_password", False)
        username = attributes.pop("username", "user")
        user = get_user_model().objects.create_user(
            username=username,
            password=password,
            **attributes,
        )
        return user

    return create_user


@pytest.fixture
def owner(user_factory):
    return user_factory(username="owner")


@pytest.fixture
def other_user(user_factory):
    return user_factory(username="other")


@pytest.fixture
def portal_admin(user_factory):
    return user_factory(username="portal-admin", is_portal_admin=True)


@pytest.fixture
def character_sheet(owner):
    return CharacterSheet.objects.create(owner=owner, display_name="")


@pytest.fixture
def ship_sheet():
    return ShipSheet.objects.create(display_name="Gemeinsames Schiff")

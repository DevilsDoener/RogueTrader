import uuid

import pytest
from django.contrib.auth import get_user_model

from sheets.models import CharacterSheet, ShipSheet


@pytest.fixture
def user_factory(db):
    def create_user(**attributes):
        password = attributes.pop("password", "Valid-Password-42!")
        attributes.setdefault("must_change_password", False)
        # A fresh unique default per call (rather than a fixed "user") so
        # tests can call user_factory() more than once without colliding on
        # the username uniqueness constraint.
        username = attributes.pop("username", None) or f"user-{uuid.uuid4().hex[:8]}"
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
def admin_user(user_factory):
    return user_factory(username="admin-user", is_portal_admin=True)


@pytest.fixture
def character_sheet(owner):
    return CharacterSheet.objects.create(owner=owner, display_name="")


@pytest.fixture
def character_factory(user_factory):
    def create_character(*, owner=None, display_name="", **attributes):
        if owner is None:
            owner = user_factory()
        return CharacterSheet.objects.create(owner=owner, display_name=display_name, **attributes)

    return create_character


@pytest.fixture
def ship_sheet():
    return ShipSheet.objects.create(display_name="Gemeinsames Schiff")

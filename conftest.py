"""Fixtures shared by every test package.

``tests/e2e/conftest.py`` overrides ``user_factory`` and ``ship_sheet`` with
``transactional_db`` variants for the live-server browser tests; the other
fixtures here build on those names and so pick up the override there.
"""

import uuid

import pytest
from django.test import override_settings

DEFAULT_PASSWORD = "Valid-Password-42!"


@pytest.fixture(autouse=True, scope="session")
def _fast_password_hasher():
    """Hash test passwords with MD5 instead of the production Argon2.

    Only the hashing cost changes: no test depends on the algorithm, and the
    security-settings tests read a freshly reloaded ``config.settings`` module,
    not ``django.conf.settings``.
    """
    with override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]):
        yield


@pytest.fixture(autouse=True)
def _restore_wiki_repository():
    """Undo any ``set_repository_for_tests`` so no test leaks its corpus."""
    from wiki import content

    saved = content._repository
    yield
    content._repository = saved


def make_user(*, password=DEFAULT_PASSWORD, username=None, **attributes):
    """Create a user who does not have to change the password on first login.

    Without a ``username`` each call gets a fresh unique one, so a test can
    call it repeatedly without colliding on the uniqueness constraint.
    """
    from django.contrib.auth import get_user_model

    attributes.setdefault("must_change_password", False)
    return get_user_model().objects.create_user(
        username=username or f"user-{uuid.uuid4().hex[:8]}",
        password=password,
        **attributes,
    )


@pytest.fixture
def user_factory(db):
    return make_user


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
def character_factory(user_factory):
    from sheets.models import CharacterSheet

    def create_character(*, owner=None, display_name="", **attributes):
        if owner is None:
            owner = user_factory()
        return CharacterSheet.objects.create(owner=owner, display_name=display_name, **attributes)

    return create_character


@pytest.fixture
def ship_sheet(db):
    """The single shared ship every authenticated user may edit.

    Returns the migration-seeded ship (see
    ``sheets/migrations/0002_seed_shared_ship.py``) rather than creating a
    second, rival active ship -- a real deployment only ever has the one
    the migration created, so tests exercising "the" active ship should
    exercise that same row. Falls back to creating one only if a previous
    test already deleted every ship (e.g. via ``ShipSheet.objects.all()
    .delete()``), so this fixture never raises ``DoesNotExist``.
    """
    from sheets.models import ShipSheet

    return ShipSheet.objects.filter(is_active=True).first() or ShipSheet.objects.create(
        display_name="Gemeinsames Schiff", is_active=True
    )

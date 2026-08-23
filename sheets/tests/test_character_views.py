"""Owner-scoped character list/create/detail/delete views.

Every user-facing lookup here starts from an owner-scoped queryset, so a
character owned by someone else -- including a portal admin who can *view*
it through the separate admin route -- is indistinguishable from a
nonexistent one (404) when reached through these routes.
"""
from __future__ import annotations

import pytest

from sheets.models import CharacterSheet


def assert_contains(response, text):
    assert text in response.content.decode()


def assert_not_contains(response, text):
    assert text not in response.content.decode()


@pytest.mark.django_db
def test_user_character_list_contains_only_owned_sheets(client, user_factory, character_factory):
    owner = user_factory()
    other = user_factory()
    character_factory(owner=owner, display_name="Own")
    character_factory(owner=other, display_name="Hidden")
    client.force_login(owner)
    response = client.get("/characters/")
    assert_contains(response, "Own")
    assert_not_contains(response, "Hidden")


@pytest.mark.django_db
def test_character_list_requires_login(client):
    response = client.get("/characters/")
    assert response.status_code == 302
    assert "/account/login/" in response.url


@pytest.mark.django_db
def test_create_character_sets_owner_server_side(client, user_factory):
    owner = user_factory()
    client.force_login(owner)
    response = client.post("/characters/", {"display_name": "Lucian", "owner": "someone-else"})

    character = CharacterSheet.objects.get(display_name="Lucian")
    assert character.owner == owner
    assert character.values == {}
    assert character.field_versions == {}
    assert response.status_code == 302
    assert response.url == f"/characters/{character.id}/"


@pytest.mark.django_db
def test_create_character_requires_display_name(client, user_factory):
    owner = user_factory()
    client.force_login(owner)
    response = client.post("/characters/", {"display_name": ""})
    assert response.status_code == 200
    assert not CharacterSheet.objects.exists()


@pytest.mark.django_db
def test_owner_can_view_own_character_detail_read_write(client, user_factory, character_factory):
    owner = user_factory()
    character = character_factory(owner=owner, display_name="Own")
    client.force_login(owner)
    response = client.get(f"/characters/{character.id}/")
    assert response.status_code == 200
    assert response.context["read_only"] is False


@pytest.mark.django_db
def test_user_cannot_view_another_users_character_detail(client, user_factory, character_factory):
    owner = user_factory()
    other = user_factory()
    character = character_factory(owner=other, display_name="Hidden")
    client.force_login(owner)
    response = client.get(f"/characters/{character.id}/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_owner_can_delete_own_character_via_post(client, user_factory, character_factory):
    owner = user_factory()
    character = character_factory(owner=owner, display_name="Own")
    client.force_login(owner)
    response = client.post(f"/characters/{character.id}/delete/")
    assert response.status_code == 302
    assert not CharacterSheet.objects.filter(pk=character.id).exists()


@pytest.mark.django_db
def test_user_cannot_delete_another_users_character(client, user_factory, character_factory):
    owner = user_factory()
    other = user_factory()
    character = character_factory(owner=other, display_name="Hidden")
    client.force_login(owner)
    response = client.post(f"/characters/{character.id}/delete/")
    assert response.status_code == 404
    assert CharacterSheet.objects.filter(pk=character.id).exists()


@pytest.mark.django_db
def test_delete_via_get_shows_confirmation_and_does_not_delete(client, user_factory, character_factory):
    owner = user_factory()
    character = character_factory(owner=owner, display_name="Own")
    client.force_login(owner)
    response = client.get(f"/characters/{character.id}/delete/")
    assert response.status_code == 200
    assert CharacterSheet.objects.filter(pk=character.id).exists()


@pytest.mark.django_db
def test_get_on_another_users_delete_confirmation_is_not_found(client, user_factory, character_factory):
    owner = user_factory()
    other = user_factory()
    character = character_factory(owner=other, display_name="Hidden")
    client.force_login(owner)
    response = client.get(f"/characters/{character.id}/delete/")
    assert response.status_code == 404
    assert CharacterSheet.objects.filter(pk=character.id).exists()

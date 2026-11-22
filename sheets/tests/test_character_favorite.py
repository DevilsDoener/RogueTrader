"""Favourite character: the star toggle and the Charaktere tab jumping to it.

The mark is owner-scoped like every other character route: nobody but the
owner can set or clear it, and someone else's character is a 404.
"""
from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction

from sheets.models import CharacterSheet
from tests.html import attr, has_link, select, select_one, texts

LIST_ALL = "/characters/?alle=1"


def _favorite(client, character, *, on=True, **extra):
    return client.post(
        f"/characters/{character.id}/favorite/", {"favorite": "1" if on else "0", **extra}
    )


@pytest.mark.django_db
def test_marking_a_favorite_clears_the_owners_previous_one(client, owner, character_factory):
    first = character_factory(owner=owner, display_name="Erster", is_favorite=True)
    second = character_factory(owner=owner, display_name="Zweiter")
    client.force_login(owner)

    response = _favorite(client, second)

    assert response.status_code == 302
    assert response.url == f"/characters/{second.id}/"
    first.refresh_from_db()
    second.refresh_from_db()
    assert (first.is_favorite, second.is_favorite) == (False, True)


@pytest.mark.django_db
def test_unmarking_clears_the_favorite(client, owner, character_factory):
    character = character_factory(owner=owner, is_favorite=True)
    client.force_login(owner)

    _favorite(client, character, on=False)

    character.refresh_from_db()
    assert character.is_favorite is False


@pytest.mark.django_db
def test_favorites_of_different_owners_are_independent(
    client, owner, other_user, character_factory
):
    others = character_factory(owner=other_user, is_favorite=True)
    mine = character_factory(owner=owner)
    client.force_login(owner)

    _favorite(client, mine)

    others.refresh_from_db()
    assert others.is_favorite is True


@pytest.mark.django_db
def test_marking_does_not_count_as_editing_the_sheet(client, owner, character_factory):
    character = character_factory(owner=owner)
    before = CharacterSheet.objects.get(pk=character.pk).updated_at
    client.force_login(owner)

    _favorite(client, character)

    assert CharacterSheet.objects.get(pk=character.pk).updated_at == before


@pytest.mark.django_db
def test_return_to_list_goes_back_to_the_full_list(client, owner, character_factory):
    character = character_factory(owner=owner)
    client.force_login(owner)

    response = _favorite(client, character, return_to="list")

    assert response.url == LIST_ALL


@pytest.mark.django_db
def test_another_users_character_cannot_be_marked(client, owner, other_user, character_factory):
    character = character_factory(owner=other_user)
    client.force_login(owner)

    response = _favorite(client, character)

    assert response.status_code == 404
    character.refresh_from_db()
    assert character.is_favorite is False


@pytest.mark.django_db
def test_a_portal_admin_cannot_mark_someone_elses_character(
    client, portal_admin, owner, character_factory
):
    character = character_factory(owner=owner)
    client.force_login(portal_admin)

    assert _favorite(client, character).status_code == 404
    character.refresh_from_db()
    assert character.is_favorite is False


@pytest.mark.django_db
def test_favorite_endpoint_requires_login_and_post(client, owner, character_factory):
    character = character_factory(owner=owner)

    anonymous = _favorite(client, character)
    assert anonymous.status_code == 302
    assert "/account/login/" in anonymous.url

    client.force_login(owner)
    assert client.get(f"/characters/{character.id}/favorite/").status_code == 405


@pytest.mark.django_db
def test_the_database_allows_one_favorite_per_owner(owner, character_factory):
    character_factory(owner=owner, is_favorite=True)
    with pytest.raises(IntegrityError), transaction.atomic():
        character_factory(owner=owner, is_favorite=True)


@pytest.mark.django_db
def test_charaktere_tab_opens_the_favorite(client, owner, character_factory):
    character_factory(owner=owner, display_name="Anderer")
    favorite = character_factory(owner=owner, display_name="Liebling", is_favorite=True)
    client.force_login(owner)

    response = client.get("/characters/")

    assert response.status_code == 302
    assert response.url == f"/characters/{favorite.id}/"


@pytest.mark.django_db
def test_charaktere_tab_shows_the_list_without_a_favorite(client, owner, character_factory):
    character_factory(owner=owner, display_name="Ohne Stern")
    client.force_login(owner)

    response = client.get("/characters/")

    assert response.status_code == 200
    assert "Ohne Stern" in response.content.decode()


@pytest.mark.django_db
def test_another_users_favorite_never_redirects(client, owner, other_user, character_factory):
    character_factory(owner=other_user, is_favorite=True)
    client.force_login(owner)

    assert client.get("/characters/").status_code == 200


@pytest.mark.django_db
def test_list_all_shows_the_list_with_the_favorite_first(client, owner, character_factory):
    character_factory(owner=owner, display_name="Aaron")
    favorite = character_factory(owner=owner, display_name="Zelda", is_favorite=True)
    client.force_login(owner)

    response = client.get(LIST_ALL)

    assert response.status_code == 200
    assert texts(response, "h2.crew-card-title") == ["Zelda", "Aaron"]
    stars = select(response, "form.favorite-form")
    assert attr(stars[0], "action") == f"/characters/{favorite.id}/favorite/"
    pressed = [attr(select_one(form, "button"), "aria-pressed") for form in stars]
    assert pressed == ["true", "false"]


@pytest.mark.django_db
def test_sheet_header_has_the_star_and_a_link_to_the_full_list(client, owner, character_factory):
    character = character_factory(owner=owner, display_name="Kopf")
    client.force_login(owner)

    html = client.get(f"/characters/{character.id}/").content.decode()

    star = select_one(html, ".sheet-page-title form.favorite-form")
    assert attr(star, "action") == f"/characters/{character.id}/favorite/"
    assert has_link(html, LIST_ALL)


@pytest.mark.django_db
def test_admin_read_only_view_has_no_star(client, portal_admin, owner, character_factory):
    character = character_factory(owner=owner)
    client.force_login(portal_admin)

    html = client.get(f"/portal-admin/characters/{character.id}/").content.decode()

    assert "/favorite/" not in html


@pytest.mark.django_db
def test_deleting_returns_to_the_full_list(client, owner, character_factory):
    keep = character_factory(owner=owner, is_favorite=True)
    gone = character_factory(owner=owner)
    client.force_login(owner)

    response = client.post(f"/characters/{gone.id}/delete/")

    assert response.url == LIST_ALL
    assert CharacterSheet.objects.filter(pk=keep.pk).exists()

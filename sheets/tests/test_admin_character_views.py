"""Read-only, portal-admin-only character visibility.

The admin routes are entirely separate from the owner routes: they never
allow mutation or deletion of a character owned by someone else, and the
detail view always renders the shared ``_sheet_viewer.html`` with
``read_only=True``.
"""
from __future__ import annotations

import pytest


def assert_contains(response, text):
    assert text in response.content.decode()


def assert_not_contains(response, text):
    assert text not in response.content.decode()


@pytest.mark.django_db
def test_admin_foreign_character_is_read_only(client, admin_user, character_factory):
    sheet = character_factory(display_name="Visible")
    client.force_login(admin_user)
    response = client.get(f"/portal-admin/characters/{sheet.id}/")
    assert response.status_code == 200
    assert response.context["read_only"] is True
    assert client.post(f"/characters/{sheet.id}/delete/").status_code == 404


@pytest.mark.django_db
def test_admin_character_list_shows_owner_display_name_and_updated(
    client, admin_user, character_factory, user_factory
):
    owner_a = user_factory(username="alice")
    owner_b = user_factory(username="bob")
    character_factory(owner=owner_a, display_name="Alpha")
    character_factory(owner=owner_b, display_name="Beta")
    client.force_login(admin_user)
    response = client.get("/portal-admin/characters/")
    assert response.status_code == 200
    assert_contains(response, "alice")
    assert_contains(response, "Alpha")
    assert_contains(response, "bob")
    assert_contains(response, "Beta")


@pytest.mark.django_db
def test_non_admin_forbidden_from_admin_character_list(client, user_factory):
    user = user_factory()
    client.force_login(user)
    response = client.get("/portal-admin/characters/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_non_admin_forbidden_from_admin_character_detail(client, user_factory, character_factory):
    user = user_factory()
    sheet = character_factory(display_name="Visible")
    client.force_login(user)
    response = client.get(f"/portal-admin/characters/{sheet.id}/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_anonymous_visitor_redirected_to_login_from_admin_character_list(client):
    # Anonymous visitors must be redirected to login, like every other
    # authenticated route in the app -- not given a bare 403.
    response = client.get("/portal-admin/characters/")
    assert response.status_code == 302
    assert response.url == "/account/login/?next=/portal-admin/characters/"


@pytest.mark.django_db
def test_anonymous_visitor_redirected_to_login_from_admin_character_detail(
    client, character_factory
):
    sheet = character_factory(display_name="Visible")
    url = f"/portal-admin/characters/{sheet.id}/"
    response = client.get(url)
    assert response.status_code == 302
    assert response.url == f"/account/login/?next={url}"


@pytest.mark.django_db
def test_admin_detail_omits_destructive_actions(client, admin_user, character_factory):
    sheet = character_factory(display_name="Visible")
    client.force_login(admin_user)
    response = client.get(f"/portal-admin/characters/{sheet.id}/")
    assert_not_contains(response, "Delete character")


@pytest.mark.django_db
def test_admin_detail_route_does_not_accept_post(client, admin_user, character_factory):
    sheet = character_factory(display_name="Visible")
    client.force_login(admin_user)
    response = client.post(f"/portal-admin/characters/{sheet.id}/")
    assert response.status_code == 405


@pytest.mark.django_db
def test_owner_route_never_shows_another_owners_character(client, admin_user, character_factory):
    """The admin can view via the admin route, but the owner mutation route
    is a completely separate lookup and must not expose it."""
    sheet = character_factory(display_name="Visible")
    client.force_login(admin_user)
    response = client.get(f"/characters/{sheet.id}/")
    assert response.status_code == 404

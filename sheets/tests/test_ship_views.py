"""View-level tests for the shared ship sheet and its privacy-conscious
audit history.

Every authenticated user may view and mutate the shared ship (see
``sheets/permissions.py``), so unlike the character views there is no
owner-scoping to test here -- instead these tests focus on: the ``/ship/``
redirect always resolving to the single active ship, the detail view always
being editable, and the history views never leaking old/new field values
except through the one-change detail fragment.
"""
from __future__ import annotations

import pytest

from sheets.models import ShipSheet
from sheets.services import patch_ship_field


def assert_contains(response, text):
    assert text in response.content.decode()


def assert_not_contains(response, text):
    assert text not in response.content.decode()


@pytest.mark.django_db
def test_ship_redirect_sends_to_the_active_ship(client, user_factory, ship_sheet):
    # A data migration (Task 5) already seeds one active ship, so the
    # ship_sheet fixture's row is a *second* active ship in the test
    # database -- deactivate the others so "the" active ship is
    # unambiguous, matching the v1 invariant of exactly one.
    ShipSheet.objects.exclude(pk=ship_sheet.pk).update(is_active=False)
    client.force_login(user_factory())
    response = client.get("/ship/")
    assert response.status_code == 302
    assert response.url == f"/ships/{ship_sheet.id}/"


@pytest.mark.django_db
def test_ship_redirect_requires_login(client, ship_sheet):
    response = client.get("/ship/")
    assert response.status_code == 302
    assert "/account/login/" in response.url


@pytest.mark.django_db
def test_ship_redirect_404s_when_no_active_ship_exists(client, user_factory):
    ShipSheet.objects.all().delete()
    client.force_login(user_factory())
    response = client.get("/ship/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_ship_redirect_ignores_inactive_ships(client, user_factory):
    ShipSheet.objects.all().delete()
    ShipSheet.objects.create(display_name="Mothballed", is_active=False)
    client.force_login(user_factory())
    response = client.get("/ship/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_any_authenticated_user_can_view_ship_detail(client, user_factory, ship_sheet):
    client.force_login(user_factory())
    response = client.get(f"/ships/{ship_sheet.id}/")
    assert response.status_code == 200
    assert response.context["read_only"] is False


@pytest.mark.django_db
def test_ship_detail_requires_login(client, ship_sheet):
    response = client.get(f"/ships/{ship_sheet.id}/")
    assert response.status_code == 302
    assert "/account/login/" in response.url


@pytest.mark.django_db
def test_ship_detail_404s_for_nonexistent_ship(client, user_factory):
    import uuid

    client.force_login(user_factory())
    response = client.get(f"/ships/{uuid.uuid4()}/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_ship_history_records_actor_without_rendering_values_in_list(
    client, user_factory, ship_sheet
):
    user = user_factory()
    patch_ship_field(
        sheet_id=ship_sheet.id,
        actor=user,
        field_id="ship_name",
        value="Rosinante",
        base_version=0,
    )
    client.force_login(user)
    response = client.get(f"/ships/{ship_sheet.id}/history/")
    assert_contains(response, user.username)
    assert_not_contains(response, "Rosinante")


@pytest.mark.django_db
def test_ship_history_shows_human_field_label(client, user_factory, ship_sheet):
    user = user_factory()
    patch_ship_field(
        sheet_id=ship_sheet.id,
        actor=user,
        field_id="ship_name",
        value="Rosinante",
        base_version=0,
    )
    client.force_login(user)
    response = client.get(f"/ships/{ship_sheet.id}/history/")
    assert_contains(response, "Name")


@pytest.mark.django_db
def test_ship_history_requires_login(client, ship_sheet):
    response = client.get(f"/ships/{ship_sheet.id}/history/")
    assert response.status_code == 302
    assert "/account/login/" in response.url


@pytest.mark.django_db
def test_ship_history_paginates_at_fifty(client, user_factory, ship_sheet):
    user = user_factory()
    version = 0
    for i in range(60):
        result = patch_ship_field(
            sheet_id=ship_sheet.id,
            actor=user,
            field_id="ship_essential_component_1",
            value=f"component-{i}",
            base_version=version,
        )
        version = result.version
    client.force_login(user)
    response = client.get(f"/ships/{ship_sheet.id}/history/")
    assert response.status_code == 200
    assert len(response.context["page_obj"].object_list) == 50
    assert response.context["page_obj"].paginator.num_pages == 2

    page_two = client.get(f"/ships/{ship_sheet.id}/history/", {"page": 2})
    assert len(page_two.context["page_obj"].object_list) == 10


@pytest.mark.django_db
def test_ship_history_detail_renders_old_and_new_values_escaped(
    client, user_factory, ship_sheet
):
    user = user_factory()
    patch_ship_field(
        sheet_id=ship_sheet.id,
        actor=user,
        field_id="ship_name",
        value="Rosinante",
        base_version=0,
    )
    patch_ship_field(
        sheet_id=ship_sheet.id,
        actor=user,
        field_id="ship_name",
        value="<script>alert(1)</script>",
        base_version=1,
    )
    client.force_login(user)
    change = ship_sheet.changes.order_by("-changed_at", "-id").first()
    response = client.get(f"/ships/{ship_sheet.id}/history/{change.id}/")
    assert response.status_code == 200
    body = response.content.decode()
    assert "Rosinante" in body
    assert "<script>alert(1)</script>" not in body
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body


@pytest.mark.django_db
def test_ship_history_detail_renders_booleans_in_german(client, user_factory, ship_sheet):
    user = user_factory()
    patch_ship_field(
        sheet_id=ship_sheet.id,
        actor=user,
        field_id="ship_space_available",
        value=True,
        base_version=0,
    )
    client.force_login(user)
    change = ship_sheet.changes.get(field_id="ship_space_available")
    response = client.get(f"/ships/{ship_sheet.id}/history/{change.id}/")
    assert_contains(response, "markiert")


@pytest.mark.django_db
def test_ship_history_detail_requires_login(client, user_factory, ship_sheet):
    user = user_factory()
    patch_ship_field(
        sheet_id=ship_sheet.id,
        actor=user,
        field_id="ship_name",
        value="Rosinante",
        base_version=0,
    )
    change = ship_sheet.changes.get()
    response = client.get(f"/ships/{ship_sheet.id}/history/{change.id}/")
    assert response.status_code == 302
    assert "/account/login/" in response.url


@pytest.mark.django_db
def test_ship_history_detail_404s_for_change_belonging_to_another_ship(
    client, user_factory, ship_sheet
):
    other_ship = ShipSheet.objects.create(display_name="Other", is_active=False)
    user = user_factory()
    patch_ship_field(
        sheet_id=other_ship.id,
        actor=user,
        field_id="ship_name",
        value="Rosinante",
        base_version=0,
    )
    change = other_ship.changes.get()
    client.force_login(user)
    response = client.get(f"/ships/{ship_sheet.id}/history/{change.id}/")
    assert response.status_code == 404

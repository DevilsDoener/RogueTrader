"""Contract tests for the strict JSON field-autosave endpoint on the shared
ship sheet.

``POST /ships/<uuid>/fields/<field_id>/`` is a thin HTTP wrapper around
``sheets.services.patch_ship_field`` -- see that module's docstring for the
concurrency/validation rules being wrapped here. Unlike the character
endpoint, every authenticated user (not just an owner) may mutate the ship,
so the permission-related tests below assert success rather than 404 for a
second, unrelated user.
"""
from __future__ import annotations

import json

import pytest

from sheets.models import ShipSheet
from sheets.services import patch_ship_field


def post_field(client, ship, field_id, value, base_version):
    return client.post(
        f"/ships/{ship.id}/fields/{field_id}/",
        data=json.dumps({"value": value, "base_version": base_version}),
        content_type="application/json",
    )


@pytest.mark.django_db
def test_field_patch_returns_new_version(client, user_factory, ship_sheet):
    client.force_login(user_factory())
    response = post_field(client, ship_sheet, "ship_name", "Rosinante", 0)
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == 1
    assert body["field_id"] == "ship_name"
    assert body["value"] == "Rosinante"
    assert "saved_at" in body


@pytest.mark.django_db
def test_field_patch_persists_value(client, user_factory, ship_sheet):
    client.force_login(user_factory())
    post_field(client, ship_sheet, "ship_name", "Rosinante", 0)
    ship_sheet.refresh_from_db()
    assert ship_sheet.values["ship_name"] == "Rosinante"
    assert ship_sheet.field_versions["ship_name"] == 1


@pytest.mark.django_db
def test_checkbox_field_patch_accepts_boolean(client, user_factory, ship_sheet):
    client.force_login(user_factory())
    response = post_field(client, ship_sheet, "ship_space_available", True, 0)
    assert response.status_code == 200
    assert response.json()["value"] is True


@pytest.mark.django_db
def test_two_users_can_edit_the_shared_ship(client, user_factory, ship_sheet):
    # Each field has its own independent version counter (see
    # sheets/services.py: field_versions.get(field_id, 0)) -- ship_speed has
    # never been written, so its base_version is still 0 regardless of the
    # sheet-wide version r1's write bumped ship_name to.
    first, second = user_factory(), user_factory()
    client.force_login(first)
    r1 = post_field(client, ship_sheet, "ship_name", "Rosinante", 0)
    client.force_login(second)
    r2 = post_field(client, ship_sheet, "ship_speed", "7", 0)
    assert r1.status_code == 200
    assert r2.status_code == 200


@pytest.mark.django_db
def test_same_field_conflict_returns_both_values(client, user_factory, ship_sheet):
    first, second = user_factory(), user_factory()
    client.force_login(first)
    patch_ship_field(
        sheet_id=ship_sheet.id,
        actor=first,
        field_id="ship_name",
        value="Server",
        base_version=0,
    )
    client.force_login(second)
    response = post_field(client, ship_sheet, "ship_name", "Browser", 0)
    assert response.status_code == 409
    body = response.json()
    assert body["field_id"] == "ship_name"
    assert body["submitted_value"] == "Browser"
    assert body["current_value"] == "Server"
    assert body["current_version"] == 1


@pytest.mark.django_db
def test_unknown_field_id_returns_422(client, user_factory, ship_sheet):
    client.force_login(user_factory())
    response = post_field(client, ship_sheet, "not_a_real_field", "x", 0)
    assert response.status_code == 422
    body = response.json()
    assert body["field_id"] == "not_a_real_field"
    assert "error" in body


@pytest.mark.django_db
def test_text_value_exceeding_max_length_returns_422(client, user_factory, ship_sheet):
    client.force_login(user_factory())
    # ship_class has max_length 30.
    response = post_field(client, ship_sheet, "ship_class", "x" * 31, 0)
    assert response.status_code == 422
    assert response.json()["field_id"] == "ship_class"


@pytest.mark.django_db
def test_checkbox_with_non_boolean_value_returns_422(client, user_factory, ship_sheet):
    client.force_login(user_factory())
    response = post_field(client, ship_sheet, "ship_space_available", "yes", 0)
    assert response.status_code == 422


@pytest.mark.django_db
def test_nonexistent_sheet_returns_404(client, user_factory):
    import uuid

    client.force_login(user_factory())
    bogus_id = uuid.uuid4()
    response = client.post(
        f"/ships/{bogus_id}/fields/ship_name/",
        data=json.dumps({"value": "x", "base_version": 0}),
        content_type="application/json",
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_anonymous_user_is_redirected_to_login(client, ship_sheet):
    response = post_field(client, ship_sheet, "ship_name", "x", 0)
    assert response.status_code == 302
    assert "/account/login/" in response.url


@pytest.mark.django_db
def test_get_method_not_allowed(client, user_factory, ship_sheet):
    client.force_login(user_factory())
    response = client.get(f"/ships/{ship_sheet.id}/fields/ship_name/")
    assert response.status_code == 405


@pytest.mark.django_db
def test_non_json_content_type_returns_400(client, user_factory, ship_sheet):
    client.force_login(user_factory())
    response = client.post(
        f"/ships/{ship_sheet.id}/fields/ship_name/",
        data={"value": "x", "base_version": 0},
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_extra_keys_in_body_returns_400(client, user_factory, ship_sheet):
    client.force_login(user_factory())
    response = client.post(
        f"/ships/{ship_sheet.id}/fields/ship_name/",
        data=json.dumps({"value": "x", "base_version": 0, "extra": "nope"}),
        content_type="application/json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_non_integer_base_version_returns_400(client, user_factory, ship_sheet):
    client.force_login(user_factory())
    response = post_field(client, ship_sheet, "ship_name", "x", "not-an-int")
    assert response.status_code == 400


@pytest.mark.django_db
def test_csrf_is_enforced(client, user_factory, ship_sheet):
    client.force_login(user_factory())
    client.handler.enforce_csrf_checks = True
    response = client.post(
        f"/ships/{ship_sheet.id}/fields/ship_name/",
        data=json.dumps({"value": "x", "base_version": 0}),
        content_type="application/json",
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_field_patch_does_not_touch_display_name(client, user_factory, ship_sheet):
    """Unlike the character name field, no ship field is special-cased to
    sync ``display_name`` -- confirm patching ship_name leaves it alone."""
    client.force_login(user_factory())
    post_field(client, ship_sheet, "ship_name", "Rosinante", 0)
    ship = ShipSheet.objects.get(pk=ship_sheet.id)
    assert ship.display_name == "Gemeinsames Schiff"

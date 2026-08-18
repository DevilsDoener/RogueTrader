"""Contract tests for the strict JSON field-autosave endpoint.

``POST /characters/<uuid>/fields/<field_id>/`` is a thin HTTP wrapper around
``sheets.services.patch_character_field`` -- see that module's docstring for
the concurrency/validation rules being wrapped here. These tests only check
the HTTP contract: request shape in, exact status code + JSON body out.
"""
from __future__ import annotations

import json

import pytest

from sheets.models import CharacterSheet
from sheets.services import patch_character_field


def _patch(client, character, field_id, value, base_version):
    return client.post(
        f"/characters/{character.id}/fields/{field_id}/",
        data=json.dumps({"value": value, "base_version": base_version}),
        content_type="application/json",
    )


@pytest.mark.django_db
def test_field_patch_returns_new_version(client, owner, character_sheet):
    client.force_login(owner)
    response = client.post(
        f"/characters/{character_sheet.id}/fields/c1_character_name/",
        data=json.dumps({"value": "Lucian Voss", "base_version": 0}),
        content_type="application/json",
    )
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == 1
    assert body["field_id"] == "c1_character_name"
    assert body["value"] == "Lucian Voss"
    assert "saved_at" in body


@pytest.mark.django_db
def test_field_patch_persists_value(client, owner, character_sheet):
    client.force_login(owner)
    _patch(client, character_sheet, "c1_character_name", "Lucian Voss", 0)
    character_sheet.refresh_from_db()
    assert character_sheet.values["c1_character_name"] == "Lucian Voss"
    assert character_sheet.field_versions["c1_character_name"] == 1


@pytest.mark.django_db
def test_checkbox_field_patch_accepts_boolean(client, owner, character_sheet):
    client.force_login(owner)
    response = _patch(client, character_sheet, "c1_ws_adv_1", True, 0)
    assert response.status_code == 200
    assert response.json()["value"] is True


@pytest.mark.django_db
def test_same_field_conflict_returns_both_values(client, owner, character_sheet):
    client.force_login(owner)
    patch_character_field(
        sheet_id=character_sheet.id,
        actor=owner,
        field_id="c1_character_name",
        value="Server",
        base_version=0,
    )
    response = client.post(
        f"/characters/{character_sheet.id}/fields/c1_character_name/",
        data=json.dumps({"value": "Browser", "base_version": 0}),
        content_type="application/json",
    )
    assert response.status_code == 409
    body = response.json()
    assert body["field_id"] == "c1_character_name"
    assert body["submitted_value"] == "Browser"
    assert body["current_value"] == "Server"
    assert body["current_version"] == 1


@pytest.mark.django_db
def test_unknown_field_id_returns_422(client, owner, character_sheet):
    client.force_login(owner)
    response = _patch(client, character_sheet, "not_a_real_field", "x", 0)
    assert response.status_code == 422
    body = response.json()
    assert body["field_id"] == "not_a_real_field"
    assert "error" in body


@pytest.mark.django_db
def test_text_value_exceeding_max_length_returns_422(client, owner, character_sheet):
    client.force_login(owner)
    # c1_character_name has max_length 80.
    response = _patch(client, character_sheet, "c1_character_name", "x" * 81, 0)
    assert response.status_code == 422
    assert response.json()["field_id"] == "c1_character_name"


@pytest.mark.django_db
def test_checkbox_with_non_boolean_value_returns_422(client, owner, character_sheet):
    client.force_login(owner)
    response = _patch(client, character_sheet, "c1_ws_adv_1", "yes", 0)
    assert response.status_code == 422


@pytest.mark.django_db
def test_foreign_user_receives_404(client, owner, other_user, character_sheet):
    client.force_login(other_user)
    response = _patch(client, character_sheet, "c1_character_name", "Hacked", 0)
    assert response.status_code == 404
    character_sheet.refresh_from_db()
    assert character_sheet.values == {}


@pytest.mark.django_db
def test_nonexistent_sheet_returns_404(client, owner):
    import uuid

    client.force_login(owner)
    response = _patch(client, owner, "c1_character_name", "x", 0)
    # Deliberately pass a bogus id; owner arg above is unused for id shape.
    bogus_id = uuid.uuid4()
    response = client.post(
        f"/characters/{bogus_id}/fields/c1_character_name/",
        data=json.dumps({"value": "x", "base_version": 0}),
        content_type="application/json",
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_portal_admin_cannot_mutate_foreign_character(client, portal_admin, character_sheet):
    client.force_login(portal_admin)
    response = _patch(client, character_sheet, "c1_character_name", "Hacked", 0)
    assert response.status_code == 404
    character_sheet.refresh_from_db()
    assert character_sheet.values == {}


@pytest.mark.django_db
def test_anonymous_user_is_redirected_to_login(client, character_sheet):
    response = _patch(client, character_sheet, "c1_character_name", "x", 0)
    assert response.status_code == 302
    assert "/account/login/" in response.url


@pytest.mark.django_db
def test_get_method_not_allowed(client, owner, character_sheet):
    client.force_login(owner)
    response = client.get(f"/characters/{character_sheet.id}/fields/c1_character_name/")
    assert response.status_code == 405


@pytest.mark.django_db
def test_non_json_content_type_returns_400(client, owner, character_sheet):
    client.force_login(owner)
    response = client.post(
        f"/characters/{character_sheet.id}/fields/c1_character_name/",
        data={"value": "x", "base_version": 0},
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_extra_keys_in_body_returns_400(client, owner, character_sheet):
    client.force_login(owner)
    response = client.post(
        f"/characters/{character_sheet.id}/fields/c1_character_name/",
        data=json.dumps({"value": "x", "base_version": 0, "extra": "nope"}),
        content_type="application/json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_non_integer_base_version_returns_400(client, owner, character_sheet):
    client.force_login(owner)
    response = _patch(client, character_sheet, "c1_character_name", "x", "not-an-int")
    assert response.status_code == 400


@pytest.mark.django_db
def test_csrf_is_enforced(client, owner, character_sheet):
    client.force_login(owner)
    client.handler.enforce_csrf_checks = True
    response = client.post(
        f"/characters/{character_sheet.id}/fields/c1_character_name/",
        data=json.dumps({"value": "x", "base_version": 0}),
        content_type="application/json",
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_field_patch_syncs_display_name(client, owner, character_sheet):
    client.force_login(owner)
    _patch(client, character_sheet, "c1_character_name", "Lucian Voss", 0)
    character = CharacterSheet.objects.get(pk=character_sheet.id)
    assert character.display_name == "Lucian Voss"

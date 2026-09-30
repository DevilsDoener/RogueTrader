"""HTTP contract shared by both strict JSON field-autosave endpoints.

``POST /characters/<uuid>/fields/<field_id>/`` and
``POST /ships/<uuid>/fields/<field_id>/`` are thin HTTP wrappers around
``sheets.services.patch_character_field`` / ``patch_ship_field`` -- see that
module's docstring for the concurrency/validation rules being wrapped here.
Every test below runs once per endpoint and only checks the HTTP contract:
request shape in, exact status code + JSON body out. Endpoint-specific
behaviour (owner scoping, display-name sync, several users on the ship) lives
in ``test_field_api.py`` and ``test_ship_field_api.py``.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Callable

import pytest

from sheets.services import patch_character_field, patch_ship_field


@dataclass
class Endpoint:
    url_prefix: str
    sheet: object
    #: The user who is allowed to mutate ``sheet`` through this endpoint.
    actor: object
    #: Who writes the "server" value in the conflict test: the owner again
    #: for a character, a second user for the shared ship.
    conflicting_actor: object
    patch_service: Callable
    text_field: str
    text_max_length: int
    checkbox_field: str

    def url(self, field_id, sheet_id=None):
        return f"{self.url_prefix}/{sheet_id or self.sheet.id}/fields/{field_id}/"

    def post(self, client, field_id, value, base_version):
        return client.post(
            self.url(field_id),
            data=json.dumps({"value": value, "base_version": base_version}),
            content_type="application/json",
        )


@pytest.fixture(params=["character", "ship"])
def endpoint(request):
    if request.param == "character":
        owner = request.getfixturevalue("owner")
        return Endpoint(
            url_prefix="/characters",
            sheet=request.getfixturevalue("character_sheet"),
            actor=owner,
            conflicting_actor=owner,
            patch_service=patch_character_field,
            text_field="c1_character_name",
            text_max_length=80,
            checkbox_field="c1_ws_adv_1",
        )
    user_factory = request.getfixturevalue("user_factory")
    return Endpoint(
        url_prefix="/ships",
        sheet=request.getfixturevalue("ship_sheet"),
        actor=user_factory(),
        conflicting_actor=user_factory(),
        patch_service=patch_ship_field,
        text_field="ship_class",
        text_max_length=30,
        checkbox_field="ship_weapon_1_location_dorsal",
    )


@pytest.mark.django_db
def test_field_patch_returns_new_version(client, endpoint):
    client.force_login(endpoint.actor)
    response = endpoint.post(client, endpoint.text_field, "Rosinante", 0)
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == 1
    assert body["field_id"] == endpoint.text_field
    assert body["value"] == "Rosinante"
    assert "saved_at" in body


@pytest.mark.django_db
def test_field_patch_persists_value(client, endpoint):
    client.force_login(endpoint.actor)
    endpoint.post(client, endpoint.text_field, "Rosinante", 0)
    endpoint.sheet.refresh_from_db()
    assert endpoint.sheet.values[endpoint.text_field] == "Rosinante"
    assert endpoint.sheet.field_versions[endpoint.text_field] == 1


@pytest.mark.django_db
def test_checkbox_field_patch_accepts_boolean(client, endpoint):
    client.force_login(endpoint.actor)
    response = endpoint.post(client, endpoint.checkbox_field, True, 0)
    assert response.status_code == 200
    assert response.json()["value"] is True


@pytest.mark.django_db
def test_same_field_conflict_returns_both_values(client, endpoint):
    endpoint.patch_service(
        sheet_id=endpoint.sheet.id,
        actor=endpoint.conflicting_actor,
        field_id=endpoint.text_field,
        value="Server",
        base_version=0,
    )
    client.force_login(endpoint.actor)
    response = endpoint.post(client, endpoint.text_field, "Browser", 0)
    assert response.status_code == 409
    body = response.json()
    assert body["field_id"] == endpoint.text_field
    assert body["submitted_value"] == "Browser"
    assert body["current_value"] == "Server"
    assert body["current_version"] == 1


@pytest.mark.django_db
def test_unknown_field_id_returns_422(client, endpoint):
    client.force_login(endpoint.actor)
    response = endpoint.post(client, "not_a_real_field", "x", 0)
    assert response.status_code == 422
    body = response.json()
    assert body["field_id"] == "not_a_real_field"
    assert "error" in body


@pytest.mark.django_db
def test_text_value_exceeding_max_length_returns_422(client, endpoint):
    client.force_login(endpoint.actor)
    response = endpoint.post(client, endpoint.text_field, "x" * (endpoint.text_max_length + 1), 0)
    assert response.status_code == 422
    assert response.json()["field_id"] == endpoint.text_field


@pytest.mark.django_db
def test_checkbox_with_non_boolean_value_returns_422(client, endpoint):
    client.force_login(endpoint.actor)
    response = endpoint.post(client, endpoint.checkbox_field, "yes", 0)
    assert response.status_code == 422


@pytest.mark.django_db
def test_nonexistent_sheet_returns_404(client, endpoint):
    client.force_login(endpoint.actor)
    response = client.post(
        endpoint.url(endpoint.text_field, sheet_id=uuid.uuid4()),
        data=json.dumps({"value": "x", "base_version": 0}),
        content_type="application/json",
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_anonymous_user_is_redirected_to_login(client, endpoint):
    response = endpoint.post(client, endpoint.text_field, "x", 0)
    assert response.status_code == 302
    assert "/account/login/" in response.url


@pytest.mark.django_db
def test_get_method_not_allowed(client, endpoint):
    client.force_login(endpoint.actor)
    response = client.get(endpoint.url(endpoint.text_field))
    assert response.status_code == 405


@pytest.mark.django_db
def test_non_json_content_type_returns_400(client, endpoint):
    client.force_login(endpoint.actor)
    response = client.post(endpoint.url(endpoint.text_field), data={"value": "x", "base_version": 0})
    assert response.status_code == 400


@pytest.mark.django_db
def test_extra_keys_in_body_returns_400(client, endpoint):
    client.force_login(endpoint.actor)
    response = client.post(
        endpoint.url(endpoint.text_field),
        data=json.dumps({"value": "x", "base_version": 0, "extra": "nope"}),
        content_type="application/json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_non_integer_base_version_returns_400(client, endpoint):
    client.force_login(endpoint.actor)
    response = endpoint.post(client, endpoint.text_field, "x", "not-an-int")
    assert response.status_code == 400


@pytest.mark.django_db
def test_csrf_is_enforced(client, endpoint):
    client.force_login(endpoint.actor)
    client.handler.enforce_csrf_checks = True
    response = endpoint.post(client, endpoint.text_field, "x", 0)
    assert response.status_code == 403

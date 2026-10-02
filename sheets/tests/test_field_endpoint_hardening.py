"""Hardening of the two strict JSON field endpoints (character and ship).

Unsafe text, oversized or hostile bodies and no-op writes. Runs once per
endpoint through the ``endpoint`` fixture of the contract tests.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from sheets.models import SheetChange
from sheets.tests.test_field_endpoint_contract import endpoint  # noqa: F401  (fixture)

#: Raw JSON values (not ``json.dumps`` output) so a lone surrogate really
#: arrives as the ``\ud800`` escape a hostile client would send.
UNSAFE_VALUES = [
    pytest.param(r'"\ud800"', id="lone-surrogate"),
    pytest.param(r'"a\u0000b"', id="nul"),
    pytest.param(r'"zeile1\nzeile2"', id="newline"),
    pytest.param(r'"a\tb"', id="tab"),
    pytest.param(r'"\u001b[31m"', id="escape"),
    pytest.param(r'"\u0085"', id="c1-next-line"),
    pytest.param(r'"‮egap"', id="bidi-override"),
    pytest.param(r'"⁦x⁩"', id="bidi-isolate"),
]


def _post_raw(client, endpoint, field_id, raw_value, base_version=0):
    return client.post(
        endpoint.url(field_id),
        data=f'{{"value": {raw_value}, "base_version": {base_version}}}',
        content_type="application/json",
    )


@pytest.mark.django_db
@pytest.mark.parametrize("raw_value", UNSAFE_VALUES)
def test_text_with_unsafe_characters_returns_422_and_stores_nothing(client, endpoint, raw_value):
    client.force_login(endpoint.actor)
    response = _post_raw(client, endpoint, endpoint.text_field, raw_value)
    assert response.status_code == 422
    assert "ungültige Zeichen" in response.json()["error"]
    endpoint.sheet.refresh_from_db()
    assert endpoint.text_field not in endpoint.sheet.values
    assert endpoint.sheet.version == 0


@pytest.mark.django_db
def test_page_still_renders_after_a_rejected_surrogate(client, endpoint):
    client.force_login(endpoint.actor)
    _post_raw(client, endpoint, endpoint.text_field, r'"\ud800"')
    assert client.get(f"{endpoint.url_prefix}/{endpoint.sheet.id}/").status_code == 200


@pytest.mark.django_db
def test_text_with_umlauts_and_emoji_is_accepted(client, endpoint):
    client.force_login(endpoint.actor)
    response = endpoint.post(client, endpoint.text_field, "Größe – Üx 🚀", 0)
    assert response.status_code == 200


@pytest.mark.django_db
def test_oversized_body_returns_413(client, endpoint):
    client.force_login(endpoint.actor)
    body = json.dumps({"value": "x" * 5000, "base_version": 0})
    response = client.post(endpoint.url(endpoint.text_field), data=body, content_type="application/json")
    assert response.status_code == 413
    assert "zu groß" in response.json()["error"]


@pytest.mark.django_db
def test_deeply_nested_json_is_rejected_before_it_is_parsed(client, endpoint):
    """The original probe: ~200 KB of ``[`` made ``json.loads`` raise RecursionError (500)."""
    client.force_login(endpoint.actor)
    nested = "[" * 100_000 + "]" * 100_000
    response = client.post(
        endpoint.url(endpoint.text_field),
        data=f'{{"value": {nested}, "base_version": 0}}',
        content_type="application/json",
    )
    assert response.status_code == 413


@pytest.mark.django_db
def test_nesting_that_fits_the_size_limit_never_gives_a_500(client, endpoint):
    client.force_login(endpoint.actor)
    nested = "[" * 2000 + "]" * 2000
    response = client.post(
        endpoint.url(endpoint.text_field),
        data=f'{{"value": {nested}, "base_version": 0}}',
        content_type="application/json",
    )
    assert response.status_code in (400, 422)


@pytest.mark.django_db
def test_a_recursion_error_while_parsing_returns_400(client, endpoint, monkeypatch):
    def too_deep(*args, **kwargs):
        raise RecursionError("maximum recursion depth exceeded while decoding a JSON array")

    monkeypatch.setattr("sheets.views.json", SimpleNamespace(loads=too_deep))
    client.force_login(endpoint.actor)
    response = endpoint.post(client, endpoint.text_field, "x", 0)
    assert response.status_code == 400


@pytest.mark.django_db
def test_writing_the_stored_value_again_is_a_noop(client, endpoint):
    client.force_login(endpoint.actor)
    first = endpoint.post(client, endpoint.text_field, "Rosinante", 0).json()
    changes = SheetChange.objects.count()
    endpoint.sheet.refresh_from_db()
    sheet_version = endpoint.sheet.version

    again = endpoint.post(client, endpoint.text_field, "Rosinante", first["version"])

    assert again.status_code == 200
    assert again.json()["version"] == first["version"]
    assert again.json()["value"] == "Rosinante"
    assert SheetChange.objects.count() == changes
    endpoint.sheet.refresh_from_db()
    assert endpoint.sheet.version == sheet_version
    assert endpoint.sheet.field_versions[endpoint.text_field] == first["version"]


@pytest.mark.django_db
def test_noop_write_with_a_stale_version_still_conflicts(client, endpoint):
    client.force_login(endpoint.actor)
    endpoint.post(client, endpoint.text_field, "Rosinante", 0)
    assert endpoint.post(client, endpoint.text_field, "Rosinante", 0).status_code == 409

"""Character-only behaviour of the field-autosave endpoint
``POST /characters/<uuid>/fields/<field_id>/``: owner scoping and the
``display_name`` sync. The HTTP contract it shares with the ship endpoint is
covered in ``test_field_endpoint_contract.py``.
"""
from __future__ import annotations

import json

import pytest

from sheets.models import CharacterSheet


def _patch(client, character, field_id, value, base_version):
    return client.post(
        f"/characters/{character.id}/fields/{field_id}/",
        data=json.dumps({"value": value, "base_version": base_version}),
        content_type="application/json",
    )


@pytest.mark.django_db
def test_foreign_user_receives_404(client, owner, other_user, character_sheet):
    client.force_login(other_user)
    response = _patch(client, character_sheet, "c1_character_name", "Hacked", 0)
    assert response.status_code == 404
    character_sheet.refresh_from_db()
    assert character_sheet.values == {}


@pytest.mark.django_db
def test_portal_admin_cannot_mutate_foreign_character(client, portal_admin, character_sheet):
    client.force_login(portal_admin)
    response = _patch(client, character_sheet, "c1_character_name", "Hacked", 0)
    assert response.status_code == 404
    character_sheet.refresh_from_db()
    assert character_sheet.values == {}


@pytest.mark.django_db
def test_field_patch_syncs_display_name(client, owner, character_sheet):
    client.force_login(owner)
    _patch(client, character_sheet, "c1_character_name", "Lucian Voss", 0)
    character = CharacterSheet.objects.get(pk=character_sheet.id)
    assert character.display_name == "Lucian Voss"

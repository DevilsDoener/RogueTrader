"""Ship-only behaviour of the field-autosave endpoint
``POST /ships/<uuid>/fields/<field_id>/``. Unlike the character endpoint,
every authenticated user (not just an owner) may mutate the ship, so these
tests assert success for a second, unrelated user. The HTTP contract it
shares with the character endpoint is covered in
``test_field_endpoint_contract.py``.
"""
from __future__ import annotations

import json

import pytest

from sheets.models import ShipSheet


def post_field(client, ship, field_id, value, base_version):
    return client.post(
        f"/ships/{ship.id}/fields/{field_id}/",
        data=json.dumps({"value": value, "base_version": base_version}),
        content_type="application/json",
    )


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
def test_field_patch_does_not_touch_display_name(client, user_factory, ship_sheet):
    """Unlike the character name field, no ship field is special-cased to
    sync ``display_name`` -- confirm patching ship_name leaves it alone."""
    client.force_login(user_factory())
    post_field(client, ship_sheet, "ship_name", "Rosinante", 0)
    ship = ShipSheet.objects.get(pk=ship_sheet.id)
    assert ship.display_name == "Gemeinsames Schiff"

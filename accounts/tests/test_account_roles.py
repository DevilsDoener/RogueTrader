"""Granting and revoking the portal-admin role from the account management.

Guard rails: only portal admins may change roles, nobody can take the role
away from themself, and the last active portal admin keeps it. Every change
is its own ``managed_account_role_changed`` audit event.
"""
import logging

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from accounts.services import AccountRuleViolation, create_managed_user, update_managed_user
from tests.html import has_attr, select_one

TEMP = "Temp-Password-42!"


def _edit(client, user, *, username=None, active=True, admin=False):
    data = {"username": username or user.username}
    if active:
        data["is_active"] = "on"
    if admin:
        data["is_portal_admin"] = "on"
    return client.post(reverse("accounts:admin_user_edit", kwargs={"pk": user.pk}), data)


@pytest.mark.django_db
def test_create_form_can_make_an_admin(client, portal_admin):
    client.force_login(portal_admin)

    client.post(
        reverse("accounts:admin_user_create"),
        {"username": "zweiter", "temporary_password": TEMP, "is_portal_admin": "on"},
    )

    assert get_user_model().objects.get(username="zweiter").is_portal_admin is True


@pytest.mark.django_db
def test_new_accounts_are_players_by_default(client, portal_admin):
    client.force_login(portal_admin)

    client.post(
        reverse("accounts:admin_user_create"), {"username": "spieler", "temporary_password": TEMP}
    )

    assert get_user_model().objects.get(username="spieler").is_portal_admin is False


@pytest.mark.django_db
def test_edit_grants_and_revokes_the_role(client, portal_admin, user_factory):
    player = user_factory(username="spieler")
    client.force_login(portal_admin)

    _edit(client, player, admin=True)
    player.refresh_from_db()
    assert player.is_portal_admin is True

    _edit(client, player, admin=False)
    player.refresh_from_db()
    assert player.is_portal_admin is False


@pytest.mark.django_db
def test_edit_form_shows_the_current_role(client, portal_admin, user_factory):
    other_admin = user_factory(username="zweiter", is_portal_admin=True)
    client.force_login(portal_admin)

    html = client.get(
        reverse("accounts:admin_user_edit", kwargs={"pk": other_admin.pk})
    ).content.decode()

    assert has_attr(select_one(html, "input[name=is_portal_admin]"), "checked")


@pytest.mark.django_db
def test_nobody_can_revoke_their_own_role(client, portal_admin, user_factory):
    user_factory(username="zweiter", is_portal_admin=True)
    client.force_login(portal_admin)

    response = _edit(client, portal_admin, admin=False)

    portal_admin.refresh_from_db()
    assert portal_admin.is_portal_admin is True
    assert "Du kannst dir die Admin-Rolle nicht selbst entziehen." in response.content.decode()


@pytest.mark.django_db
def test_the_last_active_admin_keeps_the_role(portal_admin, user_factory):
    # Defensive rule: through the views the acting admin is always active, so
    # this only bites when the service is called directly.
    last = user_factory(username="letzter", is_portal_admin=True)
    portal_admin.is_active = False
    portal_admin.save()

    with pytest.raises(AccountRuleViolation):
        update_managed_user(
            actor=portal_admin, user=last, username="letzter", active=True, portal_admin=False
        )

    last.refresh_from_db()
    assert last.is_portal_admin is True


@pytest.mark.django_db
def test_leaving_the_role_out_keeps_it(portal_admin, user_factory):
    other_admin = user_factory(username="zweiter", is_portal_admin=True)

    update_managed_user(actor=portal_admin, user=other_admin, username="umbenannt", active=True)

    other_admin.refresh_from_db()
    assert (other_admin.username, other_admin.is_portal_admin) == ("umbenannt", True)


@pytest.mark.django_db
def test_a_player_cannot_change_roles(client, user_factory):
    player = user_factory(username="spieler")
    client.force_login(player)

    assert _edit(client, player, admin=True).status_code == 403
    player.refresh_from_db()
    assert player.is_portal_admin is False


@pytest.mark.django_db
def test_role_changes_are_audited(portal_admin, user_factory, caplog):
    player = user_factory(username="spieler")
    with caplog.at_level(logging.INFO, logger="accounts.audit"):
        update_managed_user(
            actor=portal_admin, user=player, username="spieler", active=True, portal_admin=True
        )
        create_managed_user(
            actor=portal_admin, username="neu", temporary_password=TEMP, portal_admin=True
        )

    messages = [r.getMessage() for r in caplog.records if r.name == "accounts.audit"]
    assert (
        "managed_account_role_changed actor='portal-admin' target='spieler' portal_admin=True"
        in messages
    )
    assert (
        "managed_account_role_changed actor='portal-admin' target='neu' portal_admin=True"
        in messages
    )


@pytest.mark.django_db
def test_an_unchanged_role_logs_no_role_event(portal_admin, user_factory, caplog):
    player = user_factory(username="spieler")
    with caplog.at_level(logging.INFO, logger="accounts.audit"):
        update_managed_user(
            actor=portal_admin, user=player, username="spieler", active=True, portal_admin=False
        )

    assert not any("role_changed" in r.getMessage() for r in caplog.records)

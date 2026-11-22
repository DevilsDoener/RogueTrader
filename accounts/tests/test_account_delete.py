"""Deleting an account from the portal's account management.

Same guard rails as deactivating: portal admins only, never one's own
account, never the last active portal admin, never a Django staff/superuser
account. The account's characters go with it; history entries stay nameless.
"""
import logging

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.urls import reverse

from accounts.services import AccountRuleViolation, delete_managed_user
from sheets.models import CharacterSheet, SheetChange


def _delete_url(user):
    return reverse("accounts:admin_user_delete", kwargs={"pk": user.pk})


@pytest.mark.django_db
def test_confirmation_page_lists_the_characters_that_go_with_the_account(
    client, portal_admin, user_factory, character_factory
):
    player = user_factory(username="spieler")
    character_factory(owner=player, display_name="Lucian")
    client.force_login(portal_admin)

    response = client.get(_delete_url(player))

    html = response.content.decode()
    assert response.status_code == 200
    assert "Konto &bdquo;spieler&ldquo; l&ouml;schen?" in html
    assert "Lucian" in html
    assert get_user_model().objects.filter(pk=player.pk).exists()


@pytest.mark.django_db
def test_post_deletes_the_account_and_its_characters(
    client, portal_admin, user_factory, character_factory, ship_sheet
):
    player = user_factory(username="spieler")
    character_factory(owner=player, display_name="Lucian")
    change = SheetChange.objects.create(
        ship=ship_sheet, actor=player, field_id="ship_name", resulting_version=1
    )
    client.force_login(portal_admin)

    response = client.post(_delete_url(player), follow=True)

    assert not get_user_model().objects.filter(pk=player.pk).exists()
    assert not CharacterSheet.objects.filter(display_name="Lucian").exists()
    change.refresh_from_db()
    assert change.actor is None
    assert "Das Konto „spieler“ wurde gelöscht." in response.content.decode()


@pytest.mark.django_db
def test_deleting_is_audited(portal_admin, user_factory, caplog):
    player = user_factory(username="spieler")
    with caplog.at_level(logging.INFO, logger="accounts.audit"):
        delete_managed_user(actor=portal_admin, user=player)

    messages = [r.getMessage() for r in caplog.records if r.name == "accounts.audit"]
    assert any(
        m.startswith("managed_account_deleted actor='portal-admin' target='spieler'")
        for m in messages
    )


@pytest.mark.django_db
def test_an_admin_cannot_delete_their_own_account(client, portal_admin):
    client.force_login(portal_admin)

    response = client.post(_delete_url(portal_admin), follow=True)

    assert get_user_model().objects.filter(pk=portal_admin.pk).exists()
    assert "Du kannst dein eigenes Konto nicht löschen." in response.content.decode()


@pytest.mark.django_db
def test_another_portal_admin_can_be_deleted_while_one_stays_active(
    portal_admin, user_factory
):
    other_admin = user_factory(username="zweiter", is_portal_admin=True)

    delete_managed_user(actor=portal_admin, user=other_admin)

    assert not get_user_model().objects.filter(pk=other_admin.pk).exists()


@pytest.mark.django_db
def test_the_last_active_portal_admin_cannot_be_deleted(portal_admin, user_factory):
    # Defensive rule: through the views the acting admin is always an active
    # admin themself, so this only bites when the service is called directly.
    last = user_factory(username="letzter", is_portal_admin=True)
    portal_admin.is_active = False
    portal_admin.save()

    with pytest.raises(AccountRuleViolation):
        delete_managed_user(actor=portal_admin, user=last)

    assert get_user_model().objects.filter(pk=last.pk).exists()


@pytest.mark.django_db
def test_a_normal_user_cannot_delete(client, user_factory):
    victim = user_factory()
    client.force_login(user_factory())

    assert client.post(_delete_url(victim)).status_code == 403
    assert get_user_model().objects.filter(pk=victim.pk).exists()

    with pytest.raises(PermissionDenied):
        delete_managed_user(actor=user_factory(), user=victim)


@pytest.mark.django_db
def test_django_staff_accounts_are_not_reachable(client, portal_admin, user_factory):
    staff = user_factory(is_staff=True)
    client.force_login(portal_admin)

    assert client.post(_delete_url(staff)).status_code == 404
    assert get_user_model().objects.filter(pk=staff.pk).exists()


@pytest.mark.django_db
def test_get_never_deletes(client, portal_admin, user_factory):
    player = user_factory()
    client.force_login(portal_admin)
    client.get(_delete_url(player))
    assert get_user_model().objects.filter(pk=player.pk).exists()


@pytest.mark.django_db
def test_list_offers_delete_for_others_but_not_for_yourself(
    client, portal_admin, user_factory
):
    player = user_factory()
    client.force_login(portal_admin)

    html = client.get(reverse("accounts:admin_user_list")).content.decode()

    assert f'href="{_delete_url(player)}"' in html
    assert f'href="{_delete_url(portal_admin)}"' not in html

"""The portal addresses people with "du". Django's German catalogue and its
built-in CSRF failure page use formal or impersonal wording, so the messages
that can actually appear on the portal's pages are overridden."""
import re

import pytest
from django.test import Client
from django.urls import reverse

from accounts.forms import RequiredPasswordChangeForm

FORMAL = re.compile(r"\b(Sie|Ihnen|Ihr|Ihre|Ihren|Ihrem|Ihrer|Ihres)\b")


def assert_no_formal_address(text):
    match = FORMAL.search(text)
    assert match is None, f"formal address {match.group(0)!r} in: {text[:200]}"


@pytest.mark.django_db
def test_password_change_form_messages_use_du(user_factory):
    user = user_factory(password="Temp-Only-42!")
    form = RequiredPasswordChangeForm(
        user,
        {
            "old_password": "falsch",
            "new_password1": "Safer-Password-43!",
            "new_password2": "Anderes-Passwort-44!",
        },
    )

    assert not form.is_valid()
    assert form.errors["old_password"] == [
        "Dein aktuelles Passwort stimmt nicht. Gib es bitte noch einmal ein."
    ]
    assert form.errors["new_password2"] == [
        "Die beiden neuen Passwörter stimmen nicht überein."
    ]
    assert form.fields["new_password2"].help_text == (
        "Gib dasselbe neue Passwort zur Bestätigung noch einmal ein."
    )


@pytest.mark.django_db
def test_forced_password_change_page_has_no_formal_address(client, user_factory):
    user = user_factory(password="Temp-Only-42!", must_change_password=True)
    client.force_login(user)

    response = client.post(
        reverse("accounts:change_required"),
        {"old_password": "falsch", "new_password1": "1234", "new_password2": "9999"},
    )

    assert response.status_code == 200
    assert_no_formal_address(response.content.decode())


@pytest.mark.django_db
def test_login_and_character_create_errors_have_no_formal_address(client, user_factory):
    anonymous_page = client.post(reverse("accounts:login"), {"username": "", "password": ""})
    assert_no_formal_address(anonymous_page.content.decode())

    client.force_login(user_factory())
    created = client.post(reverse("sheets:character_list"), {"display_name": ""})
    assert_no_formal_address(created.content.decode())


@pytest.mark.django_db
def test_admin_account_forms_have_no_formal_address(client, portal_admin):
    client.force_login(portal_admin)

    response = client.post(
        reverse("accounts:admin_user_create"),
        {"username": "", "temporary_password": "1234"},
    )

    assert response.status_code == 200
    assert_no_formal_address(response.content.decode())


@pytest.mark.django_db
def test_csrf_failure_page_uses_du():
    strict_client = Client(enforce_csrf_checks=True)

    response = strict_client.post(
        reverse("accounts:login"), {"username": "x", "password": "y"}
    )

    assert response.status_code == 403
    body = response.content.decode()
    assert "Deine Anfrage konnte nicht bestätigt werden" in body
    assert_no_formal_address(body)

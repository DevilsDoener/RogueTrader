"""One username rule for create, edit and bootstrap_admin (AUTH-4)."""
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse

from accounts.forms import ManagedUserCreateForm, ManagedUserForm
from accounts.models import User
from accounts.services import create_managed_user, update_managed_user

TEMP = "Temp-Only-42!"

CONFUSABLE_NAMES = [
    "аdmin",  # Cyrillic a
    "admin​",  # zero-width space
    "ad​min",
    "x‮y",  # right-to-left override
    "line\nbreak",
    "a b",
    "tab\tname",
    "ümlaut",
    "<script>",
    "ａdmin",  # fullwidth a
]


@pytest.mark.django_db
@pytest.mark.parametrize("name", CONFUSABLE_NAMES)
def test_create_form_rejects_confusable_and_control_characters(name):
    form = ManagedUserCreateForm({"username": name, "temporary_password": TEMP})

    assert not form.is_valid()
    assert "username" in form.errors


@pytest.mark.django_db
@pytest.mark.parametrize("name", CONFUSABLE_NAMES)
def test_edit_form_rejects_the_same_names(user_factory, name):
    crew = user_factory(username="crew")

    form = ManagedUserForm({"username": name, "is_active": "on"}, instance=crew)

    assert not form.is_valid()
    assert "username" in form.errors


@pytest.mark.django_db
@pytest.mark.parametrize("name", ["crew", "Anna.K-2", "a_b+c@host", "x" * 150])
def test_ordinary_names_pass_both_forms(user_factory, name):
    crew = user_factory(username="other")

    assert ManagedUserCreateForm({"username": name, "temporary_password": TEMP}).is_valid()
    assert ManagedUserForm({"username": name, "is_active": "on"}, instance=crew).is_valid()


@pytest.mark.django_db
def test_names_are_trimmed():
    form = ManagedUserCreateForm({"username": "  crew  ", "temporary_password": TEMP})

    assert form.is_valid()
    assert form.cleaned_data["username"] == "crew"


@pytest.mark.django_db
def test_too_long_names_get_a_german_message():
    form = ManagedUserCreateForm({"username": "x" * 151, "temporary_password": TEMP})

    assert form.errors["username"] == ["Der Benutzername darf höchstens 150 Zeichen lang sein."]


@pytest.mark.django_db
@pytest.mark.parametrize("taken", ["alice", "Alice", "ALICE"])
def test_uniqueness_is_case_insensitive_on_create(user_factory, taken):
    user_factory(username="alice")

    form = ManagedUserCreateForm({"username": taken, "temporary_password": TEMP})

    assert form.errors["username"] == ["Dieser Benutzername ist bereits vergeben."]


@pytest.mark.django_db
def test_uniqueness_is_case_insensitive_on_edit(user_factory):
    user_factory(username="alice")
    crew = user_factory(username="crew")

    form = ManagedUserForm({"username": "Alice", "is_active": "on"}, instance=crew)

    assert form.errors["username"] == ["Dieser Benutzername ist bereits vergeben."]


@pytest.mark.django_db
def test_changing_only_the_case_of_the_own_name_is_allowed(user_factory):
    crew = user_factory(username="crew")

    assert ManagedUserForm({"username": "Crew", "is_active": "on"}, instance=crew).is_valid()


@pytest.mark.django_db
def test_existing_odd_usernames_stay_editable_unchanged(user_factory):
    old = user_factory(username="old name ü")
    twin = user_factory(username="Twin")
    user_factory(username="twin2")  # not a clash, just company

    unchanged = ManagedUserForm({"username": "old name ü", "is_active": ""}, instance=old)
    twin_form = ManagedUserForm({"username": "Twin", "is_active": "on"}, instance=twin)

    assert unchanged.is_valid(), unchanged.errors
    assert twin_form.is_valid()


@pytest.mark.django_db
def test_existing_case_variant_pairs_can_still_be_deactivated_via_edit(user_factory):
    user_factory(username="alice")
    legacy = user_factory(username="Alice")

    form = ManagedUserForm({"username": "Alice"}, instance=legacy)  # Aktiv unticked

    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_the_edit_form_keeps_the_old_name_until_the_service_saves(user_factory):
    crew = user_factory(username="crew")

    form = ManagedUserForm({"username": "renamed", "is_active": "on"}, instance=crew)

    assert form.is_valid()
    assert crew.username == "crew"


@pytest.mark.django_db
def test_services_apply_the_same_rule(portal_admin, user_factory):
    from django.core.exceptions import ValidationError

    crew = user_factory(username="crew")

    with pytest.raises(ValidationError):
        create_managed_user(actor=portal_admin, username="Crew", temporary_password=TEMP)
    with pytest.raises(ValidationError):
        update_managed_user(actor=portal_admin, user=crew, username="cr​ew", active=True)
    assert not User.objects.filter(username__iexact="cr​ew").exists()


@pytest.mark.django_db
def test_http_create_with_a_lookalike_shows_the_german_error(client, portal_admin, user_factory):
    user_factory(username="admin")
    client.force_login(portal_admin)

    response = client.post(
        reverse("accounts:admin_user_create"), {"username": "аdmin", "temporary_password": TEMP}
    )

    assert response.status_code == 200
    assert "darf nur Buchstaben (A-Z), Ziffern und @ . + - _ enthalten" in response.content.decode()
    assert not User.objects.filter(username="аdmin").exists()


@pytest.mark.django_db
def test_bootstrap_admin_uses_the_same_rule(user_factory):
    user_factory(username="gm")

    with pytest.raises(CommandError, match="already exists"):
        call_command("bootstrap_admin", username="GM", password="Valid-Password-42!")
    with pytest.raises(CommandError, match="Buchstaben"):
        call_command("bootstrap_admin", username="g m", password="Valid-Password-42!")

    call_command("bootstrap_admin", username="gm2", password="Valid-Password-42!")
    assert User.objects.get(username="gm2").is_portal_admin

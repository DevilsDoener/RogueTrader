import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_temporary_password_forces_change(client, user_factory):
    user = user_factory(password="Temp-Only-42!", must_change_password=True)

    assert client.login(username=user.username, password="Temp-Only-42!")

    response = client.get("/dashboard/")

    assert response.status_code == 302
    assert response.url == "/account/change-required/"


@pytest.mark.django_db
def test_changing_temporary_password_restores_access(client, user_factory):
    user = user_factory(password="Temp-Only-42!", must_change_password=True)
    assert client.login(username=user.username, password="Temp-Only-42!")

    response = client.post(
        reverse("accounts:change_required"),
        {
            "old_password": "Temp-Only-42!",
            "new_password1": "Safer-Password-43!",
            "new_password2": "Safer-Password-43!",
        },
    )

    user.refresh_from_db()
    assert response.status_code == 302
    assert response.url == "/dashboard/"
    assert user.must_change_password is False
    assert client.get("/dashboard/").status_code == 200


@pytest.mark.django_db
def test_inactive_user_cannot_keep_using_session(client, user_factory):
    user = user_factory(password="Valid-Password-42!")
    client.force_login(user)
    user.is_active = False
    user.save(update_fields=["is_active"])

    assert client.get("/dashboard/").status_code == 302


@pytest.mark.django_db
def test_login_refuses_an_external_next_url(client, user_factory):
    user_factory(username="crew", password="Valid-Password-42!")

    response = client.post(
        reverse("accounts:login"),
        {
            "username": "crew",
            "password": "Valid-Password-42!",
            "next": "https://attacker.invalid/steal-session",
        },
    )

    assert response.status_code == 302
    assert response.url == "/dashboard/"


@pytest.mark.django_db
def test_logout_requires_a_post_request(client, user_factory):
    user = user_factory()
    client.force_login(user)

    response = client.get(reverse("accounts:logout"))

    assert response.status_code == 405
    assert client.get("/dashboard/").status_code == 200

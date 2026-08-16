import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import LoginThrottle


@pytest.mark.django_db
def test_login_blocks_after_five_failures_and_uses_generic_error(client, user_factory):
    user_factory(username="crew", password="Correct-Password-42!")
    login_url = reverse("accounts:login")

    for _ in range(5):
        response = client.post(login_url, {"username": "crew", "password": "wrong"})
        assert response.status_code == 200
        assert "Invalid username or password." in response.content.decode()

    response = client.post(
        login_url,
        {"username": "crew", "password": "Correct-Password-42!"},
    )

    throttle = LoginThrottle.objects.get()
    assert response.status_code == 200
    assert "Invalid username or password." in response.content.decode()
    assert throttle.failure_count == 5
    assert throttle.blocked_until > timezone.now()


@pytest.mark.django_db
def test_successful_login_resets_failure_count(client, user_factory):
    user_factory(username="crew", password="Correct-Password-42!")
    login_url = reverse("accounts:login")
    client.post(login_url, {"username": "crew", "password": "wrong"})

    response = client.post(
        login_url,
        {"username": "crew", "password": "Correct-Password-42!"},
    )

    assert response.status_code == 302
    assert LoginThrottle.objects.count() == 0


@pytest.mark.django_db
def test_unknown_and_wrong_password_logins_have_same_error(client, user_factory):
    user_factory(username="crew", password="Correct-Password-42!")
    login_url = reverse("accounts:login")

    unknown = client.post(login_url, {"username": "unknown", "password": "wrong"})
    wrong_password = client.post(login_url, {"username": "crew", "password": "wrong"})

    assert "Invalid username or password." in unknown.content.decode()
    assert unknown.context["form"].non_field_errors() == wrong_password.context["form"].non_field_errors()

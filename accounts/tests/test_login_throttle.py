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
def test_valid_x_real_ip_addresses_have_independent_username_throttles(
    client, user_factory
):
    user_factory(username="crew", password="Correct-Password-42!")
    login_url = reverse("accounts:login")
    proxy_address = "10.0.0.5"

    for _ in range(5):
        client.post(
            login_url,
            {"username": "crew", "password": "wrong"},
            REMOTE_ADDR=proxy_address,
            HTTP_X_REAL_IP="192.0.2.10",
        )

    response = client.post(
        login_url,
        {"username": "crew", "password": "Correct-Password-42!"},
        REMOTE_ADDR=proxy_address,
        HTTP_X_REAL_IP="192.0.2.11",
    )

    assert response.status_code == 302
    assert response.url == "/dashboard/"
    assert LoginThrottle.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "untrusted_header",
    ["not-an-ip", "192.0.2.10, 198.51.100.20"],
)
def test_invalid_x_real_ip_falls_back_to_remote_address(
    client, user_factory, untrusted_header
):
    user_factory(username="crew", password="Correct-Password-42!")
    login_url = reverse("accounts:login")
    proxy_address = "10.0.0.5"

    for _ in range(4):
        client.post(
            login_url,
            {"username": "crew", "password": "wrong"},
            REMOTE_ADDR=proxy_address,
            HTTP_X_REAL_IP=untrusted_header,
        )
    client.post(
        login_url,
        {"username": "crew", "password": "wrong"},
        REMOTE_ADDR=proxy_address,
    )

    response = client.post(
        login_url,
        {"username": "crew", "password": "Correct-Password-42!"},
        REMOTE_ADDR=proxy_address,
    )

    assert response.status_code == 200
    assert "Invalid username or password." in response.content.decode()
    throttle = LoginThrottle.objects.get()
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


@pytest.mark.django_db
def test_too_long_unknown_username_uses_the_generic_login_error(client, user_factory):
    user_factory(username="crew", password="Correct-Password-42!")
    login_url = reverse("accounts:login")

    too_long = client.post(login_url, {"username": "x" * 151, "password": "wrong"})
    wrong_password = client.post(login_url, {"username": "crew", "password": "wrong"})

    assert too_long.status_code == 200
    assert too_long.context["form"].errors.get("username") is None
    assert too_long.context["form"].non_field_errors() == wrong_password.context["form"].non_field_errors()

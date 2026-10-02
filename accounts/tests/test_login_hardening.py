"""Login throttle hardening: source address, per-user and per-address counters,
no hashing for blocked attempts, input limits and the password-change throttle."""
import logging
from unittest import mock

import pytest
from django.test import RequestFactory
from django.urls import reverse

from accounts import throttle

PASSWORD = "Correct-Password-42!"
GENERIC_ERROR = "Benutzername oder Passwort ungültig."
LOGIN_URL = "/account/login/"
PUBLIC_ADDRESS = "198.51.100.77"  # a public peer: the address tells clients apart


def _post(client, username, password="wrong", **meta):
    return client.post(
        reverse("accounts:login"), {"username": username, "password": password}, **meta
    )


def _request(remote_addr, **headers):
    meta = {"REMOTE_ADDR": remote_addr}
    meta.update({f"HTTP_{k.upper()}": v for k, v in headers.items()})
    return RequestFactory().get("/", **meta)


# ----------------------------------------------------------- source address (AUTH-1)


@pytest.mark.django_db
def test_rotating_x_real_ip_from_an_untrusted_peer_does_not_dodge_the_limit(client, user_factory):
    user_factory(username="crew", password=PASSWORD)

    for number in range(6):
        _post(client, "crew", HTTP_X_REAL_IP=f"198.51.100.{number + 1}")
    response = _post(client, "crew", PASSWORD, HTTP_X_REAL_IP="198.51.100.99")

    assert response.status_code == 200
    assert GENERIC_ERROR in response.content.decode()


@pytest.mark.parametrize("peer", ["10.0.0.5", "::ffff:10.0.0.5"])
def test_trusted_proxy_x_real_ip_is_used(settings, peer):
    settings.TRUSTED_PROXY_IPS = ["10.0.0.0/24"]

    assert throttle.client_address(_request(peer, x_real_ip="203.0.113.7")) == "203.0.113.7"


def test_untrusted_peer_ignores_both_proxy_headers(settings):
    settings.TRUSTED_PROXY_IPS = ["10.0.0.0/24"]
    request = _request("192.0.2.1", x_real_ip="203.0.113.7", x_forwarded_for="203.0.113.8")

    assert throttle.client_address(request) == "192.0.2.1"


def test_default_trusts_no_proxy(settings):
    settings.TRUSTED_PROXY_IPS = []

    assert throttle.client_address(_request("10.0.0.5", x_real_ip="203.0.113.7")) == "10.0.0.5"


def test_trusted_proxy_without_or_with_malformed_header_falls_back_to_the_peer(settings):
    settings.TRUSTED_PROXY_IPS = ["10.0.0.5"]

    assert throttle.client_address(_request("10.0.0.5")) == "10.0.0.5"
    assert throttle.client_address(_request("10.0.0.5", x_real_ip="nonsense")) == "10.0.0.5"
    assert throttle.client_address(_request("10.0.0.5", x_real_ip="1.1.1.1, 2.2.2.2")) == "10.0.0.5"


def test_forwarded_for_uses_the_rightmost_untrusted_entry(settings):
    settings.TRUSTED_PROXY_IPS = ["10.0.0.0/8"]
    settings.TRUSTED_PROXY_HEADER = "x-forwarded-for"
    # 6.6.6.6 was typed by the client; 192.0.2.50 is what the first proxy saw.
    request = _request("10.0.0.5", x_forwarded_for="6.6.6.6, 192.0.2.50, 10.0.0.9")

    assert throttle.client_address(request) == "192.0.2.50"


def test_forwarded_for_ignores_x_real_ip_and_garbled_hops(settings):
    settings.TRUSTED_PROXY_IPS = ["10.0.0.5"]
    settings.TRUSTED_PROXY_HEADER = "x-forwarded-for"

    assert throttle.client_address(_request("10.0.0.5", x_real_ip="203.0.113.7")) == "10.0.0.5"
    garbled = _request("10.0.0.5", x_forwarded_for="203.0.113.7, garbage")
    assert throttle.client_address(garbled) == "10.0.0.5"


def test_missing_remote_addr_is_unknown():
    assert throttle.client_address(_request("")) == "unknown"


# ------------------------------------------------ per-username counter (AUTH-1)


@pytest.mark.django_db
def test_rotating_addresses_hit_the_per_username_ceiling(client, user_factory):
    user_factory(username="crew", password=PASSWORD)

    for number in range(throttle.LOGIN_USER_LIMIT):
        _post(client, "crew", REMOTE_ADDR=f"198.51.100.{number + 1}")
    response = _post(client, "crew", PASSWORD, REMOTE_ADDR="203.0.113.250")

    assert response.status_code == 200
    assert GENERIC_ERROR in response.content.decode()


@pytest.mark.django_db
def test_the_per_username_counter_ignores_case_and_whitespace(client, user_factory):
    user_factory(username="crew", password=PASSWORD)

    for number in range(throttle.LOGIN_USER_LIMIT):
        name = " CREW " if number % 2 else "Crew"
        _post(client, name, REMOTE_ADDR=f"198.51.100.{number + 1}")
    response = _post(client, "crew", PASSWORD, REMOTE_ADDR="203.0.113.250")

    assert GENERIC_ERROR in response.content.decode()


@pytest.mark.django_db
def test_a_few_failures_from_other_addresses_do_not_lock_the_real_player(client, user_factory):
    user_factory(username="crew", password=PASSWORD)
    for number in range(4):
        _post(client, "crew", REMOTE_ADDR=f"198.51.100.{number + 1}")

    response = _post(client, "crew", PASSWORD, REMOTE_ADDR="203.0.113.250")

    assert response.status_code == 302


# ------------------------------------------------ per-address counter (AUTH-2)


@pytest.mark.django_db
def test_a_username_flood_from_one_address_stops_before_any_hashing(client, user_factory):
    user_factory(username="crew", password=PASSWORD)
    for number in range(throttle.LOGIN_SOURCE_LIMIT):
        _post(client, f"ghost-{number}", REMOTE_ADDR=PUBLIC_ADDRESS)

    with mock.patch("accounts.views.authenticate") as authenticate:
        response = _post(client, "crew", PASSWORD, REMOTE_ADDR=PUBLIC_ADDRESS)

    authenticate.assert_not_called()
    assert response.status_code == 200
    assert GENERIC_ERROR in response.content.decode()


@pytest.mark.django_db
def test_an_address_flood_does_not_block_other_addresses(client, user_factory):
    user_factory(username="crew", password=PASSWORD)
    for number in range(throttle.LOGIN_SOURCE_LIMIT):
        _post(client, f"ghost-{number}", REMOTE_ADDR=PUBLIC_ADDRESS)

    response = _post(client, "crew", PASSWORD, REMOTE_ADDR="203.0.113.250")

    assert response.status_code == 302


@pytest.mark.django_db
def test_a_pair_that_is_blocked_runs_no_password_hash(client, user_factory):
    user_factory(username="crew", password=PASSWORD)
    for _ in range(throttle.LOGIN_PAIR_LIMIT):
        _post(client, "crew")

    with mock.patch("accounts.views.authenticate") as authenticate:
        response = _post(client, "crew", PASSWORD)

    authenticate.assert_not_called()
    assert GENERIC_ERROR in response.content.decode()


@pytest.mark.django_db
def test_blocked_and_wrong_password_responses_are_identical(client, user_factory):
    user_factory(username="crew", password=PASSWORD)
    wrong = _post(client, "crew")
    for _ in range(throttle.LOGIN_PAIR_LIMIT):
        _post(client, "crew")
    blocked = _post(client, "crew", PASSWORD)

    assert wrong.context["form"].non_field_errors() == blocked.context["form"].non_field_errors()
    assert blocked.context["form"].errors.keys() == wrong.context["form"].errors.keys()


# ------------------------------------------------------------- input limits (AUTH-3)


@pytest.mark.django_db
def test_oversized_credentials_are_a_generic_failure_without_hashing(client, user_factory, caplog):
    user_factory(username="crew", password=PASSWORD)

    with mock.patch("accounts.views.authenticate") as authenticate, caplog.at_level(
        logging.INFO, logger="accounts.audit"
    ):
        long_name = _post(client, "x" * 10_000)
        long_password = _post(client, "crew", "p" * 5_000)

    authenticate.assert_not_called()
    for response in (long_name, long_password):
        assert response.status_code == 200
        assert GENERIC_ERROR in response.content.decode()
        assert response.context["form"].errors.keys() == {"__all__"}
    logged = [r.getMessage() for r in caplog.records if r.name == "accounts.audit"]
    assert len(logged) == 2
    assert all(len(line) < 300 for line in logged)


@pytest.mark.django_db
def test_the_login_inputs_carry_maxlength_attributes(client):
    page = client.get(LOGIN_URL).content.decode()

    assert 'maxlength="150"' in page
    assert 'maxlength="4096"' in page


# ----------------------------------------------- password-change throttle (item 10)


def _change(client, old):
    return client.post(
        reverse("accounts:change_required"),
        {
            "old_password": old,
            "new_password1": "Brand-New-Secret-77!",
            "new_password2": "Brand-New-Secret-77!",
        },
    )


@pytest.mark.django_db
def test_wrong_current_passwords_lock_the_password_change_form(client, user_factory):
    user = user_factory(username="crew", password=PASSWORD, must_change_password=True)
    client.force_login(user)
    for _ in range(throttle.PASSWORD_CHANGE_LIMIT):
        assert _change(client, "wrong").status_code == 200

    response = _change(client, PASSWORD)  # the right one, but too late

    assert response.status_code == 200
    assert "Dein aktuelles Passwort stimmt nicht." in response.content.decode()
    user.refresh_from_db()
    assert user.must_change_password is True


@pytest.mark.django_db
def test_a_few_typos_do_not_stop_the_password_change(client, user_factory):
    user = user_factory(username="crew", password=PASSWORD, must_change_password=True)
    client.force_login(user)
    for _ in range(3):
        _change(client, "wrong")

    response = _change(client, PASSWORD)

    assert response.status_code == 302
    user.refresh_from_db()
    assert user.must_change_password is False

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts import throttle as throttle_module
from accounts.models import LoginThrottle

GENERIC_ERROR = "Benutzername oder Passwort ungültig."
TEST_CLIENT_ADDRESS = "127.0.0.1"


def pair_row(username, source_ip=TEST_CLIENT_ADDRESS):
    """The (username, address) counter row."""
    counters = throttle_module.login_counters(username, source_ip)
    return LoginThrottle.objects.filter(key_hash=counters.pair.key_hash).first()


@pytest.mark.django_db
def test_login_blocks_after_five_failures_and_uses_generic_error(client, user_factory):
    user_factory(username="crew", password="Correct-Password-42!")
    login_url = reverse("accounts:login")

    for _ in range(5):
        response = client.post(login_url, {"username": "crew", "password": "wrong"})
        assert response.status_code == 200
        assert "Benutzername oder Passwort ungültig." in response.content.decode()

    response = client.post(
        login_url,
        {"username": "crew", "password": "Correct-Password-42!"},
    )

    throttle = pair_row("crew")
    assert response.status_code == 200
    assert "Benutzername oder Passwort ungültig." in response.content.decode()
    assert throttle.failure_count == 5
    assert throttle.blocked_until > timezone.now()


@pytest.mark.django_db
def test_x_real_ip_from_a_trusted_proxy_gives_independent_username_throttles(
    client, user_factory, settings
):
    settings.TRUSTED_PROXY_IPS = ["10.0.0.5"]
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
    assert pair_row("crew", "192.0.2.10") is not None
    assert pair_row("crew", "192.0.2.11") is None  # the success reset only its own pair


@pytest.mark.django_db
@pytest.mark.parametrize(
    "untrusted_header",
    ["not-an-ip", "192.0.2.10, 198.51.100.20"],
)
def test_invalid_x_real_ip_falls_back_to_remote_address(
    client, user_factory, untrusted_header, settings
):
    settings.TRUSTED_PROXY_IPS = ["10.0.0.5"]
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
    assert "Benutzername oder Passwort ungültig." in response.content.decode()
    throttle = pair_row("crew", proxy_address)
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
    assert pair_row("crew") is None


@pytest.mark.django_db
def test_unknown_and_wrong_password_logins_have_same_error(client, user_factory):
    user_factory(username="crew", password="Correct-Password-42!")
    login_url = reverse("accounts:login")

    unknown = client.post(login_url, {"username": "unknown", "password": "wrong"})
    wrong_password = client.post(login_url, {"username": "crew", "password": "wrong"})

    assert "Benutzername oder Passwort ungültig." in unknown.content.decode()
    assert (
        unknown.context["form"].non_field_errors()
        == wrong_password.context["form"].non_field_errors()
    )


@pytest.mark.django_db
def test_too_long_unknown_username_uses_the_generic_login_error(client, user_factory):
    user_factory(username="crew", password="Correct-Password-42!")
    login_url = reverse("accounts:login")

    too_long = client.post(login_url, {"username": "x" * 151, "password": "wrong"})
    wrong_password = client.post(login_url, {"username": "crew", "password": "wrong"})

    assert too_long.status_code == 200
    assert too_long.context["form"].errors.get("username") is None
    assert (
        too_long.context["form"].non_field_errors()
        == wrong_password.context["form"].non_field_errors()
    )


def _freeze_now(monkeypatch, moment):
    monkeypatch.setattr("django.utils.timezone.now", lambda: moment)


@pytest.mark.django_db
def test_failures_older_than_the_window_start_a_new_count(client, user_factory, monkeypatch):
    user_factory(username="crew", password="Correct-Password-42!")
    login_url = reverse("accounts:login")
    start = timezone.now()
    _freeze_now(monkeypatch, start)
    for _ in range(4):
        client.post(login_url, {"username": "crew", "password": "wrong"})

    _freeze_now(monkeypatch, start + timedelta(minutes=15))
    client.post(login_url, {"username": "crew", "password": "wrong"})

    throttle = pair_row("crew")
    assert throttle.failure_count == 1
    assert throttle.window_started_at == start + timedelta(minutes=15)
    assert throttle.blocked_until is None


@pytest.mark.django_db
def test_a_block_lasts_one_window_and_then_lifts(client, user_factory, monkeypatch):
    user_factory(username="crew", password="Correct-Password-42!")
    login_url = reverse("accounts:login")
    start = timezone.now()
    _freeze_now(monkeypatch, start)
    for _ in range(5):
        client.post(login_url, {"username": "crew", "password": "wrong"})
    assert pair_row("crew").blocked_until == start + timedelta(minutes=15)

    _freeze_now(monkeypatch, start + timedelta(minutes=14, seconds=59))
    still_blocked = client.post(
        login_url, {"username": "crew", "password": "Correct-Password-42!"}
    )
    assert still_blocked.status_code == 200
    assert "Benutzername oder Passwort ungültig." in still_blocked.content.decode()
    assert pair_row("crew").failure_count == 5

    _freeze_now(monkeypatch, start + timedelta(minutes=15, seconds=1))
    lifted = client.post(login_url, {"username": "crew", "password": "Correct-Password-42!"})

    assert lifted.status_code == 302
    assert lifted.url == "/dashboard/"
    assert pair_row("crew") is None


@pytest.mark.django_db
def test_an_expired_block_restarts_the_window_on_the_next_failure(
    client, user_factory, monkeypatch
):
    user_factory(username="crew", password="Correct-Password-42!")
    login_url = reverse("accounts:login")
    start = timezone.now()
    _freeze_now(monkeypatch, start)
    for _ in range(5):
        client.post(login_url, {"username": "crew", "password": "wrong"})

    later = start + timedelta(minutes=16)
    _freeze_now(monkeypatch, later)
    response = client.post(login_url, {"username": "crew", "password": "wrong"})

    throttle = pair_row("crew")
    assert "Benutzername oder Passwort ungültig." in response.content.decode()
    assert throttle.failure_count == 1
    assert throttle.window_started_at == later
    assert throttle.blocked_until is None


@pytest.mark.django_db
def test_usernames_share_a_throttle_regardless_of_case_and_whitespace(client, user_factory):
    user_factory(username="crew", password="Correct-Password-42!")
    login_url = reverse("accounts:login")

    for username in ("crew", "CREW", " Crew ", "crew", "cReW"):
        client.post(login_url, {"username": username, "password": "wrong"})

    throttle = pair_row("crew")
    assert throttle.failure_count == 5
    assert throttle.blocked_until is not None


@pytest.mark.django_db
def test_recording_a_failure_purges_expired_rows_of_other_keys(client, user_factory, monkeypatch):
    user_factory(username="crew", password="Correct-Password-42!")
    login_url = reverse("accounts:login")
    start = timezone.now()
    _freeze_now(monkeypatch, start)
    client.post(login_url, {"username": "drifter", "password": "wrong"})
    for _ in range(5):
        client.post(login_url, {"username": "blocked", "password": "wrong"})
    assert pair_row("drifter") is not None and pair_row("blocked") is not None

    # 15 minutes on: the lone failure has expired, the block (set at ``start``
    # for one window) has too, so a new failure leaves only its own rows.
    _freeze_now(monkeypatch, start + timedelta(minutes=15))
    client.post(login_url, {"username": "crew", "password": "wrong"})

    assert pair_row("drifter") is None and pair_row("blocked") is None
    assert pair_row("crew").failure_count == 1
    assert {row.failure_count for row in LoginThrottle.objects.all()} == {1}


@pytest.mark.django_db
def test_purging_keeps_active_blocks_and_current_windows(client, user_factory, monkeypatch):
    user_factory(username="crew", password="Correct-Password-42!")
    login_url = reverse("accounts:login")
    start = timezone.now()
    _freeze_now(monkeypatch, start)
    client.post(login_url, {"username": "recent", "password": "wrong"})
    _freeze_now(monkeypatch, start + timedelta(minutes=10))
    for _ in range(5):
        client.post(login_url, {"username": "blocked", "password": "wrong"})

    # ``blocked`` opened its window 10 minutes ago and is blocked until +25.
    _freeze_now(monkeypatch, start + timedelta(minutes=16))
    client.post(login_url, {"username": "crew", "password": "wrong"})

    assert pair_row("recent") is None  # expired
    assert pair_row("crew").failure_count == 1
    blocked = pair_row("blocked")
    assert blocked.failure_count == 5
    assert blocked.blocked_until == start + timedelta(minutes=25)


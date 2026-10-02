"""Shared addresses, IPv6 buckets and the device cookie of the login throttle.

The live deployment is Docker Desktop with the port bound to 127.0.0.1 and no
reverse proxy: every request reaches gunicorn from one private gateway
address, so "one shared address" is the normal case and must not let a few
failed logins lock everybody out.
"""
import logging
import os
from unittest import mock

import pytest
from django.core import signing
from django.test import Client, RequestFactory
from django.urls import reverse

from accounts import devices, throttle

PASSWORD = "Correct-Password-42!"
GENERIC_ERROR = "Benutzername oder Passwort ungültig."
DOCKER_GATEWAY = "172.18.0.1"


def _post(client, username, password="wrong", **meta):
    return client.post(
        reverse("accounts:login"), {"username": username, "password": password}, **meta
    )


def _public(number):
    return f"198.51.100.{number}"


def _request(remote_addr, **headers):
    meta = {"REMOTE_ADDR": remote_addr}
    meta.update({f"HTTP_{k.upper()}": v for k, v in headers.items()})
    return RequestFactory().get("/", **meta)


def _logged_in_device_cookie(user_factory, username="alice", address=_public(10)):
    """A fresh browser that signed in once as ``username`` (and so holds the cookie)."""
    user_factory(username=username, password=PASSWORD)
    owner_browser = Client()
    response = _post(owner_browser, username, PASSWORD, REMOTE_ADDR=address)
    assert response.status_code == 302
    return owner_browser


def _sign_out(browser):
    """Log out through the view: ``Client.logout()`` would also drop the device cookie."""
    browser.post(reverse("accounts:logout"))


def _blocked(response):
    return response.status_code == 200 and GENERIC_ERROR in response.content.decode()


# ------------------------------------------------- shared address (High #1)


@pytest.mark.django_db
@pytest.mark.parametrize("peer", [DOCKER_GATEWAY, "127.0.0.1", "192.168.65.1", "10.1.2.3", "fd00::1"])
def test_ghost_username_flood_from_one_private_address_does_not_lock_real_players(
    client, user_factory, peer
):
    user_factory(username="alice", password=PASSWORD)
    for number in range(throttle.LOGIN_SOURCE_LIMIT + 5):
        _post(client, f"ghost-{number}", REMOTE_ADDR=peer)

    response = _post(client, "alice", PASSWORD, REMOTE_ADDR=peer)

    assert response.status_code == 302


@pytest.mark.django_db
def test_the_per_address_counter_still_stops_a_flood_from_a_public_address(client, user_factory):
    user_factory(username="alice", password=PASSWORD)
    for number in range(throttle.LOGIN_SOURCE_LIMIT):
        _post(client, f"ghost-{number}", REMOTE_ADDR=_public(5))

    assert _blocked(_post(client, "alice", PASSWORD, REMOTE_ADDR=_public(5)))


@pytest.mark.django_db
def test_a_trusted_proxy_header_address_is_counted_per_client(client, user_factory, settings):
    settings.TRUSTED_PROXY_IPS = ["172.18.0.0/16"]
    user_factory(username="alice", password=PASSWORD)
    for number in range(throttle.LOGIN_SOURCE_LIMIT):
        _post(client, f"ghost-{number}", REMOTE_ADDR=DOCKER_GATEWAY, HTTP_X_REAL_IP=_public(5))

    attacker = _post(client, "alice", PASSWORD, REMOTE_ADDR=DOCKER_GATEWAY, HTTP_X_REAL_IP=_public(5))
    other_client = _post(
        client, "alice", PASSWORD, REMOTE_ADDR=DOCKER_GATEWAY, HTTP_X_REAL_IP=_public(6)
    )

    assert _blocked(attacker)
    assert other_client.status_code == 302


@pytest.mark.django_db
def test_a_trusted_proxy_that_sends_no_client_address_does_not_distinguish(
    client, user_factory, settings
):
    settings.TRUSTED_PROXY_IPS = ["172.18.0.0/16"]
    user_factory(username="alice", password=PASSWORD)
    for number in range(throttle.LOGIN_SOURCE_LIMIT + 5):
        _post(client, f"ghost-{number}", REMOTE_ADDR=DOCKER_GATEWAY)

    assert _post(client, "alice", PASSWORD, REMOTE_ADDR=DOCKER_GATEWAY).status_code == 302


@pytest.mark.django_db
def test_an_empty_remote_addr_is_not_counted_per_address(client, user_factory):
    user_factory(username="alice", password=PASSWORD)
    for number in range(throttle.LOGIN_SOURCE_LIMIT + 5):
        _post(client, f"ghost-{number}", REMOTE_ADDR="")

    assert _post(client, "alice", PASSWORD, REMOTE_ADDR="").status_code == 302


@pytest.mark.parametrize(
    ("peer", "distinguishes"),
    [
        ("198.51.100.5", True),
        ("8.8.8.8", True),
        ("2001:db8::5", True),
        ("::ffff:8.8.8.8", True),
        ("10.0.0.5", False),
        ("172.17.0.1", False),
        ("192.168.1.9", False),
        ("127.0.0.1", False),
        ("169.254.1.1", False),
        ("100.64.0.1", False),
        ("::1", False),
        ("fd12::1", False),
        ("fe80::1", False),
        ("::ffff:10.0.0.5", False),
        ("", False),
        ("garbage", False),
    ],
)
def test_only_a_public_direct_peer_distinguishes_clients(peer, distinguishes):
    assert throttle.client_source(_request(peer)).distinguishes is distinguishes


def test_an_address_from_the_trusted_header_distinguishes_even_when_it_is_private(settings):
    settings.TRUSTED_PROXY_IPS = ["127.0.0.1"]

    source = throttle.client_source(_request("127.0.0.1", x_real_ip="192.168.1.50"))

    assert (source.address, source.distinguishes) == ("192.168.1.50", True)


# ------------------------------------------------------------- IPv6 (Medium #3)


def test_ipv6_addresses_in_one_slash_64_share_a_bucket():
    buckets = {
        throttle.client_source(_request(address)).bucket
        for address in ("2001:db8:1:2::1", "2001:db8:1:2::ffff", "2001:db8:1:2:aaaa:bbbb:cccc:dddd")
    }

    assert buckets == {"2001:db8:1:2::/64"}
    assert throttle.client_source(_request("2001:db8:1:3::1")).bucket == "2001:db8:1:3::/64"


def test_the_audit_address_stays_the_full_ipv6_address_and_mapped_ones_become_ipv4():
    assert throttle.client_address(_request("2001:db8:1:2::abcd")) == "2001:db8:1:2::abcd"
    mapped = throttle.client_source(_request("::ffff:198.51.100.5"))
    assert (mapped.address, mapped.bucket) == ("198.51.100.5", "198.51.100.5")


def test_the_ipv6_slash_64_applies_to_a_trusted_header_address_too(settings):
    settings.TRUSTED_PROXY_IPS = ["10.0.0.5"]

    source = throttle.client_source(_request("10.0.0.5", x_real_ip="2001:db8:9:9::42"))

    assert source.bucket == "2001:db8:9:9::/64"


@pytest.mark.django_db
def test_rotating_addresses_inside_one_ipv6_slash_64_still_hits_the_pair_limit(
    client, user_factory
):
    user_factory(username="alice", password=PASSWORD)
    for number in range(throttle.LOGIN_PAIR_LIMIT):
        _post(client, "alice", REMOTE_ADDR=f"2001:db8:1:2::{number + 1}")

    response = _post(client, "alice", PASSWORD, REMOTE_ADDR="2001:db8:1:2:dead:beef::1")

    assert _blocked(response)


@pytest.mark.django_db
def test_a_username_flood_from_one_ipv6_slash_64_hits_the_address_limit(client, user_factory):
    user_factory(username="alice", password=PASSWORD)
    for number in range(throttle.LOGIN_SOURCE_LIMIT):
        _post(client, f"ghost-{number}", REMOTE_ADDR=f"2001:db8:1:2::{number + 1}")

    assert _blocked(_post(client, "alice", PASSWORD, REMOTE_ADDR="2001:db8:1:2::fffe"))
    assert _post(client, "alice", PASSWORD, REMOTE_ADDR="2001:db8:1:3::1").status_code == 302


# ------------------------------------------------ device cookie (Medium #2)


@pytest.mark.django_db
def test_a_successful_login_sets_a_signed_httponly_lax_device_cookie(client, user_factory, settings):
    settings.SESSION_COOKIE_SECURE = True
    user_factory(username="alice", password=PASSWORD)

    response = _post(client, "alice", PASSWORD, REMOTE_ADDR=_public(10))

    cookie = response.cookies[devices.COOKIE_NAME]
    assert cookie["httponly"] is True
    assert cookie["secure"] is True
    assert cookie["samesite"] == "Lax"
    assert int(cookie["max-age"]) == 90 * 24 * 3600
    payload = signing.loads(cookie.value, salt=devices.SALT)
    assert payload["u"] == ["alice"]
    assert "Correct" not in cookie.value  # no secret in it


@pytest.mark.django_db
def test_the_device_cookie_follows_the_secure_setting(client, user_factory, settings):
    settings.SESSION_COOKIE_SECURE = False
    user_factory(username="alice", password=PASSWORD)

    response = _post(client, "alice", PASSWORD, REMOTE_ADDR=_public(10))

    assert not response.cookies[devices.COOKIE_NAME]["secure"]


@pytest.mark.django_db
def test_a_failed_login_sets_no_device_cookie(client, user_factory):
    user_factory(username="alice", password=PASSWORD)

    response = _post(client, "alice", "wrong", REMOTE_ADDR=_public(10))

    assert devices.COOKIE_NAME not in response.cookies


@pytest.mark.django_db
def test_an_attacker_exhausting_the_username_budget_does_not_lock_out_the_owners_browser(
    user_factory,
):
    owner_browser = _logged_in_device_cookie(user_factory)
    attacker = Client()
    for address in range(1, 5):  # 4 addresses x 5 pair failures = the per-username ceiling
        for _ in range(throttle.LOGIN_PAIR_LIMIT):
            _post(attacker, "alice", REMOTE_ADDR=_public(100 + address))
    _sign_out(owner_browser)

    with_cookie = _post(owner_browser, "alice", PASSWORD, REMOTE_ADDR=_public(20))
    without_cookie = _post(Client(), "alice", PASSWORD, REMOTE_ADDR=_public(21))

    assert with_cookie.status_code == 302
    assert _blocked(without_cookie)


@pytest.mark.django_db
def test_on_a_shared_address_an_attacker_cannot_lock_out_the_owners_browser(user_factory):
    owner_browser = _logged_in_device_cookie(user_factory, address=DOCKER_GATEWAY)
    attacker = Client()
    for _ in range(throttle.LOGIN_PAIR_LIMIT):
        _post(attacker, "alice", REMOTE_ADDR=DOCKER_GATEWAY)
    _sign_out(owner_browser)

    without_cookie = _post(Client(), "alice", PASSWORD, REMOTE_ADDR=DOCKER_GATEWAY)
    with_cookie = _post(owner_browser, "alice", PASSWORD, REMOTE_ADDR=DOCKER_GATEWAY)

    assert with_cookie.status_code == 302
    assert _blocked(without_cookie)


@pytest.mark.django_db
def test_a_tampered_or_forged_device_cookie_does_not_help(user_factory):
    owner_browser = _logged_in_device_cookie(user_factory)
    genuine = owner_browser.cookies[devices.COOKIE_NAME].value
    forged = {
        "garbage": "not-a-signed-value",
        "tampered": genuine[:-3] + ("AAA" if not genuine.endswith("AAA") else "BBB"),
        "wrong salt": signing.dumps({"d": "x", "u": ["alice"]}, salt="another-salt"),
        "wrong shape": signing.dumps({"d": 1, "u": "alice"}, salt=devices.SALT),
        "no device id": signing.dumps({"u": ["alice"]}, salt=devices.SALT),
    }
    for _ in range(throttle.LOGIN_PAIR_LIMIT):
        _post(Client(), "alice", REMOTE_ADDR=_public(30))

    for label, value in forged.items():
        stranger = Client()
        stranger.cookies[devices.COOKIE_NAME] = value
        response = _post(stranger, "alice", PASSWORD, REMOTE_ADDR=_public(30))
        assert _blocked(response), label


@pytest.mark.django_db
def test_another_users_device_cookie_does_not_vouch_for_this_username(user_factory):
    user_factory(username="alice", password=PASSWORD)
    bobs_browser = _logged_in_device_cookie(user_factory, username="bob")
    for _ in range(throttle.LOGIN_PAIR_LIMIT):
        _post(Client(), "alice", REMOTE_ADDR=_public(30))
    _sign_out(bobs_browser)

    response = _post(bobs_browser, "alice", PASSWORD, REMOTE_ADDR=_public(30))

    assert _blocked(response)


@pytest.mark.django_db
def test_an_expired_device_cookie_is_ignored(user_factory):
    owner_browser = _logged_in_device_cookie(user_factory)
    _sign_out(owner_browser)
    for _ in range(throttle.LOGIN_PAIR_LIMIT):
        _post(Client(), "alice", REMOTE_ADDR=_public(30))

    later = signing.time.time() + 91 * 24 * 3600
    with mock.patch("django.core.signing.time.time", return_value=later):
        response = _post(owner_browser, "alice", PASSWORD, REMOTE_ADDR=_public(30))

    assert _blocked(response)


@pytest.mark.django_db
def test_one_browser_is_remembered_for_several_accounts(client, user_factory):
    user_factory(username="alice", password=PASSWORD)
    user_factory(username="bob", password=PASSWORD)
    _post(client, "alice", PASSWORD, REMOTE_ADDR=_public(10))
    _sign_out(client)
    _post(client, "bob", PASSWORD, REMOTE_ADDR=_public(10))
    _sign_out(client)
    for name in ("alice", "bob"):
        for address in range(1, 5):
            for _ in range(throttle.LOGIN_PAIR_LIMIT):
                _post(Client(), name, REMOTE_ADDR=_public(100 + address))

    assert _post(client, "alice", PASSWORD, REMOTE_ADDR=_public(20)).status_code == 302
    _sign_out(client)
    assert _post(client, "bob", PASSWORD, REMOTE_ADDR=_public(20)).status_code == 302


@pytest.mark.django_db
def test_the_device_has_its_own_failure_limit(user_factory):
    owner_browser = _logged_in_device_cookie(user_factory)
    _sign_out(owner_browser)
    for number in range(throttle.LOGIN_DEVICE_LIMIT):
        # a fresh address each time keeps the pair counter out of the way
        _post(owner_browser, "alice", "wrong", REMOTE_ADDR=_public(40 + number))

    response = _post(owner_browser, "alice", PASSWORD, REMOTE_ADDR=_public(99))

    assert _blocked(response)


@pytest.mark.django_db
def test_the_device_limit_holds_on_a_shared_address_too(user_factory):
    owner_browser = _logged_in_device_cookie(user_factory, address=DOCKER_GATEWAY)
    _sign_out(owner_browser)
    for _ in range(throttle.LOGIN_DEVICE_LIMIT):
        _post(owner_browser, "alice", "wrong", REMOTE_ADDR=DOCKER_GATEWAY)

    assert _blocked(_post(owner_browser, "alice", PASSWORD, REMOTE_ADDR=DOCKER_GATEWAY))


@pytest.mark.django_db
def test_known_device_failures_do_not_use_up_the_shared_username_budget(user_factory):
    owner_browser = _logged_in_device_cookie(user_factory)
    _sign_out(owner_browser)
    for number in range(throttle.LOGIN_DEVICE_LIMIT):
        _post(owner_browser, "alice", "wrong", REMOTE_ADDR=_public(40 + number))

    # Another browser on a fresh address is not affected by the owner's typos.
    assert _post(Client(), "alice", PASSWORD, REMOTE_ADDR=_public(98)).status_code == 302


@pytest.mark.django_db
def test_a_successful_login_resets_the_device_counter(user_factory):
    owner_browser = _logged_in_device_cookie(user_factory)
    _sign_out(owner_browser)
    for number in range(throttle.LOGIN_DEVICE_LIMIT - 1):
        _post(owner_browser, "alice", "wrong", REMOTE_ADDR=_public(40 + number))
    assert _post(owner_browser, "alice", PASSWORD, REMOTE_ADDR=_public(60)).status_code == 302
    _sign_out(owner_browser)

    for number in range(throttle.LOGIN_DEVICE_LIMIT - 1):
        _post(owner_browser, "alice", "wrong", REMOTE_ADDR=_public(70 + number))

    assert _post(owner_browser, "alice", PASSWORD, REMOTE_ADDR=_public(97)).status_code == 302


@pytest.mark.django_db
def test_a_blocked_known_device_gets_the_same_generic_answer(user_factory):
    owner_browser = _logged_in_device_cookie(user_factory)
    _sign_out(owner_browser)
    wrong = _post(owner_browser, "alice", "wrong", REMOTE_ADDR=_public(40))
    for number in range(throttle.LOGIN_DEVICE_LIMIT):
        _post(owner_browser, "alice", "wrong", REMOTE_ADDR=_public(41 + number))
    blocked = _post(owner_browser, "alice", PASSWORD, REMOTE_ADDR=_public(99))

    assert wrong.context["form"].non_field_errors() == blocked.context["form"].non_field_errors()
    assert blocked.context["form"].errors.keys() == wrong.context["form"].errors.keys()
    assert wrong.content.decode().count(GENERIC_ERROR) == blocked.content.decode().count(
        GENERIC_ERROR
    )


@pytest.mark.django_db
def test_the_device_cookie_is_renewed_by_the_next_login_and_keeps_its_device_id(user_factory):
    owner_browser = _logged_in_device_cookie(user_factory)
    first = signing.loads(owner_browser.cookies[devices.COOKIE_NAME].value, salt=devices.SALT)
    _sign_out(owner_browser)

    response = _post(owner_browser, "alice", PASSWORD, REMOTE_ADDR=_public(10))

    second = signing.loads(response.cookies[devices.COOKIE_NAME].value, salt=devices.SALT)
    assert second == first


# ---------------------------------------------- collapsed audit lines (Low)


def _blocked_lines(caplog):
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == "accounts.audit"
        and record.getMessage().startswith("login_throttle_blocked")
    ]


@pytest.mark.django_db
def test_repeated_blocked_attempts_are_logged_once_per_counter_and_window(
    client, user_factory, caplog
):
    user_factory(username="alice", password=PASSWORD)
    with caplog.at_level(logging.INFO, logger="accounts.audit"):
        for _ in range(throttle.LOGIN_PAIR_LIMIT):
            _post(client, "alice", REMOTE_ADDR=_public(5))
        for _ in range(12):
            _post(client, "alice", PASSWORD, REMOTE_ADDR=_public(5))

    assert len(_blocked_lines(caplog)) == 1


@pytest.mark.django_db
def test_a_different_blocked_counter_is_logged_separately(client, user_factory, caplog):
    user_factory(username="alice", password=PASSWORD)
    user_factory(username="bob", password=PASSWORD)
    with caplog.at_level(logging.INFO, logger="accounts.audit"):
        for name in ("alice", "bob"):
            for _ in range(throttle.LOGIN_PAIR_LIMIT):
                _post(client, name, REMOTE_ADDR=_public(5))
            _post(client, name, PASSWORD, REMOTE_ADDR=_public(5))
            _post(client, name, PASSWORD, REMOTE_ADDR=_public(5))

    assert len(_blocked_lines(caplog)) == 2


@pytest.mark.django_db
def test_a_blocked_attempt_in_a_later_window_is_logged_again(client, user_factory, caplog):
    from django.core.cache import cache

    user_factory(username="alice", password=PASSWORD)
    with caplog.at_level(logging.INFO, logger="accounts.audit"):
        for _ in range(throttle.LOGIN_PAIR_LIMIT):
            _post(client, "alice", REMOTE_ADDR=_public(5))
        _post(client, "alice", PASSWORD, REMOTE_ADDR=_public(5))
        cache.clear()  # what the cache's expiry does one window later
        _post(client, "alice", PASSWORD, REMOTE_ADDR=_public(5))

    assert len(_blocked_lines(caplog)) == 2


# ------------------------------------------------------ audit file (Low)


def test_the_audit_log_file_is_created_owner_only(tmp_path, monkeypatch):
    from accounts import auditlog

    modes = []
    real_open = os.open

    def recording_open(path, flags, mode=0o777, *args, **kwargs):
        modes.append(mode)
        return real_open(path, flags, mode, *args, **kwargs)

    monkeypatch.setattr(auditlog.os, "open", recording_open)
    log_file = tmp_path / "logs" / "audit.log"
    handler = auditlog.AuditFileHandler(str(log_file), maxBytes=10_000, backupCount=1)
    logger = logging.getLogger("accounts.audit.mode-test")
    logger.propagate = False
    logger.addHandler(handler)
    try:
        logger.warning("login_failure username=%r", "crew")
    finally:
        logger.removeHandler(handler)
        handler.close()

    assert modes == [0o600]
    if os.name != "nt":
        assert (log_file.stat().st_mode & 0o777) == 0o600


@pytest.mark.skipif(os.name == "nt", reason="POSIX file modes")
def test_an_existing_world_readable_audit_log_is_tightened(tmp_path):
    from accounts import auditlog

    log_file = tmp_path / "audit.log"
    log_file.write_text("old\n", encoding="utf-8")
    log_file.chmod(0o644)
    handler = auditlog.AuditFileHandler(str(log_file), maxBytes=10_000, backupCount=1)
    logger = logging.getLogger("accounts.audit.mode-test-2")
    logger.propagate = False
    logger.addHandler(handler)
    try:
        logger.warning("login_failure")
    finally:
        logger.removeHandler(handler)
        handler.close()

    assert (log_file.stat().st_mode & 0o777) == 0o600


# ------------------------------------------------ logged paths use %r (Low)


def test_the_admin_denied_record_cannot_be_split_by_a_hostile_path(caplog):
    from django.http import HttpResponseForbidden

    from accounts.middleware import AdminAccessAuditMiddleware

    request = RequestFactory().get("/portal-admin/x%0Alogin_success%20username='root'")
    request.user = mock.Mock(**{"get_username.return_value": "player"})
    middleware = AdminAccessAuditMiddleware(lambda _request: HttpResponseForbidden())

    with caplog.at_level(logging.INFO, logger="accounts.audit"):
        middleware(request)

    (message,) = [r.getMessage() for r in caplog.records if r.name == "accounts.audit"]
    assert "\n" not in message
    assert "\\n" in message


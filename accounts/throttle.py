"""Failure counters that throttle password guessing.

Three independent counters guard a login, so that neither rotating the
username nor rotating the address gets an attacker past all of them:

* per (username, source address): ``LOGIN_PAIR_LIMIT`` failures -- the tight
  limit a player who mistypes will actually meet;
* per username, whatever the address: ``LOGIN_USER_LIMIT`` -- generous, so an
  attacker who rotates addresses still has a ceiling per account;
* per source address, whatever the username: ``LOGIN_SOURCE_LIMIT`` -- so a
  flood of made-up usernames stops before it costs a password hash each.

After the limit within one ``THROTTLE_WINDOW`` the counter blocks for one
window. Rows are keyed by an HMAC, so neither the username nor the address is
stored in clear. Counting is a single ``UPDATE ... SET n = n + 1`` inside a
write transaction, so parallel requests cannot lose increments.

The source address is ``REMOTE_ADDR`` unless that peer is one of
``settings.TRUSTED_PROXY_IPS``; only then is the one configured proxy header
(``settings.TRUSTED_PROXY_HEADER``) believed.
"""
import hashlib
import hmac
from dataclasses import dataclass
from datetime import timedelta
from functools import lru_cache
from ipaddress import ip_address, ip_network
from typing import NamedTuple

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F, Q

from .models import LoginThrottle

THROTTLE_WINDOW = timedelta(minutes=15)
LOGIN_PAIR_LIMIT = 5
THROTTLE_LIMIT = LOGIN_PAIR_LIMIT  # historic name of the per-pair limit
LOGIN_USER_LIMIT = 20
LOGIN_SOURCE_LIMIT = 20
PASSWORD_CHANGE_LIMIT = 10
_KEY_NAME_LENGTH = 150  # longer input would only make distinct keys for one username


@dataclass(frozen=True)
class Counter:
    key_hash: str
    limit: int


class LoginCounters(NamedTuple):
    pair: Counter
    user: Counter
    source: Counter


# ---------------------------------------------------------------- source address


@lru_cache(maxsize=8)
def _networks(entries: tuple):
    return tuple(ip_network(entry, strict=False) for entry in entries)


def _parse_address(value):
    """A normalised ``ipaddress`` object (IPv4-mapped IPv6 unwrapped) or ``None``."""
    try:
        address = ip_address((value or "").strip())
    except ValueError:
        return None
    mapped = getattr(address, "ipv4_mapped", None)
    return mapped or address


def _is_trusted(address, networks) -> bool:
    return any(address in network for network in networks)


def client_address(request) -> str:
    """The address the throttle and the audit log attribute a request to.

    ``REMOTE_ADDR`` by default. When the direct peer is a configured trusted
    proxy, the configured header decides instead: ``x-real-ip`` (one address)
    or ``x-forwarded-for`` (the rightmost entry that is not itself a trusted
    proxy). A missing or malformed header falls back to the peer.
    """
    peer = _parse_address(request.META.get("REMOTE_ADDR"))
    if peer is None:
        return "unknown"
    networks = _networks(tuple(getattr(settings, "TRUSTED_PROXY_IPS", ())))
    if not networks or not _is_trusted(peer, networks):
        return str(peer)

    header = getattr(settings, "TRUSTED_PROXY_HEADER", "x-real-ip")
    if header == "x-forwarded-for":
        client = _rightmost_untrusted(request.META.get("HTTP_X_FORWARDED_FOR", ""), networks)
    else:
        client = _parse_address(request.META.get("HTTP_X_REAL_IP"))
    return str(client or peer)


def _rightmost_untrusted(forwarded_for: str, networks):
    for entry in reversed(forwarded_for.split(",")):
        address = _parse_address(entry)
        if address is None:
            return None  # a garbled hop: do not guess, use the peer
        if not _is_trusted(address, networks):
            return address
    return None


# ------------------------------------------------------------------- counters


def _digest(scope: str, *parts: str) -> str:
    scope_key = hmac.new(settings.SECRET_KEY.encode(), scope.encode(), hashlib.sha256).digest()
    message = "\x00".join(parts).encode()
    return hmac.new(scope_key, message, hashlib.sha256).hexdigest()


def _normalise(username: str) -> str:
    return username.strip().casefold()[:_KEY_NAME_LENGTH]


def login_counters(username: str, source_ip: str) -> LoginCounters:
    name = _normalise(username)
    return LoginCounters(
        pair=Counter(_digest("login-pair", name, source_ip), LOGIN_PAIR_LIMIT),
        user=Counter(_digest("login-user", name), LOGIN_USER_LIMIT),
        source=Counter(_digest("login-source", source_ip), LOGIN_SOURCE_LIMIT),
    )


def password_change_counter(user) -> Counter:
    return Counter(_digest("password-change", str(user.pk)), PASSWORD_CHANGE_LIMIT)


def is_blocked(counters, now) -> bool:
    """Whether any counter blocks right now. Reads only: no hashing, no writes."""
    return LoginThrottle.objects.filter(
        key_hash__in=[counter.key_hash for counter in counters],
        blocked_until__gt=now,
    ).exists()


def _purge_expired(now) -> None:
    """Delete rows whose window has run out and that are not blocking anyone.

    Such a row would be restarted from scratch on its next failure anyway, so
    removing it changes no lockout decision; it only stops rows for one-off
    usernames and addresses from piling up.
    """
    LoginThrottle.objects.filter(window_started_at__lte=now - THROTTLE_WINDOW).filter(
        Q(blocked_until__isnull=True) | Q(blocked_until__lte=now)
    ).delete()


def _count_failure(counter: Counter, now) -> None:
    rows = LoginThrottle.objects.filter(key_hash=counter.key_hash)
    in_window = rows.filter(window_started_at__gt=now - THROTTLE_WINDOW)
    if not in_window.update(failure_count=F("failure_count") + 1):
        # No row, or its window ran out: start a fresh, unblocked one.
        restarted = rows.update(window_started_at=now, failure_count=1, blocked_until=None)
        if not restarted:
            try:
                with transaction.atomic():
                    LoginThrottle.objects.create(
                        key_hash=counter.key_hash, window_started_at=now, failure_count=1
                    )
            except IntegrityError:  # another request created it first
                rows.update(failure_count=F("failure_count") + 1)
    rows.filter(failure_count__gte=counter.limit).update(blocked_until=now + THROTTLE_WINDOW)


@transaction.atomic
def record_failure(counters, now) -> None:
    _purge_expired(now)
    for counter in counters:
        _count_failure(counter, now)


def reset(counter: Counter) -> None:
    LoginThrottle.objects.filter(key_hash=counter.key_hash).delete()

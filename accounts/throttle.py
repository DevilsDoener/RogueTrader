"""Failure counters that throttle password guessing.

Independent counters guard a login, so that neither rotating the username nor
rotating the address gets an attacker past all of them:

* per (username, source address): ``LOGIN_PAIR_LIMIT`` failures -- the tight
  limit a player who mistypes will actually meet;
* per username, whatever the address: ``LOGIN_USER_LIMIT`` -- generous, so an
  attacker who rotates addresses still has a ceiling per account;
* per source address, whatever the username: ``LOGIN_SOURCE_LIMIT`` -- so a
  flood of made-up usernames stops before it costs a password hash each. It
  only applies when the address tells clients apart (see below);
* per device: ``LOGIN_DEVICE_LIMIT`` failures from a browser that holds a valid
  device cookie for the username (``accounts.devices``). Such a browser is
  not blocked by the per-username and per-address counters, so an attacker who
  burns an account's shared budgets cannot lock its owner out of the browser
  they already used.

After the limit within one ``THROTTLE_WINDOW`` the counter blocks for one
window. Rows are keyed by an HMAC, so neither the username nor the address is
stored in clear. Counting is a single ``UPDATE ... SET n = n + 1`` inside a
write transaction, so parallel requests cannot lose increments.

The source address is ``REMOTE_ADDR`` unless that peer is one of
``settings.TRUSTED_PROXY_IPS``; only then is the one configured proxy header
(``settings.TRUSTED_PROXY_HEADER``) believed. An address only *distinguishes
clients* when it came from that trusted header or the direct peer is a public
address. Behind Docker Desktop (or any proxy that is not listed) every request
arrives from one private gateway address; counting that address would let a
handful of failed logins lock everybody out, so the per-address counter is
skipped. IPv6 clients are keyed by their /64 (the smallest normal allocation),
so rotating inside one network does not mint new buckets.
"""
import hashlib
import hmac
from dataclasses import dataclass
from datetime import timedelta
from functools import lru_cache
from ipaddress import IPv6Address, ip_address, ip_network
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
LOGIN_DEVICE_LIMIT = 10
PASSWORD_CHANGE_LIMIT = 10
_KEY_NAME_LENGTH = 150  # longer input would only make distinct keys for one username


@dataclass(frozen=True)
class Counter:
    key_hash: str
    limit: int


@dataclass(frozen=True)
class LoginCounters:
    """The counters one login attempt touches.

    ``source`` is ``None`` when the address does not tell clients apart;
    ``device`` is ``None`` unless the request carries a valid device cookie for
    the username. ``blocking`` are the counters whose block refuses the attempt
    and ``counting`` the ones a failure is added to.
    """

    pair: Counter
    user: Counter
    source: Counter | None = None
    device: Counter | None = None
    shared_address: bool = False

    @property
    def blocking(self) -> list:
        if self.device is not None:
            # On a shared address the pair counter is really a per-username one
            # that an attacker could fill; the device counter guards this browser.
            return [self.device] if self.shared_address else [self.device, self.pair]
        return [c for c in (self.pair, self.user, self.source) if c is not None]

    @property
    def counting(self) -> list:
        if self.device is not None:
            return [self.device, self.pair]
        return [c for c in (self.pair, self.user, self.source) if c is not None]


class ClientSource(NamedTuple):
    address: str  # the full address, for logs ("unknown" if there is none)
    bucket: str  # what the counters key on: the address, or the /64 of an IPv6 one
    distinguishes: bool  # whether the address tells this client from other clients


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


#: Peers that look the same for many clients when they reach us: loopback,
#: private and link-local ranges (Docker's bridge gateway, a LAN proxy) and CGNAT.
_SHARED_RANGES = tuple(
    ip_network(entry)
    for entry in (
        "0.0.0.0/8",
        "10.0.0.0/8",
        "100.64.0.0/10",
        "127.0.0.0/8",
        "169.254.0.0/16",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "::/128",
        "::1/128",
        "fc00::/7",
        "fe80::/10",
    )
)


def _is_public(address) -> bool:
    return not any(
        address in network for network in _SHARED_RANGES if network.version == address.version
    )


def _bucket(address) -> str:
    if isinstance(address, IPv6Address):
        return str(ip_network(f"{address}/64", strict=False))
    return str(address)


def client_source(request) -> ClientSource:
    """Where a request comes from, and whether that address identifies the client.

    ``REMOTE_ADDR`` by default. When the direct peer is a configured trusted
    proxy, the configured header decides instead: ``x-real-ip`` (one address)
    or ``x-forwarded-for`` (the rightmost entry that is not itself a trusted
    proxy). A missing or malformed header falls back to the peer, which then
    stands for every client of that proxy and so does not distinguish them.
    """
    peer = _parse_address(request.META.get("REMOTE_ADDR"))
    if peer is None:
        return ClientSource("unknown", "unknown", False)
    networks = _networks(tuple(getattr(settings, "TRUSTED_PROXY_IPS", ())))
    if not networks or not _is_trusted(peer, networks):
        return ClientSource(str(peer), _bucket(peer), _is_public(peer))

    header = getattr(settings, "TRUSTED_PROXY_HEADER", "x-real-ip")
    if header == "x-forwarded-for":
        client = _rightmost_untrusted(request.META.get("HTTP_X_FORWARDED_FOR", ""), networks)
    else:
        client = _parse_address(request.META.get("HTTP_X_REAL_IP"))
    if client is None or _is_trusted(client, networks):
        return ClientSource(str(peer), _bucket(peer), False)
    return ClientSource(str(client), _bucket(client), True)


def client_address(request) -> str:
    """The address the audit log attributes a request to."""
    return client_source(request).address


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


def normalise_username(username: str) -> str:
    return username.strip().casefold()[:_KEY_NAME_LENGTH]


def login_counters(
    username: str,
    source: str,
    *,
    distinguishes: bool = True,
    device_id: str | None = None,
) -> LoginCounters:
    """The counters for one attempt on ``username`` from the address bucket ``source``.

    ``distinguishes`` is :attr:`ClientSource.distinguishes`; ``device_id`` is the
    id of a valid device cookie for this username, if the request has one.
    """
    name = normalise_username(username)
    return LoginCounters(
        pair=Counter(_digest("login-pair", name, source), LOGIN_PAIR_LIMIT),
        user=Counter(_digest("login-user", name), LOGIN_USER_LIMIT),
        source=(
            Counter(_digest("login-source", source), LOGIN_SOURCE_LIMIT) if distinguishes else None
        ),
        device=(
            Counter(_digest("login-device", name, device_id), LOGIN_DEVICE_LIMIT)
            if device_id
            else None
        ),
        shared_address=not distinguishes,
    )


def password_change_counter(user) -> Counter:
    return Counter(_digest("password-change", str(user.pk)), PASSWORD_CHANGE_LIMIT)


def blocking_keys(counters, now) -> list[str]:
    """The key hashes of the counters that block right now.

    Reads only: no hashing, no writes. ``counters`` is a :class:`LoginCounters`
    (its ``blocking`` set is checked) or any iterable of :class:`Counter`.
    """
    checked = counters.blocking if isinstance(counters, LoginCounters) else list(counters)
    return list(
        LoginThrottle.objects.filter(
            key_hash__in=[counter.key_hash for counter in checked],
            blocked_until__gt=now,
        ).values_list("key_hash", flat=True)
    )


def is_blocked(counters, now) -> bool:
    return bool(blocking_keys(counters, now))


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
    """Add one failure to every counter of ``counters`` (a :class:`LoginCounters`
    counts its ``counting`` set; any iterable of :class:`Counter` counts all)."""
    _purge_expired(now)
    counted = counters.counting if isinstance(counters, LoginCounters) else counters
    for counter in counted:
        _count_failure(counter, now)


def reset(counter: Counter) -> None:
    LoginThrottle.objects.filter(key_hash=counter.key_hash).delete()

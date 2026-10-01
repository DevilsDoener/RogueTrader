"""Login throttle per (normalised username, source address).

After ``THROTTLE_LIMIT`` failures inside one ``THROTTLE_WINDOW`` the pair is
blocked for one window. Rows are keyed by an HMAC of the pair, so neither the
username nor the address is stored in clear.
"""
import hashlib
import hmac
from datetime import timedelta
from ipaddress import ip_address

from django.conf import settings
from django.db import IntegrityError, transaction

from .models import LoginThrottle

THROTTLE_WINDOW = timedelta(minutes=15)
THROTTLE_LIMIT = 5


def client_address(request) -> str:
    """The proxy-supplied ``X-Real-IP`` if it is one valid address, else
    ``REMOTE_ADDR``, else ``"unknown"``."""
    forwarded_address = request.META.get("HTTP_X_REAL_IP")
    try:
        return str(ip_address(forwarded_address))
    except (TypeError, ValueError):
        pass

    try:
        return str(ip_address(request.META.get("REMOTE_ADDR")))
    except (TypeError, ValueError):
        return "unknown"


def throttle_key(username: str, source_ip: str) -> str:
    normalized_identifier = username.strip().casefold()
    message = f"{normalized_identifier}\x00{source_ip}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()


def _restart_window_if_expired(throttle: LoginThrottle, now) -> bool:
    """Start a fresh, unblocked window once the current one has run out."""
    if now - throttle.window_started_at < THROTTLE_WINDOW:
        return False
    throttle.window_started_at = now
    throttle.failure_count = 0
    throttle.blocked_until = None
    return True


def is_blocked(key_hash: str, now) -> bool:
    throttle = LoginThrottle.objects.filter(key_hash=key_hash).first()
    if throttle is None:
        return False
    if throttle.blocked_until and throttle.blocked_until > now:
        return True
    if _restart_window_if_expired(throttle, now):
        throttle.save(update_fields=["failure_count", "window_started_at", "blocked_until"])
    return False


@transaction.atomic
def record_failure(key_hash: str, now) -> None:
    throttle = LoginThrottle.objects.select_for_update().filter(key_hash=key_hash).first()
    if throttle is None:
        try:
            with transaction.atomic():
                throttle = LoginThrottle.objects.create(
                    key_hash=key_hash,
                    window_started_at=now,
                )
        except IntegrityError:
            throttle = LoginThrottle.objects.select_for_update().get(key_hash=key_hash)
    _restart_window_if_expired(throttle, now)
    throttle.failure_count += 1
    if throttle.failure_count >= THROTTLE_LIMIT:
        throttle.blocked_until = now + THROTTLE_WINDOW
    throttle.save()


def reset(key_hash: str) -> None:
    LoginThrottle.objects.filter(key_hash=key_hash).delete()

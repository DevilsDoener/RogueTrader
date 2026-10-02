"""The device cookie: how a browser that logged in before is recognised.

After a successful login the portal sets a signed, ``HttpOnly`` cookie that
names the account(s) this browser has signed in to and carries a random device
id (the OWASP "device cookie" pattern). A login attempt for a username the
cookie vouches for is a *known device*: it is not refused because strangers
used up that username's shared failure budgets (see ``accounts.throttle``), but
it has its own failure counter keyed on the device id.

The value is ``django.core.signing`` output under a dedicated salt, so it
cannot be forged or edited, and a cookie issued for one username does nothing
for another. It holds no password and nothing secret: stealing it only grants
the 10-failures-per-15-minutes device budget, never access.
"""
import secrets

from django.conf import settings
from django.core import signing

from .throttle import normalise_username

COOKIE_NAME = "rt_device"
SALT = "accounts.device-cookie.v1"
MAX_AGE = 60 * 60 * 24 * 90  # 90 days, renewed by every successful login
MAX_USERNAMES = 5  # accounts one browser is remembered for (shared family PC)


def _read(request) -> tuple[str, list[str]] | None:
    """``(device_id, usernames)`` from a valid cookie, else ``None``."""
    raw = request.COOKIES.get(COOKIE_NAME)
    if not raw:
        return None
    try:
        payload = signing.loads(raw, salt=SALT, max_age=MAX_AGE)
        device_id = payload["d"]
        usernames = payload["u"]
    except (signing.BadSignature, KeyError, TypeError):
        return None
    if (
        not isinstance(device_id, str)
        or not device_id
        or not isinstance(usernames, list)
        or not all(isinstance(name, str) for name in usernames)
    ):
        return None
    return device_id, usernames


def device_id_for(request, username: str) -> str | None:
    """The device id if the request's cookie is valid and vouches for ``username``."""
    cookie = _read(request)
    if cookie is None:
        return None
    device_id, usernames = cookie
    return device_id if normalise_username(username) in usernames else None


def remember(response, request, username: str) -> None:
    """Set (or renew) the device cookie on ``response`` after a successful login."""
    name = normalise_username(username)
    cookie = _read(request)
    device_id, usernames = cookie if cookie else (secrets.token_urlsafe(16), [])
    usernames = [other for other in usernames if other != name] + [name]
    response.set_cookie(
        COOKIE_NAME,
        signing.dumps(
            {"d": device_id, "u": usernames[-MAX_USERNAMES:]}, salt=SALT, compress=False
        ),
        max_age=MAX_AGE,
        secure=settings.SESSION_COOKIE_SECURE,
        httponly=True,
        samesite="Lax",
    )

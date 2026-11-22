"""Plain helpers shared by the test packages (fixtures live in conftest.py).

Kept as an importable module so the root conftest, the app test packages
and the browser tests all use one definition.
"""
from __future__ import annotations

from django.db import connection
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

#: The password ``make_user`` gives every test user unless told otherwise.
DEFAULT_PASSWORD = "Valid-Password-42!"


def count_queries(client, url) -> int:
    """How many SQL queries one successful GET of ``url`` takes."""
    with CaptureQueriesContext(connection) as queries:
        assert client.get(url).status_code == 200
    return len(queries)


def post_login(client, username, password="wrong", **meta):
    """POST the login form, with optional request META (e.g. REMOTE_ADDR)."""
    return client.post(
        reverse("accounts:login"), {"username": username, "password": password}, **meta
    )


def request_from(remote_addr, **headers):
    """A bare GET request from ``remote_addr``; ``x_real_ip=...`` becomes HTTP_X_REAL_IP."""
    meta = {"REMOTE_ADDR": remote_addr}
    meta.update({f"HTTP_{name.upper()}": value for name, value in headers.items()})
    return RequestFactory().get("/", **meta)

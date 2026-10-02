"""Accounts tests start with an empty cache: the login view remembers which
blocked attempts it already logged there (once per counter and window)."""
import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _empty_cache():
    cache.clear()
    yield
    cache.clear()

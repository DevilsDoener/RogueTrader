"""Tests for the production security posture of config/settings.py.

These reload the settings module in-process (via ``sys.modules``) rather
than shelling out, so tests can assert directly on the exception type
(``django.core.exceptions.ImproperlyConfigured``) and on the resulting
module's attributes. The original module object is restored after each
test so ``django.conf.settings`` (already configured before the test run
started) keeps pointing at consistent state.
"""

import importlib
import sys

import pytest
from django.core.exceptions import ImproperlyConfigured

SETTINGS_MODULE = "config.settings"

# Every environment variable config/settings.py reads that affects the
# behaviour under test here. Cleared before each reload so leftover values
# from the real process environment cannot leak into a "production" test.
_ENV_VARS = (
    "DJANGO_DEBUG",
    "DJANGO_SECRET_KEY",
    "DJANGO_ALLOWED_HOSTS",
    "PUBLIC_BASE_URL",
    "ENABLE_HSTS",
)

# A secret that is long and random enough to pass the production strength
# check, but obviously not a real deployment secret.
_STRONG_TEST_SECRET = "th1s-is-a-64-char-test-secret-1234567890abcdefghijklmnopqrstuv"

PRODUCTION_ENV = {
    "DJANGO_DEBUG": "false",
    "DJANGO_SECRET_KEY": _STRONG_TEST_SECRET,
    "DJANGO_ALLOWED_HOSTS": "portal.example.com",
    "PUBLIC_BASE_URL": "https://portal.example.com",
    "ENABLE_HSTS": "1",
}


@pytest.fixture
def settings_from_env(monkeypatch):
    """Reload config.settings with a controlled environment.

    Returns a callable: settings_from_env(**env) -> the freshly executed
    settings module, or raises whatever exception module-level code raised
    (e.g. ImproperlyConfigured).
    """
    original_module = sys.modules.get(SETTINGS_MODULE)

    def _load(**env):
        for key in _ENV_VARS:
            monkeypatch.delenv(key, raising=False)
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        sys.modules.pop(SETTINGS_MODULE, None)
        return importlib.import_module(SETTINGS_MODULE)

    try:
        yield _load
    finally:
        # Restore whatever module object django.conf.settings was already
        # wrapping so later tests keep talking to consistent settings.
        sys.modules.pop(SETTINGS_MODULE, None)
        if original_module is not None:
            sys.modules[SETTINGS_MODULE] = original_module
        else:
            importlib.import_module(SETTINGS_MODULE)


@pytest.fixture
def production_settings(settings_from_env):
    return settings_from_env(**PRODUCTION_ENV)


def test_production_rejects_default_secret(settings_from_env):
    with pytest.raises(ImproperlyConfigured):
        settings_from_env(**{**PRODUCTION_ENV, "DJANGO_SECRET_KEY": "change-me"})


def test_production_rejects_the_env_example_placeholder_secret(settings_from_env):
    with pytest.raises(ImproperlyConfigured):
        settings_from_env(
            **{
                **PRODUCTION_ENV,
                "DJANGO_SECRET_KEY": "replace-with-a-long-random-secret",
            }
        )


def test_production_rejects_a_short_secret(settings_from_env):
    with pytest.raises(ImproperlyConfigured):
        settings_from_env(**{**PRODUCTION_ENV, "DJANGO_SECRET_KEY": "short"})


def test_production_rejects_a_missing_secret(settings_from_env):
    env = dict(PRODUCTION_ENV)
    del env["DJANGO_SECRET_KEY"]
    with pytest.raises(ImproperlyConfigured):
        settings_from_env(**env)


def test_production_requires_explicit_allowed_hosts(settings_from_env):
    env = dict(PRODUCTION_ENV)
    del env["DJANGO_ALLOWED_HOSTS"]
    with pytest.raises(ImproperlyConfigured):
        settings_from_env(**env)


def test_allowed_hosts_is_explicit_in_production(production_settings):
    assert production_settings.ALLOWED_HOSTS == ["portal.example.com"]


def test_https_security_is_enabled_in_production(production_settings):
    assert production_settings.SESSION_COOKIE_SECURE is True
    assert production_settings.CSRF_COOKIE_SECURE is True
    assert production_settings.SECURE_SSL_REDIRECT is True
    assert production_settings.SECURE_PROXY_SSL_HEADER == (
        "HTTP_X_FORWARDED_PROTO",
        "https",
    )


def test_csrf_trusted_origins_derive_from_public_base_url(production_settings):
    assert production_settings.CSRF_TRUSTED_ORIGINS == ["https://portal.example.com"]


def test_hsts_is_enabled_only_when_flag_is_set(settings_from_env):
    without_hsts = settings_from_env(**{**PRODUCTION_ENV, "ENABLE_HSTS": "0"})
    assert without_hsts.SECURE_HSTS_SECONDS == 0
    assert without_hsts.SECURE_HSTS_INCLUDE_SUBDOMAINS is False
    assert without_hsts.SECURE_HSTS_PRELOAD is False

    with_hsts = settings_from_env(**PRODUCTION_ENV)
    assert with_hsts.SECURE_HSTS_SECONDS == 31536000
    assert with_hsts.SECURE_HSTS_INCLUDE_SUBDOMAINS is True
    assert with_hsts.SECURE_HSTS_PRELOAD is True


def test_mime_sniffing_protection_is_enabled(production_settings):
    assert production_settings.SECURE_CONTENT_TYPE_NOSNIFF is True


def test_frames_are_denied(production_settings):
    assert production_settings.X_FRAME_OPTIONS == "DENY"


def test_error_responses_are_sanitized_in_production(production_settings):
    # DEBUG=False is what makes Django return generic 500/404 pages instead
    # of debug tracebacks that could leak secrets or sheet content.
    assert production_settings.DEBUG is False


def test_development_defaults_remain_usable_when_debug_is_enabled(settings_from_env):
    dev_settings = settings_from_env(DJANGO_DEBUG="true")

    assert dev_settings.DEBUG is True
    assert dev_settings.SESSION_COOKIE_SECURE is False
    assert dev_settings.CSRF_COOKIE_SECURE is False
    assert dev_settings.SECURE_SSL_REDIRECT is False
    # A random secret is generated automatically; no explicit hosts/secret
    # are required for local development.
    assert dev_settings.SECRET_KEY
    assert dev_settings.ALLOWED_HOSTS == ["127.0.0.1", "localhost"]

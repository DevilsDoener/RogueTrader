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
from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured

SETTINGS_MODULE = "config.settings"
REPO_ROOT = Path(__file__).resolve().parents[2]

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


def test_production_rejects_a_blank_allowed_hosts_value(settings_from_env):
    # docker compose substitutes an unset ${DJANGO_ALLOWED_HOSTS} (no
    # default in compose.yaml) as an empty string, not as a missing
    # variable -- confirm that still trips the same check.
    with pytest.raises(ImproperlyConfigured):
        settings_from_env(**{**PRODUCTION_ENV, "DJANGO_ALLOWED_HOSTS": ""})


def test_compose_does_not_supply_a_fallback_for_allowed_hosts():
    # Regression guard: compose.yaml must NOT default DJANGO_ALLOWED_HOSTS
    # to anything (e.g. "${DJANGO_ALLOWED_HOSTS:-127.0.0.1,localhost}"),
    # or an operator who forgets to set it in .env would silently get a
    # running container instead of the startup failure config/settings.py
    # is supposed to guarantee in production.
    compose_text = (REPO_ROOT / "compose.yaml").read_text(encoding="utf-8")
    assert "DJANGO_ALLOWED_HOSTS: ${DJANGO_ALLOWED_HOSTS}" in compose_text
    assert "DJANGO_ALLOWED_HOSTS:-" not in compose_text


def test_allowed_hosts_is_explicit_in_production(production_settings):
    # 127.0.0.1/localhost are always appended (see settings.py) so the
    # container HEALTHCHECK and the docs/operations.md manual smoke test
    # (both of which hit /healthz/ over loopback with a "Host:
    # 127.0.0.1:8000" header) never trip DisallowedHost, without an
    # operator having to remember to add loopback to
    # DJANGO_ALLOWED_HOSTS themselves.
    assert production_settings.ALLOWED_HOSTS == [
        "portal.example.com",
        "127.0.0.1",
        "localhost",
    ]


def test_allowed_hosts_does_not_duplicate_an_operator_supplied_loopback_host(
    settings_from_env,
):
    settings = settings_from_env(
        **{**PRODUCTION_ENV, "DJANGO_ALLOWED_HOSTS": "portal.example.com,127.0.0.1"}
    )
    assert settings.ALLOWED_HOSTS == ["portal.example.com", "127.0.0.1", "localhost"]


@pytest.mark.django_db
def test_healthcheck_over_plain_http_on_loopback_succeeds_in_production(
    production_settings, settings, client
):
    # Regression guard for the container HEALTHCHECK and the manual smoke
    # test in docs/operations.md: a plain-HTTP request to /healthz/ on
    # 127.0.0.1 must neither be redirected to HTTPS (SECURE_SSL_REDIRECT is
    # True in production) nor rejected as DisallowedHost, even though
    # DJANGO_ALLOWED_HOSTS is set to the real public hostname only.
    #
    # This applies the same production-shaped values ``production_settings``
    # computed to the *live* settings object (via pytest-django's
    # ``settings`` fixture) rather than the freshly reloaded module, because
    # a real HTTP request must be dispatched through the actual configured
    # Django app (URLconf, middleware) to prove the healthcheck path works
    # end-to-end, not just that the raw attribute values look right.
    settings.ALLOWED_HOSTS = production_settings.ALLOWED_HOSTS
    settings.SECURE_SSL_REDIRECT = production_settings.SECURE_SSL_REDIRECT
    settings.SECURE_REDIRECT_EXEMPT = production_settings.SECURE_REDIRECT_EXEMPT

    response = client.get("/healthz/", SERVER_NAME="127.0.0.1")

    assert response.status_code == 200


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


def test_csrf_trusted_origins_strips_a_trailing_slash_from_public_base_url(
    settings_from_env,
):
    # .env.example/docs/operations.md show PUBLIC_BASE_URL without a
    # trailing slash, but Django's CSRF origin matching requires an origin
    # with no path component -- an operator who adds one anyway must still
    # get a working trusted origin, not every POST silently 403ing.
    settings = settings_from_env(
        **{**PRODUCTION_ENV, "PUBLIC_BASE_URL": "https://portal.example.com/"}
    )
    assert settings.CSRF_TRUSTED_ORIGINS == ["https://portal.example.com"]


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
    # Local dev/tests never run `collectstatic`, so there is no
    # staticfiles.json manifest on disk -- must stay on plain storage, not
    # the WhiteNoise manifest backend that would need one.
    assert (
        dev_settings.STORAGES["staticfiles"]["BACKEND"]
        == "django.contrib.staticfiles.storage.StaticFilesStorage"
    )


def test_production_uses_the_whitenoise_manifest_backend_for_staticfiles(
    production_settings,
):
    # Regression guard for the Dockerfile bug where `collectstatic` ran
    # without DJANGO_DEBUG=false at build time: it silently produced no
    # staticfiles.json manifest, so the production runtime (DEBUG=false,
    # selecting this same backend) crashed every page render with
    # `ValueError: Missing staticfiles manifest entry for ...` out of
    # `{% static %}`. This only asserts the backend selection; the
    # manifest-missing fail-safe itself is covered separately below.
    assert (
        production_settings.STORAGES["staticfiles"]["BACKEND"]
        == "whitenoise.storage.CompressedManifestStaticFilesStorage"
    )


def test_whitenoise_manifest_strict_mode_is_disabled(production_settings):
    # Defense in depth for the same bug class: even if a staticfiles.json
    # manifest is ever missing or incomplete at runtime for some reason
    # collectstatic running correctly doesn't fully rule out (a wiped
    # STATIC_ROOT volume, a future Dockerfile regression, ...), WhiteNoise
    # must degrade gracefully instead of hard-crashing every page. See the
    # WHITENOISE_MANIFEST_STRICT comment in config/settings.py.
    assert production_settings.WHITENOISE_MANIFEST_STRICT is False


def test_missing_staticfiles_manifest_does_not_crash_static_lookups(tmp_path):
    # Functional proof of the fail-safe above: point WhiteNoise's manifest
    # storage backend at a directory that has never had `collectstatic`
    # run against it (no staticfiles.json at all -- the exact state the
    # Dockerfile bug left STATIC_ROOT in) and confirm resolving a static
    # file's stored name degrades instead of raising.
    from whitenoise.storage import CompressedManifestStaticFilesStorage

    (tmp_path / "portal.css").write_text("body { color: red; }")

    storage = CompressedManifestStaticFilesStorage(
        location=str(tmp_path), base_url="/static/"
    )
    # A wholly absent manifest file loads as "no entries", not an error.
    assert storage.hashed_files == {}

    # With manifest_strict=True (WhiteNoise/Django's default), this call
    # raises `ValueError: Missing staticfiles manifest entry for
    # 'portal.css'`. WHITENOISE_MANIFEST_STRICT=False (config/settings.py)
    # makes the storage pick this setting up in __init__, so it must
    # instead fall back to hashing the file's actual on-disk contents.
    assert storage.manifest_strict is False
    name = storage.stored_name("portal.css")
    assert name != "portal.css"

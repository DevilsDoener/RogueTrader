"""Settings that back the auth hardening: proxy trust, audit file, SQLite
write locking, sliding sessions."""
import importlib
import sys

import pytest
from django.core.exceptions import ImproperlyConfigured

SETTINGS_MODULE = "config.settings"
_ENV_VARS = (
    "DJANGO_DEBUG",
    "DJANGO_SECRET_KEY",
    "DJANGO_ALLOWED_HOSTS",
    "TRUSTED_PROXY_IPS",
    "TRUSTED_PROXY_HEADER",
    "AUDIT_LOG_FILE",
    "DATABASE_PATH",
)
PRODUCTION_ENV = {
    "DJANGO_DEBUG": "false",
    "DJANGO_SECRET_KEY": "th1s-is-a-64-char-test-secret-1234567890abcdefghijklmnopqrstuv",
    "DJANGO_ALLOWED_HOSTS": "portal.example.com",
}


@pytest.fixture
def load_settings(monkeypatch):
    original = sys.modules.get(SETTINGS_MODULE)

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
        sys.modules.pop(SETTINGS_MODULE, None)
        if original is not None:
            sys.modules[SETTINGS_MODULE] = original
        else:
            importlib.import_module(SETTINGS_MODULE)


def test_trusted_proxies_default_to_none(load_settings):
    loaded = load_settings(**PRODUCTION_ENV)

    assert loaded.TRUSTED_PROXY_IPS == []
    assert loaded.TRUSTED_PROXY_HEADER == "x-real-ip"


def test_trusted_proxies_are_parsed_from_a_comma_list(load_settings):
    loaded = load_settings(
        **PRODUCTION_ENV,
        TRUSTED_PROXY_IPS=" 127.0.0.1, 172.16.0.0/12 ,::1",
        TRUSTED_PROXY_HEADER="X-Forwarded-For",
    )

    assert loaded.TRUSTED_PROXY_IPS == ["127.0.0.1", "172.16.0.0/12", "::1"]
    assert loaded.TRUSTED_PROXY_HEADER == "x-forwarded-for"


@pytest.mark.parametrize(
    "env",
    [{"TRUSTED_PROXY_IPS": "10.0.0.5, nonsense"}, {"TRUSTED_PROXY_HEADER": "x-client-ip"}],
)
def test_bad_proxy_settings_fail_the_start(load_settings, env):
    with pytest.raises(ImproperlyConfigured):
        load_settings(**PRODUCTION_ENV, **env)


def test_production_writes_a_rotating_audit_file_next_to_the_database(load_settings):
    loaded = load_settings(**PRODUCTION_ENV, DATABASE_PATH="/data/db.sqlite3")

    handler = loaded.LOGGING["handlers"]["audit_file"]
    assert handler["class"] == "accounts.auditlog.AuditFileHandler"
    assert handler["filename"].replace("\\", "/") == "/data/logs/audit.log"
    assert handler["maxBytes"] > 0 and handler["backupCount"] >= 2
    audit_logger = loaded.LOGGING["loggers"]["accounts.audit"]
    assert audit_logger["handlers"] == ["audit_file"]
    assert audit_logger["propagate"] is True  # the console handler stays in the root logger
    assert "console" in loaded.LOGGING["root"]["handlers"]


def test_audit_file_location_is_configurable(load_settings):
    loaded = load_settings(**PRODUCTION_ENV, AUDIT_LOG_FILE="/var/log/rt/audit.log")

    assert loaded.LOGGING["handlers"]["audit_file"]["filename"] == "/var/log/rt/audit.log"


def test_development_keeps_the_audit_trail_on_the_console_only(load_settings):
    loaded = load_settings()

    assert "audit_file" not in loaded.LOGGING["handlers"]
    assert loaded.LOGGING["loggers"]["accounts.audit"]["handlers"] == []


def test_sqlite_takes_the_write_lock_up_front_and_waits(load_settings):
    options = load_settings().DATABASES["default"]["OPTIONS"]

    assert options["transaction_mode"] == "IMMEDIATE"
    assert options["timeout"] == 20


def test_sessions_last_14_days_from_the_last_request(load_settings):
    loaded = load_settings()

    assert loaded.SESSION_COOKIE_AGE == 14 * 24 * 3600
    assert loaded.SESSION_SAVE_EVERY_REQUEST is True


def test_sessions_slide_with_activity(client, user_factory):
    from django.conf import settings

    user = user_factory(username="crew")
    client.force_login(user)

    response = client.get("/dashboard/")

    cookie = response.cookies[settings.SESSION_COOKIE_NAME]
    assert int(cookie["max-age"]) == settings.SESSION_COOKIE_AGE


def test_deploy_check_warns_when_no_proxy_is_trusted(settings):
    from accounts.checks import PROXY_NOT_TRUSTED, check_trusted_proxy

    settings.DEBUG = False
    settings.TRUSTED_PROXY_IPS = []
    assert [w.id for w in check_trusted_proxy(None)] == [PROXY_NOT_TRUSTED]

    settings.TRUSTED_PROXY_IPS = ["127.0.0.1"]
    assert check_trusted_proxy(None) == []

    settings.DEBUG = True
    settings.TRUSTED_PROXY_IPS = []
    assert check_trusted_proxy(None) == []

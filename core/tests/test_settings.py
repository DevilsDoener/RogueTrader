import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def import_settings(**environment: str) -> subprocess.CompletedProcess[str]:
    child_environment = os.environ.copy()
    child_environment.pop("DJANGO_SECRET_KEY", None)
    child_environment.update(environment)
    return subprocess.run(
        [sys.executable, "-c", "import config.settings"],
        cwd=PROJECT_ROOT,
        env=child_environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_production_settings_require_an_explicit_secret_key():
    result = import_settings(DJANGO_DEBUG="false")

    assert result.returncode != 0
    assert "DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is false" in result.stderr


def test_production_settings_accept_an_explicit_secret_key():
    result = import_settings(
        DJANGO_DEBUG="false",
        DJANGO_SECRET_KEY="test-only-secret-key-that-is-long-enough-1234",
        DJANGO_ALLOWED_HOSTS="portal.example.com",
    )

    assert result.returncode == 0

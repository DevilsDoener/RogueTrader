"""Hardening pinned in the container files (audit findings L-1, L-5, L-6, L-7, L-4).

Plain text checks: the behaviour itself was verified by building the image and
running both services read-only (see the fix report); these keep a later edit
from quietly dropping a setting.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def dockerfile():
    return (ROOT / "Dockerfile").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def services():
    text = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    top = text.split("\nvolumes:\n")[0]
    blocks = re.split(r"(?m)^  (?=[a-z]+:\s*$)", top)
    return {block.split(":", 1)[0]: block for block in blocks if re.match(r"[a-z]+:\s*\n", block)}


def test_the_base_image_is_pinned_by_digest(dockerfile):
    assert re.search(r"(?m)^FROM python:3\.13-slim@sha256:[0-9a-f]{64}\s*$", dockerfile)


def test_the_image_defaults_to_production_mode(dockerfile):
    assert re.search(r"(?m)^\s+DJANGO_DEBUG=false\s", dockerfile)


def test_code_is_root_owned_and_only_data_belongs_to_the_runtime_user(dockerfile):
    assert "--chown" not in dockerfile
    assert re.search(r"chown app:app /data\b", dockerfile)
    assert "chown app:app /app" not in dockerfile
    assert dockerfile.index("collectstatic") < dockerfile.index("\nUSER app")


def test_the_build_secret_is_a_labelled_placeholder_above_the_production_floor(dockerfile):
    match = re.search(r'DJANGO_SECRET_KEY="(docker-build-placeholder[\w-]*)-\$\(', dockerfile)
    token = re.search(r"token_urlsafe\((\d+)\)", dockerfile)

    assert match and token
    # token_urlsafe(n) yields about 1.3 * n characters; 50 is Django's own bar.
    assert len(match.group(1)) + 1 + int(token.group(1)) >= 50


def test_gunicorn_runs_several_workers_with_a_timeout_and_an_access_log(dockerfile):
    cmd = dockerfile[dockerfile.index("\nCMD ") :]

    for fragment in ('"--workers", "3"', '"--timeout", "30"', '"--access-logfile", "-"'):
        assert fragment in cmd


@pytest.mark.parametrize("name", ["portal", "backup"])
def test_both_services_are_locked_down(services, name):
    block = services[name]

    assert "no-new-privileges:true" in block
    assert re.search(r"cap_drop:\s*\n\s+- ALL", block)
    assert re.search(r"(?m)^    read_only: true\s*$", block)
    assert re.search(r"tmpfs:\s*\n\s+- /tmp", block)


def test_the_backup_loop_handles_sigterm(services):
    block = services["backup"]

    assert "trap 'exit 0' TERM" in block
    assert "wait $$!" in block
    assert not re.search(r"(?m)^\s+sleep \d+\s*$", block)

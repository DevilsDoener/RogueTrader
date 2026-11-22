"""Content-Security-Policy and Permissions-Policy (audit findings M-2, wiki-js L2).

The browser-side proof -- every page loads and works with the header enforced,
with zero ``securitypolicyviolation`` events -- is ``tests/e2e/test_csp.py``.
These tests pin the header itself and the templates/static files it relies on.
"""

import hashlib
import re
from pathlib import Path

import pytest

from config.security_headers import (
    CONTENT_SECURITY_POLICY,
    PERMISSIONS_POLICY,
    SecurityHeadersMiddleware,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SKIPPED_DIRS = {
    ".venv",
    "staticfiles",
    "node_modules",
    "graphify-out",
    "tmp",
    "tests",
    "__pycache__",
}
SKIPPED_DIRS |= {".superpowers", ".claude", ".agents", ".codex", "docs", "content"}

#: Third-party code shipped as-is (see its README). Its license comments name
#: other origins, so the "no URL in our scripts" rule skips it; instead the
#: files are pinned byte-for-byte and still checked for string evaluation.
VENDOR_DIR = REPO_ROOT / "static" / "vendor"
VENDORED_SHA256 = {
    "vis-network/vis-data.min.js": (
        "d8b143cd2f0dce0dd965ed288b4c81afa9f8d9198c637f0faafe5fedb1439ba6"
    ),
    "vis-network/vis-network.min.js": (
        "06ce49495201e04fcab5ff3c8553fea23aeff7a1953ea2b737fcf28f36fe7fe5"
    ),
    "vis-network/vis-network.min.css": (
        "09c5d2c8b0a8595d5aa3e5aeebb657fdda7c4b24c911c2e685628a8b7fa23cbe"
    ),
}


def _directives(policy):
    return {
        parts[0]: parts[1:]
        for parts in (item.split() for item in policy.split(";") if item.strip())
    }


def _project_files(*suffixes):
    for path in REPO_ROOT.rglob("*"):
        if path.suffix in suffixes and not SKIPPED_DIRS & set(path.relative_to(REPO_ROOT).parts):
            yield path


def test_the_policy_is_strict_about_scripts_and_embedding():
    directives = _directives(CONTENT_SECURITY_POLICY)

    assert directives["default-src"] == ["'self'"]
    assert directives["script-src"] == ["'self'"]
    assert directives["style-src"] == ["'self'"]
    assert directives["style-src-attr"] == ["'unsafe-inline'"]
    assert directives["frame-ancestors"] == ["'none'"]
    assert directives["base-uri"] == ["'none'"]
    assert directives["object-src"] == ["'none'"]
    assert directives["form-action"] == ["'self'"]
    assert "unsafe-eval" not in CONTENT_SECURITY_POLICY
    assert "*" not in CONTENT_SECURITY_POLICY
    assert "http:" not in CONTENT_SECURITY_POLICY


def test_the_permissions_policy_switches_off_unused_browser_features():
    for feature in ("camera", "microphone", "geolocation", "payment", "usb"):
        assert f"{feature}=()" in PERMISSIONS_POLICY


@pytest.mark.django_db
@pytest.mark.parametrize("path", ["/account/login/", "/healthz/", "/no-such-page/"])
def test_anonymous_responses_carry_both_headers(client, path):
    response = client.get(path)

    assert response["Content-Security-Policy"] == CONTENT_SECURITY_POLICY
    assert response["Permissions-Policy"] == PERMISSIONS_POLICY


@pytest.mark.django_db
def test_a_login_redirect_and_a_signed_in_page_carry_the_headers(client, owner):
    redirect = client.get("/dashboard/")
    assert redirect.status_code == 302
    assert redirect["Content-Security-Policy"] == CONTENT_SECURITY_POLICY

    client.force_login(owner)
    page = client.get("/dashboard/")
    assert page.status_code == 200
    assert page["Content-Security-Policy"] == CONTENT_SECURITY_POLICY
    assert page["Permissions-Policy"] == PERMISSIONS_POLICY


def test_the_middleware_runs_before_whitenoise_so_static_files_get_the_header():
    from django.conf import settings

    middleware = settings.MIDDLEWARE
    ours = middleware.index("config.security_headers.SecurityHeadersMiddleware")

    assert ours < middleware.index("whitenoise.middleware.WhiteNoiseMiddleware")


def test_a_view_that_sets_its_own_policy_keeps_it(rf):
    from django.http import HttpResponse

    def view(request):
        response = HttpResponse("ok")
        response.headers["Content-Security-Policy"] = "default-src 'none'"
        return response

    response = SecurityHeadersMiddleware(view)(rf.get("/"))

    assert response["Content-Security-Policy"] == "default-src 'none'"
    assert response["Permissions-Policy"] == PERMISSIONS_POLICY


def test_no_template_has_an_inline_script_handler_or_style_block():
    inline_script = re.compile(
        r"<script\b(?![^>]*\bsrc=)(?![^>]*type=[\"']application/json[\"'])", re.I
    )
    handler = re.compile(r"""<[a-z][^>]*\son[a-z]+\s*=""", re.I)
    problems = []
    for path in _project_files(".html"):
        text = path.read_text(encoding="utf-8")
        name = path.relative_to(REPO_ROOT).as_posix()
        if inline_script.search(text):
            problems.append(f"{name}: inline <script>")
        if handler.search(text):
            problems.append(f"{name}: inline event handler")
        if re.search(r"<style\b", text, re.I):
            problems.append(f"{name}: <style> block")
        if re.search(r"javascript:", text, re.I):
            problems.append(f"{name}: javascript: URL")

    assert problems == []


def test_no_template_loads_anything_from_another_origin():
    external = re.compile(r"""(?:src|href|action)\s*=\s*["']?(?:https?:)?//""", re.I)
    problems = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in _project_files(".html")
        if external.search(path.read_text(encoding="utf-8"))
    ]

    assert problems == []


def test_no_script_evaluates_strings_or_names_another_origin():
    pattern = re.compile(r"\beval\s*\(|new\s+Function\s*\(|document\.write\s*\(|https?://")
    problems = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in _project_files(".js")
        if VENDOR_DIR not in path.parents and pattern.search(path.read_text(encoding="utf-8"))
    ]

    assert problems == []


def test_vendored_files_are_the_pinned_ones_and_never_evaluate_strings():
    shipped = {
        path.relative_to(VENDOR_DIR).as_posix()
        for path in VENDOR_DIR.rglob("*")
        if path.suffix in {".js", ".css"}
    }
    assert shipped == set(VENDORED_SHA256)
    for name, digest in VENDORED_SHA256.items():
        assert hashlib.sha256((VENDOR_DIR / name).read_bytes()).hexdigest() == digest, name

    evaluates = re.compile(r"\beval\s*\(|new\s+Function\s*\(|document\.write\s*\(")
    for name in VENDORED_SHA256:
        assert not evaluates.search((VENDOR_DIR / name).read_text(encoding="utf-8")), name

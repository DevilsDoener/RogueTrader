"""Scripts are external files with a guaranteed load order (CSP preparation).

No template carries an inline ``<script>`` or an inline event handler, so a
``script-src 'self'`` Content-Security-Policy can be added without
``'unsafe-inline'``. ``json_script`` data blocks (``type="application/json"``)
are rendered by Django and are not executed, so they are fine.
"""
import re
from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse

from wiki.content import set_repository_for_tests

_INLINE_SCRIPT_RE = re.compile(r"<script\b(?![^>]*\bsrc\s*=)[^>]*>", re.IGNORECASE)
_EVENT_HANDLER_RE = re.compile(r"""<[a-z][^>]*\son[a-z]+\s*=""", re.IGNORECASE)
_JS_URL_RE = re.compile(r"""(?:href|src|action)\s*=\s*["']\s*javascript:""", re.IGNORECASE)


def _project_templates():
    base = Path(settings.BASE_DIR)
    roots = [base / "templates", *base.glob("*/templates")]
    for root in roots:
        yield from root.rglob("*.html")


def test_no_template_has_an_inline_script_or_event_handler():
    offenders = []
    for path in _project_templates():
        text = path.read_text(encoding="utf-8")
        for pattern in (_INLINE_SCRIPT_RE, _EVENT_HANDLER_RE, _JS_URL_RE):
            if pattern.search(text):
                offenders.append(f"{path.relative_to(settings.BASE_DIR)}: {pattern.pattern[:20]}")

    assert offenders == []


@pytest.mark.django_db
def test_the_login_page_has_no_inline_script(client):
    content = client.get(reverse("accounts:login")).content.decode()

    assert _INLINE_SCRIPT_RE.findall(content) == []


@pytest.mark.django_db
def test_the_js_class_script_runs_before_the_stylesheet(client, user_factory):
    client.force_login(user_factory())

    head = client.get(reverse("dashboard")).content.decode().split("</head>")[0]

    assert "js/js-class" in head
    assert head.index("js-class") < head.index("portal")
    # Blocking on purpose (no defer/async): the first paint already has the class.
    script_tag = re.search(r"<script[^>]*js-class[^>]*>", head).group(0)
    assert "defer" not in script_tag and "async" not in script_tag


@pytest.mark.django_db
def test_the_double_submit_guard_is_a_deferred_file(client, user_factory):
    client.force_login(user_factory())

    content = client.get(reverse("dashboard")).content.decode()

    assert re.search(r"<script[^>]*\bdefer\b[^>]*no-double-submit", content)


@pytest.fixture
def installed(make_repository):
    repository = make_repository({"01-Chapter.md": "# Chapter\n\n## Combat\nA weapon.\n"})
    set_repository_for_tests(repository)
    return repository


def _positions(content, *names):
    return [content.index(f"js/{name}.js") for name in names]


@pytest.mark.django_db
def test_chapter_scripts_load_in_dependency_order(client, user_factory, installed):
    client.force_login(user_factory())

    content = client.get(reverse("wiki:chapter", args=["chapter"]), {"q": "weapon"}).content.decode()
    positions = _positions(
        content, "wiki-text", "wiki-recent", "auspex", "wiki-highlight", "wiki-reader"
    )

    assert positions == sorted(positions)


@pytest.mark.django_db
def test_the_highlight_script_is_only_loaded_with_search_terms(client, user_factory, installed):
    client.force_login(user_factory())
    url = reverse("wiki:chapter", args=["chapter"])

    assert "js/wiki-highlight.js" not in client.get(url).content.decode()
    assert "js/wiki-highlight.js" in client.get(url, {"q": "weapon"}).content.decode()


@pytest.mark.django_db
def test_the_library_script_follows_the_helpers_it_uses(client, user_factory, installed):
    client.force_login(user_factory())

    content = client.get(reverse("wiki:index")).content.decode()
    positions = _positions(content, "wiki-text", "wiki-recent", "wiki-library")

    assert positions == sorted(positions)


def test_each_static_helper_defines_its_one_global():
    js = Path(settings.BASE_DIR) / "static" / "js"

    assert "window.RTWikiText" in (js / "wiki-text.js").read_text(encoding="utf-8")
    assert "RTWikiText" not in (js / "wiki-recent.js").read_text(encoding="utf-8")
    assert "window.RTWikiRecent" in (js / "wiki-recent.js").read_text(encoding="utf-8")
    assert "initHighlight" not in (js / "wiki-reader.js").read_text(encoding="utf-8")

"""Snippets are built from escaped segments plus a literal ``<mark>`` (audit I3).

The result is a ``SafeString`` made in one place, so the templates need no
``|safe`` and the JSON field the palette renders is already escaped.
"""
import pytest
from django.urls import reverse
from django.utils.safestring import SafeString

from wiki.snippets import make_snippet
from wiki.suggest import suggest

HOSTILE = "<img src=x onerror=alert(1)> weapon & 'quotes' \"too\""


def test_the_snippet_is_marked_safe_at_the_source():
    assert isinstance(make_snippet("A plasma weapon.", ["plasma"]), SafeString)
    assert isinstance(make_snippet("No match here.", ["absent"]), SafeString)
    assert isinstance(make_snippet("", []), SafeString)


def test_hostile_text_is_escaped_and_only_mark_is_markup():
    snippet = make_snippet(HOSTILE, ["weapon"])

    assert snippet == (
        "&lt;img src=x onerror=alert(1)&gt; <mark>weapon</mark> "
        "&amp; &#x27;quotes&#x27; &quot;too&quot;"
    )
    assert "<img" not in snippet


def test_a_hostile_match_is_escaped_inside_the_mark():
    snippet = make_snippet("a <b>bold</b> move", ["<b>"])

    assert snippet == "a <mark>&lt;b&gt;</mark>bold&lt;/b&gt; move"


def test_the_fallback_snippet_without_a_match_is_escaped():
    assert "<script" not in make_snippet("<script>alert(1)</script>", ["absent"])


@pytest.fixture
def installed(make_repository):
    return make_repository(
        {"01-Chapter.md": f"# Chapter\n\n## Combat\n{HOSTILE}\n"}, install=True
    )


@pytest.mark.django_db
def test_search_page_renders_the_snippet_escaped(client, user_factory, installed):
    client.force_login(user_factory())

    content = client.get(reverse("wiki:search"), {"q": "weapon"}).content.decode()

    assert "&lt;img src=x onerror=alert(1)&gt; <mark>weapon</mark>" in content
    assert "<img src=x" not in content


def test_the_suggest_payload_carries_the_escaped_snippet(installed):
    hit = suggest(installed, "weapon")["hits"][0]

    assert hit["snippet_html"].startswith("&lt;img src=x onerror=alert(1)&gt; <mark>weapon</mark>")


def test_the_search_template_does_not_use_the_safe_filter():
    from pathlib import Path

    import wiki

    template = Path(wiki.__file__).parent / "templates" / "wiki" / "search_results.html"

    assert "snippet|safe" not in template.read_text(encoding="utf-8")

"""Headings are rendered by the template, not by the sanitizer.

Every heading is an outline node, so its body HTML no longer contains a
heading tag at all and the anchor ``id`` is written in template context. That
is what lets ``wiki/markdown.py`` keep ``id`` out of the Bleach allowlist
entirely -- a value copied from the document could otherwise shadow a DOM
global or one of the shell's own element ids.
"""
import re

import pytest
from django.urls import reverse

from wiki.content import WikiRepository, set_repository_for_tests


def _render(client, user_factory, tmp_path, settings, body):
    (tmp_path / "01-Chapter.md").write_text(body, encoding="utf-8")
    settings.WIKI_CONTENT_ROOT = tmp_path
    settings.WIKI_CONTENT_ALLOWLIST = ["01-Chapter.md"]
    set_repository_for_tests(WikiRepository.load())
    client.force_login(user_factory())
    response = client.get(reverse("wiki:chapter", kwargs={"chapter_slug": "chapter"}))
    assert response.status_code == 200
    return response.content.decode()


@pytest.mark.django_db
def test_each_section_gets_exactly_one_prefixed_anchor(client, user_factory, tmp_path, settings):
    content = _render(
        client,
        user_factory,
        tmp_path,
        settings,
        "# Chapter\n\n## Alpha\na\n\n### Beta\nb\n\n## Gamma\nc\n",
    )

    ids = re.findall(r'<section id="([^"]+)"', content)

    assert ids == ["sec-alpha", "sec-beta", "sec-gamma"]
    assert len(ids) == len(set(ids))


@pytest.mark.django_db
def test_nesting_is_reflected_in_the_heading_levels(client, user_factory, tmp_path, settings):
    content = _render(
        client, user_factory, tmp_path, settings, "# Chapter\n\n## Alpha\na\n\n### Beta\nb\n"
    )

    assert re.search(r'<section id="sec-alpha">\s*<h2>', content)
    assert re.search(r'<section id="sec-beta">\s*<h3>', content)


@pytest.mark.django_db
def test_inline_markup_in_a_heading_survives(client, user_factory, tmp_path, settings):
    """05-Armoury.md has exactly one such heading: Table 5-5 ... (`1d100`)."""
    content = _render(
        client, user_factory, tmp_path, settings, "# Chapter\n\n## Effects (`1d100`)\nBody.\n"
    )

    assert "<code>1d100</code>" in content
    assert "`1d100`" not in content


@pytest.mark.django_db
def test_a_literal_heading_with_an_id_in_the_source_stays_text(
    client, user_factory, tmp_path, settings
):
    """`html: False` escapes it long before it could become a tag with an id."""
    content = _render(
        client,
        user_factory,
        tmp_path,
        settings,
        '# Chapter\n\n## Real\n\n<h2 id="main-content">injected</h2>\n',
    )

    assert 'id="main-content">injected' not in content
    assert "&lt;h2 id=" in content


@pytest.mark.django_db
def test_every_heading_carries_a_permalink(client, user_factory, tmp_path, settings):
    content = _render(client, user_factory, tmp_path, settings, "# Chapter\n\n## Alpha\na\n")

    assert '<a class="wiki-anchor" href="#sec-alpha"' in content

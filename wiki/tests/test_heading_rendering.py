"""Headings are rendered by the template, not by the sanitizer.

Every heading is an outline node, so its body HTML contains no heading tag at
all and the anchor ``id`` is written in template context. That is what lets
``wiki/markdown.py`` keep ``id`` out of the Bleach allowlist entirely -- a
value copied from the document could otherwise shadow a DOM global or one of
the shell's own element ids.
"""
import re

import pytest
from django.urls import reverse


def _render(
    client, user_factory, make_repository, body, name="01-Chapter.md", slug="chapter"
):
    make_repository({name: body}, install=True)
    client.force_login(user_factory())
    response = client.get(reverse("wiki:chapter", kwargs={"chapter_slug": slug}))
    assert response.status_code == 200
    return response.content.decode()


def _heading_texts(html: str, level: int) -> list[str]:
    """Visible text of every ``<hN>`` on the page, permalink anchor removed."""
    blocks = re.findall(rf"<h{level}[^>]*>(.*?)</h{level}>", html, re.DOTALL)
    without_anchor = [
        re.sub(r'<a class="wiki-anchor".*?</a>', "", block, flags=re.DOTALL)
        for block in blocks
    ]
    return [re.sub(r"<[^>]+>", "", text).strip() for text in without_anchor]


@pytest.mark.django_db
def test_each_section_gets_exactly_one_prefixed_anchor(client, user_factory, make_repository):
    content = _render(
        client,
        user_factory,
        make_repository,
        "# Chapter\n\n## Alpha\na\n\n### Beta\nb\n\n## Gamma\nc\n",
    )

    ids = re.findall(r'<section id="([^"]+)"', content)

    assert ids == ["sec-alpha", "sec-beta", "sec-gamma"]
    assert len(ids) == len(set(ids))


@pytest.mark.django_db
def test_nesting_is_reflected_in_the_heading_levels(client, user_factory, make_repository):
    content = _render(
        client, user_factory, make_repository, "# Chapter\n\n## Alpha\na\n\n### Beta\nb\n"
    )

    assert re.search(r'<section id="sec-alpha">\s*<h2>', content)
    assert re.search(r'<section id="sec-beta">\s*<h3>', content)


@pytest.mark.django_db
def test_inline_markup_in_a_heading_survives(client, user_factory, make_repository):
    """05-Armoury.md has exactly one such heading: Table 5-5 ... (`1d100`)."""
    content = _render(
        client, user_factory, make_repository, "# Chapter\n\n## Effects (`1d100`)\nBody.\n"
    )

    assert "<code>1d100</code>" in content
    assert "`1d100`" not in content


@pytest.mark.django_db
def test_a_literal_heading_with_an_id_in_the_source_stays_text(
    client, user_factory, make_repository
):
    """`html: False` escapes it long before it could become a tag with an id."""
    content = _render(
        client,
        user_factory,
        make_repository,
        '# Chapter\n\n## Real\n\n<h2 id="main-content">injected</h2>\n',
    )

    assert 'id="main-content">injected' not in content
    assert "&lt;h2 id=" in content


@pytest.mark.django_db
def test_every_heading_carries_a_permalink(client, user_factory, make_repository):
    content = _render(client, user_factory, make_repository, "# Chapter\n\n## Alpha\na\n")

    assert '<a class="wiki-anchor" href="#sec-alpha"' in content


@pytest.mark.django_db
def test_chapter_intro_heading_is_not_duplicated_when_slug_and_title_differ(
    client, user_factory, make_repository
):
    # The filename-derived chapter slug ("second") and the H1-derived intro
    # section id ("plasma-doctrine") deliberately differ: the template must key
    # on `is_intro`, not on the two strings coinciding.
    content = _render(
        client,
        user_factory,
        make_repository,
        "# Plasma Doctrine\nIntro body text.\n\n## Details\nMore text.",
        name="02-Second.md",
        slug="second",
    )

    # The intro section's title equals the chapter title, so the chapter
    # heading must appear exactly once, as the <h1>; the intro section must
    # not render its own duplicate <h2> with the same text. The real "##
    # Details" section still gets its <h2> normally.
    assert _heading_texts(content, 1) == ["Plasma Doctrine"]
    assert _heading_texts(content, 2) == ["Details"]

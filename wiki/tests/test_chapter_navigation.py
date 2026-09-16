"""Chapter-page navigation: breadcrumbs, prev/next, and the nested contents.

Before the heading tree the table of contents was a flat list of H2s, which
for most chapters meant a handful of entries and for the career-paths chapter
meant one. It now mirrors the tree, with a compact index standing in for
sections whose children are really a glossary.
"""
import re

import pytest
from django.urls import reverse

from wiki.content import WikiRepository, set_repository_for_tests

CHAPTERS = ("01-One.md", "02-Two.md", "03-Three.md")


def _publish(tmp_path, settings, bodies):
    for name, body in bodies.items():
        (tmp_path / name).write_text(body, encoding="utf-8")
    settings.WIKI_CONTENT_ROOT = tmp_path
    settings.WIKI_CONTENT_ALLOWLIST = list(bodies)
    set_repository_for_tests(WikiRepository.load())


def _get(client, user_factory, slug):
    client.force_login(user_factory())
    response = client.get(reverse("wiki:chapter", kwargs={"chapter_slug": slug}))
    assert response.status_code == 200
    return response.content.decode()


@pytest.fixture
def three_chapters(tmp_path, settings):
    _publish(
        tmp_path,
        settings,
        {
            "01-One.md": "# One\n\n## Alpha\na\n",
            "02-Two.md": "# Two\n\n## Beta\nb\n\n### Beta Detail\nbd\n",
            "03-Three.md": "# Three\n\n## Gamma\nc\n",
        },
    )


@pytest.mark.django_db
def test_breadcrumbs_lead_back_to_the_wiki_index(client, user_factory, three_chapters):
    content = _get(client, user_factory, "two")

    assert 'class="wiki-breadcrumbs"' in content
    assert f'href="{reverse("wiki:index")}"' in content


@pytest.mark.django_db
def test_a_middle_chapter_links_both_neighbours(client, user_factory, three_chapters):
    content = _get(client, user_factory, "two")

    assert reverse("wiki:chapter", kwargs={"chapter_slug": "one"}) in content
    assert reverse("wiki:chapter", kwargs={"chapter_slug": "three"}) in content
    assert 'rel="prev"' in content
    assert 'rel="next"' in content


@pytest.mark.django_db
def test_the_first_chapter_has_no_previous_link(client, user_factory, three_chapters):
    content = _get(client, user_factory, "one")

    assert 'rel="prev"' not in content
    assert 'rel="next"' in content


@pytest.mark.django_db
def test_the_last_chapter_has_no_next_link(client, user_factory, three_chapters):
    content = _get(client, user_factory, "three")

    assert 'rel="prev"' in content
    assert 'rel="next"' not in content


@pytest.mark.django_db
def test_the_contents_nest_sub_sections(client, user_factory, three_chapters):
    content = _get(client, user_factory, "two")
    toc = content.split('class="wiki-section-nav"', 1)[1].split("</nav>", 1)[0]

    assert "#sec-beta" in toc
    assert "#sec-beta-detail" in toc
    # Nested, not flattened into one list.
    assert toc.count('class="wiki-toc-list"') >= 2


@pytest.mark.django_db
def test_a_glossary_section_renders_as_a_compact_index(
    client, user_factory, tmp_path, settings
):
    entries = "\n\n".join(f"### Entry {index}\nBody." for index in range(20))
    _publish(
        tmp_path, settings, {"01-One.md": f"# One\n\n## Descriptions\nIntro.\n\n{entries}\n"}
    )
    settings.WIKI_TOC_GLOSSARY_THRESHOLD = 16

    content = _get(client, user_factory, "one")
    toc = content.split('class="wiki-section-nav"', 1)[1].split("</nav>", 1)[0]

    assert 'class="wiki-toc-index"' in toc
    assert toc.count("#sec-entry-") == 20


@pytest.mark.django_db
def test_a_small_group_stays_a_nested_list(client, user_factory, tmp_path, settings):
    entries = "\n\n".join(f"### Entry {index}\nBody." for index in range(3))
    _publish(
        tmp_path, settings, {"01-One.md": f"# One\n\n## Descriptions\nIntro.\n\n{entries}\n"}
    )
    settings.WIKI_TOC_GLOSSARY_THRESHOLD = 16

    content = _get(client, user_factory, "one")

    assert 'class="wiki-toc-index"' not in content


@pytest.mark.django_db
def test_the_contents_stop_at_the_configured_depth(
    client, user_factory, tmp_path, settings
):
    _publish(
        tmp_path,
        settings,
        {"01-One.md": "# One\n\n## A\na\n\n### B\nb\n\n#### C\nc\n\n##### D\nd\n"},
    )
    settings.WIKI_TOC_MAX_DEPTH = 2

    content = _get(client, user_factory, "one")
    toc = content.split('class="wiki-section-nav"', 1)[1].split("</nav>", 1)[0]

    assert "#sec-a" in toc
    assert "#sec-b" in toc
    assert "#sec-c" not in toc
    # The section itself is still rendered and linkable, just not listed.
    assert '<section id="sec-c">' in content


@pytest.mark.django_db
def test_chapter_html_is_compressed_for_clients_that_accept_it(
    client, user_factory, three_chapters
):
    client.force_login(user_factory())
    url = reverse("wiki:chapter", kwargs={"chapter_slug": "two"})

    plain = client.get(url)
    compressed = client.get(url, headers={"accept-encoding": "gzip"})

    assert plain.get("Content-Encoding") is None
    assert compressed["Content-Encoding"] == "gzip"


@pytest.mark.django_db
def test_search_results_are_not_compressed(client, user_factory, three_chapters):
    """The search page reflects `q`; keep compression away from it."""
    client.force_login(user_factory())

    response = client.get(
        reverse("wiki:search"), {"q": "alpha"}, headers={"accept-encoding": "gzip"}
    )

    assert response.get("Content-Encoding") is None

"""Chapter-page navigation: breadcrumbs, prev/next, and the nested contents.

The table of contents mirrors the heading tree, with a compact index standing
in for sections whose children are really a glossary.
"""
import json

import pytest
from django.urls import reverse


def _get(client, user_factory, slug):
    client.force_login(user_factory())
    response = client.get(reverse("wiki:chapter", kwargs={"chapter_slug": slug}))
    assert response.status_code == 200
    return response.content.decode()


def _toc(content):
    return content.split('class="wiki-section-nav"', 1)[1].split("</nav>", 1)[0]


def _glossary_chapter(make_repository, entry_count):
    entries = "\n\n".join(f"### Entry {index}\nBody." for index in range(entry_count))
    make_repository(
        {"01-One.md": f"# One\n\n## Descriptions\nIntro.\n\n{entries}\n"}, install=True
    )


@pytest.fixture
def three_chapters(make_repository):
    make_repository(
        {
            "01-One.md": "# One\n\n## Alpha\na\n",
            "02-Two.md": "# Two\n\n## Beta\nb\n\n### Beta Detail\nbd\n",
            "03-Three.md": "# Three\n\n## Gamma\nc\n",
        },
        install=True,
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
    toc = _toc(content)

    assert "#sec-beta" in toc
    assert "#sec-beta-detail" in toc
    # Nested, not flattened into one list.
    assert toc.count('class="wiki-toc-list"') >= 2


@pytest.mark.django_db
def test_a_glossary_section_renders_as_a_compact_index(
    client, user_factory, make_repository, settings
):
    _glossary_chapter(make_repository, 20)
    settings.WIKI_TOC_GLOSSARY_THRESHOLD = 16

    content = _get(client, user_factory, "one")
    toc = _toc(content)

    assert 'class="wiki-toc-index"' in toc
    assert toc.count("#sec-entry-") == 20


@pytest.mark.django_db
def test_a_small_group_stays_a_nested_list(client, user_factory, make_repository, settings):
    _glossary_chapter(make_repository, 3)
    settings.WIKI_TOC_GLOSSARY_THRESHOLD = 16

    content = _get(client, user_factory, "one")

    assert 'class="wiki-toc-index"' not in content


@pytest.mark.django_db
def test_the_contents_stop_at_the_configured_depth(
    client, user_factory, make_repository, settings
):
    make_repository(
        {"01-One.md": "# One\n\n## A\na\n\n### B\nb\n\n#### C\nc\n\n##### D\nd\n"},
        install=True,
    )
    settings.WIKI_TOC_MAX_DEPTH = 2

    content = _get(client, user_factory, "one")
    toc = _toc(content)

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


@pytest.mark.django_db
def test_the_outline_sits_beside_the_article_not_inside_it(
    client, user_factory, three_chapters
):
    """It is the chapter's main way around, so it is its own left-hand menu.

    Inside the article it pushed the text down and scrolled out of reach after
    a screenful; on an 800-section corpus that made it close to useless.
    """
    content = _get(client, user_factory, "two")

    layout = content.split('class="wiki-layout"', 1)[1]
    nav_at = layout.index('class="wiki-section-nav"')
    article_at = layout.index('class="wiki-article"')

    assert nav_at < article_at, "the outline must precede the article"
    # And it must not have been left behind inside the article as well.
    article = layout[article_at:]
    assert "wiki-section-nav" not in article


@pytest.mark.django_db
def test_a_chapter_without_sections_renders_no_outline_menu(
    client, user_factory, make_repository
):
    make_repository({"01-One.md": "# One\n"}, install=True)

    content = _get(client, user_factory, "one")

    assert "wiki-section-nav" not in content
    assert "wiki-layout" in content


@pytest.mark.django_db
def test_empty_chapter_displays_placeholder_for_logged_in_user(
    client, user_factory, make_repository
):
    make_repository({"09-Placeholder.md": "# Placeholder"}, install=True)

    content = _get(client, user_factory, "placeholder")

    assert "Dieses Kapitel ist noch nicht ausgearbeitet." in content


@pytest.mark.django_db
def test_sub_sections_are_collapsed_until_asked_for(
    client, user_factory, three_chapters
):
    """A chapter has a handful of top-level sections and hundreds below them.

    Measured on Playing the Game: the outline is 650px tall collapsed against
    3259px expanded, so folding is what keeps the menu scannable at all.
    """
    content = _get(client, user_factory, "two")
    toc = _toc(content)

    assert '<details class="wiki-toc-branch">' in toc
    # Collapsed: no `open` attribute on the branch.
    assert "<details class=\"wiki-toc-branch\" open" not in toc
    # The parent's own link stays reachable from the summary.
    assert '<summary><a href="#sec-beta"' in toc
    assert "#sec-beta-detail" in toc


@pytest.mark.django_db
def test_a_section_without_children_is_a_plain_link(
    client, user_factory, three_chapters
):
    """Only branches get a disclosure; leaves must not look expandable."""
    content = _get(client, user_factory, "one")
    toc = _toc(content)

    assert "#sec-alpha" in toc
    assert "wiki-toc-branch" not in toc


@pytest.mark.django_db
def test_a_glossary_index_lives_inside_its_disclosure(
    client, user_factory, make_repository, settings
):
    _glossary_chapter(make_repository, 20)
    settings.WIKI_TOC_GLOSSARY_THRESHOLD = 16

    content = _get(client, user_factory, "one")
    toc = _toc(content)
    branch = toc.split('<details class="wiki-toc-branch">', 1)[1].split("</details>", 1)[0]

    assert 'class="wiki-toc-index"' in branch
    assert branch.count("#sec-entry-") == 20


def _primary_nav(content):
    return content.split('id="primary-nav"', 1)[1].split("</nav>", 1)[0]


@pytest.mark.django_db
def test_the_primary_nav_lists_every_chapter_under_wiki(
    client, user_factory, three_chapters
):
    """Switching chapters no longer needs prev/next or a list at the bottom."""
    nav = _primary_nav(_get(client, user_factory, "two"))
    tree = nav.split('<ul class="primary-nav-sub" aria-label="Kapitel">', 1)[1].split("</ul>", 1)[0]

    for slug in ("one", "two", "three"):
        assert f'href="{reverse("wiki:chapter", kwargs={"chapter_slug": slug})}"' in tree
    assert 'class="primary-nav-numeral"' in tree


@pytest.mark.django_db
def test_only_the_current_chapter_is_the_current_page(
    client, user_factory, three_chapters
):
    nav = _primary_nav(_get(client, user_factory, "two"))

    assert nav.count('aria-current="page"') == 1
    current = nav.split('aria-current="page"', 1)[0].rsplit("<a ", 1)[1]
    assert reverse("wiki:chapter", kwargs={"chapter_slug": "two"}) in current


@pytest.mark.django_db
def test_the_wiki_index_keeps_the_wiki_link_current(
    client, user_factory, three_chapters
):
    client.force_login(user_factory())
    content = client.get(reverse("wiki:index")).content.decode()
    nav = _primary_nav(content)

    assert 'class="primary-nav-sub"' in nav
    assert nav.count('aria-current="page"') == 1
    current = nav.split('aria-current="page"', 1)[0].rsplit("<a ", 1)[1]
    assert f'href="{reverse("wiki:index")}"' in current


@pytest.mark.django_db
def test_the_dashboard_nav_has_no_chapter_tree(client, user_factory, three_chapters):
    client.force_login(user_factory())
    content = client.get(reverse("dashboard")).content.decode()

    assert "primary-nav-sub" not in content


@pytest.mark.django_db
def test_the_folded_chapter_list_at_the_bottom_is_gone(
    client, user_factory, three_chapters
):
    """The chapter tree in the primary nav replaces it."""
    content = _get(client, user_factory, "two")

    assert "wiki-chapter-list" not in content
    assert "Alle Kapitel" not in content


@pytest.mark.django_db
def test_the_reading_aids_are_in_place(client, user_factory, three_chapters):
    content = _get(client, user_factory, "two")
    toc = _toc(content)

    assert 'class="wiki-toc-filter js-only"' in toc
    assert toc.index("wiki-toc-filter") < toc.index('class="wiki-toc-list"')
    assert 'class="wiki-to-top js-only" hidden' in content
    assert 'data-chapter-title="Two"' in content
    assert "js/wiki-reader.js" in content
    # Progress bar only on the sticky copy of the chapter nav.
    assert content.count('class="wiki-progress js-only"') == 1
    sticky = content.split("wiki-chapter-nav--sticky", 1)[1].split("</nav>", 1)[0]
    assert 'class="wiki-progress js-only"' in sticky


@pytest.mark.django_db
def test_a_search_query_passes_highlight_terms_to_the_page(
    client, user_factory, three_chapters
):
    client.force_login(user_factory())
    url = reverse("wiki:chapter", kwargs={"chapter_slug": "two"})

    response = client.get(url, {"q": "Waffe"})
    content = response.content.decode()

    assert '<script id="wiki-highlight-terms" type="application/json">' in content
    terms = content.split('id="wiki-highlight-terms" type="application/json">', 1)[1]
    assert '"weapon"' in terms.split("</script>", 1)[0]
    assert response.context["highlight_terms"] == ["waffe", "weapon"]


@pytest.mark.django_db
def test_without_a_query_there_are_no_highlight_terms(
    client, user_factory, three_chapters
):
    content = _get(client, user_factory, "two")

    assert "wiki-highlight-terms" not in content


@pytest.mark.django_db
def test_a_chapter_opened_with_a_query_is_not_compressed(
    client, user_factory, three_chapters
):
    """It echoes `q` (topbar field, highlight terms): same BREACH rule as search."""
    client.force_login(user_factory())
    url = reverse("wiki:chapter", kwargs={"chapter_slug": "two"})

    response = client.get(url, {"q": "Waffe"}, headers={"accept-encoding": "gzip"})

    assert response.get("Content-Encoding") is None


@pytest.mark.django_db
def test_markup_in_the_query_only_reaches_the_page_as_escaped_json(
    client, user_factory, three_chapters
):
    client.force_login(user_factory())
    url = reverse("wiki:chapter", kwargs={"chapter_slug": "two"})

    content = client.get(url, {"q": "<img src=x onerror=alert(1)>"}).content.decode()

    assert "<img" not in content
    script = content.split('<script id="wiki-highlight-terms" type="application/json">', 1)[1]
    payload = script.split("</script>", 1)[0]
    assert "<" not in payload and ">" not in payload
    assert json.loads(payload) == ["alert", "img", "onerror", "src"]
    article = content.split('class="wiki-article"', 1)[1].split("</article>", 1)[0]
    assert "onerror" not in article

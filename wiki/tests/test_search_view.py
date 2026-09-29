"""The search results page.

It previously rendered an empty ``<ul>`` for every unproductive case, so
"nothing typed yet", "too short to search" and "searched, found nothing" all
looked identical.
"""
import re

import pytest
from django.urls import reverse

from wiki.content import WikiRepository, set_repository_for_tests
from wiki.manifest import QuickLink
from wiki.search import MIN_QUERY_LENGTH


@pytest.fixture
def corpus(tmp_path, settings):
    (tmp_path / "01-Chapter.md").write_text(
        "# Chapter\n\n## Combat\nTaking cover helps.\n", encoding="utf-8"
    )
    settings.WIKI_CONTENT_ROOT = tmp_path
    settings.WIKI_CONTENT_ALLOWLIST = ["01-Chapter.md"]
    set_repository_for_tests(WikiRepository.load())


def _search(client, user_factory, query=None):
    client.force_login(user_factory())
    params = {} if query is None else {"q": query}
    response = client.get(reverse("wiki:search"), params)
    assert response.status_code == 200
    return response.content.decode()


@pytest.mark.django_db
def test_hits_are_listed(client, user_factory, corpus):
    content = _search(client, user_factory, "cover")

    assert "1 Treffer" in content
    assert "wiki-results" in content


@pytest.mark.django_db
def test_no_query_shows_an_invitation(client, user_factory, corpus):
    content = _search(client, user_factory)

    assert "empty-state" in content
    assert "Treffer" not in content


@pytest.mark.django_db
def test_a_too_short_query_says_so(client, user_factory, corpus):
    content = _search(client, user_factory, "c" * (MIN_QUERY_LENGTH - 1))

    assert "empty-state" in content
    assert str(MIN_QUERY_LENGTH) in content
    assert "Keine Treffer" not in content


@pytest.mark.django_db
def test_zero_hits_explains_the_english_corpus(client, user_factory, corpus):
    content = _search(client, user_factory, "zzzznothing")

    assert "Keine Treffer" in content
    assert "Englisch" in content


@pytest.mark.django_db
def test_a_result_link_carries_the_query_and_the_anchor(client, user_factory, corpus):
    content = _search(client, user_factory, "cover")
    chapter_url = reverse("wiki:chapter", kwargs={"chapter_slug": "chapter"})

    assert f'href="{chapter_url}?q=cover#sec-combat"' in content


@pytest.mark.django_db
def test_a_query_with_special_characters_is_url_encoded(client, user_factory, corpus):
    content = _search(client, user_factory, "cover helps")

    assert "?q=cover%20helps#" in content or "?q=cover+helps#" in content


@pytest.mark.django_db
def test_the_chapter_page_keeps_the_query_in_the_search_box(
    client, user_factory, corpus
):
    """Following a result carries ?q= along; the topbar shows it for refining."""
    client.force_login(user_factory())

    response = client.get(
        reverse("wiki:chapter", kwargs={"chapter_slug": "chapter"}), {"q": "cover"}
    )
    content = response.content.decode()

    assert 'id="topbar-search-input"' in content
    assert 'value="cover"' in content


# -- facets, filter, cap, hit cards -----------------------------------------


@pytest.fixture
def book(tmp_path, settings):
    """Two manifest chapters (numerals I and II) plus front matter."""
    (tmp_path / "01-Charaktererschaffung.md").write_text(
        "# Chapter I: Character Creation\n\n## Origins\n\n### Homeworld\n"
        "Shelter for the wanderer.\n\n## Skills\nShelter and cover.\n",
        encoding="utf-8",
    )
    (tmp_path / "02-Karrierewege.md").write_text(
        "# Chapter II: Careers\n\n## Explorator\nShelter in the void.\n",
        encoding="utf-8",
    )
    (tmp_path / "00-Foreword.md").write_text(
        "# Foreword\n\n## Note\nShelter from the storm.\n", encoding="utf-8"
    )
    settings.WIKI_CONTENT_ROOT = tmp_path
    settings.WIKI_CONTENT_ALLOWLIST = [
        "00-Foreword.md",
        "01-Charaktererschaffung.md",
        "02-Karrierewege.md",
    ]
    set_repository_for_tests(WikiRepository.load())


def _get(client, user_factory, **params):
    client.force_login(user_factory())
    response = client.get(reverse("wiki:search"), params)
    assert response.status_code == 200
    return response


def _path_line(content):
    return content.split('class="search-hit-path">')[1].split("</p>")[0]


@pytest.mark.django_db
def test_facets_count_hits_per_chapter_in_book_order(client, user_factory, book):
    response = _get(client, user_factory, q="shelter")
    facets = response.context["facets"]

    assert [(f["chapter"].slug, f["count"]) for f in facets] == [
        ("foreword", 1),
        ("charaktererschaffung", 2),
        ("karrierewege", 1),
    ]
    assert response.context["all_count"] == 4
    assert response.context["total_count"] == 4
    assert response.context["active_chapter"] is None
    content = response.content.decode()
    assert 'class="search-facets"' in content
    assert 'aria-label="Nach Kapitel eingrenzen"' in content
    assert "Alle Kapitel" in content
    assert "I &middot; Character Creation" in content


@pytest.mark.django_db
def test_kapitel_filters_to_that_chapter(client, user_factory, book):
    response = _get(client, user_factory, q="shelter", kapitel="charaktererschaffung")
    content = response.content.decode()

    assert response.context["active_chapter"].slug == "charaktererschaffung"
    assert response.context["total_count"] == 2
    assert response.context["all_count"] == 4
    assert {r.chapter_slug for r in response.context["results"]} == {
        "charaktererschaffung"
    }
    assert "2 Treffer" in content
    assert "in Character Creation" in content
    assert content.count('aria-current="true"') == 1
    assert "search-hit-card--best" not in content
    assert "Bester Treffer" not in content
    # Facets still list every chapter so the reader can switch.
    assert len(response.context["facets"]) == 3


@pytest.mark.django_db
def test_an_unknown_kapitel_is_ignored(client, user_factory, book):
    response = _get(client, user_factory, q="shelter", kapitel="nope")

    assert response.context["active_chapter"] is None
    assert response.context["total_count"] == 4


@pytest.mark.django_db
def test_a_kapitel_without_hits_is_ignored(client, user_factory, book):
    response = _get(client, user_factory, q="storm", kapitel="karrierewege")

    assert response.context["active_chapter"] is None
    assert response.context["total_count"] == 1


@pytest.mark.django_db
def test_results_are_capped_at_fifty(client, user_factory, tmp_path, settings):
    sections = "".join(f"## Part {i}\nlantern glow {i}.\n\n" for i in range(60))
    (tmp_path / "01-Chapter.md").write_text(
        f"# Chapter\n\n{sections}", encoding="utf-8"
    )
    settings.WIKI_CONTENT_ROOT = tmp_path
    settings.WIKI_CONTENT_ALLOWLIST = ["01-Chapter.md"]
    set_repository_for_tests(WikiRepository.load())

    response = _get(client, user_factory, q="lantern")
    content = response.content.decode()

    assert len(response.context["results"]) == 50
    assert response.context["total_count"] == 60
    assert response.context["results_capped"] is True
    assert "60 Treffer" in content
    assert "die besten 50 werden angezeigt" in content


@pytest.mark.django_db
def test_a_small_result_set_is_not_flagged_as_capped(client, user_factory, book):
    response = _get(client, user_factory, q="shelter")

    assert response.context["results_capped"] is False
    assert "die besten 50" not in response.content.decode()


@pytest.mark.django_db
def test_a_hit_card_leads_with_its_link_then_path_and_snippet(
    client, user_factory, book
):
    content = _get(client, user_factory, q="wanderer").content.decode()
    chapter_url = reverse(
        "wiki:chapter", kwargs={"chapter_slug": "charaktererschaffung"}
    )

    assert '<ol class="wiki-results">' in content
    assert (
        f'<a class="search-hit-title" href="{chapter_url}?q=wanderer#sec-homeworld">'
        in content
    )
    assert content.index("search-hit-title") < content.index("search-hit-path")
    assert content.index("search-hit-path") < content.index("search-hit-snippet")
    path = _path_line(content)
    assert "I &middot; Character Creation" in path
    assert "Origins" in path
    assert "&rsaquo;" in path
    assert "<mark>" in content


@pytest.mark.django_db
def test_the_first_link_of_every_card_points_into_the_chapter(
    client, user_factory, book
):
    content = _get(client, user_factory, q="shelter").content.decode()
    cards = re.findall(r'<li class="search-hit-card[^>]*>(.*?)</li>', content, re.S)

    assert len(cards) == 4
    for card in cards:
        href = re.search(r'<a [^>]*href="([^"]+)"', card).group(1)
        assert href.startswith("/wiki/")
        assert "?q=shelter#sec-" in href


@pytest.mark.django_db
def test_only_the_first_unfiltered_card_is_the_best_hit(client, user_factory, book):
    content = _get(client, user_factory, q="shelter").content.decode()

    assert content.count("search-hit-card--best") == 1
    assert content.count("Bester Treffer") == 1
    assert content.index("search-hit-card--best") < content.index("search-hit-title")


@pytest.mark.django_db
def test_front_matter_shows_no_leading_separator(client, user_factory, book):
    path = _path_line(_get(client, user_factory, q="storm").content.decode())

    assert path.strip().startswith("Foreword")
    assert "&middot;" not in path


@pytest.mark.django_db
def test_no_hits_offers_the_quick_links(client, user_factory, book, monkeypatch):
    monkeypatch.setattr(
        "wiki.content.QUICK_LINKS",
        (QuickLink("Kandidaten", "karrierewege", "explorator"),),
    )
    content = _get(client, user_factory, q="zzzznothing").content.decode()
    url = reverse("wiki:chapter", kwargs={"chapter_slug": "karrierewege"})

    assert '<ul class="quick-links">' in content
    assert (
        f'<a class="quick-link" href="{url}#sec-explorator">Kandidaten</a>' in content
    )
    assert "search-facets" not in content


@pytest.mark.django_db
def test_hits_do_not_render_the_quick_links(client, user_factory, book):
    content = _get(client, user_factory, q="shelter").content.decode()

    assert "quick-links" not in content

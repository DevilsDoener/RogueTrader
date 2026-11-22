"""The search results page.

"Nothing typed yet", "too short to search" and "searched, found nothing" each
get their own message rather than one indistinguishable empty list.
"""
import pytest
from django.urls import reverse

from tests.html import attr, has_link, select, select_one
from wiki.manifest import QuickLink
from wiki.search import MIN_QUERY_LENGTH


@pytest.fixture
def corpus(make_repository):
    make_repository(
        {"01-Chapter.md": "# Chapter\n\n## Combat\nTaking cover helps.\n"}, install=True
    )


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
    # The shell's Auspex palette has its own "Alle Treffer" link; only the
    # page's main content must not talk about hits.
    main = content.split('<main id="main-content"', 1)[1].split("</main>", 1)[0]

    assert "empty-state" in main
    assert "Treffer" not in main


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

    assert has_link(content, f"{chapter_url}?q=cover#sec-combat")


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
def book(make_repository):
    """Two manifest chapters (numerals I and II) plus front matter."""
    make_repository(
        {
            "00-Foreword.md": "# Foreword\n\n## Note\nShelter from the storm.\n",
            "01-Charaktererschaffung.md": (
                "# Chapter I: Character Creation\n\n## Origins\n\n### Homeworld\n"
                "Shelter for the wanderer.\n\n## Skills\nShelter and cover.\n"
            ),
            "02-Karrierewege.md": (
                "# Chapter II: Careers\n\n## Explorator\nShelter in the void.\n"
            ),
        },
        install=True,
    )


def _get(client, user_factory, **params):
    client.force_login(user_factory())
    response = client.get(reverse("wiki:search"), params)
    assert response.status_code == 200
    return response


def _shown(response):
    return [result for result, _chapter in response.context["hits"]]


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
    assert attr(select_one(content, ".search-facets"), "aria-label") == (
        "Nach Kapitel eingrenzen"
    )
    assert "Alle Kapitel" in content
    assert "I &middot; Character Creation" in content


@pytest.mark.django_db
def test_kapitel_filters_to_that_chapter(client, user_factory, book):
    response = _get(client, user_factory, q="shelter", kapitel="charaktererschaffung")
    content = response.content.decode()

    assert response.context["active_chapter"].slug == "charaktererschaffung"
    assert response.context["total_count"] == 2
    assert response.context["all_count"] == 4
    assert {r.chapter_slug for r in _shown(response)} == {
        "charaktererschaffung"
    }
    assert "2 Treffer" in content
    assert "in Character Creation" in content
    assert len(select(content, "[aria-current=true]")) == 1
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
def test_results_are_capped_at_fifty(client, user_factory, make_repository):
    sections = "".join(f"## Part {i}\nlantern glow {i}.\n\n" for i in range(60))
    make_repository({"01-Chapter.md": f"# Chapter\n\n{sections}"}, install=True)

    response = _get(client, user_factory, q="lantern")
    content = response.content.decode()

    assert len(_shown(response)) == 50
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

    results = select_one(content, "ol.wiki-results")
    titles = select(results, "a.search-hit-title")
    assert f"{chapter_url}?q=wanderer#sec-homeworld" in [attr(a, "href") for a in titles]
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
    cards = select(content, "li.search-hit-card")

    assert len(cards) == 4
    for card in cards:
        href = attr(select(card, "a")[0], "href")
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
        (QuickLink("Candidates", "karrierewege", "explorator"),),
    )
    content = _get(client, user_factory, q="zzzznothing").content.decode()
    url = reverse("wiki:chapter", kwargs={"chapter_slug": "karrierewege"})

    assert has_link(select_one(content, "ul.quick-links"), f"{url}#sec-explorator", "Candidates")
    assert "search-facets" not in content


@pytest.mark.django_db
def test_hits_do_not_render_the_quick_links(client, user_factory, book):
    content = _get(client, user_factory, q="shelter").content.decode()

    assert "quick-links" not in content

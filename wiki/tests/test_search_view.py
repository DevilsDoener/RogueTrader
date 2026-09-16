"""The search results page.

It previously rendered an empty ``<ul>`` for every unproductive case, so
"nothing typed yet", "too short to search" and "searched, found nothing" all
looked identical.
"""
import pytest
from django.urls import reverse

from wiki.content import WikiRepository, set_repository_for_tests
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

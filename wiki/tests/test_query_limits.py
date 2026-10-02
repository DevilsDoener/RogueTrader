"""Over-long queries are cut, not rejected (audit finding L1).

Search, suggestions and highlighting share ``wiki.search.clamp_query``: at most
``MAX_QUERY_LENGTH`` characters and ``MAX_QUERY_TOKENS`` words are looked at,
so a script posting thousands of distinct terms cannot make one request scan
the corpus for each of them.
"""
import time

import pytest
from django.urls import reverse

from wiki.search import MAX_QUERY_LENGTH, MAX_QUERY_TOKENS, clamp_query, query_tokens
from wiki.suggest import suggest

WORDS = [f"term{index:03d}" for index in range(40)]


@pytest.fixture
def repository(make_repository):
    return make_repository(
        {
            "01-Chapter.md": (
                "# Chapter\nIntro.\n\n## Combat\n"
                + " ".join(WORDS)
                + " weapon training.\n"
            )
        },
        install=True,
    )


def test_clamp_keeps_a_normal_query_untouched():
    assert clamp_query("hit locations") == "hit locations"
    assert clamp_query(None) == ""


def test_clamp_cuts_the_characters():
    assert len(clamp_query("a" * 5000)) == MAX_QUERY_LENGTH


def test_clamp_cuts_the_words():
    clamped = clamp_query(" ".join(WORDS))

    assert clamped.split() == WORDS[:MAX_QUERY_TOKENS]


def test_query_tokens_are_capped_even_inside_one_word():
    assert len(query_tokens("-".join(WORDS))) == MAX_QUERY_TOKENS


def test_highlight_terms_are_capped(repository):
    terms = repository.highlight_terms(" ".join(WORDS))

    assert len(terms) <= MAX_QUERY_TOKENS
    assert set(terms) == set(WORDS[:MAX_QUERY_TOKENS])


def test_search_ignores_words_past_the_cap(repository):
    # Every word is in the section; the eleventh and beyond are not even looked at,
    # so a nonsense word past the cap does not turn the hit into a miss.
    query = " ".join(WORDS[:MAX_QUERY_TOKENS]) + " zzzznotthere"

    assert [hit.section_id for hit in repository.search(query)] == ["combat"]


def test_search_accepts_a_five_thousand_character_query_quickly(repository):
    started = time.perf_counter()
    assert repository.search("a" * 5000) == ()
    repository.search(" ".join(WORDS * 30))

    assert time.perf_counter() - started < 0.2


def test_suggest_truncates_and_echoes_the_clamped_query(repository):
    result = suggest(repository, "a" * 5000)

    assert result["query"] == "a" * MAX_QUERY_LENGTH


def test_suggest_with_a_thousand_terms_is_fast_and_bounded(repository):
    query = " ".join(f"w{index:04d}" for index in range(1000))
    started = time.perf_counter()
    result = suggest(repository, query)

    assert time.perf_counter() - started < 0.2
    assert len(result["query"]) <= MAX_QUERY_LENGTH
    assert len(result["query"].split()) <= MAX_QUERY_TOKENS


@pytest.mark.django_db
def test_chapter_view_highlights_at_most_the_capped_terms(client, user_factory, repository):
    client.force_login(user_factory())

    response = client.get(
        reverse("wiki:chapter", args=["chapter"]), {"q": " ".join(WORDS)}
    )

    assert response.status_code == 200
    assert len(response.context["highlight_terms"]) <= MAX_QUERY_TOKENS


@pytest.mark.django_db
def test_search_page_shows_the_clamped_query(client, user_factory, repository):
    client.force_login(user_factory())

    response = client.get(reverse("wiki:search"), {"q": "a" * 5000})

    assert response.status_code == 200
    assert response.context["query"] == "a" * MAX_QUERY_LENGTH


@pytest.mark.django_db
def test_suggest_endpoint_survives_an_over_long_query(client, user_factory, repository):
    client.force_login(user_factory())

    response = client.get(reverse("wiki:suggest"), {"q": "x" * 3000})

    assert response.status_code == 200
    assert len(response.json()["query"]) == MAX_QUERY_LENGTH

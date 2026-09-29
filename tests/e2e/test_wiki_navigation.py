"""Playwright checks for the wiki navigation: the Bibliothek (index) page.

Runs against the real ``content/`` corpus so the live filter is exercised on
the chapters a reader actually sees.
"""
from __future__ import annotations

import json

import pytest

from wiki.content import WikiRepository, get_repository, set_repository_for_tests

from .conftest import login_via_browser

pytestmark = pytest.mark.django_db(transaction=True)

CARD_TALENTS = '.library-card:has(a.library-card-title:text-is("Talents"))'
CARD_STARSHIPS = '.library-card:has(a.library-card-title:text-is("Starships"))'


@pytest.fixture
def real_corpus(settings):
    original_repository = get_repository()
    settings.WIKI_CONTENT_ROOT = settings.BASE_DIR / "content"
    settings.WIKI_CONTENT_ALLOWLIST = settings.WIKI_DEFAULT_CONTENT_ALLOWLIST
    set_repository_for_tests(WikiRepository.load())
    try:
        yield
    finally:
        set_repository_for_tests(original_repository)


def _details_open(page) -> bool:
    return page.eval_on_selector(f"{CARD_TALENTS} details", "element => element.open")


def _open_library(page, live_server, owner):
    login_via_browser(page, live_server, username=owner.username)
    page.goto(f"{live_server.url}/wiki/")
    page.wait_for_selector("#library-filter")


def test_typing_filters_the_cards_and_clearing_restores_them(
    page, live_server, owner, real_corpus
):
    _open_library(page, live_server, owner)
    assert page.is_visible(CARD_TALENTS)
    assert page.is_visible(CARD_STARSHIPS)
    total = page.locator(".library-card").count()
    assert total > 10

    page.fill("#library-filter", "talent")

    assert page.is_visible(CARD_TALENTS)
    assert not page.is_visible(CARD_STARSHIPS)
    assert page.is_hidden(".library-empty")

    page.fill("#library-filter", "")

    assert page.is_visible(CARD_STARSHIPS)
    assert page.locator(".library-card:not([hidden])").count() == total


def test_matching_sections_open_and_a_miss_shows_the_empty_note(
    page, live_server, owner, real_corpus
):
    _open_library(page, live_server, owner)
    assert not _details_open(page)

    page.fill("#library-filter", "detailed talent")
    assert _details_open(page)
    assert page.locator(f"{CARD_TALENTS} a.is-match").count() >= 1

    page.fill("#library-filter", "")
    assert not _details_open(page)
    assert page.locator("a.is-match").count() == 0

    page.fill("#library-filter", "qqzzxxyy")
    assert page.is_visible(".library-empty")
    assert page.locator(".library-card:not([hidden])").count() == 0


def test_enter_starts_the_fulltext_search(page, live_server, owner, real_corpus):
    _open_library(page, live_server, owner)

    page.fill("#library-filter", "talent")
    page.press("#library-filter", "Enter")
    page.wait_for_url("**/search/?q=talent")

    assert "/search/" in page.url


def test_weiterlesen_appears_only_with_a_stored_reading_position(
    page, live_server, owner, real_corpus
):
    _open_library(page, live_server, owner)
    assert page.is_hidden(".library-recent")

    entries = [
        {"title": "Erfolgsgrade", "chapter": "Playing the Game", "url": "/wiki/playing-the-game/#sec-x", "ts": 3},
        {"title": "Evil", "chapter": "Elsewhere", "url": "https://example.com/wiki/", "ts": 2},
        {"title": "Talente", "chapter": "Talents", "url": "/wiki/talents/", "ts": 1},
    ]
    page.evaluate(
        "(value) => localStorage.setItem('rt-wiki-recent', value)", json.dumps(entries)
    )
    page.reload()
    page.wait_for_selector("#library-filter")

    assert page.is_visible(".library-recent")
    links = page.locator(".library-recent-card")
    assert links.count() == 2  # the off-site entry is dropped
    assert page.inner_text(".library-recent-title") == "Erfolgsgrade"
    assert page.get_attribute(".library-recent-card", "href") == "/wiki/playing-the-game/#sec-x"

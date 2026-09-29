"""Playwright checks for the wiki navigation: the Bibliothek (index) page and
the reading aids on a chapter page (scroll-spy, outline filter, highlight).

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


def test_filtering_hides_bands_without_a_match_entirely(
    page, live_server, owner, real_corpus
):
    _open_library(page, live_server, owner)
    vorspann = '.library-band:has(h2:text-is("Vorspann"))'
    kapitel = '.library-band:has(h2:text-is("Kapitel"))'
    anhang = '.library-band:has(h2:text-is("Anhang"))'
    assert page.is_visible(vorspann) and page.is_visible(kapitel) and page.is_visible(anhang)

    page.fill("#library-filter", "critical")

    assert page.is_visible(kapitel)
    assert not page.is_visible(vorspann)
    assert not page.is_visible(anhang)
    assert page.is_hidden(f"{vorspann} .library-band-heading")

    page.fill("#library-filter", "")

    assert page.is_visible(vorspann) and page.is_visible(anhang)


def test_a_contents_list_the_reader_opened_stays_open_after_filtering(
    page, live_server, owner, real_corpus
):
    _open_library(page, live_server, owner)
    page.click(f"{CARD_TALENTS} summary")
    assert _details_open(page)

    page.fill("#library-filter", "detailed talent")
    assert _details_open(page)
    page.fill("#library-filter", "")

    assert _details_open(page)


# ---- Chapter page: reading aids (static/js/wiki-reader.js) -----------------

ATTACK_LINK = '.wiki-section-nav a[href="#sec-the-attack"]'
HEALING_LINK = '.wiki-section-nav a[href="#sec-healing"]'


def _open_chapter(page, live_server, owner, path):
    login_via_browser(page, live_server, username=owner.username)
    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(f"{live_server.url}{path}")
    page.wait_for_selector(".wiki-article")


def _scroll_to(page, element_id):
    page.evaluate("(id) => document.getElementById(id).scrollIntoView()", element_id)


def test_scrolling_to_a_section_marks_it_in_the_outline(
    page, live_server, owner, real_corpus
):
    _open_chapter(page, live_server, owner, "/wiki/playing-the-game/")
    assert page.get_attribute(ATTACK_LINK, "aria-current") is None

    _scroll_to(page, "sec-the-attack")
    page.wait_for_selector(f'{ATTACK_LINK}[aria-current="location"]')

    assert page.locator('.wiki-section-nav [aria-current="location"]').count() == 1
    assert "is-active" in page.get_attribute(ATTACK_LINK, "class")
    # The outline scrolled itself so the marked entry is in view.
    assert page.evaluate(
        """(selector) => {
            const nav = document.querySelector('.wiki-section-nav').getBoundingClientRect();
            const link = document.querySelector(selector).getBoundingClientRect();
            return link.top >= nav.top && link.bottom <= nav.bottom;
        }""",
        ATTACK_LINK,
    )

    _scroll_to(page, "sec-healing")
    page.wait_for_selector(f'{HEALING_LINK}[aria-current="location"]')

    assert page.get_attribute(ATTACK_LINK, "aria-current") is None
    assert page.locator('.wiki-section-nav [aria-current="location"]').count() == 1


def test_the_outline_filter_hides_sections_that_do_not_match(
    page, live_server, owner, real_corpus
):
    _open_chapter(page, live_server, owner, "/wiki/playing-the-game/")
    hit_locations = '.wiki-section-nav a:text-is("Table 9-6: Hit Locations")'
    healing = '.wiki-section-nav a:text-is("Healing")'
    assert page.is_visible(".wiki-toc-filter")
    assert page.is_visible(healing)
    assert not page.is_visible(hit_locations)  # folded away inside its branch

    page.fill(".wiki-toc-filter", "hit")

    assert page.is_visible(hit_locations)
    assert not page.is_visible(healing)

    page.fill(".wiki-toc-filter", "")

    assert page.is_visible(healing)
    assert not page.is_visible(hit_locations)  # its branch folds up again


def test_a_search_query_highlights_the_chapter_until_removed(
    page, live_server, owner, real_corpus
):
    _open_chapter(page, live_server, owner, "/wiki/armoury/?q=Waffe")
    page.wait_for_selector("mark.wiki-hit")

    assert page.locator("mark.wiki-hit").count() >= 1
    assert page.is_visible(".wiki-hit-bar")
    assert "Stellen markiert" in page.inner_text(".wiki-hit-bar")

    page.click('.wiki-hit-bar button:text-is("Markierung entfernen")')

    assert page.locator("mark.wiki-hit").count() == 0
    assert page.locator(".wiki-hit-bar").count() == 0
    assert "q=" not in page.url


def test_leaving_a_chapter_records_the_reading_position(
    page, live_server, owner, real_corpus
):
    _open_chapter(page, live_server, owner, "/wiki/playing-the-game/")
    _scroll_to(page, "sec-healing")
    page.wait_for_selector(f'{HEALING_LINK}[aria-current="location"]')

    page.goto(f"{live_server.url}/wiki/")
    page.wait_for_selector("#library-filter")
    stored = json.loads(page.evaluate("localStorage.getItem('rt-wiki-recent')"))

    assert stored[0]["url"] == "/wiki/playing-the-game/#sec-healing"
    assert stored[0]["title"] == "Healing"
    assert stored[0]["chapter"] == "Playing the Game"
    paths = [entry["url"].split("#")[0] for entry in stored]
    assert paths.count("/wiki/playing-the-game/") == 1
    assert page.inner_text(".library-recent-title") == "Healing"


def test_the_current_chapter_is_marked_in_the_chapter_tree(
    page, live_server, owner, real_corpus
):
    _open_chapter(page, live_server, owner, "/wiki/talents/")
    current = page.locator('#primary-nav [aria-current="page"]')

    assert current.count() == 1
    assert current.get_attribute("href") == "/wiki/talents/"
    assert page.is_visible('#primary-nav .primary-nav-sub a[href="/wiki/armoury/"]')

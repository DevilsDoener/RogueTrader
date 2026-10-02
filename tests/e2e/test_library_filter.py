"""Playwright checks for the Bibliothek (``/wiki/``): the live card filter,
the "Weiterlesen" row and the filter-to-search hand-off
(``static/js/wiki-library.js``).

Runs against the real ``content/`` corpus (the ``real_corpus`` fixture in
``conftest.py``) so the filter is exercised on the chapters a reader sees.
"""
from __future__ import annotations

import json

import pytest

from .conftest import login_via_browser

pytestmark = pytest.mark.django_db(transaction=True)

CARD_TALENTS = '.library-card:has(a.library-card-title:text-is("Talents"))'
CARD_STARSHIPS = '.library-card:has(a.library-card-title:text-is("Starships"))'


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
        {"title": "Degrees of Success", "chapter": "Playing the Game", "url": "/wiki/playing-the-game/#sec-x", "ts": 3},
        {"title": "Evil", "chapter": "Elsewhere", "url": "https://example.com/wiki/", "ts": 2},
        # "/\host" is protocol-relative to a browser, despite the "/wiki/".
        {"title": "Sneaky", "chapter": "Elsewhere", "url": "/\\evil.example/wiki/", "ts": 2},
        {"title": "Talente", "chapter": "Talents", "url": "/wiki/talents/", "ts": 1},
    ]
    page.evaluate(
        "(value) => localStorage.setItem('rt-wiki-recent', value)", json.dumps(entries)
    )
    page.reload()
    page.wait_for_selector("#library-filter")

    assert page.is_visible(".library-recent")
    links = page.locator(".library-recent-card")
    assert links.count() == 2  # both off-site entries are dropped
    assert page.inner_text(".library-recent-title") == "Degrees of Success"
    assert page.get_attribute(".library-recent-card", "href") == "/wiki/playing-the-game/#sec-x"


def test_filtering_hides_bands_without_a_match_entirely(
    page, live_server, owner, real_corpus
):
    _open_library(page, live_server, owner)
    vorspann = '.library-band:has(h2:text-is("Front Matter"))'
    kapitel = '.library-band:has(h2:text-is("Chapters"))'
    anhang = '.library-band:has(h2:text-is("Appendix"))'
    assert page.is_visible(vorspann) and page.is_visible(kapitel) and page.is_visible(anhang)

    page.fill("#library-filter", "critical")

    assert page.is_visible(kapitel)
    assert not page.is_visible(vorspann)
    assert not page.is_visible(anhang)
    assert page.is_hidden(f"{vorspann} .library-band-heading")

    page.fill("#library-filter", "")

    assert page.is_visible(vorspann) and page.is_visible(anhang)


def test_a_level_two_match_is_shown_and_marked_inside_its_card(
    page, live_server, owner, real_corpus
):
    _open_library(page, live_server, owner)
    card = '.library-card:has(a.library-card-title:text-is("Playing the Game"))'
    sub_link = f'{card} .library-card-subsections a:text-is("Critical Damage")'
    # Unfiltered, the level-2 entries stay out of the way.
    page.click(f"{card} summary")
    assert page.locator(sub_link).count() == 1
    assert not page.is_visible(sub_link)
    page.click(f"{card} summary")

    page.fill("#library-filter", "critical")

    assert page.is_visible(sub_link)
    assert "is-match" in (page.get_attribute(sub_link, "class") or "")
    assert page.get_attribute(sub_link, "href") == "/wiki/playing-the-game/#sec-critical-damage"
    # Only matching level-2 entries appear, not their unmatched siblings.
    visible_subs = page.locator(f"{card} .library-card-subsections a:visible")
    assert visible_subs.count() >= 1
    for text in visible_subs.all_inner_texts():
        assert "critical" in text.casefold()

    page.fill("#library-filter", "")
    assert not page.is_visible(sub_link)


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

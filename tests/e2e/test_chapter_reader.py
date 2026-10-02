"""Playwright checks for the reading aids on a chapter page: scroll-spy,
outline filter, reading position, chapter tree and the search-term highlight
(``static/js/wiki-reader.js`` and ``static/js/wiki-highlight.js``).

Runs against the real ``content/`` corpus (the ``real_corpus`` fixture in
``conftest.py``).
"""
from __future__ import annotations

import json
import re

import pytest

from .conftest import login_via_browser

pytestmark = pytest.mark.django_db(transaction=True)

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


def test_the_outline_filter_shows_a_focus_ring(page, live_server, owner, real_corpus):
    _open_chapter(page, live_server, owner, "/wiki/playing-the-game/")
    shadow = "getComputedStyle(document.querySelector('.wiki-toc-filter')).boxShadow"
    unfocused = page.evaluate(shadow)

    page.focus(".wiki-toc-filter")
    page.wait_for_timeout(250)  # past the box-shadow transition
    focused = page.evaluate(shadow)

    # One extra shadow layer: the 3px ring, laid over the two mask shadows.
    assert focused != unfocused
    assert focused.count("rgb") == unfocused.count("rgb") + 1
    assert "0px 0px 0px 3px" in focused


def test_a_search_query_highlights_the_chapter_until_removed(
    page, live_server, owner, real_corpus
):
    _open_chapter(page, live_server, owner, "/wiki/armoury/?q=Waffe")
    page.wait_for_selector("mark.wiki-hit")
    # The status bar is inserted empty and filled a frame later.
    page.wait_for_selector(".wiki-hit-bar button")

    assert page.locator("mark.wiki-hit").count() >= 1
    assert page.is_visible(".wiki-hit-bar")
    assert re.fullmatch(r"\d+ Stellen markiert", page.inner_text(".wiki-hit-count"))

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
    assert isinstance(stored[0]["ts"], int)
    assert stored[0]["ts"] > 0
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


def test_a_single_hit_is_counted_in_the_singular(page, live_server, owner, real_corpus):
    _open_chapter(page, live_server, owner, "/wiki/foreword/?q=dystopian")
    page.wait_for_selector(".wiki-hit-bar button")

    assert page.locator("mark.wiki-hit").count() == 1
    assert page.inner_text(".wiki-hit-count") == "1 Stelle markiert"


def test_markup_in_the_query_is_never_injected(page, live_server, owner, real_corpus):
    _open_chapter(
        page, live_server, owner, "/wiki/armoury/?q=%3Cimg%20src%3Dx%20onerror%3Dalert(1)%3E"
    )

    assert page.locator("img[src='x']").count() == 0
    assert page.locator("[onerror]").count() == 0
    terms = json.loads(page.inner_text("#wiki-highlight-terms"))
    assert terms and all(re.fullmatch(r"\w+", term) for term in terms)
    # Whatever got marked is plain text from the book.
    assert page.locator("mark.wiki-hit *").count() == 0


def test_an_instant_jump_past_many_sections_updates_the_outline(
    page, live_server, owner, real_corpus
):
    """No heading is left inside the old observer band after this jump, so
    only a per-frame re-evaluation catches it (scrollbar drag, Home/End,
    find-in-page)."""
    _open_chapter(page, live_server, owner, "/wiki/playing-the-game/")
    page.evaluate(
        """() => {
            const heading = document.querySelector('#sec-healing > h2');
            const top = heading.getBoundingClientRect().top + window.scrollY;
            window.scrollTo({ top: top - 40, behavior: 'instant' });
        }"""
    )

    page.wait_for_selector(f'{HEALING_LINK}[aria-current="location"]')
    assert page.locator('.wiki-section-nav [aria-current="location"]').count() == 1

    page.evaluate("window.scrollTo({ top: 0, behavior: 'instant' })")
    page.wait_for_function(
        "!document.querySelector('.wiki-section-nav [aria-current=\"location\"]')"
    )


def test_a_targeted_section_keeps_its_gold_rule_clear_of_the_text(
    page, live_server, owner, real_corpus
):
    _open_chapter(page, live_server, owner, "/wiki/playing-the-game/#sec-the-attack")
    gap = page.evaluate(
        """() => {
            const section = document.getElementById('sec-the-attack');
            const paragraph = section.querySelector(':scope > p');
            const range = document.createRange();
            range.selectNodeContents(paragraph);
            return range.getClientRects()[0].left - section.getBoundingClientRect().left;
        }"""
    )
    assert page.evaluate(
        "getComputedStyle(document.getElementById('sec-the-attack')).boxShadow"
    ) != "none"
    assert gap >= 4

"""Playwright checks for the Auspex command palette (``static/js/auspex.js``):
opening, keyboard navigation, focus handling, suggestions, the empty state
with recent reading, and the failure paths.

Runs against the real ``content/`` corpus (the ``real_corpus`` fixture in
``conftest.py``).
"""
from __future__ import annotations

import json
import re

import pytest

from .conftest import login_via_browser

pytestmark = pytest.mark.django_db(transaction=True)

PALETTE_OPEN = "#auspex[open]"
PALETTE_CLOSED = "#auspex:not([open])"
PALETTE_INPUT = "#auspex .auspex-input"


def _open_library(page, live_server, owner):
    login_via_browser(page, live_server, username=owner.username)
    page.goto(f"{live_server.url}/wiki/")
    page.wait_for_selector("#library-filter")


def _open_dashboard(page, live_server, owner):
    login_via_browser(page, live_server, username=owner.username)
    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(f"{live_server.url}/dashboard/")
    page.wait_for_selector("#topbar-search-input")


def test_ctrl_k_opens_the_palette_and_arrow_enter_follows_a_suggestion(
    page, live_server, owner, real_corpus
):
    _open_dashboard(page, live_server, owner)
    assert page.is_visible(".topbar-search-kbd")
    assert page.locator(PALETTE_OPEN).count() == 0

    page.keyboard.press("Control+k")
    page.wait_for_selector(PALETTE_OPEN)
    assert page.evaluate("document.activeElement.classList.contains('auspex-input')")
    # The focused field is marked by a focus-coloured rule under its row.
    assert page.evaluate(
        "getComputedStyle(document.querySelector('.auspex-input-row')).boxShadow"
    ) != "none"

    page.keyboard.type("hit locations")
    option = page.locator(
        '#auspex .auspex-option:has(.auspex-option-title:has-text("Hit Locations"))'
    ).first
    option.wait_for()
    assert page.get_attribute(PALETTE_INPUT, "aria-expanded") == "true"
    assert page.locator("#auspex .auspex-group").first.inner_text().lower() == "abschnitte"
    assert "?q=hit%20locations" in page.get_attribute("#auspex .auspex-all", "href")
    # Snippets carry the server's <mark> and nothing else.
    assert page.locator("#auspex .auspex-option-snippet mark").count() >= 1
    assert page.locator("#auspex .auspex-option-snippet *:not(mark)").count() == 0

    page.keyboard.press("ArrowDown")
    first = page.locator("#auspex .auspex-option").first
    assert first.get_attribute("aria-selected") == "true"
    assert page.get_attribute(PALETTE_INPUT, "aria-activedescendant") == first.get_attribute("id")

    page.keyboard.press("Enter")
    page.wait_for_url(re.compile(r".*/wiki/playing-the-game/.*"))
    page.wait_for_selector(".wiki-article")
    assert page.locator(PALETTE_OPEN).count() == 0


def test_arrow_keys_wrap_and_ids_stay_unique(page, live_server, owner, real_corpus):
    _open_dashboard(page, live_server, owner)
    page.keyboard.press("Control+k")
    page.fill(PALETTE_INPUT, "hit locations")
    page.locator("#auspex .auspex-option").first.wait_for()
    options = page.locator("#auspex .auspex-option")
    count = options.count()
    ids = [options.nth(i).get_attribute("id") for i in range(count)]
    assert len(set(ids)) == count

    page.keyboard.press("ArrowUp")  # from nothing: wraps to the last option
    assert page.get_attribute(PALETTE_INPUT, "aria-activedescendant") == ids[-1]
    page.keyboard.press("ArrowDown")  # and back round to the first
    assert page.get_attribute(PALETTE_INPUT, "aria-activedescendant") == ids[0]
    assert page.locator('#auspex [aria-selected="true"]').count() == 1

    # Typing on drops the active option: it belonged to the previous query.
    page.keyboard.type("x")
    assert page.get_attribute(PALETTE_INPUT, "aria-activedescendant") is None


def test_slash_opens_the_palette_only_outside_text_fields(
    page, live_server, owner, real_corpus
):
    _open_library(page, live_server, owner)

    page.focus("#library-filter")
    page.keyboard.press("/")
    assert page.input_value("#library-filter") == "/"
    assert page.locator(PALETTE_OPEN).count() == 0

    page.evaluate("document.activeElement.blur()")
    page.keyboard.press("/")
    page.wait_for_selector(PALETTE_OPEN)
    assert page.input_value(PALETTE_INPUT) == ""  # the "/" itself is not typed

    page.keyboard.type("talent")
    page.keyboard.press("Escape")
    page.wait_for_selector(PALETTE_CLOSED, state="attached")
    assert page.input_value("#library-filter") == "/"


def test_escape_returns_focus_to_where_the_reader_was(
    page, live_server, owner, real_corpus
):
    _open_dashboard(page, live_server, owner)
    page.focus('#primary-nav a[href="/wiki/"]')

    page.keyboard.press("Control+k")
    page.wait_for_selector(PALETTE_OPEN)
    page.keyboard.press("Escape")
    page.wait_for_selector(PALETTE_CLOSED, state="attached")

    assert page.evaluate("document.activeElement.getAttribute('href')") == "/wiki/"


def test_the_topbar_field_opens_the_palette_without_looping(
    page, live_server, owner, real_corpus
):
    login_via_browser(page, live_server, username=owner.username)
    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(f"{live_server.url}/wiki/armoury/?q=Waffe")
    page.wait_for_selector(".wiki-article")

    page.click("#topbar-search-input")
    page.wait_for_selector(PALETTE_OPEN)
    assert page.input_value(PALETTE_INPUT) == "Waffe"
    assert page.evaluate("document.activeElement.classList.contains('auspex-input')")

    page.keyboard.press("Escape")
    page.wait_for_selector(PALETTE_CLOSED, state="attached")
    # Let any focus bounce settle (two frames) before checking it stayed shut.
    page.evaluate("() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))")
    assert page.locator(PALETTE_OPEN).count() == 0
    # Focus returns to the field that opened it, and that does not reopen it.
    assert page.evaluate("document.activeElement.id") == "topbar-search-input"

    # A click on the backdrop closes it too.
    page.keyboard.press("Control+k")
    page.wait_for_selector(PALETTE_OPEN)
    page.mouse.click(20, 880)
    page.wait_for_selector(PALETTE_CLOSED, state="attached")


def test_tabbing_through_the_topbar_field_leaves_the_palette_closed(
    page, live_server, owner, real_corpus
):
    _open_dashboard(page, live_server, owner)
    page.focus(".topbar .brand")

    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.id") == "topbar-search-input"
    page.evaluate("() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))")
    assert page.locator(PALETTE_OPEN).count() == 0

    # Tab passes on through the header: no dialog grabbed the focus.
    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.matches('.topbar-search button')")
    assert page.locator(PALETTE_OPEN).count() == 0


def test_typing_into_the_topbar_field_opens_the_palette_with_that_letter(
    page, live_server, owner, real_corpus
):
    _open_dashboard(page, live_server, owner)
    page.focus(".topbar .brand")
    page.keyboard.press("Tab")
    assert page.locator(PALETTE_OPEN).count() == 0

    page.keyboard.press("h")
    page.wait_for_selector(PALETTE_OPEN)
    assert page.evaluate("document.activeElement.classList.contains('auspex-input')")
    assert page.input_value(PALETTE_INPUT) == "h"
    assert page.input_value("#topbar-search-input") == ""

    # The caret sits after the carried letter, so typing simply continues.
    page.keyboard.type("it locations")
    assert page.input_value(PALETTE_INPUT) == "hit locations"
    page.locator("#auspex .auspex-option").first.wait_for()


def test_palette_groups_are_named_by_their_headings(
    page, live_server, owner, real_corpus
):
    _open_dashboard(page, live_server, owner)
    page.keyboard.press("Control+k")
    page.fill(PALETTE_INPUT, "hit locations")
    page.locator("#auspex .auspex-option").first.wait_for()

    groups = page.locator("#auspex [role=listbox] > [role=group]")
    assert groups.count() >= 1
    for index in range(groups.count()):
        group = groups.nth(index)
        heading_id = group.get_attribute("aria-labelledby")
        assert heading_id
        heading = page.locator(f"#{heading_id}")
        assert heading.count() == 1
        assert heading.inner_text().strip()
        assert group.locator("[role=option]").count() >= 1
    # Every option sits in a group; none is left directly in the listbox.
    assert page.locator("#auspex [role=listbox] > [role=option]").count() == 0
    assert page.get_attribute(PALETTE_INPUT, "aria-label") == "Regelwerk durchsuchen"


def test_the_empty_palette_lists_recent_reading(page, live_server, owner, real_corpus):
    _open_dashboard(page, live_server, owner)
    page.keyboard.press("Control+k")
    page.wait_for_selector(PALETTE_OPEN)
    # The note is a live region beside the listbox, not inside it.
    assert "Tippe, um Kapitel" in page.inner_text('#auspex .auspex-note[role="status"]')
    assert page.locator("#auspex [role=listbox] .auspex-note").count() == 0
    assert page.get_attribute(PALETTE_INPUT, "aria-expanded") == "false"

    entries = [
        {
            "title": "Healing",
            "chapter": "Playing the Game",
            "url": "/wiki/playing-the-game/#sec-healing",
            "ts": 3,
        },
        {"title": "Evil", "chapter": "Elsewhere", "url": "https://example.com/wiki/", "ts": 2},
        {"title": "Sneaky", "chapter": "Elsewhere", "url": "/\\evil.example/wiki/", "ts": 1},
    ]
    page.evaluate(
        "(value) => localStorage.setItem('rt-wiki-recent', value)", json.dumps(entries)
    )
    page.reload()
    page.wait_for_selector("#topbar-search-input")
    page.keyboard.press("Control+k")
    page.wait_for_selector(PALETTE_OPEN)

    assert page.inner_text("#auspex .auspex-group").lower() == "zuletzt gelesen"
    options = page.locator("#auspex .auspex-option")
    assert options.count() == 1  # both off-site entries are dropped
    assert options.first.get_attribute("href") == "/wiki/playing-the-game/#sec-healing"
    assert page.is_hidden("#auspex .auspex-note")
    assert page.inner_text("#auspex .auspex-option-title") == "Healing"

    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    page.wait_for_url(re.compile(r".*/wiki/playing-the-game/#sec-healing$"))


def test_enter_without_a_choice_searches_the_full_text(
    page, live_server, owner, real_corpus
):
    _open_dashboard(page, live_server, owner)
    page.keyboard.press("Control+k")
    page.fill(PALETTE_INPUT, "qqzzxxyy")
    page.wait_for_selector("#auspex .auspex-note:has-text('Keine Vorschläge')")

    page.keyboard.press("Enter")
    page.wait_for_url("**/search/?q=qqzzxxyy")


def test_a_failing_suggest_request_keeps_enter_working(
    page, live_server, owner, real_corpus
):
    _open_dashboard(page, live_server, owner)
    page.route(
        "**/search/suggest/**", lambda route: route.fulfill(status=500, body="boom")
    )
    page.keyboard.press("Control+k")
    page.fill(PALETTE_INPUT, "talent")
    page.wait_for_selector("#auspex .auspex-note.is-error:has-text('Auspex gestört')")
    assert page.locator("#auspex .auspex-input-row.is-scanning").count() == 0

    page.keyboard.press("Enter")
    page.wait_for_url("**/search/?q=talent")


def test_suggestions_only_link_to_wiki_and_search_pages(
    page, live_server, owner, real_corpus
):
    _open_dashboard(page, live_server, owner)
    payload = {
        "query": "talent",
        "chapters": [
            {
                "title": "Proto",
                "short_title": "Proto",
                "numeral": "",
                "url": "//evil.example/wiki/",
            },
            {
                "title": "Slash",
                "short_title": "Slash",
                "numeral": "",
                "url": "/\\evil.example/wiki/",
            },
        ],
        "sections": [
            {
                "title": "Script",
                "chapter": "X",
                "numeral": "",
                "path": [],
                "url": "javascript:alert(1)",
            },
            {
                "title": "Talents",
                "chapter": "Talents",
                "numeral": "IV",
                "path": [],
                "url": "/wiki/talents/",
            },
        ],
        "hits": [
            {"title": "Absolute", "chapter": "X", "numeral": "", "path": [], "snippet_html": "x",
             "url": "https://evil.example/wiki/"},
            {"title": "Search", "chapter": "X", "numeral": "", "path": [], "snippet_html": "x",
             "url": "/search/?q=talent"},
        ],
    }
    page.route(
        "**/search/suggest/**",
        lambda route: route.fulfill(
            status=200, content_type="application/json", body=json.dumps(payload)
        ),
    )
    page.keyboard.press("Control+k")
    page.fill(PALETTE_INPUT, "talent")
    page.locator("#auspex .auspex-option").first.wait_for()

    hrefs = page.eval_on_selector_all(
        "#auspex .auspex-option", "els => els.map((el) => el.getAttribute('href'))"
    )
    assert hrefs == ["/wiki/talents/", "/search/?q=talent"]


def test_typing_in_the_dashboard_search_does_not_open_the_palette(
    page, live_server, owner, real_corpus
):
    _open_dashboard(page, live_server, owner)
    page.click("#dashboard-search-input")
    page.keyboard.type("a/b")

    assert page.input_value("#dashboard-search-input") == "a/b"
    assert page.locator(PALETTE_OPEN).count() == 0


def test_a_lone_surrogate_in_the_query_does_not_break_the_palette(
    page, live_server, owner, real_corpus
):
    """A half-pasted emoji made encodeURIComponent throw and froze the palette."""
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    _open_dashboard(page, live_server, owner)
    page.keyboard.press("Control+k")
    page.wait_for_selector(PALETTE_OPEN)

    page.evaluate(
        """() => {
            const input = document.querySelector('#auspex .auspex-input');
            input.value = 'hit loc\ud83d';
            input.dispatchEvent(new Event('input', { bubbles: true }));
        }"""
    )
    page.fill(PALETTE_INPUT, "hit locations")

    page.locator(
        '#auspex .auspex-option:has(.auspex-option-title:has-text("Hit Locations"))'
    ).first.wait_for()
    assert errors == []

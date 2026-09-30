"""Playwright checks for the wiki navigation: the Bibliothek (index) page and
the reading aids on a chapter page (scroll-spy, outline filter, highlight).

Runs against the real ``content/`` corpus so the live filter is exercised on
the chapters a reader actually sees.
"""
from __future__ import annotations

import json
import re

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


# ---- Auspex command palette (static/js/auspex.js) --------------------------

PALETTE_OPEN = "#auspex[open]"
PALETTE_CLOSED = "#auspex:not([open])"
PALETTE_INPUT = "#auspex .auspex-input"


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
        {"title": "Healing", "chapter": "Playing the Game", "url": "/wiki/playing-the-game/#sec-healing", "ts": 3},
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
            {"title": "Proto", "short_title": "Proto", "numeral": "", "url": "//evil.example/wiki/"},
            {"title": "Slash", "short_title": "Slash", "numeral": "", "url": "/\\evil.example/wiki/"},
        ],
        "sections": [
            {"title": "Script", "chapter": "X", "numeral": "", "path": [], "url": "javascript:alert(1)"},
            {"title": "Talents", "chapter": "Talents", "numeral": "IV", "path": [], "url": "/wiki/talents/"},
        ],
        "hits": [
            {"title": "Absolute", "chapter": "X", "numeral": "", "path": [], "snippet_html": "x",
             "url": "https://evil.example/wiki/"},
            {"title": "Search", "chapter": "X", "numeral": "", "path": [], "snippet_html": "x",
             "url": "/search/?q=talent"},
        ],
        "search_url": "/search/?q=talent",
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

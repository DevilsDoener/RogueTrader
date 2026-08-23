"""Playwright checks for the shared shell's accessibility and responsive
behaviour (Task 9, Step 4): no page-level horizontal overflow at the three
required viewports, a working skip link, visible keyboard focus, and a
labelled, keyboard-operable navigation drawer below the 800px breakpoint.

The character sheet's own pan/zoom viewport (`.sheet-viewport`) is exempt
from the overflow check -- it may legitimately be wider than the visible
viewport since the user pans/zooms it; only the outer *document* must never
need horizontal scrolling.
"""
from __future__ import annotations

import pytest

from .conftest import login_via_browser

pytestmark = pytest.mark.django_db(transaction=True)

VIEWPORTS = [
    ("desktop", 1440, 900),
    ("tablet", 768, 1024),
    ("mobile", 390, 844),
]


def _assert_no_page_level_horizontal_overflow(page):
    overflow = page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow <= 1, f"page-level horizontal overflow of {overflow}px"


@pytest.mark.parametrize("name, width, height", VIEWPORTS)
def test_dashboard_has_no_horizontal_overflow(
    page, live_server, owner, character_factory, name, width, height
):
    character_factory(owner=owner, display_name="Lucian Voss")
    login_via_browser(page, live_server, username=owner.username)
    page.set_viewport_size({"width": width, "height": height})

    page.goto(f"{live_server.url}/dashboard/")
    page.wait_for_selector("#dashboard-heading")

    _assert_no_page_level_horizontal_overflow(page)


@pytest.mark.parametrize("name, width, height", VIEWPORTS)
def test_character_list_has_no_horizontal_overflow(
    page, live_server, owner, name, width, height
):
    login_via_browser(page, live_server, username=owner.username)
    page.set_viewport_size({"width": width, "height": height})

    page.goto(f"{live_server.url}/characters/")

    _assert_no_page_level_horizontal_overflow(page)


@pytest.mark.parametrize("name, width, height", VIEWPORTS)
def test_character_sheet_page_has_no_horizontal_overflow(
    page, live_server, owner, character_factory, name, width, height
):
    character = character_factory(owner=owner)
    login_via_browser(page, live_server, username=owner.username)
    page.set_viewport_size({"width": width, "height": height})

    page.goto(f"{live_server.url}/characters/{character.id}/")
    page.wait_for_selector('[data-field-id="c1_character_name"]')

    # The sheet viewport itself may need internal panning -- only the
    # surrounding document must never grow a horizontal scrollbar.
    _assert_no_page_level_horizontal_overflow(page)


def test_skip_link_moves_focus_to_main_content(page, live_server, owner):
    login_via_browser(page, live_server, username=owner.username)
    page.goto(f"{live_server.url}/dashboard/")

    page.keyboard.press("Tab")
    focused_href = page.evaluate("document.activeElement.getAttribute('href')")
    assert focused_href == "#main-content"

    page.keyboard.press("Enter")
    assert page.evaluate("document.activeElement.id") == "main-content"


def test_nav_drawer_toggle_is_labelled_and_toggles_aria_expanded(
    page, live_server, owner
):
    login_via_browser(page, live_server, username=owner.username)
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(f"{live_server.url}/dashboard/")

    toggle = page.locator("#nav-toggle")
    assert toggle.get_attribute("aria-label")
    assert toggle.get_attribute("aria-expanded") == "false"

    toggle.click()
    assert toggle.get_attribute("aria-expanded") == "true"
    assert page.locator("#primary-nav").is_visible()

    page.keyboard.press("Escape")
    assert toggle.get_attribute("aria-expanded") == "false"


def test_primary_nav_is_always_visible_on_desktop(page, live_server, owner):
    login_via_browser(page, live_server, username=owner.username)
    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(f"{live_server.url}/dashboard/")

    assert page.locator("#primary-nav").is_visible()
    assert not page.locator("#nav-toggle").is_visible()


def test_focused_nav_link_has_a_visible_focus_outline(page, live_server, owner):
    login_via_browser(page, live_server, username=owner.username)
    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(f"{live_server.url}/dashboard/")

    page.locator("#primary-nav a").first.focus()
    outline_style = page.evaluate(
        "getComputedStyle(document.activeElement).outlineStyle"
    )
    assert outline_style != "none"

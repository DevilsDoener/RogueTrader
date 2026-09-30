"""Playwright checks for the desktop shell's accessibility and layout."""
from __future__ import annotations

import pytest

from .conftest import (
    NAMED_DESKTOP_VIEWPORTS,
    VIEWPORT_WIDE,
    login_via_browser,
    open_character,
    open_ship,
)

pytestmark = pytest.mark.django_db(transaction=True)


def _assert_no_page_level_horizontal_overflow(page):
    overflow = page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow <= 1, f"page-level horizontal overflow of {overflow}px"


@pytest.mark.parametrize(("viewport_name", "viewport"), NAMED_DESKTOP_VIEWPORTS)
def test_dashboard_has_no_horizontal_overflow(
    page, live_server, owner, character_factory, viewport_name, viewport
):
    character_factory(owner=owner, display_name="Lucian Voss")
    login_via_browser(page, live_server, username=owner.username)
    page.set_viewport_size(viewport)

    page.goto(f"{live_server.url}/dashboard/")
    page.wait_for_selector("#dashboard-heading")

    _assert_no_page_level_horizontal_overflow(page)


@pytest.mark.parametrize(("viewport_name", "viewport"), NAMED_DESKTOP_VIEWPORTS)
def test_character_list_has_no_horizontal_overflow(
    page, live_server, owner, viewport_name, viewport
):
    login_via_browser(page, live_server, username=owner.username)
    page.set_viewport_size(viewport)

    page.goto(f"{live_server.url}/characters/")

    _assert_no_page_level_horizontal_overflow(page)


@pytest.mark.parametrize(("viewport_name", "viewport"), NAMED_DESKTOP_VIEWPORTS)
def test_character_sheet_page_has_no_horizontal_overflow(
    page, live_server, owner, character_factory, viewport_name, viewport
):
    page.set_viewport_size(viewport)
    open_character(page, live_server, owner, character_factory)

    _assert_no_page_level_horizontal_overflow(page)


@pytest.mark.parametrize(("viewport_name", "viewport"), NAMED_DESKTOP_VIEWPORTS)
def test_ship_sheet_page_has_no_horizontal_overflow(
    page, live_server, owner, ship_sheet, viewport_name, viewport
):
    page.set_viewport_size(viewport)
    open_ship(page, live_server, owner, ship_sheet)

    _assert_no_page_level_horizontal_overflow(page)


def test_skip_link_moves_focus_to_main_content(page, live_server, owner):
    login_via_browser(page, live_server, username=owner.username)
    page.goto(f"{live_server.url}/dashboard/")

    page.keyboard.press("Tab")
    focused_href = page.evaluate("document.activeElement.getAttribute('href')")
    assert focused_href == "#main-content"

    page.keyboard.press("Enter")
    assert page.evaluate("document.activeElement.id") == "main-content"


def test_primary_nav_is_permanently_visible_on_desktop(page, live_server, owner):
    login_via_browser(page, live_server, username=owner.username)
    page.set_viewport_size(VIEWPORT_WIDE)
    page.goto(f"{live_server.url}/dashboard/")

    assert page.locator("#primary-nav").is_visible()


def test_focused_nav_link_has_a_visible_focus_outline(page, live_server, owner):
    login_via_browser(page, live_server, username=owner.username)
    page.set_viewport_size(VIEWPORT_WIDE)
    page.goto(f"{live_server.url}/dashboard/")

    page.locator("#primary-nav a").first.focus()
    outline_style = page.evaluate(
        "getComputedStyle(document.activeElement).outlineStyle"
    )
    assert outline_style != "none"

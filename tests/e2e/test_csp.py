"""The portal under its Content-Security-Policy: zero violations on every main page.

``config.security_headers`` sends a strict policy (no inline script, no
external origin). Every e2e test therefore already runs under it; this file
visits the pages one by one *and* listens for ``securitypolicyviolation``
events and CSP console errors, so a blocked script, stylesheet, image or
fetch fails here with the page that caused it rather than as an unrelated
timeout elsewhere. It also pins that the header really is on the page the
browser receives.
"""
from __future__ import annotations

import pytest

from sheets.models import SheetChange

from .conftest import login_via_browser, wait_saved

pytestmark = pytest.mark.django_db(transaction=True)

_LISTENER = """
window.__cspViolations = [];
document.addEventListener('securitypolicyviolation', (event) => {
  window.__cspViolations.push(
    event.violatedDirective + ' blocked ' + (event.blockedURI || 'inline') +
    ' at ' + event.sourceFile + ':' + event.lineNumber
  );
});
"""


class _Watch:
    """Collects CSP violations (DOM event) and CSP/page errors (console)."""

    def __init__(self, page):
        self.page = page
        self.console = []
        page.add_init_script(_LISTENER)
        page.on("console", self._on_console)
        page.on("pageerror", lambda error: self.console.append(f"pageerror: {error}"))

    def _on_console(self, message):
        text = message.text
        if message.type == "error" and (
            "Content Security Policy" in text or "Refused to" in text or "violates" in text
        ):
            self.console.append(text)

    def assert_clean(self, where):
        # The event fires asynchronously after the blocked load: give it a tick.
        self.page.wait_for_timeout(150)
        violations = self.page.evaluate("window.__cspViolations || []")
        assert violations == [], f"{where}: {violations}"
        assert self.console == [], f"{where}: {self.console}"


@pytest.fixture
def watch(page):
    return _Watch(page)


def test_the_browser_receives_the_policy_with_the_login_page(page, live_server):
    response = page.goto(f"{live_server.url}/account/login/")

    policy = response.header_value("content-security-policy")
    assert "script-src 'self'" in policy
    assert "unsafe-inline" not in policy.split("style-src-attr")[0]
    assert response.header_value("permissions-policy").startswith("camera=()")


def test_login_and_dashboard_are_clean(page, live_server, owner, watch):
    page.goto(f"{live_server.url}/account/login/")
    page.wait_for_selector('input[name="username"]')
    watch.assert_clean("login")

    login_via_browser(page, live_server, username=owner.username)
    page.wait_for_selector("#topbar-search-input")
    watch.assert_clean("dashboard")


def test_library_chapter_and_search_are_clean(page, live_server, owner, real_corpus, watch):
    login_via_browser(page, live_server, username=owner.username)
    page.set_viewport_size({"width": 1440, "height": 900})

    page.goto(f"{live_server.url}/wiki/")
    page.wait_for_selector("#library-filter")
    page.fill("#library-filter", "psi")
    watch.assert_clean("library")

    chapter = page.evaluate(
        """() => [...document.querySelectorAll('a[href^="/wiki/"]')]
            .map((a) => a.getAttribute('href'))
            .find((href) => href !== '/wiki/' && /^\\/wiki\\/[^/]+\\/$/.test(href))"""
    )
    assert chapter, "the library lists no chapter"
    page.goto(f"{live_server.url}{chapter}")
    page.wait_for_selector(".wiki-article")
    watch.assert_clean("chapter")

    page.goto(f"{live_server.url}{chapter}?q=the")
    page.wait_for_selector(".wiki-article")
    page.wait_for_selector("mark")
    watch.assert_clean("chapter with ?q=")

    page.goto(f"{live_server.url}/search/?q=hit+locations")
    page.wait_for_selector("main")
    watch.assert_clean("search results")


def test_the_auspex_palette_is_clean(page, live_server, owner, real_corpus, watch):
    login_via_browser(page, live_server, username=owner.username)
    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(f"{live_server.url}/dashboard/")
    page.wait_for_selector("#topbar-search-input")

    page.keyboard.press("Control+k")
    page.wait_for_selector("#auspex[open]")
    watch.assert_clean("palette opened")
    page.keyboard.type("hit locations")
    page.wait_for_selector("#auspex .auspex-option")
    watch.assert_clean("palette with suggestions")
    page.keyboard.press("Escape")
    watch.assert_clean("palette closed")


def test_the_character_pages_are_clean(page, live_server, owner, character_factory, watch):
    character = character_factory(owner=owner)
    login_via_browser(page, live_server, username=owner.username)
    page.set_viewport_size({"width": 1440, "height": 900})

    page.goto(f"{live_server.url}/characters/")
    watch.assert_clean("character list")

    page.goto(f"{live_server.url}/characters/{character.id}/")
    page.wait_for_selector('[data-field-id="c1_character_name"]')
    watch.assert_clean("character sheet, first page")

    page.fill('[data-field-id="c1_character_name"]', "Kasimir")
    page.locator('[data-field-id="c1_character_name"]').blur()
    wait_saved(page)
    watch.assert_clean("character sheet after typing")

    second_field = page.locator('[data-field-id="c2_gear_22"]')
    second_field.scroll_into_view_if_needed()
    second_field.fill("Lasgun")
    second_field.blur()
    wait_saved(page)
    watch.assert_clean("character sheet, second page, after typing")


def test_the_ship_pages_are_clean(page, live_server, user_factory, ship_sheet, watch):
    user = user_factory()
    SheetChange.objects.create(
        ship=ship_sheet, actor=user, field_id="ship_name",
        old_value="alt", new_value="neu", resulting_version=1,
    )
    login_via_browser(page, live_server, username=user.username)
    page.set_viewport_size({"width": 1440, "height": 900})

    page.goto(f"{live_server.url}/ships/{ship_sheet.id}/")
    page.wait_for_selector('[data-field-id="ship_name"]')
    page.fill('[data-field-id="ship_name"]', "Sturmvogel")
    page.locator('[data-field-id="ship_name"]').blur()
    wait_saved(page)
    watch.assert_clean("ship sheet after typing")

    page.goto(f"{live_server.url}/ships/{ship_sheet.id}/history/")
    page.wait_for_selector("#ship-history-table")
    watch.assert_clean("ship history")
    page.locator(".ship-history-expand").first.click()
    page.wait_for_function("document.querySelector('#ship-history-table dl') !== null")
    watch.assert_clean("ship history detail")


def test_the_account_admin_pages_are_clean(
    page, live_server, portal_admin, other_user, character_factory, watch
):
    character = character_factory(owner=other_user)
    login_via_browser(page, live_server, username=portal_admin.username)
    page.set_viewport_size({"width": 1440, "height": 900})

    for path in (
        "/portal-admin/accounts/",
        "/portal-admin/accounts/create/",
        f"/portal-admin/accounts/{other_user.pk}/edit/",
        f"/portal-admin/accounts/{other_user.pk}/reset-password/",
        f"/portal-admin/characters/{character.id}/",
    ):
        page.goto(f"{live_server.url}{path}")
        page.wait_for_load_state("networkidle")
        watch.assert_clean(path)


def test_the_forced_password_change_page_is_clean(page, live_server, user_factory, watch):
    user = user_factory(must_change_password=True)
    login_via_browser(page, live_server, username=user.username)

    assert "/account/change-required/" in page.url
    watch.assert_clean("forced password change")


def test_an_injected_inline_script_is_blocked_and_the_watch_sees_it(page, live_server, watch):
    """Negative control: without it a silent watcher would pass everything."""
    page.goto(f"{live_server.url}/account/login/")
    page.evaluate(
        """() => {
          const script = document.createElement('script');
          script.textContent = 'window.__injected = true';
          document.body.appendChild(script);
        }"""
    )
    page.wait_for_timeout(150)

    assert page.evaluate("window.__injected") is None
    assert any("script-src" in entry for entry in page.evaluate("window.__cspViolations"))

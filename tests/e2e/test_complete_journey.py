"""Task 11, Step 1: a single real end-to-end acceptance journey.

This drives the whole portal the way a game group would actually use it,
through real (headless) browser sessions against a real HTTP server
(pytest-django's ``live_server``) -- see ``tests/e2e/conftest.py`` for why
the fixtures below use ``transactional_db``/``django_db(transaction=True)``
instead of the default ``db``.

Covered in one continuous flow, matching the Task 11 brief:
  1. Bootstrap the initial portal admin via the real management command.
  2. As that admin, create two managed users with temporary passwords.
  3. Force both users through the mandatory first-login password change.
  4. Create multiple private characters as each user.
  5. Verify the two owners cannot see each other's characters.
  6. Verify the admin has read-only visibility across both owners, and
     cannot mutate or delete a character it doesn't own.
  7. Edit different shared-ship fields from both accounts and see them
     merge.
  8. Provoke a real same-field conflict between the two accounts and
     resolve it by resubmitting the loser's value.
  9. Search the wiki and open a matched section.
 10. Simulate an application restart.
 11. Verify every accepted value -- accounts, characters, ship fields, the
     conflict's outcome, and wiki content -- survived that "restart".

What "restart the app" means here
----------------------------------
A real ``docker compose restart`` isn't reachable from inside a single
pytest process that already has Django loaded and a live HTTP server
thread running. What *is* checked, faithfully, is every reason a restart
could plausibly break this app:

* Nothing may be cached only in the browser: after step 9 we clear the
  browser context's cookies *and* ``localStorage`` on both sessions --
  this destroys the Django session id, the "must change password" bypass,
  and the sheet viewer's remembered page/zoom -- and log back in from
  scratch, exactly as a returning user would after a server bounce.
* Nothing may be cached only in the wiki app's process-wide singleton: we
  explicitly rebuild ``wiki.content.WikiRepository`` from disk again (the
  exact call ``WikiConfig.ready()`` makes on a fresh process boot) and
  swap it in, rather than continuing to reuse the one already parsed
  earlier in this test process.
* Everything else the journey depends on (accounts, character/ship field
  values, field versions, audit history) only ever lives in the SQLite
  database, which is what a real restart leaves untouched -- so re-reading
  it through fresh, unauthenticated browser sessions is precisely the
  right check.
"""
from __future__ import annotations

import uuid

import pytest
from django.core.management import call_command

from wiki.content import WikiRepository, get_repository, set_repository_for_tests

from .conftest import login_via_browser

pytestmark = pytest.mark.django_db(transaction=True)

# None of these resemble the (randomly-suffixed) usernames they're paired
# with -- Django's UserAttributeSimilarityValidator would otherwise reject
# a password that overlaps too much with the username it belongs to.
ADMIN_PASSWORD = "Voidship-Anchor-77!"
USER_A_TEMP_PASSWORD = "Quarantine-Berth-01!"
USER_B_TEMP_PASSWORD = "Quarantine-Berth-02!"
USER_A_NEW_PASSWORD = "Starfall-Cinder-93!"
USER_B_NEW_PASSWORD = "Starfall-Ember-64!"

WIKI_SEARCH_TERM = "Explorer"
WIKI_CHAPTER_FILE = "01-Charaktererschaffung.md"


def _wait_saved(page):
    page.wait_for_function(
        "document.getElementById('sheet-save-status').textContent === 'Gespeichert'",
        timeout=5000,
    )


def _force_password_change(page, *, old_password: str, new_password: str):
    """Fill and submit the mandatory first-login password change form.

    The user is expected to already be mid-login (the previous POST to
    /account/login/ redirected through the ForcePasswordChangeMiddleware to
    /account/change-required/).
    """
    page.wait_for_url("**/account/change-required/")
    page.fill('input[name="old_password"]', old_password)
    page.fill('input[name="new_password1"]', new_password)
    page.fill('input[name="new_password2"]', new_password)
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")


def _create_managed_user_via_admin_ui(page, live_server, *, username: str, temporary_password: str):
    page.goto(f"{live_server.url}/portal-admin/accounts/create/")
    page.fill('input[name="username"]', username)
    page.fill('input[name="temporary_password"]', temporary_password)
    # Scoped to the form card: a bare 'button[type="submit"]' would also
    # match base.html's always-present topbar search/logout buttons on any
    # authenticated page, and (being first in DOM order) that one wins.
    page.click('.form-card button[type="submit"]')
    # No trailing "**": the create page's own URL
    # (".../portal-admin/accounts/create/") must NOT satisfy this pattern,
    # or wait_for_url would return immediately without waiting for the
    # POST's redirect back to the list page to actually happen.
    page.wait_for_url("**/portal-admin/accounts/")


def _create_character_via_ui(page, live_server, *, display_name: str) -> str:
    """Creates a character through the real owner-facing form and returns
    its detail-page URL (the create view redirects straight there)."""
    page.goto(f"{live_server.url}/characters/")
    page.fill('#create-character input[name="display_name"]', display_name)
    page.click('#create-character button[type="submit"]')
    page.wait_for_url("**/characters/*/")
    return page.url


def _set_text_field(page, field_id: str, value: str):
    field = page.locator(f'[data-field-id="{field_id}"]')
    field.fill(value)
    field.blur()
    _wait_saved(page)


def _logout_via_post(page):
    """POST /account/logout/ for real (it's POST-only, see accounts/urls.py)
    so the session is actually torn down before the next login."""
    csrf_token = page.evaluate("document.cookie.match(/csrftoken=([^;]+)/)[1]")
    page.evaluate(
        """(csrftoken) => {
            const form = document.createElement('form');
            form.method = 'POST';
            form.action = '/account/logout/';
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = 'csrfmiddlewaretoken';
            input.value = csrftoken;
            form.appendChild(input);
            document.body.appendChild(form);
            form.submit();
        }""",
        csrf_token,
    )
    page.wait_for_load_state("networkidle")


def test_complete_portal_journey(page, second_page, live_server, settings, ship_sheet):
    # ---- Preserve/override the wiki content repository around this test.
    # WikiConfig.ready() already ran once at process start against whatever
    # WIKI_CONTENT_ROOT was set to then (normally unset/missing locally),
    # so the live repository singleton has zero chapters until we point it
    # at this checkout's real Markdown source and reload it -- the same
    # thing a production container does by mounting the book read-only and
    # letting WikiConfig.ready() parse it on boot.
    original_repository = get_repository()
    settings.WIKI_CONTENT_ROOT = settings.BASE_DIR / "content"
    settings.WIKI_CONTENT_ALLOWLIST = [WIKI_CHAPTER_FILE]
    set_repository_for_tests(WikiRepository.load())

    try:
        _run_journey(page, second_page, live_server, ship_sheet)
    finally:
        set_repository_for_tests(original_repository)


def _run_journey(page, second_page, live_server, ship_sheet):
    suffix = uuid.uuid4().hex[:8]
    admin_username = f"gm-{suffix}"
    user_a_username = f"anna-{suffix}"
    user_b_username = f"bruno-{suffix}"

    # ---- Step 1: bootstrap the initial portal admin via the real command.
    call_command("bootstrap_admin", username=admin_username, password=ADMIN_PASSWORD)

    # ---- Step 2: admin creates two managed users with temporary passwords.
    login_via_browser(page, live_server, username=admin_username, password=ADMIN_PASSWORD)
    _create_managed_user_via_admin_ui(
        page, live_server, username=user_a_username, temporary_password=USER_A_TEMP_PASSWORD
    )
    _create_managed_user_via_admin_ui(
        page, live_server, username=user_b_username, temporary_password=USER_B_TEMP_PASSWORD
    )
    listing = page.content()
    assert user_a_username in listing
    assert user_b_username in listing

    _logout_via_post(page)

    # ---- Step 3: both users are forced through their first-login password change.
    login_via_browser(page, live_server, username=user_a_username, password=USER_A_TEMP_PASSWORD)
    _force_password_change(page, old_password=USER_A_TEMP_PASSWORD, new_password=USER_A_NEW_PASSWORD)
    assert "/dashboard/" in page.url

    login_via_browser(second_page, live_server, username=user_b_username, password=USER_B_TEMP_PASSWORD)
    _force_password_change(second_page, old_password=USER_B_TEMP_PASSWORD, new_password=USER_B_NEW_PASSWORD)
    assert "/dashboard/" in second_page.url

    # ---- Step 4: each user creates multiple private characters.
    user_a_char1_url = _create_character_via_ui(page, live_server, display_name="Lucian Voss")
    page.wait_for_selector('[data-field-id="c1_character_name"]')
    _set_text_field(page, "c1_character_name", "Lucian Voss, Rogue Trader")
    _create_character_via_ui(page, live_server, display_name="Second Explorer")

    user_b_char1_url = _create_character_via_ui(second_page, live_server, display_name="Brother Bruno")
    second_page.wait_for_selector('[data-field-id="c1_character_name"]')
    _set_text_field(second_page, "c1_character_name", "Brother Bruno, Missionary")

    # ---- Step 5: mutual invisibility between the two owners.
    page.goto(f"{live_server.url}/characters/")
    own_list_html = page.content()
    assert "Lucian Voss" in own_list_html
    assert "Second Explorer" in own_list_html
    assert "Brother Bruno" not in own_list_html

    foreign_response = page.goto(user_b_char1_url)
    assert foreign_response.status == 404

    second_page.goto(f"{live_server.url}/characters/")
    other_list_html = second_page.content()
    assert "Brother Bruno" in other_list_html
    assert "Lucian Voss" not in other_list_html

    foreign_response_b = second_page.goto(user_a_char1_url)
    assert foreign_response_b.status == 404

    # ---- Step 6: admin read-only visibility, with no mutate/delete access.
    # `page` is reused for the admin here rather than opening a third
    # browser context -- user A's edits above are already saved server-side
    # (SQLite), so nothing is lost by swapping this context's login.
    _logout_via_post(page)
    login_via_browser(page, live_server, username=admin_username, password=ADMIN_PASSWORD)

    page.goto(f"{live_server.url}/portal-admin/characters/")
    admin_list_html = page.content()
    assert user_a_username in admin_list_html and "Lucian Voss" in admin_list_html
    assert user_b_username in admin_list_html and "Brother Bruno" in admin_list_html

    admin_detail_url = user_a_char1_url.replace("/characters/", "/portal-admin/characters/")
    page.goto(admin_detail_url)
    page.wait_for_selector('[data-field-id="c1_character_name"]')
    assert page.input_value('[data-field-id="c1_character_name"]') == "Lucian Voss, Rogue Trader"
    assert page.locator('[data-field-id="c1_character_name"]').is_disabled()

    # The admin's owner-scoped GET on someone else's delete-confirmation URL
    # must be indistinguishable from the character not existing.
    admin_delete_attempt = page.goto(f"{user_a_char1_url}delete/")
    assert admin_delete_attempt.status == 404

    # Log the admin back out so user A can resume its own session below.
    _logout_via_post(page)
    login_via_browser(page, live_server, username=user_a_username, password=USER_A_NEW_PASSWORD)

    # ---- Step 7: both accounts edit the shared ship, on different fields.
    # Navigate via the real "/ship/" redirect route (not a direct ship UUID
    # URL) so this journey actually exercises the redirect a real user
    # follows -- ship_sheet is the migration-seeded ship (see
    # tests/e2e/conftest.py), the same single active ship a production
    # deployment has, so the redirect always resolves to it unambiguously.
    page.goto(f"{live_server.url}/ship/")
    page.wait_for_selector('[data-field-id="ship_name"]')
    ship_url = page.url
    assert ship_url == f"{live_server.url}/ships/{ship_sheet.id}/"
    second_page.goto(f"{live_server.url}/ship/")
    second_page.wait_for_selector('[data-field-id="ship_speed"]')

    _set_text_field(page, "ship_name", "Rosinante")
    _set_text_field(second_page, "ship_speed", "7")

    page.reload()
    page.wait_for_selector('[data-field-id="ship_name"]')
    assert page.input_value('[data-field-id="ship_name"]') == "Rosinante"
    assert page.input_value('[data-field-id="ship_speed"]') == "7"

    # ---- Step 8: provoke and resolve a real same-field conflict.
    # Neither browser has touched ship_class yet, so both still hold
    # base_version 0 for it -- exactly the race a real two-player edit
    # would produce.
    class_field_a = page.locator('[data-field-id="ship_class"]')
    class_field_a.fill("Frigate")
    class_field_a.blur()
    _wait_saved(page)

    class_field_b = second_page.locator('[data-field-id="ship_class"]')
    class_field_b.fill("Cruiser")
    class_field_b.blur()

    panel = second_page.locator(".sheet-conflict-panel")
    panel.wait_for(timeout=5000)
    retry_button = panel.locator("text=Meinen Wert erneut speichern")
    assert retry_button.count() == 1
    retry_button.click()
    _wait_saved(second_page)
    assert second_page.input_value('[data-field-id="ship_class"]') == "Cruiser"

    page.reload()
    page.wait_for_selector('[data-field-id="ship_class"]')
    assert page.input_value('[data-field-id="ship_class"]') == "Cruiser"

    # ---- Step 9: search the wiki and open the matched section.
    page.goto(f"{live_server.url}/dashboard/")
    page.fill("#dashboard-search-input", WIKI_SEARCH_TERM)
    page.click(".dashboard-search button[type='submit']")
    page.wait_for_selector(".wiki-results")
    result_link = page.locator(".wiki-results li a").first
    assert result_link.count() == 1
    result_link.click()
    page.wait_for_load_state("networkidle")
    assert "charaktererschaffung" in page.url
    assert "Character Creation" in page.content()

    # ---- Step 10: simulate an application restart (see module docstring).
    set_repository_for_tests(WikiRepository.load())
    for context_page in (page, second_page):
        context_page.context.clear_cookies()
        context_page.evaluate("() => { localStorage.clear(); }")

    # ---- Step 11: verify every accepted value survived the "restart".
    login_via_browser(page, live_server, username=user_a_username, password=USER_A_NEW_PASSWORD)
    page.goto(f"{live_server.url}/characters/")
    assert "Lucian Voss" in page.content()
    assert "Second Explorer" in page.content()

    page.goto(user_a_char1_url)
    page.wait_for_selector('[data-field-id="c1_character_name"]')
    assert page.input_value('[data-field-id="c1_character_name"]') == "Lucian Voss, Rogue Trader"

    login_via_browser(second_page, live_server, username=user_b_username, password=USER_B_NEW_PASSWORD)
    second_page.goto(f"{live_server.url}/characters/")
    assert "Brother Bruno" in second_page.content()

    second_page.goto(user_b_char1_url)
    second_page.wait_for_selector('[data-field-id="c1_character_name"]')
    assert second_page.input_value('[data-field-id="c1_character_name"]') == "Brother Bruno, Missionary"

    page.goto(ship_url)
    page.wait_for_selector('[data-field-id="ship_name"]')
    assert page.input_value('[data-field-id="ship_name"]') == "Rosinante"
    assert page.input_value('[data-field-id="ship_speed"]') == "7"
    assert page.input_value('[data-field-id="ship_class"]') == "Cruiser"

    page.goto(f"{live_server.url}/dashboard/")
    page.fill("#dashboard-search-input", WIKI_SEARCH_TERM)
    page.click(".dashboard-search button[type='submit']")
    page.wait_for_selector(".wiki-results")
    assert page.locator(".wiki-results li a").first.count() == 1

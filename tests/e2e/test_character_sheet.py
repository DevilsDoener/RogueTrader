"""Playwright end-to-end tests for the interactive character sheet viewer.

These drive a real (headless) Chromium instance against a real HTTP server
(pytest-django's ``live_server``) backed by the test database -- see
``tests/e2e/conftest.py`` for why fixtures here use ``transactional_db``
instead of the default ``db``.
"""
from __future__ import annotations

import pytest

from sheets.services import patch_character_field

from .conftest import login_via_browser

pytestmark = pytest.mark.django_db(transaction=True)


def test_tab_order_follows_schema_order(page, live_server, owner, character_factory):
    character = character_factory(owner=owner)
    login_via_browser(page, live_server, username=owner.username)
    page.goto(f"{live_server.url}/characters/{character.id}/")

    # Schema order on character-page-1 puts c1_player_name right after
    # c1_character_name (see sheets/data/character-page-1.json) -- tabbing
    # from the first field must land on the second, matching declared
    # schema order rather than visual/DOM happenstance.
    page.focus('[data-field-id="c1_character_name"]')
    page.keyboard.press("Tab")
    active_field_id = page.evaluate("document.activeElement.dataset.fieldId")
    assert active_field_id == "c1_player_name"


def test_text_field_survives_reload(page, live_server, owner, character_factory):
    character = character_factory(owner=owner)
    login_via_browser(page, live_server, username=owner.username)
    page.goto(f"{live_server.url}/characters/{character.id}/")

    field = page.locator('[data-field-id="c1_character_name"]')
    field.fill("Lucian Voss")
    field.blur()
    page.wait_for_function(
        "document.getElementById('sheet-save-status').textContent === 'Gespeichert'",
        timeout=5000,
    )

    page.reload()
    page.wait_for_selector('[data-field-id="c1_character_name"]')
    assert page.input_value('[data-field-id="c1_character_name"]') == "Lucian Voss"


def test_checkbox_field_survives_reload(page, live_server, owner, character_factory):
    character = character_factory(owner=owner)
    login_via_browser(page, live_server, username=owner.username)
    page.goto(f"{live_server.url}/characters/{character.id}/")

    checkbox = page.locator('[data-field-id="c1_ws_adv_1"]')
    checkbox.check()
    page.wait_for_function(
        "document.getElementById('sheet-save-status').textContent === 'Gespeichert'",
        timeout=5000,
    )

    page.reload()
    page.wait_for_selector('[data-field-id="c1_ws_adv_1"]')
    assert page.is_checked('[data-field-id="c1_ws_adv_1"]')


def test_zoom_does_not_change_proportional_alignment(page, live_server, owner, character_factory):
    character = character_factory(owner=owner)
    login_via_browser(page, live_server, username=owner.username)
    page.goto(f"{live_server.url}/characters/{character.id}/")
    page.wait_for_selector('[data-field-id="c1_character_name"]')

    measure = """
    () => {
      const canvas = document.querySelector('.sheet-page:not([hidden]) .sheet-canvas');
      const field = document.querySelector('[data-field-id="c1_character_name"]').closest('.sheet-field');
      const canvasRect = canvas.getBoundingClientRect();
      const fieldRect = field.getBoundingClientRect();
      return {
        x: (fieldRect.left - canvasRect.left) / canvasRect.width,
        y: (fieldRect.top - canvasRect.top) / canvasRect.height,
        w: fieldRect.width / canvasRect.width,
        h: fieldRect.height / canvasRect.height,
      };
    }
    """
    before = page.evaluate(measure)

    for _ in range(3):
        page.click("#zoom-in")

    after = page.evaluate(measure)

    for key in ("x", "y", "w", "h"):
        assert before[key] == pytest.approx(after[key], abs=0.002), key


def test_foreign_user_receives_404(page, live_server, owner, other_user, character_factory):
    character = character_factory(owner=owner)
    login_via_browser(page, live_server, username=other_user.username)
    response = page.goto(f"{live_server.url}/characters/{character.id}/")
    assert response.status == 404


def test_disabled_admin_view_emits_no_field_requests(
    page, live_server, portal_admin, owner, character_factory
):
    character = character_factory(owner=owner, display_name="Locked")
    login_via_browser(page, live_server, username=portal_admin.username)

    field_requests = []
    page.on("request", lambda req: field_requests.append(req.url) if "/fields/" in req.url else None)

    page.goto(f"{live_server.url}/portal-admin/characters/{character.id}/")
    page.wait_for_selector('[data-field-id="c1_character_name"]')

    field = page.locator('[data-field-id="c1_character_name"]')
    assert field.is_disabled()

    # Attempting to interact with a disabled control is a no-op in a real
    # browser, but click/fill it anyway to prove no request escapes even if
    # something slipped through.
    field.click(force=True)
    page.keyboard.type("Should not save")
    page.wait_for_timeout(700)  # longer than the 600ms text-input debounce

    assert field_requests == []


def test_simulated_same_field_conflict_shows_both_choices(
    page, live_server, owner, character_factory
):
    character = character_factory(owner=owner)
    login_via_browser(page, live_server, username=owner.username)
    page.goto(f"{live_server.url}/characters/{character.id}/")
    page.wait_for_selector('[data-field-id="c1_character_name"]')

    # Simulate a second user's concurrent write landing between page load
    # and this browser's save: the client still thinks base_version is 0.
    patch_character_field(
        sheet_id=character.id,
        actor=owner,
        field_id="c1_character_name",
        value="Someone Else",
        base_version=0,
    )

    field = page.locator('[data-field-id="c1_character_name"]')
    field.fill("My Local Edit")
    field.blur()

    panel = page.locator(".sheet-conflict-panel")
    panel.wait_for(timeout=5000)
    assert panel.locator("text=Aktuellen Wert übernehmen").count() == 1
    assert panel.locator("text=Meinen Wert erneut speichern").count() == 1

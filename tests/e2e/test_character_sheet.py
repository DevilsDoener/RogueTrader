"""Playwright end-to-end tests for the interactive character sheet viewer.

These drive a real (headless) Chromium instance against a real HTTP server
(pytest-django's ``live_server``) backed by the test database -- see
``tests/e2e/conftest.py`` for why fixtures here use ``transactional_db``
instead of the default ``db``.
"""
from __future__ import annotations

import pytest

from sheets.schema import load_schema
from sheets.services import patch_character_field

from .conftest import login_via_browser

pytestmark = pytest.mark.django_db(transaction=True)

RESPONSIVE_VIEWPORTS = [
    ("desktop", {"width": 1440, "height": 900}),
    ("tablet", {"width": 768, "height": 1024}),
    ("mobile", {"width": 390, "height": 844}),
]


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


@pytest.mark.parametrize(
    ("starting_field_id", "expected_next_field_id"),
    [
        ("c2_gear_22", "c2_gear_23"),
        ("c2_acquisition_14", "c2_acquisition_15"),
    ],
)
def test_page_2_split_line_fields_are_direct_dom_tab_neighbours(
    page,
    live_server,
    owner,
    character_factory,
    starting_field_id,
    expected_next_field_id,
):
    character = character_factory(owner=owner)
    login_via_browser(page, live_server, username=owner.username)
    page.goto(f"{live_server.url}/characters/{character.id}/")
    page.click('.sheet-page-tab[data-page-index="1"]')

    page.focus(f'[data-field-id="{starting_field_id}"]')
    page.keyboard.press("Tab")

    assert page.evaluate("document.activeElement.dataset.fieldId") == expected_next_field_id


def test_split_line_values_remain_independently_visible_and_editable(
    page, live_server, owner, character_factory
):
    initial_values = {
        "c2_gear_22": "existing gear 22",
        "c2_gear_23": "legacy gear 23",
        "c2_acquisition_14": "existing acquisition 14",
        "c2_acquisition_15": "legacy acquisition 15",
    }
    character = character_factory(owner=owner, values=initial_values)
    login_via_browser(page, live_server, username=owner.username)
    page.goto(f"{live_server.url}/characters/{character.id}/")
    page.click('.sheet-page-tab[data-page-index="1"]')

    for field_id, expected_value in initial_values.items():
        field = page.locator(f'[data-field-id="{field_id}"]')
        assert field.is_editable()
        assert field.input_value() == expected_value

    edited_values = {
        "c2_gear_23": "edited gear 23",
        "c2_acquisition_15": "edited acquisition 15",
    }
    for field_id, edited_value in edited_values.items():
        field = page.locator(f'[data-field-id="{field_id}"]')
        field.fill(edited_value)
        field.blur()
        page.wait_for_function(
            "document.getElementById('sheet-save-status').textContent === 'Gespeichert'",
            timeout=5000,
        )

    page.reload()
    page.click('.sheet-page-tab[data-page-index="1"]')
    expected_after_reload = initial_values | edited_values
    for field_id, expected_value in expected_after_reload.items():
        assert page.input_value(f'[data-field-id="{field_id}"]') == expected_value


def test_internal_template_comment_is_not_visible(
    page, live_server, owner, character_factory
):
    character = character_factory(owner=owner)
    login_via_browser(page, live_server, username=owner.username)
    page.goto(f"{live_server.url}/characters/{character.id}/")

    assert page.get_by_text("Bare include fragment", exact=False).count() == 0


@pytest.mark.parametrize(
    ("page_id", "page_index"),
    (("character-page-1", 0), ("character-page-2", 1)),
)
@pytest.mark.parametrize(("viewport_name", "viewport"), RESPONSIVE_VIEWPORTS)
def test_every_character_field_keeps_schema_order_label_kind_and_geometry(
    page,
    live_server,
    owner,
    character_factory,
    page_id,
    page_index,
    viewport_name,
    viewport,
):
    schema = load_schema(page_id)
    character = character_factory(owner=owner)
    login_via_browser(page, live_server, username=owner.username)
    page.set_viewport_size(viewport)
    page.goto(f"{live_server.url}/characters/{character.id}/")
    page.wait_for_selector('[data-field-id="c1_character_name"]')
    if page_index:
        page.click(f'.sheet-page-tab[data-page-index="{page_index}"]')

    rendered = page.locator(
        f'.sheet-page[data-page-id="{page_id}"] .sheet-input'
    ).evaluate_all(
        """(inputs) => inputs.map((input) => {
          const field = input.closest('.sheet-field');
          const canvas = input.closest('.sheet-canvas');
          const f = field.getBoundingClientRect();
          const c = canvas.getBoundingClientRect();
          return {
            id: input.dataset.fieldId,
            label: input.getAttribute('aria-label'),
            kind: input.dataset.kind,
            tabIndex: input.tabIndex,
            x: (f.left - c.left) / c.width,
            y: (f.top - c.top) / c.height,
            width: f.width / c.width,
            height: f.height / c.height,
            clipped: f.left < c.left - 0.75 || f.top < c.top - 0.75 ||
                     f.right > c.right + 0.75 || f.bottom > c.bottom + 0.75,
          };
        })"""
    )

    assert [field["id"] for field in rendered] == [field.id for field in schema.fields]
    for field_spec, actual in zip(schema.fields, rendered, strict=True):
        context = f"{page_id}/{field_spec.id} at {viewport_name}"
        assert actual["label"] == field_spec.label, context
        assert actual["kind"] == field_spec.kind, context
        assert actual["tabIndex"] == 0, context
        assert not actual["clipped"], context
        assert actual["x"] == pytest.approx(float(field_spec.x / 100), abs=0.001), context
        assert actual["y"] == pytest.approx(float(field_spec.y / 100), abs=0.001), context
        assert actual["width"] == pytest.approx(float(field_spec.width / 100), abs=0.001), context
        assert actual["height"] == pytest.approx(float(field_spec.height / 100), abs=0.001), context


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


def test_viewer_uses_document_scroll_without_zoom_or_pan(
    page, live_server, owner, character_factory
):
    character = character_factory(owner=owner)
    login_via_browser(page, live_server, username=owner.username)
    page.evaluate("localStorage.clear()")
    page.set_viewport_size({"width": 768, "height": 600})
    page.goto(f"{live_server.url}/characters/{character.id}/")
    page.wait_for_selector('[data-field-id="c1_character_name"]')

    assert page.locator(".sheet-toolbar-zoom").count() == 0
    assert page.locator("#zoom-in, #zoom-out, #fit-width, #fit-page").count() == 0

    geometry = page.evaluate(
        """
    () => {
      const viewport = document.querySelector('.sheet-viewport');
      const canvas = document.querySelector('.sheet-page:not([hidden]) .sheet-canvas');
      const viewportRect = viewport.getBoundingClientRect();
      const canvasRect = canvas.getBoundingClientRect();
      const style = getComputedStyle(viewport);
      const pinch = new WheelEvent('wheel', {
        bubbles: true,
        cancelable: true,
        ctrlKey: true,
        deltaY: -100,
      });
      const pinchWasNotCancelled = viewport.dispatchEvent(pinch);
      return {
        heightDifference: Math.abs(viewportRect.height - canvasRect.height),
        overflowY: style.overflowY,
        touchAction: style.touchAction,
        transform: getComputedStyle(document.querySelector('.sheet-canvas-wrapper')).transform,
        pinchWasNotCancelled,
        documentScrollable: document.documentElement.scrollHeight > window.innerHeight,
      };
    }
    """
    )

    assert geometry["heightDifference"] <= 1
    assert geometry["overflowY"] == "visible"
    assert geometry["touchAction"] == "auto"
    assert geometry["transform"] == "none"
    assert geometry["pinchWasNotCancelled"]
    assert geometry["documentScrollable"]

    zoom_key = f"sheets:viewer:{owner.id}:{character.id}:zoom"
    assert page.evaluate("key => localStorage.getItem(key)", zoom_key) is None

    page.evaluate("window.scrollTo(0, 0)")
    page.mouse.wheel(0, 500)
    page.wait_for_function("window.scrollY > 0")


def test_page_index_persists_without_zoom_state(page, live_server, owner, character_factory):
    character = character_factory(owner=owner)
    login_via_browser(page, live_server, username=owner.username)
    page.evaluate("localStorage.clear()")
    page.goto(f"{live_server.url}/characters/{character.id}/")
    page.wait_for_selector('[data-field-id="c1_character_name"]')

    page.click('.sheet-page-tab[data-page-index="1"]')
    page.reload()
    page.wait_for_selector('.sheet-page[data-page-index="1"]:not([hidden])')

    assert page.locator('.sheet-page-tab[data-page-index="1"]').get_attribute("aria-current") == "true"
    page_key = f"sheets:viewer:{owner.id}:{character.id}:page"
    zoom_key = f"sheets:viewer:{owner.id}:{character.id}:zoom"
    assert page.evaluate("key => localStorage.getItem(key)", page_key) == "1"
    assert page.evaluate("key => localStorage.getItem(key)", zoom_key) is None


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

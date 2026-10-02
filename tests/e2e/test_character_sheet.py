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

from .conftest import NAMED_DESKTOP_VIEWPORTS, login_via_browser, open_character, wait_saved

pytestmark = pytest.mark.django_db(transaction=True)


def test_tab_order_follows_schema_order(page, live_server, owner, character_factory):
    open_character(page, live_server, owner, character_factory)

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
def test_page_2_final_line_fields_are_direct_dom_tab_neighbours(
    page,
    live_server,
    owner,
    character_factory,
    starting_field_id,
    expected_next_field_id,
):
    open_character(page, live_server, owner, character_factory)

    page.focus(f'[data-field-id="{starting_field_id}"]')
    page.keyboard.press("Tab")

    assert page.evaluate("document.activeElement.dataset.fieldId") == expected_next_field_id


def test_full_line_and_new_skill_values_remain_visible_and_editable(
    page, live_server, owner, character_factory
):
    initial_values = {
        "c2_gear_22": "existing gear 22",
        "c2_gear_23": "legacy gear 23",
        "c2_acquisition_14": "existing acquisition 14",
        "c2_acquisition_15": "legacy acquisition 15",
    }
    open_character(page, live_server, owner, character_factory, values=initial_values)

    for field_id, expected_value in initial_values.items():
        field = page.locator(f'[data-field-id="{field_id}"]')
        assert field.is_editable()
        assert field.input_value() == expected_value

    edited_values = {
        "c2_gear_23": "edited gear 23",
        "c1_skill_acrobatics_note": "35",
        "c1_talent_first_line": "New talent",
        "c2_acquisition_15": "edited acquisition 15",
    }
    for field_id, edited_value in edited_values.items():
        field = page.locator(f'[data-field-id="{field_id}"]')
        field.fill(edited_value)
        field.blur()
        wait_saved(page)

    page.reload()
    expected_after_reload = initial_values | edited_values
    for field_id, expected_value in expected_after_reload.items():
        assert page.input_value(f'[data-field-id="{field_id}"]') == expected_value


def test_internal_template_comment_is_not_visible(
    page, live_server, owner, character_factory
):
    open_character(page, live_server, owner, character_factory)

    assert page.get_by_text("Bare include fragment", exact=False).count() == 0


@pytest.mark.parametrize(
    "page_id",
    ("character-page-1", "character-page-2"),
)
@pytest.mark.parametrize(("viewport_name", "viewport"), NAMED_DESKTOP_VIEWPORTS)
def test_every_character_field_keeps_schema_order_label_kind_and_geometry(
    page,
    live_server,
    owner,
    character_factory,
    page_id,
    viewport_name,
    viewport,
):
    schema = load_schema(page_id)
    page.set_viewport_size(viewport)
    open_character(page, live_server, owner, character_factory)

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
    open_character(page, live_server, owner, character_factory)

    field = page.locator('[data-field-id="c1_character_name"]')
    field.fill("Lucian Voss")
    field.blur()
    wait_saved(page)

    page.reload()
    page.wait_for_selector('[data-field-id="c1_character_name"]')
    assert page.input_value('[data-field-id="c1_character_name"]') == "Lucian Voss"


def test_checkbox_field_survives_reload(page, live_server, owner, character_factory):
    open_character(page, live_server, owner, character_factory)

    checkbox = page.locator('[data-field-id="c1_ws_adv_1"]')
    checkbox.check()
    wait_saved(page)

    page.reload()
    page.wait_for_selector('[data-field-id="c1_ws_adv_1"]')
    assert page.is_checked('[data-field-id="c1_ws_adv_1"]')


def test_viewer_scrolls_with_the_document(page, live_server, owner, character_factory):
    page.set_viewport_size({"width": 1024, "height": 768})
    open_character(page, live_server, owner, character_factory)

    geometry = page.evaluate(
        """
    () => {
      const viewport = document.querySelector('.sheet-viewport');
      const canvas = document.querySelector('.sheet-page .sheet-canvas');
      const viewportRect = viewport.getBoundingClientRect();
      const canvasRect = canvas.getBoundingClientRect();
      const style = getComputedStyle(viewport);
      return {
        containsMoreThanOneCanvas: viewportRect.height > canvasRect.height,
        overflowY: style.overflowY,
        transform: getComputedStyle(document.querySelector('.sheet-canvas-wrapper')).transform,
        documentScrollable: document.documentElement.scrollHeight > window.innerHeight,
      };
    }
    """
    )

    assert geometry["containsMoreThanOneCanvas"]
    assert geometry["overflowY"] == "visible"
    assert geometry["transform"] == "none"
    assert geometry["documentScrollable"]

    page.evaluate("window.scrollTo(0, 0)")
    page.mouse.wheel(0, 500)
    page.wait_for_function("window.scrollY > 0")


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
    page.on(
        "request", lambda req: field_requests.append(req.url) if "/fields/" in req.url else None
    )

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


@pytest.mark.parametrize(
    ("viewport", "field_id", "remote_value", "local_value", "resolution"),
    [
        (
            {"width": 1440, "height": 900},
            "c2_wounds_critical_damage",
            "12",
            "7",
            "take-current",
        ),
        (
            {"width": 1024, "height": 768},
            "c2_fate_points_current",
            "3",
            "2",
            "retry-mine",
        ),
    ],
)
def test_page_2_edge_conflicts_are_fully_visible_and_resolvable_on_desktop(
    page,
    live_server,
    owner,
    character_factory,
    viewport,
    field_id,
    remote_value,
    local_value,
    resolution,
):
    page.set_viewport_size(viewport)
    character = open_character(page, live_server, owner, character_factory)
    field = page.locator(f'[data-field-id="{field_id}"]')
    field.scroll_into_view_if_needed()

    # Simulate a second user's concurrent write landing between page load
    # and this browser's save: the client still thinks base_version is 0.
    patch_character_field(
        sheet_id=character.id,
        actor=owner,
        field_id=field_id,
        value=remote_value,
        base_version=0,
    )

    field.fill(local_value)
    field.blur()

    panel = page.locator(".sheet-conflict-panel")
    panel.wait_for(timeout=5000)
    geometry = panel.evaluate(
        """(panel) => {
          const rect = panel.getBoundingClientRect();
          const buttons = Array.from(panel.querySelectorAll('button')).map((button) => {
            const buttonRect = button.getBoundingClientRect();
            return {
              left: buttonRect.left,
              top: buttonRect.top,
              right: buttonRect.right,
              bottom: buttonRect.bottom,
            };
          });
          const inset = 2;
          const corners = [
            [rect.left + inset, rect.top + inset],
            [rect.right - inset, rect.top + inset],
            [rect.left + inset, rect.bottom - inset],
            [rect.right - inset, rect.bottom - inset],
          ];
          return {
            left: rect.left,
            top: rect.top,
            right: rect.right,
            bottom: rect.bottom,
            viewportWidth: window.innerWidth,
            viewportHeight: window.innerHeight,
            documentWidth: document.documentElement.scrollWidth,
            clientWidth: document.documentElement.clientWidth,
            buttons,
            paintedCorners: corners.every(([x, y]) => {
              const hit = document.elementFromPoint(x, y);
              return hit && (hit === panel || panel.contains(hit));
            }),
          };
        }"""
    )

    assert geometry["left"] >= 0
    assert geometry["top"] >= 0
    assert geometry["right"] <= geometry["viewportWidth"]
    assert geometry["bottom"] <= geometry["viewportHeight"]
    assert geometry["paintedCorners"]
    assert geometry["documentWidth"] <= geometry["clientWidth"] + 1
    assert len(geometry["buttons"]) == 2
    for button in geometry["buttons"]:
        assert button["left"] >= geometry["left"]
        assert button["top"] >= geometry["top"]
        assert button["right"] <= geometry["right"]
        assert button["bottom"] <= geometry["bottom"]

    if resolution == "take-current":
        panel.locator(".sheet-conflict-take-current").click()
        assert field.input_value() == remote_value
        assert panel.count() == 0
        page.reload()
        assert page.input_value(f'[data-field-id="{field_id}"]') == remote_value
    else:
        panel.locator(".sheet-conflict-retry-mine").click()
        wait_saved(page)
        page.reload()
        assert page.input_value(f'[data-field-id="{field_id}"]') == local_value


def test_speak_language_fourth_row_survives_reload(page, live_server, owner, character_factory):
    open_character(page, live_server, owner, character_factory)
    for suffix in ("basic", "trained", "plus10", "plus20", "bonus"):
        field = page.locator(f'[data-field-id="c1_skill_speak_language_custom_3_{suffix}"]')
        if suffix == "bonus":
            field.fill("15")
            field.blur()
        else:
            field.check()
        wait_saved(page)
    page.reload()
    for suffix in ("basic", "trained", "plus10", "plus20"):
        assert page.is_checked(f'[data-field-id="c1_skill_speak_language_custom_3_{suffix}"]')
    assert page.input_value('[data-field-id="c1_skill_speak_language_custom_3_bonus"]') == "15"


@pytest.mark.parametrize("width", [1024, 1440])
def test_bonus_numbers_and_uniform_rows(page, live_server, owner, character_factory, width):
    fields = load_schema("character-page-1").fields
    bonus_ids = [field.id for field in fields if field.id.endswith("_bonus")]
    values = {field_id: "10" for field_id in bonus_ids}
    values.update({field.id: True for field in fields if "_adv_" in field.id})
    for field in fields:
        if field.id.startswith(
            ("c1_special_ability_", "c1_psychic_discipline_", "c1_psychic_power_")
        ):
            values[field.id] = "Beispiel"
        elif field.id.startswith(("c1_psychic_sustain_", "c1_psychic_range_")):
            values[field.id] = "10"
    for field in load_schema("character-page-2").fields:
        if field.id.startswith("c2_insanity_"):
            values[field.id] = "Beispiel"

    page.set_viewport_size({"width": width, "height": 1000})
    open_character(page, live_server, owner, character_factory, values=values)

    for field_id in bonus_ids:
        bonus = page.locator(f'[data-field-id="{field_id}"]')
        assert bonus.input_value() == "10"
        assert bonus.get_attribute("type") == "text"
        assert bonus.evaluate("el => getComputedStyle(el).textAlign") == "center"

    for prefix in ("c1_special_ability_", "c1_psychic_discipline_", "c1_psychic_power_"):
        lefts = page.locator(f'[data-field-id^="{prefix}"]').evaluate_all(
            "els => els.map(el => el.getBoundingClientRect().left)"
        )
        # The complete standalone artwork has a slight printed-line drift
        # down the page. The calibrated fields follow it by less than half
        # a rendered pixel at the widest tested viewport.
        assert max(lefts) - min(lefts) < 0.6

    for row in range(1, 7):
        bottoms = [
            page.locator(f'[data-field-id="c1_psychic_{column}_{row}"]').evaluate(
                "el => el.getBoundingClientRect().bottom"
            )
            for column in ("power", "sustain", "range")
        ]
        # The same source-page rotation shifts the three column baselines by
        # less than one rendered pixel while keeping each input on its line.
        assert max(bottoms) - min(bottoms) < 1.0

    acrobatics_bonus = page.locator('[data-field-id="c1_skill_acrobatics_bonus"]')
    acrobatics_bonus.fill("20")
    acrobatics_bonus.blur()
    wait_saved(page)
    page.reload()
    assert page.locator('[data-field-id="c1_skill_acrobatics_bonus"]').input_value() == "20"

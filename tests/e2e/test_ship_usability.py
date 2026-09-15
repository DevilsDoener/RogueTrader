import json
from pathlib import Path

import pytest
from .conftest import login_via_browser

pytestmark = pytest.mark.django_db(transaction=True)

@pytest.mark.parametrize("width", [1024, 1440])
def test_ship_values_fit_and_enlarged_markers_save(page, live_server, user_factory, ship_sheet, width):
    user = user_factory()
    ship_sheet.values = {f"ship_weapon_{n}_damage": "1d10+2" for n in range(1, 5)}
    ship_sheet.save(update_fields=["values"])
    page.set_viewport_size({"width": width, "height": 1000})
    login_via_browser(page, live_server, username=user.username)
    page.goto(f"{live_server.url}/ships/{ship_sheet.id}/")
    for n in range(1, 5):
        damage = page.locator(f'[data-field-id="ship_weapon_{n}_damage"]')
        damage.scroll_into_view_if_needed()
        page.wait_for_function("""id => {
            const el=document.querySelector('[data-field-id="'+id+'"]');
            const s=getComputedStyle(el), c=document.createElement('canvas').getContext('2d');
            c.font=s.font;
            return c.measureText(el.value).width <= el.clientWidth-parseFloat(s.paddingLeft)-parseFloat(s.paddingRight)+1;
        }""", arg=f"ship_weapon_{n}_damage", timeout=3000)
    for field in ("ship_space_available", "ship_space_used", "ship_power_available", "ship_power_used",
                  *[f"ship_weapon_capacity_{side}" for side in ("dorsal","prow","keel","port","starboard")]):
        el=page.locator(f'[data-field-id="{field}"]')
        el.fill("12")
        el.blur()
        page.wait_for_function("document.getElementById('sheet-save-status').textContent === 'Gespeichert'")
    # Clicking the printed label, away from the small dot, toggles only this marker.
    hit=page.locator('label[for="field-ship_weapon_1_type_macro_battery"]')
    hit.click(position={"x": 3, "y": 2})
    page.wait_for_function("document.getElementById('sheet-save-status').textContent === 'Gespeichert'")
    assert page.locator('[data-field-id="ship_weapon_1_type_macro_battery"]').is_checked()
    assert not page.locator('[data-field-id="ship_weapon_1_type_lance"]').is_checked()
    # Every enlarged region must resolve to its own marker, including row edges.
    for hit_label in page.locator('.sheet-pip-hit').all():
        hit_label.scroll_into_view_if_needed()
        assert hit_label.evaluate("""label => {
            const r=label.getBoundingClientRect();
            return [[0.15,0.5],[0.85,0.5]].every(([x,y]) => {
                const el=document.elementFromPoint(r.left+r.width*x,r.top+r.height*y);
                return el===label || el.id===label.htmlFor;
            });
        }""")
    damage = page.locator('[data-field-id="ship_weapon_1_damage"]')
    damage.fill("2d10+12")
    damage.blur()
    page.wait_for_function("document.getElementById('sheet-save-status').textContent === 'Gespeichert'")
    page.reload()
    assert page.locator('[data-field-id="ship_weapon_1_damage"]').input_value()=="2d10+12"
    assert page.locator('[data-field-id="ship_space_available"]').input_value()=="12"
    assert page.locator('[data-field-id="ship_weapon_capacity_dorsal"]').input_value()=="12"
    assert page.locator('[data-field-id="ship_weapon_1_type_macro_battery"]').is_checked()
    page.wait_for_function("""() => {
        const el=document.querySelector('[data-field-id="ship_weapon_1_damage"]');
        const s=getComputedStyle(el),c=document.createElement('canvas').getContext('2d');
        c.font=s.font;
        return c.measureText(el.value).width <= el.clientWidth-parseFloat(s.paddingLeft)-parseFloat(s.paddingRight)+1;
    }""")
    out=Path("tmp/ship-fixed");out.mkdir(exist_ok=True)
    page.locator('.sheet-canvas').screenshot(path=str(out/f"ship-{width}.png"))

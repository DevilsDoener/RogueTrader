from pathlib import Path
import pytest
from sheets.schema import load_schema
from .conftest import login_via_browser

pytestmark=pytest.mark.django_db(transaction=True)

@pytest.mark.parametrize("width", [1024,1440])
def test_bonus_numbers_and_uniform_rows(page,live_server,owner,character_factory,width):
    fields=load_schema("character-page-1").fields
    bonus=[f.id for f in fields if f.id.endswith("_bonus")]
    values={fid:"10" for fid in bonus}
    values.update({f.id:True for f in fields if "_adv_" in f.id})
    for f in fields:
        if f.id.startswith(("c1_special_ability_","c1_psychic_discipline_","c1_psychic_power_")):values[f.id]="Beispiel"
        elif f.id.startswith(("c1_psychic_sustain_","c1_psychic_range_")):values[f.id]="10"
    for f in load_schema("character-page-2").fields:
        if f.id.startswith("c2_insanity_"):values[f.id]="Beispiel"
    character=character_factory(owner=owner,values=values)
    page.set_viewport_size({"width":width,"height":1000})
    login_via_browser(page,live_server,username=owner.username)
    page.goto(f"{live_server.url}/characters/{character.pk}/")
    for fid in bonus:
        el=page.locator(f'[data-field-id="{fid}"]')
        assert el.input_value()=="10"
        assert el.get_attribute("type")=="text"
        assert el.evaluate("el=>getComputedStyle(el).textAlign")=="center"
    for prefix in ("c1_special_ability_","c1_psychic_discipline_","c1_psychic_power_"):
        lefts=page.locator(f'[data-field-id^="{prefix}"]').evaluate_all("els=>els.map(el=>el.getBoundingClientRect().left)")
        assert max(lefts)-min(lefts)<0.1
    for row in range(1,7):
        bottoms=[page.locator(f'[data-field-id="c1_psychic_{column}_{row}"]').evaluate("el=>el.getBoundingClientRect().bottom") for column in ("power","sustain","range")]
        assert max(bottoms)-min(bottoms)<0.1
    el=page.locator('[data-field-id="c1_skill_acrobatics_bonus"]')
    el.fill("20");el.blur()
    page.wait_for_function("document.getElementById('sheet-save-status').textContent==='Gespeichert'")
    page.reload()
    assert page.locator('[data-field-id="c1_skill_acrobatics_bonus"]').input_value()=="20"
    out=Path("tmp/character-refinement");out.mkdir(exist_ok=True)
    for number in (1,2):
        page.locator(f'.sheet-page[data-page-id="character-page-{number}"] .sheet-canvas').screenshot(path=str(out/f"page-{number}-{width}.png"))

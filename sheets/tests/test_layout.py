"""Authoring must preserve geometry and reject ambiguous generated layouts."""
from copy import deepcopy
import json

import pytest

from sheets.schema import FieldSpec, SchemaError


def source():
    return {
        "page_id": "example", "image": {"width": 1000, "height": 2000},
        "templates": {"weapon": {"name": {
            "kind": "text", "x": 2, "y": 3, "width": 20, "height": 2,
            "max_length": 60, "text_style": "line",
        }}},
        "sections": [{"id": "weapon-1", "origin": [10, 20], "template": "weapon",
                      "fields": [{"slot": "name", "id": "saved_weapon_name", "label": "Weapon"}]}],
    }


def compile_source(payload):
    from sheets.layout import compile_layout
    return compile_layout(payload)


def test_section_offsets_preserve_persistent_identity_and_template_defaults():
    payload = source()
    original = deepcopy(payload)
    result = compile_source(payload)["fields"][0]
    assert (result["x"], result["y"], result["width"]) == (12, 23, 20)
    assert (result["id"], result["label"], result["max_length"]) == ("saved_weapon_name", "Weapon", 60)
    assert payload == original


def test_instance_correction_does_not_change_other_instances():
    payload = source()
    second = deepcopy(payload["sections"][0])
    second.update(id="weapon-2", origin=[10, 40])
    second["fields"][0].update(id="second_name", width=18, y=4)
    payload["sections"].append(second)
    fields = compile_source(payload)["fields"]
    assert [(f["width"], f["y"]) for f in fields] == [(20, 23), (18, 44)]


@pytest.mark.parametrize("change", [
    lambda p: p["sections"][0].update(template="missing"),
    lambda p: p["sections"][0]["fields"][0].update(slot="missing"),
    lambda p: p["sections"][0].update(origin=[90, 20]),
    lambda p: p["sections"][0].update(origin=["NaN", 0]),
    lambda p: p["sections"][0].update(origin=[0]),
    lambda p: p["sections"].append(deepcopy(p["sections"][0])),
    lambda p: p["sections"][0]["fields"].append(deepcopy(p["sections"][0]["fields"][0])),
    lambda p: p["sections"][0]["fields"][0].update(wdith=18),
])
def test_invalid_layout_is_rejected(change):
    payload = source()
    change(payload)
    with pytest.raises(SchemaError):
        compile_source(payload)


def test_explicit_presentation_does_not_depend_on_field_name():
    raw = dict(source()["templates"]["weapon"]["name"], id="any_name", label="Value",
               text_style="characteristic")
    field = FieldSpec.from_dict(raw)
    assert field.text_style == "characteristic"
    assert field.align == "center"
    raw.update(kind="checkbox", text_style="line", checkbox_style="pip")
    assert FieldSpec.from_dict(raw).checkbox_style == "pip"


@pytest.mark.parametrize("style", [{"text_style": "typo"}, {"checkbox_style": "typo"},
                                  {"text_style": "characteristic", "align": "left"}])
def test_invalid_presentation_is_rejected(style):
    raw = dict(source()["templates"]["weapon"]["name"], id="field", label="Field")
    raw.update(style)
    with pytest.raises(SchemaError):
        FieldSpec.from_dict(raw)


def test_checked_in_schemas_match_editable_sources():
    from sheets.layout import build_layouts, LAYOUT_DIR, DATA_DIR
    assert build_layouts(LAYOUT_DIR, DATA_DIR, check=True) == []


def test_generation_check_is_read_only_and_rejects_stale_output(tmp_path):
    from sheets.layout import build_layouts
    from sheets.schema import KNOWN_PAGE_IDS
    layouts = tmp_path / "layouts"
    outputs = tmp_path / "data"
    layouts.mkdir()
    for page_id in KNOWN_PAGE_IDS:
        payload = source()
        payload["page_id"] = page_id
        (layouts / f"{page_id}.json").write_text(json.dumps(payload), encoding="utf-8")
    assert build_layouts(layouts, outputs, check=True) == list(KNOWN_PAGE_IDS)
    assert not outputs.exists()
    build_layouts(layouts, outputs)
    assert build_layouts(layouts, outputs, check=True) == []
    target = outputs / "ship-page.json"
    target.write_text("{}", encoding="utf-8")
    assert build_layouts(layouts, outputs, check=True) == ["ship-page"]
    assert target.read_text(encoding="utf-8") == "{}"
    # Invalid final source must not overwrite any of the valid earlier outputs.
    (layouts / "ship-page.json").write_text("{}", encoding="utf-8")
    before = {p.name: p.read_bytes() for p in outputs.iterdir()}
    with pytest.raises(SchemaError):
        build_layouts(layouts, outputs)
    assert {p.name: p.read_bytes() for p in outputs.iterdir()} == before

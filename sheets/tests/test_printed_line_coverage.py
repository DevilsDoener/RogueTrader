"""Regression checks against independently measured printed lines on all three sheets."""
import pytest
import json
from pathlib import Path
from sheets.schema import load_schema


@pytest.mark.parametrize("prefix,lefts,width,bottoms", [
    ("gear", [1385,1386,1386,1386,1386,1386,1386,1387,1387,1387,1387,1387,
              1388,1388,1388,1388,1388,1389,1389,1389,1389,1389,1390], 525,
             [1023,1069,1115,1160,1205,1251,1298,1344,1390,1436,1482,1528,
              1573,1619,1664,1710,1756,1802,1848,1894,1940,1985,2031]),
    ("acquisition", [1945,1946,1946,1946,1946,1946,1947,1947,1947,1947,1947,
                     1948,1948,1948,1948], 524,
                    [1025,1071,1117,1162,1207,1253,1300,1346,1392,1437,1483,
                     1529,1575,1620,1666]),
])
def test_every_gear_and_acquisition_line_has_one_full_width_field(prefix,lefts,width,bottoms):
    schema = load_schema("character-page-2")
    for index, (left, bottom) in enumerate(zip(lefts, bottoms, strict=True), 1):
        field = schema.field_by_id(f"c2_{prefix}_{index}")
        assert round(field.x * schema.image_width / 100) == left
        assert round(field.width * schema.image_width / 100) == width
        assert round((field.y + field.height) * schema.image_height / 100) == bottom


def test_page_2_pips_follow_printed_circle_centres_not_a_flat_row():
    schema = load_schema("character-page-2")
    first = schema.field_by_id("c2_ws_adv_1")
    last = schema.field_by_id("c2_fel_adv_4")
    # Visually measured from the original artwork; the final circle is lower.
    assert float((first.y + first.height / 2) * schema.image_height / 100) == pytest.approx(836, abs=1)
    assert float((last.y + last.height / 2) * schema.image_height / 100) > 837


def test_ship_printed_round_markers_use_round_fills():
    schema = load_schema("ship-page")
    for field in schema.fields:
        if field.kind == "checkbox" and "capacity" not in field.id and field.id.startswith("ship_weapon_"):
            assert field.checkbox_style == "pip", field.id


def test_ship_missing_fourth_component_line_is_editable():
    schema = load_schema("ship-page")
    field = schema.field_by_id("ship_essential_component_7")
    assert round(field.y * schema.image_height / 100) == 860
    assert round(field.width * schema.image_width / 100) == 988


def test_reviewed_text_rectangles_match_measured_artwork():
    reference = json.loads((Path(__file__).resolve().parents[2] /
                            "tests/fixtures/text-line-rectangles.json").read_text(encoding="utf-8"))
    for page_id, rectangles in reference.items():
        schema = load_schema(page_id)
        for field_id, expected in rectangles.items():
            field = schema.field_by_id(field_id)
            actual = {key: round(getattr(field, key) * size / 100)
                      for key, size in (("x",schema.image_width),("y",schema.image_height),
                                        ("width",schema.image_width),("height",schema.image_height))}
            assert actual == expected, field_id


def test_page_1_missing_skill_and_talent_lines_are_editable():
    schema = load_schema("character-page-1")
    notes = [field for field in schema.fields
             if field.id.startswith("c1_skill_") and field.id.endswith("_note")]
    assert len(notes) == 44
    assert all(field.kind == "text" and field.text_style == "line" for field in notes)
    assert schema.field_by_id("c1_talent_first_line").kind == "text"

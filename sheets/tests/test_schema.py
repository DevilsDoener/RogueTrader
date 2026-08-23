"""Structural and validation tests for ``sheets.schema``.

These tests exercise ``SheetSchema``/``FieldSpec`` parsing and validation
logic against both inline payloads and the real (currently placeholder)
schema JSON files under ``sheets/data/``. See
``.superpowers/sdd/2026-08-16-rogue-trader-portal/task-4-dispatch-context.md``
for why the on-disk data is placeholder-only at this stage: these tests
confirm the schema *machinery* works, not that the real sheet has been
mapped yet.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from sheets.schema import (
    KNOWN_PAGE_IDS,
    FieldSpec,
    SchemaError,
    SheetSchema,
    load_schema,
)


def _base_payload(**overrides):
    payload = {
        "page_id": "character-page-1",
        "image": {"width": 1230, "height": 1620},
        "fields": [
            {
                "id": "character_name",
                "kind": "text",
                "x": 7,
                "y": 5,
                "width": 40,
                "height": 2,
                "max_length": 80,
                "label": "Character name",
            },
        ],
    }
    payload.update(overrides)
    return payload


@pytest.fixture(params=KNOWN_PAGE_IDS)
def known_page_schema(request) -> SheetSchema:
    return load_schema(request.param)


@pytest.fixture
def character_page_1_schema() -> SheetSchema:
    return load_schema("character-page-1")


@pytest.fixture
def character_page_2_schema() -> SheetSchema:
    return load_schema("character-page-2")


@pytest.fixture
def ship_page_schema() -> SheetSchema:
    return load_schema("ship-page")


class TestSchemaValidation:
    def test_schema_rejects_duplicate_ids(self):
        payload = {
            "page_id": "character-page-1",
            "image": {"width": 1230, "height": 1620},
            "fields": [
                {
                    "id": "character_name",
                    "kind": "text",
                    "x": 7,
                    "y": 5,
                    "width": 40,
                    "height": 2,
                    "max_length": 80,
                    "label": "Character name",
                },
                {
                    "id": "character_name",
                    "kind": "text",
                    "x": 50,
                    "y": 5,
                    "width": 40,
                    "height": 2,
                    "max_length": 80,
                    "label": "Player name",
                },
            ],
        }
        with pytest.raises(SchemaError, match="duplicate field id"):
            SheetSchema.from_dict(payload)

    def test_all_field_bounds_stay_inside_page(self, character_page_1_schema):
        for field_spec in character_page_1_schema.fields:
            assert 0 <= field_spec.x < 100
            assert 0 <= field_spec.y < 100
            assert field_spec.x + field_spec.width <= 100
            assert field_spec.y + field_spec.height <= 100

    @pytest.mark.parametrize(
        "field_overrides",
        [
            {"x": -1},
            {"y": -1},
            {"x": 61, "width": 40},
            {"y": 99, "height": 2},
        ],
    )
    def test_rejects_out_of_bounds_field(self, field_overrides):
        field = _base_payload()["fields"][0].copy()
        field.update(field_overrides)
        payload = _base_payload(fields=[field])
        with pytest.raises(SchemaError):
            SheetSchema.from_dict(payload)

    @pytest.mark.parametrize("field_overrides", [{"width": 0}, {"height": 0}, {"width": -5}])
    def test_rejects_non_positive_dimensions(self, field_overrides):
        field = _base_payload()["fields"][0].copy()
        field.update(field_overrides)
        payload = _base_payload(fields=[field])
        with pytest.raises(SchemaError):
            SheetSchema.from_dict(payload)

    def test_rejects_missing_label(self):
        field = _base_payload()["fields"][0].copy()
        field["label"] = ""
        payload = _base_payload(fields=[field])
        with pytest.raises(SchemaError):
            SheetSchema.from_dict(payload)

    def test_rejects_invalid_kind(self):
        field = _base_payload()["fields"][0].copy()
        field["kind"] = "dropdown"
        payload = _base_payload(fields=[field])
        with pytest.raises(SchemaError):
            SheetSchema.from_dict(payload)

    def test_rejects_non_positive_max_length(self):
        field = _base_payload()["fields"][0].copy()
        field["max_length"] = 0
        payload = _base_payload(fields=[field])
        with pytest.raises(SchemaError):
            SheetSchema.from_dict(payload)

    def test_quantizes_coordinates_to_four_decimal_places(self):
        field = _base_payload()["fields"][0].copy()
        field["x"] = 7.123456789
        payload = _base_payload(fields=[field])
        schema = SheetSchema.from_dict(payload)
        assert schema.fields[0].x == Decimal("7.1235")

    def test_field_coordinates_are_decimal_instances(self):
        payload = _base_payload()
        schema = SheetSchema.from_dict(payload)
        field_spec = schema.fields[0]
        assert isinstance(field_spec.x, Decimal)
        assert isinstance(field_spec.y, Decimal)
        assert isinstance(field_spec.width, Decimal)
        assert isinstance(field_spec.height, Decimal)


class TestValidateValue:
    def test_text_accepts_string_within_max_length(self):
        field_spec = FieldSpec(
            id="c1_character_name",
            kind="text",
            x=Decimal("1"),
            y=Decimal("1"),
            width=Decimal("10"),
            height=Decimal("2"),
            max_length=5,
            label="Name",
        )
        field_spec.validate_value("Kara")  # should not raise

    def test_text_rejects_string_over_max_length(self):
        field_spec = FieldSpec(
            id="c1_character_name",
            kind="text",
            x=Decimal("1"),
            y=Decimal("1"),
            width=Decimal("10"),
            height=Decimal("2"),
            max_length=3,
            label="Name",
        )
        with pytest.raises(SchemaError):
            field_spec.validate_value("Karamazov")

    def test_text_rejects_non_string(self):
        field_spec = FieldSpec(
            id="c1_character_name",
            kind="text",
            x=Decimal("1"),
            y=Decimal("1"),
            width=Decimal("10"),
            height=Decimal("2"),
            max_length=10,
            label="Name",
        )
        with pytest.raises(SchemaError):
            field_spec.validate_value(123)

    def test_checkbox_accepts_json_booleans(self):
        field_spec = FieldSpec(
            id="c1_ws_advance_1",
            kind="checkbox",
            x=Decimal("1"),
            y=Decimal("1"),
            width=Decimal("2"),
            height=Decimal("2"),
            max_length=1,
            label="WS advance",
        )
        field_spec.validate_value(True)
        field_spec.validate_value(False)

    @pytest.mark.parametrize("value", [1, 0, "true", None, "yes"])
    def test_checkbox_rejects_non_boolean(self, value):
        field_spec = FieldSpec(
            id="c1_ws_advance_1",
            kind="checkbox",
            x=Decimal("1"),
            y=Decimal("1"),
            width=Decimal("2"),
            height=Decimal("2"),
            max_length=1,
            label="WS advance",
        )
        with pytest.raises(SchemaError):
            field_spec.validate_value(value)

    def test_schema_validate_value_looks_up_field_by_id(self, character_page_1_schema):
        first_field = character_page_1_schema.fields[0]
        value = True if first_field.kind == "checkbox" else "x"
        character_page_1_schema.validate_value(first_field.id, value)

    def test_schema_validate_value_rejects_unknown_field_id(self, character_page_1_schema):
        with pytest.raises(SchemaError):
            character_page_1_schema.validate_value("does_not_exist", "x")


class TestLoadSchema:
    def test_known_page_ids_load_successfully(self, known_page_schema):
        assert known_page_schema.page_id in KNOWN_PAGE_IDS

    def test_load_schema_rejects_unknown_page_id(self):
        with pytest.raises(SchemaError):
            load_schema("not-a-real-page")

    def test_load_schema_caches_by_page_id(self):
        first = load_schema("character-page-1")
        second = load_schema("character-page-1")
        assert first is second

    def test_field_ids_are_unique_within_a_page(self, known_page_schema):
        ids = [field_spec.id for field_spec in known_page_schema.fields]
        assert len(ids) == len(set(ids))

    def test_field_ids_are_unique_across_both_character_pages(
        self, character_page_1_schema, character_page_2_schema
    ):
        page_1_ids = {field_spec.id for field_spec in character_page_1_schema.fields}
        page_2_ids = {field_spec.id for field_spec in character_page_2_schema.fields}
        assert page_1_ids.isdisjoint(page_2_ids)

    def test_all_fields_have_labels(self, known_page_schema):
        for field_spec in known_page_schema.fields:
            assert field_spec.label.strip() != ""

    def test_all_fields_have_positive_dimensions(self, known_page_schema):
        for field_spec in known_page_schema.fields:
            assert field_spec.width > 0
            assert field_spec.height > 0

    def test_all_fields_have_positive_max_length(self, known_page_schema):
        for field_spec in known_page_schema.fields:
            assert field_spec.max_length > 0

    def test_image_dimensions_are_positive(self, known_page_schema):
        assert known_page_schema.image_width > 0
        assert known_page_schema.image_height > 0

    def test_page_2_retains_every_printed_characteristic_advancement_circle(
        self, character_page_2_schema
    ):
        characteristic_ids = ("ws", "bs", "s", "t", "ag", "int", "per", "wp", "fel")
        expected_ids = {
            f"c2_{characteristic}_adv_{advance}"
            for characteristic in characteristic_ids
            for advance in range(1, 5)
        }
        actual_ids = {field_spec.id for field_spec in character_page_2_schema.fields}

        assert expected_ids <= actual_ids

    @pytest.mark.parametrize(
        ("page_id", "field_id", "expected_geometry"),
        [
            (
                "character-page-1",
                "c1_ws_adv_1",
                ("1.8617", "24.4923", "0.6137", "0.4308"),
            ),
            (
                "character-page-1",
                "c1_skill_acrobatics_basic",
                ("20.4992", "31.8154", "1.7185", "1.2923"),
            ),
            (
                "character-page-2",
                "c2_ws_adv_1",
                ("4.9919", "22.6741", "0.6039", "0.4621"),
            ),
            (
                "ship-page",
                "ship_weapon_capacity_dorsal",
                ("64.2372", "31.9646", "2.4089", "1.6908"),
            ),
            (
                "ship-page",
                "ship_weapon_1_location_dorsal",
                ("70.8462", "80.8374", "0.4941", "0.6441"),
            ),
        ],
    )
    def test_representative_checkbox_geometry_matches_original_artwork(
        self, page_id, field_id, expected_geometry
    ):
        schema = load_schema(page_id)
        field_spec = next(field for field in schema.fields if field.id == field_id)

        assert (
            field_spec.x,
            field_spec.y,
            field_spec.width,
            field_spec.height,
        ) == tuple(Decimal(value) for value in expected_geometry)

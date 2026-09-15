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

import hashlib
import json
from decimal import Decimal
from pathlib import Path

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


def _field_rect_in_source_pixels(schema: SheetSchema, field_id: str) -> tuple[int, int, int, int]:
    field_spec = next(field for field in schema.fields if field.id == field_id)
    return (
        round(field_spec.x * schema.image_width / 100),
        round(field_spec.y * schema.image_height / 100),
        round(field_spec.width * schema.image_width / 100),
        round(field_spec.height * schema.image_height / 100),
    )


def _rectangles_overlap(first: FieldSpec, second: FieldSpec) -> bool:
    return (
        first.x < second.x + second.width
        and second.x < first.x + first.width
        and first.y < second.y + second.height
        and second.y < first.y + first.height
    )


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

    @pytest.mark.parametrize(
        ("field_id", "expected_rect"),
        [
            # Widened left inset (2026-08-25 field-calibration fix): the box
            # previously started 15-26px inside the printed "CHARACTER
            # NAME" label's own ink, causing typed values to visually
            # overlap the label's trailing glyphs.
            ("c1_character_name", (490, 191, 675, 34)),
            ("c1_player_name", (1430, 193, 738, 34)),
            ("c1_career_path", (410, 265, 522, 34)),
            ("c1_rank", (1040, 267, 125, 34)),
            # Narrowed (2026-08-26 owner request): the box previously ran to
            # 1675px, overlapping the printed "MOTIVATION" label that starts at
            # ~1645px; it now ends before that label.
            ("c1_home_world", (1435, 268, 200, 34)),
            ("c1_motivation", (1855, 268, 313, 34)),
            ("c1_profit_factor_starting", (1740, 2800, 355, 34)),
            # Moved right (2026-08-27 owner review): started at 1710, cutting
            # ~24px into the printed "Current" label (ends ~1734).
            ("c1_profit_factor_current", (1740, 2846, 355, 34)),
            ("c1_profit_factor_misfortunes", (1810, 2892, 285, 34)),
        ],
    )
    def test_page_1_text_fields_cover_only_the_printed_input_lines(
        self, character_page_1_schema, field_id, expected_rect
    ):
        assert _field_rect_in_source_pixels(character_page_1_schema, field_id) == expected_rect

    def test_page_2_weapon_fields_follow_the_printed_input_lines(
        self, character_page_2_schema
    ):
        expected = {
            1: {
                "name": (219, 925, 1203), "class": (209, 975, 441),
                "damage": (579, 975, 788), "type": (875, 975, 1002),
                "pen": (1071, 975, 1198), "range": (227, 1025, 439),
                "rof": (524, 1025, 735), "clip": (811, 1025, 940),
                "reload": (1058, 1025, 1186),
                "special_rules_1": (340, 1075, 1193), "special_rules_2": (126, 1125, 1193),
            },
            2: {
                "name": (218, 1309, 1201), "class": (207, 1359, 439),
                "damage": (576, 1359, 787), "type": (874, 1359, 1001),
                "pen": (1069, 1359, 1197), "range": (225, 1409, 436),
                "rof": (523, 1409, 734), "clip": (811, 1409, 938),
                "reload": (1057, 1409, 1184),
                "special_rules_1": (338, 1459, 1191), "special_rules_2": (124, 1509, 1191),
            },
            3: {
                "name": (217, 1692, 1199), "class": (206, 1742, 438),
                "damage": (575, 1743, 786), "type": (873, 1743, 1000),
                "pen": (1067, 1744, 1195), "range": (225, 1792, 436),
                "rof": (521, 1793, 733), "clip": (809, 1794, 937),
                "reload": (1055, 1794, 1183),
                "special_rules_1": (336, 1843, 1189), "special_rules_2": (123, 1893, 1189),
            },
            4: {
                "name": (216, 2076, 1199), "class": (205, 2124, 436),
                "damage": (573, 2126, 785), "type": (871, 2126, 998),
                "pen": (1065, 2126, 1193), "range": (223, 2175, 435),
                "rof": (519, 2176, 731), "clip": (807, 2176, 935),
                "reload": (1053, 2176, 1181),
                "special_rules_1": (334, 2228, 1187), "special_rules_2": (122, 2278, 1187),
            },
            5: {
                "name": (214, 2460, 1197), "class": (203, 2510, 434),
                "damage": (571, 2510, 782), "type": (869, 2510, 996),
                "pen": (1063, 2510, 1191), "range": (221, 2560, 433),
                "rof": (517, 2560, 729), "clip": (805, 2560, 932),
                "reload": (1051, 2560, 1179),
                "special_rules_1": (333, 2610, 1185), "special_rules_2": (118, 2660, 1185),
            },
        }

        for weapon, fields in expected.items():
            for suffix, (left, line_y, right) in fields.items():
                field_id = f"c2_weapon_{weapon}_{suffix}"
                assert _field_rect_in_source_pixels(character_page_2_schema, field_id) == (
                    left,
                    line_y - 36,
                    right - left,
                    34,
                )

    def test_page_2_list_fields_cover_printed_lines_and_preserve_legacy_ids(
        self, character_page_2_schema
    ):
        field_ids = {field.id for field in character_page_2_schema.fields}
        assert {f"c2_gear_{index}" for index in range(1, 24)} <= field_ids
        assert {f"c2_acquisition_{index}" for index in range(1, 16)} <= field_ids
        assert {f"c2_mutation_{index}" for index in range(1, 7)} <= field_ids

        for prefix, count, expected_x, expected_width in (
            ("gear", 21, 1294, 525),
            ("acquisition", 13, 1854, 524),
            ("mutation", 6, 1849, 524),
        ):
            for index in range(1, count + 1):
                x, _y, width, _height = _field_rect_in_source_pixels(
                    character_page_2_schema, f"c2_{prefix}_{index}"
                )
                assert (x, width) == (expected_x, expected_width)

        # Formerly split last-line fields now each occupy a complete printed
        # line. The first printed line is no longer skipped; IDs remain stable.
        final_line_rectangles = {
            "c2_gear_22": (1294, 1863, 525, 34),
            "c2_gear_23": (1294, 1909, 525, 34),
            "c2_acquisition_14": (1854, 1499, 524, 34),
            "c2_acquisition_15": (1854, 1545, 524, 34),
        }
        for field_id, expected_rect in final_line_rectangles.items():
            assert _field_rect_in_source_pixels(
                character_page_2_schema, field_id
            ) == expected_rect

        ordered_ids = [field.id for field in character_page_2_schema.fields]
        gear_index = ordered_ids.index("c2_gear_22")
        acquisition_index = ordered_ids.index("c2_acquisition_14")
        assert ordered_ids[gear_index : gear_index + 3] == [
            "c2_gear_22",
            "c2_gear_23",
            "c2_acquisition_1",
        ]
        assert ordered_ids[acquisition_index : acquisition_index + 3] == [
            "c2_acquisition_14",
            "c2_acquisition_15",
            "c2_mutation_1",
        ]

    def test_character_pages_retain_all_interactive_fields(
        self, character_page_1_schema, character_page_2_schema
    ):
        # 2026-08-26: page 1 grew by 29 text fields (owner review) -- extra
        # talent/special/psychic lines, skill specialisation write-ins, and
        # misfortune lines. Page 1 went 414 -> 443.
        # 2026-08-28: page 2 grew by 8 text fields (owner review) -- a second
        # "Special Rules" line per weapon (5), two Corruption malignancy
        # continuation lines, and one Insanity disorders continuation line.
        # Page 2 went 167 -> 175.
        assert len(character_page_1_schema.fields) == 490
        assert len(character_page_2_schema.fields) == 175
        assert len(character_page_1_schema.fields) + len(character_page_2_schema.fields) == 665

    @pytest.mark.parametrize(
        ("page_id", "expected_digest"),
        [
            (
                "character-page-1",
                "3d820a42c15536d6d8319408480a192297d02ccbb7d58ffa41bdc6741d44b93a",
            ),
            (
                "character-page-2",
                "d200ea7fdb023f263c1d9bdb4b5f15641d973b209ededb9ce51789bda349501a",
            ),
        ],
    )
    def test_character_field_ids_kinds_and_order_match_the_persisted_contract(
        self, page_id, expected_digest
    ):
        schema = load_schema(page_id)
        contract = "".join(
            f"{field.id}\t{field.kind}\n" for field in schema.fields
            if not (field.id.startswith("c1_skill_") and field.id.endswith("_note"))
            and field.id != "c1_talent_first_line"
        ).encode("utf-8")

        assert hashlib.sha256(contract).hexdigest() == expected_digest

    @pytest.mark.parametrize(
        ("field_id", "expected_x", "expected_width"),
        [
            ("c2_corruption_current_points", 1545, 255),
            ("c2_corruption_degree", 1405, 395),
            ("c2_corruption_malignancies", 1520, 280),
            # 2026-08-28 owner review: wounds + insanity value fields started
            # ~65-105px right of their labels, leaving the front of each
            # printed line bare. Moved left to begin just after the label so
            # each field covers the full line (same right edge, x=2350px).
            ("c2_wounds_total", 1945, 405),
            ("c2_wounds_current", 1982, 368),
            ("c2_wounds_critical_damage", 2120, 230),
            ("c2_wounds_fatigue", 1979, 371),
            ("c2_insanity_current_points", 2094, 256),
            ("c2_insanity_degree", 1975, 375),
            ("c2_insanity_disorders", 2013, 337),
            # 2026-08-28 owner review: armour TYPE fields started ~30-64px
            # after "TYPE:" and overshot the box's right border. Moved to begin
            # just after "TYPE:" and end at the box's inner right edge (full
            # line within each location box).
            ("c2_armour_head_type", 1612, 203),
            ("c2_armour_right_arm_type", 1320, 213),
            ("c2_armour_left_arm_type", 1880, 203),
            ("c2_armour_body_type", 1596, 217),
            ("c2_armour_right_leg_type", 1328, 203),
            ("c2_armour_left_leg_type", 1878, 203),
        ],
    )
    def test_page_2_right_column_fields_start_after_their_printed_labels(
        self, character_page_2_schema, field_id, expected_x, expected_width
    ):
        x, _y, width, _height = _field_rect_in_source_pixels(character_page_2_schema, field_id)
        assert (x, width) == (expected_x, expected_width)

    def test_armour_weight_field_covers_its_printed_input_box(
        self, character_page_2_schema
    ):
        assert _field_rect_in_source_pixels(character_page_2_schema, "c2_armour_weight") == (
            2005,
            2855,
            230,
            80,
        )

    @pytest.mark.parametrize("page_id", ("character-page-1", "character-page-2"))
    def test_character_fields_do_not_overlap(self, page_id):
        schema = load_schema(page_id)
        overlaps = [
            (first.id, second.id)
            for index, first in enumerate(schema.fields)
            for second in schema.fields[index + 1 :]
            if _rectangles_overlap(first, second)
        ]
        assert overlaps == []

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
                # Re-centred on its printed pip and enlarged to fill it
                # (2026-08-27 owner review of the "Adv. Taken" pips).
                "c1_ws_adv_1",
                ("1.7185", "24.4000", "0.8592", "0.6462"),
            ),
            (
                "character-page-1",
                "c1_skill_acrobatics_basic",
                ("20.4992", "31.8154", "1.7185", "1.2923"),
            ),
            (
                "character-page-2",
                # Individually aligned to the actual printed circle again:
                # source (122,732), diameter 21px. No artificial flat row.
                "c2_ws_adv_1",
                ("4.9114", "22.5508", "0.8454", "0.6470"),
            ),
            (
                "ship-page",
                "ship_weapon_capacity_dorsal",
                ("64.1754", "31.8438", "2.5633", "1.8921"),
            ),
            (
                "ship-page",
                "ship_weapon_1_location_dorsal",
                ("70.7844", "80.7568", "0.6177", "0.8052"),
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

    def test_all_352_checkbox_rectangles_match_independent_pixel_reference(self):
        reference_path = (
            Path(__file__).resolve().parents[2]
            / "tests"
            / "fixtures"
            / "checkbox-rectangles.json"
        )
        reference = json.loads(reference_path.read_text(encoding="utf-8"))
        expected_counts = {
            "character-page-1": 288,
            "character-page-2": 36,
            "ship-page": 28,
        }

        assert {page_id: len(rectangles) for page_id, rectangles in reference.items()} == (
            expected_counts
        )
        assert sum(expected_counts.values()) == 352

        for page_id, expected_rectangles in reference.items():
            schema = load_schema(page_id)
            checkboxes = [field for field in schema.fields if field.kind == "checkbox"]
            assert [field.id for field in checkboxes] == list(expected_rectangles)

            for field in checkboxes:
                actual_left = round(field.x * schema.image_width / 100)
                actual_top = round(field.y * schema.image_height / 100)
                actual_right = round((field.x + field.width) * schema.image_width / 100)
                actual_bottom = round((field.y + field.height) * schema.image_height / 100)
                expected = expected_rectangles[field.id]
                actual = (actual_left, actual_top, actual_right, actual_bottom)

                for edge_name, actual_edge, expected_edge in zip(
                    ("left", "top", "right", "bottom"),
                    actual,
                    expected,
                    strict=True,
                ):
                    assert abs(actual_edge - expected_edge) <= 0, (
                        f"{page_id}/{field.id} {edge_name}: "
                        f"schema={actual_edge}px reference={expected_edge}px"
                    )

    def test_checkbox_calibration_artifacts_match_reviewed_source_hashes(self):
        root = Path(__file__).resolve().parents[2]
        manifest = json.loads(
            (root / "tests" / "fixtures" / "checkbox-calibration-manifest.json")
            .read_text(encoding="utf-8")
        )

        artifacts = [manifest["rectangle_reference"], *manifest["sources"].values()]
        for artifact in artifacts:
            digest = hashlib.sha256((root / artifact["path"]).read_bytes()).hexdigest()
            assert digest == artifact["sha256"], artifact["path"]

    @pytest.mark.parametrize(
        ("page_id", "field_id", "expected_geometry"),
        [
            (
                "character-page-1",
                "c1_ws_value",
                ("1.3093", "19.3538", "9.7791", "4.3692"),
            ),
            # Full-box widths (2026-08-26 owner request): these
            # characteristic-value boxes span the whole printed box (matching
            # WS/BS) instead of clearing the bonus circle. This reverts the
            # 2026-08-25 narrowing.
            (
                "character-page-1",
                "c1_s_value",
                ("22.4223", "19.3846", "9.8199", "4.3077"),
            ),
            (
                "character-page-1",
                "c1_int_value",
                ("54.0917", "19.5385", "9.8199", "4.2769"),
            ),
            (
                "character-page-1",
                "c1_per_value",
                ("64.6481", "19.5385", "9.82", "4.2769"),
            ),
            (
                "character-page-1",
                "c1_wp_value",
                ("75.2046", "19.5385", "9.8199", "4.2769"),
            ),
            (
                "character-page-1",
                "c1_fel_value",
                ("85.7610", "19.5385", "9.7791", "4.2769"),
            ),
            (
                "character-page-2",
                "c2_movement_full_move",
                ("28.5829", "9.3654", "9.2593", "2.7726"),
            ),
            (
                "character-page-2",
                "c2_movement_charge",
                ("40.0966", "9.3654", "9.3398", "2.7726"),
            ),
            (
                "character-page-2",
                "c2_movement_base_jump",
                ("74.7987", "9.4886", "9.2995", "2.7726"),
            ),
        ],
    )
    def test_representative_text_box_geometry_matches_original_artwork(
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

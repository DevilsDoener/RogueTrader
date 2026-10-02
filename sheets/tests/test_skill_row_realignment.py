"""Skill IDs of character page 1 follow the printed rows (migration 0007).

The layout keeps every control where it was; only the IDs changed. These tests
pin the position of the renamed rows, the new fourth Forbidden Lore row and the
data migration that moves stored values and field versions along.
"""
import pytest

from sheets.schema import load_schema
from sheets.tests.helpers import load_migration, run_migration_step

MIGRATION = "0007_realign_skill_row_ids"
SLOTS = ("basic", "trained", "plus10", "plus20", "bonus")


def _migration():
    return load_migration(MIGRATION)


def _rect(schema, field_id):
    field = schema.field_by_id(field_id)
    return (
        round(field.x * schema.image_width / 100),
        round(field.y * schema.image_height / 100),
        round(field.width * schema.image_width / 100),
        round(field.height * schema.image_height / 100),
    )


def test_migration_mapping_only_targets_existing_fields_and_is_invertible():
    migration = _migration()
    schema = load_schema("character-page-1")
    ids = {field.id for field in schema.fields}
    assert set(migration.FORWARD.values()) <= ids
    assert set(migration.FORWARD.values()) | migration.BACKWARD_DROPPED <= ids
    assert len(migration.FORWARD) == len(set(migration.FORWARD.values())) == 65
    assert {migration.BACKWARD[new]: new for new in migration.BACKWARD} == migration.FORWARD
    assert not migration.BACKWARD_DROPPED & set(migration.BACKWARD)
    assert not any(key.endswith("_note") for key in migration.FORWARD)


@pytest.mark.parametrize(
    ("stem", "rect"),
    [
        # Positions are those of the former IDs (evaluate, forbidden_lore, ...).
        ("drive_custom_1", (673, 2202, 42, 42)),
        ("evaluate", (673, 2248, 42, 42)),
        ("forbidden_lore", (673, 2338, 43, 42)),
        ("forbidden_lore_custom_1", (674, 2384, 42, 41)),
        ("forbidden_lore_custom_2", (674, 2430, 42, 41)),
        ("pilot", (2120, 1515, 42, 40)),
        ("pilot_custom_1", (2120, 1561, 42, 42)),
        ("pilot_custom_2", (2120, 1607, 42, 42)),
        ("psyniscience", (2120, 1653, 42, 40)),
        ("scholastic_lore", (2120, 1745, 42, 41)),
        ("scholastic_lore_custom_1", (2120, 1791, 42, 41)),
        ("scholastic_lore_custom_2", (2120, 1837, 42, 41)),
        ("scholastic_lore_custom_3", (2119, 1882, 43, 41)),
        # New fourth Forbidden Lore row, one row pitch below custom_2.
        ("forbidden_lore_custom_3", (674, 2476, 42, 41)),
    ],
)
def test_renamed_and_new_skill_rows_sit_on_their_printed_rows(stem, rect):
    schema = load_schema("character-page-1")
    assert _rect(schema, f"c1_skill_{stem}_basic") == rect


def test_new_forbidden_lore_row_copies_the_row_above():
    schema = load_schema("character-page-1")
    pitch = None
    for slot in SLOTS:
        above = schema.field_by_id(f"c1_skill_forbidden_lore_custom_2_{slot}")
        new = schema.field_by_id(f"c1_skill_forbidden_lore_custom_3_{slot}")
        assert (new.kind, new.x, new.width, new.height) == (
            above.kind, above.x, above.width, above.height
        )
        assert (new.max_length, new.text_style, new.checkbox_style, new.input_mode) == (
            above.max_length, above.text_style, above.checkbox_style, above.input_mode
        )
        delta = round(new.y - above.y, 4)
        pitch = pitch or delta
        assert delta == pitch
    row_pitch_px = pitch * schema.image_height / 100
    assert 45.5 < row_pitch_px < 46.5


@pytest.mark.django_db
def test_migration_moves_values_and_versions_with_the_position(character_factory):
    migration = _migration()
    values = {"c1_character_name": "Keep", "c1_skill_evaluate_note": "42", "c1_unknown": 1}
    versions = {"c1_character_name": 5, "c1_skill_pilot_note": 7}
    expected_values = dict(values)
    expected_versions = dict(versions)
    for old, new in migration.FORWARD.items():
        values[old] = f"value:{old}"
        versions[old] = len(old)
        expected_values[new] = f"value:{old}"
        expected_versions[new] = len(old)
    character = character_factory(values=values, field_versions=versions)
    untouched = character_factory(values={"c1_skill_acrobatics_basic": True})

    run_migration_step(migration.forwards)

    character.refresh_from_db()
    untouched.refresh_from_db()
    assert character.values == expected_values
    assert character.field_versions == expected_versions
    assert untouched.values == {"c1_skill_acrobatics_basic": True}
    # performer_custom_2 values now live under pilot; nothing was lost
    assert character.values["c1_skill_pilot_basic"] == "value:c1_skill_performer_custom_2_basic"
    assert "c1_skill_performer_custom_2_basic" not in character.values
    assert "c1_skill_forbidden_lore_custom_3_basic" not in character.values
    assert len(character.values) == len(values)

    # reverse restores the old keys exactly
    run_migration_step(migration.backwards)
    character.refresh_from_db()
    original = {k: v for k, v in values.items()}
    assert character.values == original
    assert character.field_versions == versions


@pytest.mark.django_db
def test_reverse_drops_values_of_the_new_row_and_keeps_others(character_factory):
    migration = _migration()
    character = character_factory(
        values={
            "c1_skill_forbidden_lore_custom_3_basic": True,
            "c1_skill_forbidden_lore_custom_3_bonus": "12",
            "c1_skill_forbidden_lore_custom_2_basic": True,
            "c1_skill_drive_custom_1_bonus": "10",
            "c1_character_name": "Keep",
        },
        field_versions={"c1_skill_forbidden_lore_custom_3_basic": 3, "c1_skill_drive_custom_1_bonus": 4},
    )

    run_migration_step(migration.backwards)

    character.refresh_from_db()
    assert character.values == {
        "c1_skill_forbidden_lore_custom_3_basic": True,  # old custom_3 = new custom_2
        "c1_skill_evaluate_bonus": "10",
        "c1_character_name": "Keep",
    }
    assert character.field_versions == {"c1_skill_evaluate_bonus": 4}


@pytest.mark.django_db
def test_migration_ignores_characters_without_affected_keys(character_factory):
    migration = _migration()
    character = character_factory(values={"c1_skill_acrobatics_bonus": "5"})
    before = character.updated_at
    run_migration_step(migration.forwards)
    character.refresh_from_db()
    assert character.values == {"c1_skill_acrobatics_bonus": "5"}
    assert character.updated_at == before

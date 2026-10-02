import pytest

from sheets.schema import SchemaError, load_schema
from sheets.tests.helpers import load_migration, run_migration_step


def test_all_bonus_cells_accept_two_digit_numbers():
    fields=[f for f in load_schema("character-page-1").fields if f.id.endswith("_bonus")]
    assert len(fields)==65
    for field in fields:
        assert field.kind=="text" and field.input_mode=="numeric"
        assert field.text_style=="center" and field.max_length==2
        for value in ("", "0", "10", "99"):
            field.validate_value(value)
        for value in (True, False, "100", "x", "-1"):
            with pytest.raises(SchemaError):
                field.validate_value(value)


@pytest.mark.django_db
def test_bonus_mark_migration_preserves_other_values(character_factory):
    character=character_factory(values={"c1_skill_acrobatics_bonus":True,"c1_skill_awareness_bonus":False,"c1_character_name":"Keep"})
    character.field_versions={"c1_skill_acrobatics_bonus":3}
    character.save()
    migration=load_migration("0004_character_bonus_numbers")
    run_migration_step(migration.archive_marks)
    character.refresh_from_db()
    assert character.values=={
        "c1_skill_acrobatics_bonus":"","c1_skill_awareness_bonus":"","c1_character_name":"Keep"
    }
    assert character.field_versions["c1_skill_acrobatics_bonus"]==4
    assert character.changes.get(field_id="c1_skill_acrobatics_bonus").old_value is True
    run_migration_step(migration.archive_marks)
    assert character.changes.count()==2

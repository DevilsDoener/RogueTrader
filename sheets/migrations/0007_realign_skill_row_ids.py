"""Realign the persistent skill IDs of character page 1 with the printed rows.

Every skill checkbox sat on the correct printed box, but in two blocks the
field IDs were shifted by one printed row (Evaluate/Forbidden Lore on the left,
Performer/Pilot/Psyniscience/Scholastic Lore on the right). The layout keeps
every control where it is and only renames the IDs; this migration moves the
stored values and field versions along, so every mark and number stays on the
same printed box. See ``docs/checkbox-row-mapping.md``.

The rename is simultaneous: all old keys of a character are read first, removed,
and only then are the new keys written, so a chain such as ``evaluate`` ->
``drive_custom_1`` and ``forbidden_lore`` -> ``evaluate`` cannot clobber a
value. Keys that are not in the mapping (including the ``c1_skill_*_note``
text fields and the ``c1_*_spec_*`` fields) are left untouched. The audit trail
(``SheetChange``) is append-only and keeps the field IDs as they were written.

The fourth Forbidden Lore row is new (``forbidden_lore_custom_3_*``). The
reverse migration applies the inverse mapping and has to drop anything stored
under those new keys, because the old layout has no field for them; values
there cannot be restored when migrating backwards.
"""

from django.db import migrations


SLOTS = ("basic", "trained", "plus10", "plus20", "bonus")

# old stem -> new stem
STEM_RENAMES = {
    "evaluate": "drive_custom_1",
    "forbidden_lore": "evaluate",
    "forbidden_lore_custom_1": "forbidden_lore",
    "forbidden_lore_custom_2": "forbidden_lore_custom_1",
    "forbidden_lore_custom_3": "forbidden_lore_custom_2",
    "performer_custom_2": "pilot",
    "pilot": "pilot_custom_1",
    "pilot_custom_1": "pilot_custom_2",
    "pilot_custom_2": "psyniscience",
    "psyniscience": "scholastic_lore",
    "scholastic_lore": "scholastic_lore_custom_1",
    "scholastic_lore_custom_1": "scholastic_lore_custom_2",
    "scholastic_lore_custom_2": "scholastic_lore_custom_3",
}

# Stem of the new printed row; it has no counterpart in the old layout.
NEW_ROW_STEM = "forbidden_lore_custom_3"


def _field(stem, slot):
    return f"c1_skill_{stem}_{slot}"


FORWARD = {
    _field(old, slot): _field(new, slot)
    for old, new in STEM_RENAMES.items()
    for slot in SLOTS
}
BACKWARD = {new: old for old, new in FORWARD.items()}
# Keys that only exist in the new layout and are dropped on the way back.
BACKWARD_DROPPED = frozenset(_field(NEW_ROW_STEM, slot) for slot in SLOTS)


def rename_keys(mapping, data, dropped=frozenset()):
    """Return ``data`` with the keys of ``mapping`` renamed simultaneously.

    Returns ``None`` if nothing had to change.
    """
    if not isinstance(data, dict):
        return None
    moved = {key: data[key] for key in data if key in mapping}
    removed = [key for key in data if key in dropped]
    if not moved and not removed:
        return None
    result = {
        key: value
        for key, value in data.items()
        if key not in mapping and key not in dropped
    }
    for old_key, value in moved.items():
        result[mapping[old_key]] = value
    return result


def _apply(apps, schema_editor, mapping, dropped=frozenset()):
    Character = apps.get_model("sheets", "CharacterSheet")
    alias = schema_editor.connection.alias
    for character in Character.objects.using(alias).all().iterator():
        values = rename_keys(mapping, character.values, dropped)
        versions = rename_keys(mapping, character.field_versions, dropped)
        update_fields = []
        if values is not None:
            character.values = values
            update_fields.append("values")
        if versions is not None:
            character.field_versions = versions
            update_fields.append("field_versions")
        if update_fields:
            character.save(using=alias, update_fields=update_fields)


def forwards(apps, schema_editor):
    _apply(apps, schema_editor, FORWARD)


def backwards(apps, schema_editor):
    _apply(apps, schema_editor, BACKWARD, BACKWARD_DROPPED)


class Migration(migrations.Migration):
    dependencies = [("sheets", "0006_sync_characteristics_between_pages")]
    operations = [migrations.RunPython(forwards, backwards)]

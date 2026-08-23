"""Keep values from two retired duplicate overlays visible without truncation.

Each retired field and its surviving target allowed 60 characters. Combining
two arbitrary valid values into one 60-character string cannot be lossless.
The forward migration therefore swaps/moves the retired value into the
visible target and keeps any previous target value under the now-inactive
legacy key. A small marker records presence (not content), making the
operation idempotent and allowing the reverse migration to restore the old
layout exactly. Edits made to the visible target after migrating become the
legacy value again when reversing.
"""

from django.db import migrations


MARKER_KEY = "__sheets_migration_0003_removed_character_fields__"
MARKER_VERSION = 1
FIELD_PAIRS = (
    ("c2_gear_23", "c2_gear_22"),
    ("c2_acquisition_15", "c2_acquisition_14"),
)


def move_removed_values_to_visible_fields(apps, schema_editor):
    CharacterSheet = apps.get_model("sheets", "CharacterSheet")

    for sheet in CharacterSheet.objects.all().iterator():
        values = dict(sheet.values or {})
        if MARKER_KEY in values:
            continue

        field_versions = dict(sheet.field_versions or {})
        pair_states = {}

        for legacy_id, target_id in FIELD_PAIRS:
            if legacy_id not in values:
                continue

            target_was_present = target_id in values
            target_version_was_present = target_id in field_versions
            legacy_version_was_present = legacy_id in field_versions
            legacy_value = values[legacy_id]
            legacy_version = field_versions.get(legacy_id)

            if target_was_present:
                values[legacy_id] = values[target_id]
            else:
                values.pop(legacy_id)
            values[target_id] = legacy_value

            if target_version_was_present:
                field_versions[legacy_id] = field_versions[target_id]
            else:
                field_versions.pop(legacy_id, None)
            if legacy_version_was_present:
                field_versions[target_id] = legacy_version
            else:
                field_versions.pop(target_id, None)

            pair_states[legacy_id] = {
                "target_was_present": target_was_present,
                "target_version_was_present": target_version_was_present,
            }

        if not pair_states:
            continue

        values[MARKER_KEY] = {"version": MARKER_VERSION, "pairs": pair_states}
        sheet.values = values
        sheet.field_versions = field_versions
        sheet.save(update_fields=["values", "field_versions"])


def restore_removed_values(apps, schema_editor):
    CharacterSheet = apps.get_model("sheets", "CharacterSheet")

    for sheet in CharacterSheet.objects.all().iterator():
        values = dict(sheet.values or {})
        marker = values.get(MARKER_KEY)
        if not isinstance(marker, dict) or marker.get("version") != MARKER_VERSION:
            continue

        pair_states = marker.get("pairs")
        if not isinstance(pair_states, dict):
            continue

        field_versions = dict(sheet.field_versions or {})

        for legacy_id, target_id in FIELD_PAIRS:
            state = pair_states.get(legacy_id)
            if not isinstance(state, dict):
                continue

            current_target_was_present = target_id in values
            current_target_value = values.get(target_id)
            original_target_value = values.get(legacy_id)
            current_target_version_was_present = target_id in field_versions
            current_target_version = field_versions.get(target_id)
            original_target_version = field_versions.get(legacy_id)

            if current_target_was_present:
                values[legacy_id] = current_target_value
            else:
                values.pop(legacy_id, None)

            if state.get("target_was_present"):
                values[target_id] = original_target_value
            else:
                values.pop(target_id, None)

            if current_target_version_was_present:
                field_versions[legacy_id] = current_target_version
            else:
                field_versions.pop(legacy_id, None)

            if state.get("target_version_was_present"):
                field_versions[target_id] = original_target_version
            else:
                field_versions.pop(target_id, None)

        values.pop(MARKER_KEY, None)
        sheet.values = values
        sheet.field_versions = field_versions
        sheet.save(update_fields=["values", "field_versions"])


class Migration(migrations.Migration):

    dependencies = [
        ("sheets", "0002_seed_shared_ship"),
    ]

    operations = [
        migrations.RunPython(
            move_removed_values_to_visible_fields,
            restore_removed_values,
        ),
    ]

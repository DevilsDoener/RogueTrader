"""Synchronize the duplicated characteristics on both printed pages."""

from django.db import migrations


CHARACTERISTICS = ("ws", "bs", "s", "t", "ag", "int", "per", "wp", "fel")
SLOTS = ("value", "adv_1", "adv_2", "adv_3", "adv_4")


def _valid(slot, value):
    if slot == "value":
        return isinstance(value, str) and (
            value == "" or (value.isascii() and value.isdigit() and len(value) <= 2)
        )
    return type(value) is bool


def sync_existing(apps, schema_editor):
    Character = apps.get_model("sheets", "CharacterSheet")
    Change = apps.get_model("sheets", "SheetChange")
    alias = schema_editor.connection.alias

    for character in Character.objects.using(alias).all().iterator():
        values = dict(character.values)
        versions = dict(character.field_versions)
        changed = False

        for characteristic in CHARACTERISTICS:
            for slot in SLOTS:
                page_one = f"c1_{characteristic}_{slot}"
                page_two = f"c2_{characteristic}_{slot}"
                if page_one in values:
                    canonical = values[page_one]
                elif page_two in values:
                    canonical = values[page_two]
                else:
                    continue
                if not _valid(slot, canonical):
                    continue

                for target in (page_one, page_two):
                    old = values.get(target)
                    if old == canonical:
                        continue
                    character.version += 1
                    Change.objects.using(alias).create(
                        character_id=character.pk,
                        actor_id=None,
                        field_id=target,
                        old_value=old,
                        new_value=canonical,
                        resulting_version=character.version,
                    )
                    values[target] = canonical
                    versions[target] = character.version
                    changed = True

        if changed:
            character.values = values
            character.field_versions = versions
            character.save(
                using=alias,
                update_fields=["values", "field_versions", "version", "updated_at"],
            )


class Migration(migrations.Migration):
    dependencies = [("sheets", "0005_calculate_character_movement")]
    operations = [migrations.RunPython(sync_existing, migrations.RunPython.noop)]

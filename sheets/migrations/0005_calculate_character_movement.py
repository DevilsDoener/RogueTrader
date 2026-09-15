"""Reconcile previously manual movement fields, retaining old values in audit."""
from django.db import migrations

SOURCE = "c2_movement_half_move"
FACTORS = {"c2_movement_full_move": 2, "c2_movement_charge": 3, "c2_movement_run": 6}

def calculate_existing(apps, schema_editor):
    Character=apps.get_model("sheets","CharacterSheet")
    Change=apps.get_model("sheets","SheetChange")
    alias=schema_editor.connection.alias
    for character in Character.objects.using(alias).all().iterator():
        source=character.values.get(SOURCE)
        if not isinstance(source,str) or (source and not (source.isascii() and source.isdigit() and len(source)<=6)):
            continue
        values=dict(character.values);versions=dict(character.field_versions);changed=False
        for field,factor in FACTORS.items():
            value=str(int(source)*factor) if source else ""
            old=values.get(field)
            if old==value:continue
            character.version+=1
            Change.objects.using(alias).create(character_id=character.pk,actor_id=None,field_id=field,
                old_value=old,new_value=value,resulting_version=character.version)
            values[field]=value;versions[field]=character.version;changed=True
        if changed:
            character.values=values;character.field_versions=versions
            character.save(using=alias,update_fields=["values","field_versions","version","updated_at"])

class Migration(migrations.Migration):
    dependencies=[("sheets","0004_character_bonus_numbers")]
    operations=[migrations.RunPython(calculate_existing)]

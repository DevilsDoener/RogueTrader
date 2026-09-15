"""Archive former resource marks in history before enabling numeric entry."""
from django.db import migrations

RESOURCE_FIELDS = (
    "ship_space_available", "ship_space_used", "ship_power_available", "ship_power_used",
    "ship_weapon_capacity_dorsal", "ship_weapon_capacity_prow", "ship_weapon_capacity_keel",
    "ship_weapon_capacity_port", "ship_weapon_capacity_starboard",
)

def archive_marks(apps, schema_editor):
    Ship = apps.get_model("sheets", "ShipSheet")
    Change = apps.get_model("sheets", "SheetChange")
    alias = schema_editor.connection.alias
    for ship in Ship.objects.using(alias).all().iterator():
        values = dict(ship.values)
        versions = dict(ship.field_versions)
        changed = False
        for field in RESOURCE_FIELDS:
            old = values.get(field)
            if not isinstance(old, bool):
                continue
            version = versions.get(field, 0) + 1
            Change.objects.using(alias).create(
                ship_id=ship.pk, actor_id=None, field_id=field,
                old_value=old, new_value="", resulting_version=version,
            )
            values[field] = ""
            versions[field] = version
            ship.version += 1
            changed = True
        if changed:
            ship.values = values
            ship.field_versions = versions
            ship.save(using=alias, update_fields=["values", "field_versions", "version"])

class Migration(migrations.Migration):
    dependencies = [("sheets", "0002_seed_shared_ship")]
    operations = [migrations.RunPython(archive_marks)]

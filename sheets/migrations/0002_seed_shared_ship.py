import uuid

from django.db import migrations

# Fixed UUID for the one shared ship this migration seeds. Used by the
# reverse migration so it deletes only the row it created (never any ship
# an operator may have added or renamed since).
SEED_SHIP_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def seed_shared_ship(apps, schema_editor):
    ShipSheet = apps.get_model("sheets", "ShipSheet")
    if ShipSheet.objects.exists():
        return
    ShipSheet.objects.create(
        id=SEED_SHIP_ID,
        display_name="Gemeinsames Schiff",
        values={},
        field_versions={},
        version=0,
        is_active=True,
    )


def remove_seeded_ship(apps, schema_editor):
    ShipSheet = apps.get_model("sheets", "ShipSheet")
    ShipSheet.objects.filter(pk=SEED_SHIP_ID).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("sheets", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_shared_ship, remove_seeded_ship),
    ]

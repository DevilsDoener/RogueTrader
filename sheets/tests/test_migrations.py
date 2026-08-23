"""Data-migration coverage for persisted character-sheet JSON values."""

from __future__ import annotations

import importlib

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from sheets.services import patch_character_field


pytestmark = pytest.mark.django_db(transaction=True)

MIGRATE_FROM = ("sheets", "0002_seed_shared_ship")


@pytest.fixture
def character_sheet_at_migration_0002(owner):
    executor = MigrationExecutor(connection)
    executor.migrate([MIGRATE_FROM])
    old_apps = executor.loader.project_state([MIGRATE_FROM]).apps
    CharacterSheet = old_apps.get_model("sheets", "CharacterSheet")

    yield CharacterSheet, owner

    latest_executor = MigrationExecutor(connection)
    latest_executor.migrate(latest_executor.loader.graph.leaf_nodes())


def _migrate_sheets_to_latest():
    executor = MigrationExecutor(connection)
    targets = executor.loader.graph.leaf_nodes("sheets")
    executor.migrate(targets)
    return executor.loader.project_state(targets).apps


def test_removed_legacy_values_move_to_visible_targets_without_data_loss(
    character_sheet_at_migration_0002,
):
    CharacterSheet, owner = character_sheet_at_migration_0002
    sixty_gear_characters = "G" * 60
    sixty_acquisition_characters = "A" * 60
    sheet = CharacterSheet.objects.create(
        owner_id=owner.pk,
        display_name="Legacy values",
        values={
            "c2_gear_22": "existing gear line 22",
            "c2_gear_23": sixty_gear_characters,
            "c2_acquisition_14": "existing acquisition line 14",
            "c2_acquisition_15": sixty_acquisition_characters,
        },
        field_versions={
            "c2_gear_22": 7,
            "c2_gear_23": 11,
            "c2_acquisition_14": 13,
            "c2_acquisition_15": 17,
        },
        version=17,
    )

    new_apps = _migrate_sheets_to_latest()
    MigratedCharacterSheet = new_apps.get_model("sheets", "CharacterSheet")
    migrated = MigratedCharacterSheet.objects.get(pk=sheet.pk)

    assert migrated.values["c2_gear_22"] == sixty_gear_characters
    assert migrated.values["c2_acquisition_14"] == sixty_acquisition_characters
    assert len(migrated.values["c2_gear_22"]) == 60
    assert len(migrated.values["c2_acquisition_14"]) == 60
    assert migrated.values["c2_gear_23"] == "existing gear line 22"
    assert migrated.values["c2_acquisition_15"] == "existing acquisition line 14"
    assert migrated.field_versions == {
        "c2_gear_22": 11,
        "c2_gear_23": 7,
        "c2_acquisition_14": 17,
        "c2_acquisition_15": 13,
    }
    assert migrated.version == 17

    before_second_run = (migrated.values.copy(), migrated.field_versions.copy())
    migration = importlib.import_module(
        "sheets.migrations.0003_migrate_removed_character_fields"
    )
    migration.move_removed_values_to_visible_fields(new_apps, None)
    migrated.refresh_from_db()
    assert (migrated.values, migrated.field_versions) == before_second_run


def test_reverse_migration_restores_targets_and_keeps_edits_to_moved_values(
    character_sheet_at_migration_0002,
):
    CharacterSheet, owner = character_sheet_at_migration_0002
    sheet = CharacterSheet.objects.create(
        owner_id=owner.pk,
        display_name="Reverse values",
        values={
            "c2_gear_22": "original visible gear",
            "c2_gear_23": "legacy gear",
            "c2_acquisition_15": "legacy acquisition without prior target",
        },
        field_versions={
            "c2_gear_22": 2,
            "c2_gear_23": 4,
            "c2_acquisition_15": 6,
        },
        version=6,
    )

    new_apps = _migrate_sheets_to_latest()
    MigratedCharacterSheet = new_apps.get_model("sheets", "CharacterSheet")
    migrated = MigratedCharacterSheet.objects.get(pk=sheet.pk)
    patch_character_field(
        sheet_id=migrated.pk,
        actor=owner,
        field_id="c2_gear_22",
        value="edited legacy gear",
        base_version=4,
    )
    patch_character_field(
        sheet_id=migrated.pk,
        actor=owner,
        field_id="c2_acquisition_14",
        value="edited legacy acquisition",
        base_version=6,
    )

    reverse_executor = MigrationExecutor(connection)
    reverse_executor.migrate([MIGRATE_FROM])
    old_apps = reverse_executor.loader.project_state([MIGRATE_FROM]).apps
    RestoredCharacterSheet = old_apps.get_model("sheets", "CharacterSheet")
    restored = RestoredCharacterSheet.objects.get(pk=sheet.pk)

    assert restored.values == {
        "c2_gear_22": "original visible gear",
        "c2_gear_23": "edited legacy gear",
        "c2_acquisition_15": "edited legacy acquisition",
    }
    assert restored.field_versions == {
        "c2_gear_22": 2,
        "c2_gear_23": 7,
        "c2_acquisition_15": 8,
    }
    assert restored.version == 8

    migration = importlib.import_module(
        "sheets.migrations.0003_migrate_removed_character_fields"
    )
    before_second_reverse = (restored.values.copy(), restored.field_versions.copy())
    migration.restore_removed_values(old_apps, None)
    restored.refresh_from_db()
    assert (restored.values, restored.field_versions) == before_second_reverse

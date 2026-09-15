"""Keep old bonus marks in the audit log before enabling two-digit values."""
from django.db import migrations

BONUS_FIELDS = (
    'c1_skill_acrobatics_bonus',
    'c1_skill_awareness_bonus',
    'c1_skill_barter_bonus',
    'c1_skill_blather_bonus',
    'c1_skill_carouse_bonus',
    'c1_skill_charm_bonus',
    'c1_skill_chem_use_bonus',
    'c1_skill_ciphers_bonus',
    'c1_skill_climb_bonus',
    'c1_skill_command_bonus',
    'c1_skill_commerce_bonus',
    'c1_skill_common_lore_bonus',
    'c1_skill_common_lore_custom_1_bonus',
    'c1_skill_common_lore_custom_2_bonus',
    'c1_skill_common_lore_custom_3_bonus',
    'c1_skill_concealment_bonus',
    'c1_skill_contortionist_bonus',
    'c1_skill_deceive_bonus',
    'c1_skill_demolition_bonus',
    'c1_skill_disguise_bonus',
    'c1_skill_dodge_bonus',
    'c1_skill_drive_bonus',
    'c1_skill_evaluate_bonus',
    'c1_skill_forbidden_lore_bonus',
    'c1_skill_forbidden_lore_custom_1_bonus',
    'c1_skill_forbidden_lore_custom_2_bonus',
    'c1_skill_forbidden_lore_custom_3_bonus',
    'c1_skill_gamble_bonus',
    'c1_skill_inquiry_bonus',
    'c1_skill_interrogation_bonus',
    'c1_skill_intimidate_bonus',
    'c1_skill_invocation_bonus',
    'c1_skill_lip_reading_bonus',
    'c1_skill_literacy_bonus',
    'c1_skill_logic_bonus',
    'c1_skill_midicae_bonus',
    'c1_skill_navigation_bonus',
    'c1_skill_performer_bonus',
    'c1_skill_performer_custom_1_bonus',
    'c1_skill_performer_custom_2_bonus',
    'c1_skill_pilot_bonus',
    'c1_skill_pilot_custom_1_bonus',
    'c1_skill_pilot_custom_2_bonus',
    'c1_skill_psyniscience_bonus',
    'c1_skill_scholastic_lore_bonus',
    'c1_skill_scholastic_lore_custom_1_bonus',
    'c1_skill_scholastic_lore_custom_2_bonus',
    'c1_skill_scrutiny_bonus',
    'c1_skill_search_bonus',
    'c1_skill_secret_tongue_bonus',
    'c1_skill_security_bonus',
    'c1_skill_shadowing_bonus',
    'c1_skill_silent_move_bonus',
    'c1_skill_sleight_of_hand_bonus',
    'c1_skill_speak_language_bonus',
    'c1_skill_speak_language_custom_1_bonus',
    'c1_skill_speak_language_custom_2_bonus',
    'c1_skill_survival_bonus',
    'c1_skill_swim_bonus',
    'c1_skill_tech_use_bonus',
    'c1_skill_tracking_bonus',
    'c1_skill_trade_bonus',
    'c1_skill_wrangling_bonus',
)

def archive_marks(apps, schema_editor):
    Character = apps.get_model("sheets", "CharacterSheet")
    Change = apps.get_model("sheets", "SheetChange")
    alias = schema_editor.connection.alias
    for character in Character.objects.using(alias).all().iterator():
        values = dict(character.values)
        versions = dict(character.field_versions)
        changed = False
        for field in BONUS_FIELDS:
            old = values.get(field)
            if not isinstance(old, bool):
                continue
            version = versions.get(field, 0) + 1
            Change.objects.using(alias).create(
                character_id=character.pk, actor_id=None, field_id=field,
                old_value=old, new_value="", resulting_version=version,
            )
            values[field] = ""
            versions[field] = version
            character.version += 1
            changed = True
        if changed:
            character.values = values
            character.field_versions = versions
            character.save(using=alias, update_fields=["values", "field_versions", "version", "updated_at"])

class Migration(migrations.Migration):
    dependencies = [("sheets", "0003_ship_resource_numbers")]
    operations = [migrations.RunPython(archive_marks)]

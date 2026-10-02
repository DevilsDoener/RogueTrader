"""Unsafe sheet text: rejected on write, harmless when already stored; plus
the small structural guarantees of the viewer/history/permission helpers."""
from __future__ import annotations

import dataclasses

import pytest
from django.urls import reverse

from sheets import history, schema, services, viewer
from sheets.cards import character_card
from sheets.models import CharacterSheet, SheetChange
from sheets.permissions import can_mutate_character, characters_owned_by
from sheets.textsafety import display_text, unsafe_text_problem

TEXT_FIELD = schema.load_schema(schema.SHIP_PAGE_ID).field_by_id("ship_class")
NUMERIC_FIELD = next(
    f
    for p in schema.KNOWN_PAGE_IDS
    for f in schema.load_schema(p).fields
    if f.kind == "text" and f.input_mode == "numeric"
)


@pytest.mark.parametrize(
    "bad",
    ["\ud800", "\udfff", "\x00", "\n", "\r", "\t", "\x1b", "\x7f", "\x85", "\x9f",
     "‪", "‫", "‬", "‭", "‮", "⁦", "⁧", "⁨", "⁩"],
)
def test_validate_value_rejects_unsafe_characters(bad):
    with pytest.raises(schema.SchemaError, match="ungültige Zeichen"):
        TEXT_FIELD.validate_value(f"ab{bad}")


@pytest.mark.parametrize("good", ["", "Größe", "Rogue Trader 40.000", "日本語", "🚀", "a‍b", " x"])
def test_validate_value_accepts_ordinary_text(good):
    TEXT_FIELD.validate_value(good)


def test_numeric_field_still_reports_the_number_rule():
    with pytest.raises(schema.SchemaError, match="whole number"):
        NUMERIC_FIELD.validate_value("1a")


def test_validation_messages_do_not_echo_the_submitted_value():
    with pytest.raises(schema.SchemaError) as excinfo:
        TEXT_FIELD.validate_value(["secret-looking-value"])
    assert "secret-looking-value" not in str(excinfo.value)


def test_unsafe_text_problem_names_the_class():
    assert unsafe_text_problem("ok") is None
    assert unsafe_text_problem("\ud800") == "not valid UTF-8 text"
    assert unsafe_text_problem("‮") == "bidirectional control character"
    assert unsafe_text_problem("\x00") == "control character"


def test_display_text_cleans_strings_and_leaves_other_values_alone():
    assert display_text("a\ud800b‮c\x00d") == "a�bcd"
    assert display_text("Größe") == "Größe"
    assert display_text(True) is True
    assert display_text(None) is None
    assert display_text(12) == 12
    display_text("a\ud800").encode("utf-8")


@pytest.mark.django_db
def test_stored_surrogate_does_not_break_any_page(client, owner, character_sheet, ship_sheet):
    """Values stored before the write path rejected them must not 500 pages."""
    character_sheet.values = {"c1_career_path": "\ud800", "c1_rank": "‮7", "c1_ws_value": "\ud83d"}
    character_sheet.save()
    ship_sheet.values = {"ship_class": "x\udc00y"}
    ship_sheet.save()
    change = SheetChange.objects.create(
        ship=ship_sheet, actor=owner, field_id="ship_class",
        old_value="\ud800", new_value="\udc00", resulting_version=1,
    )
    client.force_login(owner)
    for url in (
        reverse("sheets:character_detail", args=[character_sheet.pk]),
        reverse("sheets:character_list"),
        reverse("dashboard"),
        reverse("sheets:ship_detail", args=[ship_sheet.pk]),
        reverse("sheets:ship_history", args=[ship_sheet.pk]),
        reverse("sheets:ship_history_detail", args=[ship_sheet.pk, change.pk]),
    ):
        response = client.get(url)
        assert response.status_code == 200, url
        response.content.decode("utf-8")


@pytest.mark.django_db
def test_admin_can_view_a_character_with_a_stored_surrogate(client, user_factory, character_sheet):
    character_sheet.values = {"c1_career_path": "\ud800"}
    character_sheet.save()
    client.force_login(user_factory(is_portal_admin=True))
    response = client.get(reverse("sheets:admin_character_detail", args=[character_sheet.pk]))
    assert response.status_code == 200


def test_history_format_value_is_clean():
    assert history.format_value("\ud800x") == "�x"
    assert history.format_value(True) == "markiert"
    assert history.format_value(False) == "nicht markiert"
    assert history.format_value(None) == "–"
    assert history.format_value(3) == "3"


@pytest.mark.django_db
def test_card_values_are_clean(owner):
    sheet = CharacterSheet.objects.create(owner=owner, display_name="Zoë")
    sheet.values = {"c1_career_path": "Arch\x00-Militant\ud800"}
    card = character_card(sheet)
    assert card["career_rank"] == ["Arch-Militant�"]


# ---- Ship read_only is enforced like the character one (F6) ---------------

@pytest.mark.django_db
def test_ship_read_only_field_cannot_be_written(monkeypatch, user_factory, ship_sheet):
    real = schema.load_schema(schema.SHIP_PAGE_ID)
    locked = tuple(
        dataclasses.replace(f, read_only=True) if f.id == "ship_class" else f for f in real.fields
    )
    fake = dataclasses.replace(real, fields=locked)
    monkeypatch.setattr(
        services.schema, "load_schema", lambda page_id: fake if page_id == schema.SHIP_PAGE_ID else real
    )
    with pytest.raises(services.FieldValidationError, match="schreibgeschützt"):
        services.patch_ship_field(
            sheet_id=ship_sheet.id, actor=user_factory(), field_id="ship_class", value="x", base_version=0
        )
    ship_sheet.refresh_from_db()
    assert "ship_class" not in ship_sheet.values


# ---- Single owner-scoped definition (P1) ---------------------------------

@pytest.mark.django_db
def test_characters_owned_by_agrees_with_can_mutate_character(owner, user_factory, character_sheet):
    stranger = user_factory()
    admin = user_factory(is_portal_admin=True)
    for user in (owner, stranger, admin):
        assert characters_owned_by(user).filter(pk=character_sheet.pk).exists() == can_mutate_character(
            user, character_sheet
        )
    assert list(characters_owned_by(owner)) == [character_sheet]


def test_layout_field_keys_match_the_field_spec():
    from sheets.layout import FIELD_KEYS

    assert FIELD_KEYS == {f.name for f in dataclasses.fields(schema.FieldSpec)} | {"align"}


# ---- Extracted viewer/history helpers (P2) --------------------------------

@pytest.mark.django_db
def test_viewer_contexts_have_the_documented_shape(character_sheet, ship_sheet):
    ctx = viewer.character_context(character_sheet, read_only=True)
    assert ctx["read_only"] is True and ctx["field_update_url_template"] is None
    assert [p["page_id"] for p in ctx["pages"]] == list(schema.CHARACTER_PAGE_IDS)
    assert set(ctx["client_rules"]) == {"movement", "counterparts"}
    live = viewer.character_context(character_sheet, read_only=False)
    assert live["field_update_url_template"].endswith("/__FIELD_ID__/")
    assert viewer.ship_context(ship_sheet)["read_only"] is False


@pytest.mark.django_db
def test_history_rows_fall_back_to_the_field_id_for_unknown_fields(owner, ship_sheet):
    known = SheetChange.objects.create(ship=ship_sheet, actor=owner, field_id="ship_class", resulting_version=1)
    unknown = SheetChange.objects.create(ship=ship_sheet, actor=owner, field_id="retired_field", resulting_version=2)
    rows = history.history_rows(ship_sheet, [known, unknown])
    assert rows[0]["field_label"] == TEXT_FIELD.label
    assert rows[1]["field_label"] == "retired_field"
    assert rows[1]["detail_url"].endswith(f"/history/{unknown.pk}/")


#: Invisible / line-breaking characters, spelled with chr() so the test source
#: itself holds none of them literally.
INVISIBLE_CHARACTERS = [
    pytest.param(chr(code), id=f"U+{code:04X}")
    for code in (0x061C, 0x200B, 0x200E, 0x200F, 0x2028, 0x2029, 0xFEFF)
]


@pytest.mark.parametrize("bad", INVISIBLE_CHARACTERS)
def test_invisible_and_line_separator_characters_are_rejected(bad):
    with pytest.raises(schema.SchemaError, match="ungültige Zeichen"):
        TEXT_FIELD.validate_value(f"ab{bad}cd")
    assert unsafe_text_problem(bad) is not None
    assert display_text(f"ab{bad}cd") == "abcd"


def test_zero_width_joiners_stay_allowed_for_emoji_sequences():
    family = "👨" + chr(0x200D) + "👩" + chr(0x200D) + "👧"
    TEXT_FIELD.validate_value(family)
    assert display_text(family) == family


def test_textsafety_source_holds_no_literal_invisible_characters():
    from pathlib import Path

    from sheets import textsafety

    source = Path(textsafety.__file__).read_text(encoding="utf-8")
    assert source.isascii()

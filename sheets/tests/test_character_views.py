"""Owner-scoped character list/create/detail/delete views.

Every user-facing lookup here starts from an owner-scoped queryset, so a
character owned by someone else -- including a portal admin who can *view*
it through the separate admin route -- is indistinguishable from a
nonexistent one (404) when reached through these routes.
"""
from __future__ import annotations

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from sheets.forms import CharacterCreateForm
from sheets.models import CharacterSheet
from sheets.tests.helpers import assert_contains, assert_not_contains


@pytest.mark.django_db
def test_user_character_list_contains_only_owned_sheets(client, user_factory, character_factory):
    owner = user_factory()
    other = user_factory()
    character_factory(owner=owner, display_name="Own")
    character_factory(owner=other, display_name="Hidden")
    client.force_login(owner)
    response = client.get("/characters/")
    assert_contains(response, "Own")
    assert_not_contains(response, "Hidden")


@pytest.mark.django_db
def test_character_list_requires_login(client):
    response = client.get("/characters/")
    assert response.status_code == 302
    assert "/account/login/" in response.url


@pytest.mark.django_db
def test_create_character_sets_owner_server_side(client, user_factory):
    owner = user_factory()
    client.force_login(owner)
    response = client.post("/characters/", {"display_name": "Lucian", "owner": "someone-else"})

    character = CharacterSheet.objects.get(display_name="Lucian")
    assert character.owner == owner
    assert character.values == {}
    assert character.field_versions == {}
    assert response.status_code == 302
    assert response.url == f"/characters/{character.id}/"


@pytest.mark.django_db
@pytest.mark.parametrize("display_name", ["", "   "], ids=["blank", "whitespace-only"])
def test_create_character_requires_display_name(client, user_factory, display_name):
    owner = user_factory()
    client.force_login(owner)
    response = client.post("/characters/", {"display_name": display_name})
    assert response.status_code == 200
    assert not CharacterSheet.objects.exists()
    assert response.context["form"].errors == {"display_name": ["Bitte einen Namen angeben."]}


@pytest.mark.django_db
def test_create_character_strips_surrounding_whitespace_from_the_name(client, user_factory):
    owner = user_factory()
    client.force_login(owner)
    client.post("/characters/", {"display_name": "  Lucian Voss  "})
    assert CharacterSheet.objects.get(owner=owner).display_name == "Lucian Voss"


def test_create_form_keeps_the_german_name_label():
    assert CharacterCreateForm().fields["display_name"].label == "Name"


@pytest.mark.django_db
def test_owner_can_view_own_character_detail_read_write(client, user_factory, character_factory):
    owner = user_factory()
    character = character_factory(owner=owner, display_name="Own")
    client.force_login(owner)
    response = client.get(f"/characters/{character.id}/")
    assert response.status_code == 200
    assert response.context["read_only"] is False


@pytest.mark.django_db
def test_user_cannot_view_another_users_character_detail(client, user_factory, character_factory):
    owner = user_factory()
    other = user_factory()
    character = character_factory(owner=other, display_name="Hidden")
    client.force_login(owner)
    response = client.get(f"/characters/{character.id}/")
    assert response.status_code == 404


@pytest.mark.django_db
def test_owner_can_delete_own_character_via_post(client, user_factory, character_factory):
    owner = user_factory()
    character = character_factory(owner=owner, display_name="Own")
    client.force_login(owner)
    response = client.post(f"/characters/{character.id}/delete/")
    assert response.status_code == 302
    assert not CharacterSheet.objects.filter(pk=character.id).exists()


@pytest.mark.django_db
def test_user_cannot_delete_another_users_character(client, user_factory, character_factory):
    owner = user_factory()
    other = user_factory()
    character = character_factory(owner=other, display_name="Hidden")
    client.force_login(owner)
    response = client.post(f"/characters/{character.id}/delete/")
    assert response.status_code == 404
    assert CharacterSheet.objects.filter(pk=character.id).exists()


@pytest.mark.django_db
def test_delete_via_get_shows_confirmation_and_does_not_delete(client, user_factory, character_factory):
    owner = user_factory()
    character = character_factory(owner=owner, display_name="Own")
    client.force_login(owner)
    response = client.get(f"/characters/{character.id}/delete/")
    assert response.status_code == 200
    assert CharacterSheet.objects.filter(pk=character.id).exists()


@pytest.mark.django_db
def test_get_on_another_users_delete_confirmation_is_not_found(client, user_factory, character_factory):
    owner = user_factory()
    other = user_factory()
    character = character_factory(owner=other, display_name="Hidden")
    client.force_login(owner)
    response = client.get(f"/characters/{character.id}/delete/")
    assert response.status_code == 404
    assert CharacterSheet.objects.filter(pk=character.id).exists()


# ---------------------------------------------------------------------------
# Character list: dossier cards (presentation only, built by
# sheets.cards.character_card from ``character.values``).
# ---------------------------------------------------------------------------

FILLED_VALUES = {
    "c1_career_path": "Rogue Trader",
    "c1_rank": "3",
    "c1_home_world": "Void Born",
    "c1_ws_value": "38",
    "c1_bs_value": "41",
    "c1_s_value": "29",
    "c1_t_value": "33",
    "c1_ag_value": "35",
    "c1_int_value": "40",
    "c1_per_value": "36",
    "c1_wp_value": "37",
    "c1_fel_value": "47",
    "c2_wounds_current": "11",
    "c2_wounds_total": "13",
    "c2_fate_points_current": "2",
    "c2_fate_points_total": "3",
    "c1_xp_to_spend": "250",
    "c1_profit_factor_current": "42",
}


@pytest.mark.django_db
def test_character_list_card_shows_name_career_characteristics_and_stats(
    client, user_factory, character_factory
):
    owner = user_factory()
    character = character_factory(owner=owner, display_name="Lucian Voss", values=FILLED_VALUES)
    client.force_login(owner)
    response = client.get("/characters/")
    html = response.content.decode()

    assert response.status_code == 200
    assert f'href="/characters/{character.id}/"' in html
    assert "Lucian Voss" in html
    assert "Rogue Trader · Rank 3 · Void Born" in html
    assert "<dt>Fel</dt>" in html
    assert "<dd>47</dd>" in html
    assert '<span class="crew-stat-label">Wounds</span>' in html
    assert '<span class="crew-stat-value">11 / 13</span>' in html
    assert '<span class="crew-stat-value">2 / 3</span>' in html
    assert '<span class="crew-stat-label">Profit Factor</span>' in html
    assert "Bogen &ouml;ffnen" in html or "Bogen öffnen" in html
    assert f'href="/characters/{character.id}/delete/"' in html
    assert 'class="button button-danger crew-card-delete"' in html


@pytest.mark.django_db
def test_character_list_card_with_empty_values_renders_without_none(
    client, user_factory, character_factory
):
    owner = user_factory()
    character_factory(owner=owner, display_name="", values={})
    client.force_login(owner)
    response = client.get("/characters/")
    html = response.content.decode()

    assert response.status_code == 200
    assert "Unbenannter Charakter" in html
    assert "None" not in html
    assert "Noch keine Werte eingetragen." in html
    # No characteristics strip and no stat chips when nothing is filled in.
    assert "crew-card-characteristics" not in html
    assert "crew-stat" not in html
    assert "Rank" not in html


@pytest.mark.django_db
def test_character_list_card_partial_values_skip_missing_parts(
    client, user_factory, character_factory
):
    owner = user_factory()
    character_factory(
        owner=owner,
        display_name="Half Done",
        values={"c1_career_path": "Seneschal", "c1_ws_value": "30", "c2_wounds_total": "12", "c1_rank": ""},
    )
    client.force_login(owner)
    html = client.get("/characters/").content.decode()

    assert '<p class="crew-card-meta">Seneschal</p>' in html
    assert "<dd>30</dd>" in html
    assert '<span class="crew-stat-value">– / 12</span>' in html
    assert "Fate" not in html
    assert "None" not in html


@pytest.mark.django_db
def test_character_list_escapes_sheet_values(client, user_factory, character_factory):
    owner = user_factory()
    character_factory(
        owner=owner, display_name="<b>X</b>", values={"c1_career_path": "<script>alert(1)</script>"}
    )
    client.force_login(owner)
    html = client.get("/characters/").content.decode()

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    assert "<b>X</b>" not in html


@pytest.mark.django_db
def test_character_list_never_shows_another_users_character_card(
    client, user_factory, character_factory
):
    owner = user_factory()
    other = user_factory()
    character_factory(owner=owner, display_name="Own", values={"c1_career_path": "Arch-Militant"})
    foreign = character_factory(
        owner=other, display_name="Foreign Captain", values={"c1_career_path": "Navigator"}
    )
    client.force_login(owner)
    response = client.get("/characters/")
    html = response.content.decode()

    assert "Arch-Militant" in html
    assert "Foreign Captain" not in html
    assert "Navigator" not in html
    assert str(foreign.id) not in html
    assert [card["name"] for card in response.context["cards"]] == ["Own"]


@pytest.mark.django_db
def test_character_list_empty_state_points_at_create_form(client, user_factory):
    owner = user_factory()
    client.force_login(owner)
    html = client.get("/characters/").content.decode()

    assert "Noch keine Charaktere vorhanden." in html
    assert 'href="#create-character"' in html
    assert 'id="create-character"' in html
    assert 'name="display_name"' in html
    assert 'id="id_display_name"' in html


def _query_count(client, url):
    with CaptureQueriesContext(connection) as queries:
        assert client.get(url).status_code == 200
    return len(queries)


@pytest.mark.django_db
def test_character_list_query_count_does_not_grow_per_character(
    client, owner, character_factory
):
    client.force_login(owner)
    character_factory(owner=owner, display_name="One", values=FILLED_VALUES)
    baseline = _query_count(client, "/characters/")
    for index in range(3):
        character_factory(owner=owner, display_name=f"More {index}", values=FILLED_VALUES)
    assert _query_count(client, "/characters/") == baseline

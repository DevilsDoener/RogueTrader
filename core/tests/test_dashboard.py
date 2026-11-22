"""Content and role tests for the authenticated dashboard (``GET /dashboard/``).

The dashboard is the Kommandobrücke: the rulebook search, a selection of the
caller's own characters as dossier tiles, the single shared ship and grouped
rule shortcuts. It carries no wiki chapter list (the wiki is reached through
the nav, the palette and the search). It must never leak another user's
characters, must gate the portal-admin navigation on ``is_portal_admin``, and
must never fabricate statistics for an empty state.
"""
from datetime import timedelta

import pytest
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from tests.html import attr, has_link, select, select_one, text, texts
from tests.support import count_queries
from wiki.content import WikiRepository, set_repository_for_tests
from wiki.manifest import DASHBOARD_SHORTCUTS


def _set_wiki_chapters(settings, tmp_path, filenames_and_titles):
    for filename, title in filenames_and_titles:
        (tmp_path / filename).write_text(f"# {title}\nContent", encoding="utf-8")
    settings.WIKI_CONTENT_ROOT = tmp_path
    settings.WIKI_CONTENT_ALLOWLIST = [name for name, _ in filenames_and_titles]
    set_repository_for_tests(WikiRepository.load())


def test_dashboard_requires_login(client):
    response = client.get(reverse("dashboard"))

    assert response.status_code == 302
    assert response.url.startswith("/account/login/")


def test_dashboard_shows_only_the_caller_owned_characters(
    client, owner, other_user, character_factory
):
    character_factory(owner=owner, display_name="Lucian Voss")
    character_factory(owner=other_user, display_name="Someone Else's Rogue")
    client.force_login(owner)

    response = client.get(reverse("dashboard"))
    content = response.content.decode()

    assert "Lucian Voss" in content
    assert "Someone Else's Rogue" not in content


def test_dashboard_never_queries_all_characters_for_a_normal_user(
    client, owner, other_user, character_factory
):
    character_factory(owner=other_user, display_name="Not Mine")
    client.force_login(owner)

    response = client.get(reverse("dashboard"))

    assert response.context["character_tiles"] == []


def test_dashboard_limits_to_five_most_recently_updated_characters(
    client, owner, character_factory
):
    for index in range(7):
        character_factory(owner=owner, display_name=f"Character {index}")
    client.force_login(owner)

    response = client.get(reverse("dashboard"))

    assert len(response.context["character_tiles"]) == 5


def test_dashboard_orders_characters_by_most_recently_updated(
    client, owner, character_factory
):
    older = character_factory(owner=owner, display_name="Older")
    newer = character_factory(owner=owner, display_name="Newer")
    # ``updated_at`` is an auto_now field, so set both explicitly via
    # ``.update()`` (which bypasses auto_now) to get a deterministic,
    # unambiguous ordering instead of relying on two saves landing in
    # different timestamp ticks.
    now = timezone.now()
    type(older).objects.filter(pk=older.pk).update(updated_at=now - timedelta(hours=1))
    type(newer).objects.filter(pk=newer.pk).update(updated_at=now)

    client.force_login(owner)
    response = client.get(reverse("dashboard"))

    names = [tile["name"] for tile in response.context["character_tiles"]]
    assert names.index("Newer") < names.index("Older")


def test_dashboard_shows_the_shared_ship_for_any_authenticated_user(client, owner):
    # Every environment has exactly one seeded active ShipSheet (see
    # sheets/migrations/0002_seed_shared_ship.py) -- use it rather than
    # creating a second "active" ship, which would make "the" active ship
    # ambiguous.
    from sheets.models import ShipSheet

    ship = ShipSheet.objects.filter(is_active=True).order_by("id").first()
    client.force_login(owner)

    response = client.get(reverse("dashboard"))
    content = response.content.decode()

    assert response.context["ship"] == ship
    assert ship.display_name in content
    assert has_link(content, reverse("sheets:ship_detail", args=[ship.pk]))
    assert has_link(content, reverse("sheets:ship_history", args=[ship.pk]))


def test_dashboard_portal_admin_sees_admin_navigation(client, portal_admin):
    client.force_login(portal_admin)

    response = client.get(reverse("dashboard"))
    content = response.content.decode()

    assert reverse("accounts:admin_user_list") in content
    assert reverse("sheets:admin_character_list") in content


def test_dashboard_normal_user_does_not_see_admin_navigation(client, owner):
    client.force_login(owner)

    response = client.get(reverse("dashboard"))
    content = response.content.decode()

    assert reverse("accounts:admin_user_list") not in content
    assert reverse("sheets:admin_character_list") not in content


def test_dashboard_empty_state_links_to_character_creation_without_fake_stats(
    client, owner
):
    client.force_login(owner)

    response = client.get(reverse("dashboard"))
    content = response.content.decode()

    assert reverse("sheets:character_list") in content
    # No invented character/ship counts or percentages in the empty state.
    assert "%" not in content


def test_dashboard_has_no_wiki_chapter_list(client, owner, settings, tmp_path):
    _set_wiki_chapters(
        settings,
        tmp_path,
        [("01-First.md", "First Chapter"), ("02-Second.md", "Second Chapter")],
    )
    client.force_login(owner)

    response = client.get(reverse("dashboard"))
    content = response.content.decode()

    assert "First Chapter" not in content
    assert "Second Chapter" not in content
    assert select(content, "#wiki-panel-heading") == []
    assert "chapters" not in response.context
    assert "wiki_parts" not in response.context
    # The wiki itself stays one click away (nav, palette, hero search).
    assert has_link(content, reverse("wiki:index"))


def test_dashboard_search_form_posts_to_search_route(client, owner):
    client.force_login(owner)

    response = client.get(reverse("dashboard"))
    content = response.content.decode()

    form = select_one(content, "form.dashboard-search")
    assert attr(form, "action") == reverse("wiki:search")
    assert select(form, "input#dashboard-search-input")


# -- Charakterauswahl --------------------------------------------------------


def _tile_names(content):
    """Character names in the order their tiles appear."""
    return texts(content, "a.bridge-crew-link")


def test_character_tiles_are_most_recent_first_with_values(
    client, owner, character_factory
):
    older = character_factory(
        owner=owner,
        display_name="Older Rogue",
        values={"c1_ws_value": "31", "c1_career_path": "Void-Master"},
    )
    newer = character_factory(
        owner=owner,
        display_name="Lucian Voss",
        values={
            "c1_career_path": "Rogue Trader",
            "c1_rank": "2",
            "c1_home_world": "Void Born",
            "c1_ws_value": "42",
            "c1_fel_value": "47",
            "c2_wounds_current": "11",
            "c2_wounds_total": "14",
            "c2_fate_points_current": "2",
            "c2_fate_points_total": "3",
            "c1_xp_to_spend": "450",
        },
    )
    now = timezone.now()
    type(older).objects.filter(pk=older.pk).update(updated_at=now - timedelta(hours=1))
    type(newer).objects.filter(pk=newer.pk).update(updated_at=now)
    client.force_login(owner)

    content = client.get(reverse("dashboard")).content.decode()

    assert _tile_names(content) == ["Lucian Voss", "Older Rogue"]
    detail_url = reverse("sheets:character_detail", args=[newer.pk])
    assert attr(select(content, "a.bridge-crew-link")[0], "href") == detail_url
    # Only the newest tile carries the marker, and it sits inside that tile.
    assert content.count("Zuletzt bearbeitet") == 1
    first_tile = select_one(content, "li.bridge-crew-tile.is-latest")
    tile_text = text(first_tile)
    assert "Lucian Voss" in tile_text
    assert "Zuletzt bearbeitet" in tile_text
    # Career and rank, but no home world on the compact tile.
    assert texts(first_tile, ".bridge-crew-meta") == ["Rogue Trader · Rank 2"]
    assert "Void Born" not in tile_text
    # The nine characteristics, Wounds and Fate -- not the roster-only XP chip.
    assert texts(first_tile, "dt") == ["WS", "BS", "S", "T", "Ag", "Int", "Per", "WP", "Fel"]
    values = texts(first_tile, "dd")
    assert "42" in values
    assert "47" in values
    assert texts(first_tile, ".crew-stat-value") == ["11 / 14", "2 / 3"]
    assert "XP to Spend" not in tile_text


def test_character_tiles_never_include_another_users_characters(
    client, owner, other_user, character_factory
):
    character_factory(owner=owner, display_name="Lucian Voss")
    foreign = character_factory(
        owner=other_user, display_name="Foreign Rogue", values={"c1_ws_value": "99"}
    )
    client.force_login(owner)

    response = client.get(reverse("dashboard"))
    content = response.content.decode()

    assert _tile_names(content) == ["Lucian Voss"]
    assert [tile["name"] for tile in response.context["character_tiles"]] == ["Lucian Voss"]
    assert "Foreign Rogue" not in content
    assert reverse("sheets:character_detail", args=[foreign.pk]) not in content
    assert "99" not in texts(content, "dd")


def test_character_selection_offers_a_new_character_tile(client, owner, character_factory):
    character_factory(owner=owner, display_name="Lucian Voss")
    client.force_login(owner)

    content = client.get(reverse("dashboard")).content.decode()

    create_url = f'{reverse("sheets:character_list")}?alle=1#create-character'
    assert attr(select_one(content, "a.bridge-crew-new"), "href") == create_url
    assert "Neuer Charakter" in content
    assert "Ersten Charakter erstellen" not in content


def test_character_selection_empty_state(client, owner, other_user, character_factory):
    character_factory(owner=other_user, display_name="Not Mine")
    client.force_login(owner)

    content = client.get(reverse("dashboard")).content.decode()

    assert "Noch keine Charaktere vorhanden." in content
    create_url = f'{reverse("sheets:character_list")}?alle=1#create-character'
    assert has_link(content, create_url, "Ersten Charakter erstellen")
    assert "bridge-crew-tile" not in content
    assert "Not Mine" not in content


# -- Regel-Shortcuts ---------------------------------------------------------


def _publish_shortcut_targets(settings, tmp_path):
    """A one-chapter corpus holding two of the Combat group's targets."""
    (tmp_path / "09-Playing-The-Game.md").write_text(
        "# Chapter IX: Playing the Game\n\n"
        "## Table 9-4: Combat Actions\nx\n\n## Fatigue\ny\n",
        encoding="utf-8",
    )
    settings.WIKI_CONTENT_ROOT = tmp_path
    settings.WIKI_CONTENT_ALLOWLIST = ["09-Playing-The-Game.md"]
    set_repository_for_tests(WikiRepository.load())


def test_rule_shortcuts_render_grouped_with_section_hrefs(
    client, owner, settings, tmp_path
):
    _publish_shortcut_targets(settings, tmp_path)
    client.force_login(owner)

    content = client.get(reverse("dashboard")).content.decode()
    chapter_url = reverse("wiki:chapter", kwargs={"chapter_slug": "playing-the-game"})

    assert "Regel-Shortcuts" in content
    assert texts(content, "h3.bridge-rule-title#bridge-rule-group-1") == ["Combat"]
    assert has_link(content, f"{chapter_url}#sec-table-9-4-combat-actions", "Combat Actions")
    assert has_link(content, f"{chapter_url}#sec-fatigue", "Fatigue")
    # Links whose target is not in this corpus -- and groups left empty by
    # that -- are dropped, never rendered as dead links.
    assert "Hit Locations" not in content
    assert "Psychic Powers" not in content
    assert "/wiki/armoury/" not in content


def test_rule_shortcuts_are_omitted_when_the_wiki_is_unavailable(
    client, owner, monkeypatch
):
    monkeypatch.setattr("wiki.content._repository", None)
    client.force_login(owner)

    response = client.get(reverse("dashboard"))

    assert response.status_code == 200
    assert response.context["shortcuts"] == ()
    assert "Regel-Shortcuts" not in response.content.decode()


@pytest.mark.parametrize("group", DASHBOARD_SHORTCUTS, ids=lambda group: group.glyph)
def test_every_shortcut_glyph_has_its_own_icon(group):
    fallback = render_to_string("core/_shortcut_glyph.html", {"glyph": "unknown"})

    assert "<svg" in fallback
    assert render_to_string("core/_shortcut_glyph.html", {"glyph": group.glyph}) != fallback


def test_dashboard_query_count_does_not_grow_per_character(client, owner, character_factory):
    client.force_login(owner)
    character_factory(owner=owner, display_name="One", values={"c1_ws_value": "1"})
    baseline = count_queries(client, reverse("dashboard"))
    for index in range(3):
        character_factory(owner=owner, display_name=f"More {index}", values={"c1_ws_value": "2"})
    assert count_queries(client, reverse("dashboard")) == baseline

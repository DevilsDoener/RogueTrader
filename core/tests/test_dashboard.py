"""Content and role tests for the authenticated dashboard (``GET /dashboard/``).

The dashboard is the "double command center" home page: a global search
entry point plus equally-weighted entries into the wiki and the caller's own
characters, alongside the single shared ship. It must never leak another
user's characters, must gate the portal-admin navigation on
``is_portal_admin``, and must never fabricate statistics for an empty state.
"""
from django.urls import reverse

from wiki.content import WikiRepository, set_repository_for_tests


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

    assert response.context["characters"] == []


def test_dashboard_limits_to_five_most_recently_updated_characters(
    client, owner, character_factory
):
    for index in range(7):
        character_factory(owner=owner, display_name=f"Character {index}")
    client.force_login(owner)

    response = client.get(reverse("dashboard"))

    assert len(response.context["characters"]) == 5


def test_dashboard_orders_characters_by_most_recently_updated(
    client, owner, character_factory
):
    from datetime import timedelta

    from django.utils import timezone

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

    names = [character.display_name for character in response.context["characters"]]
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

    assert response.context["ship"] == ship
    assert ship.display_name in response.content.decode()


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


def test_dashboard_shows_ordered_wiki_chapters(client, owner, settings, tmp_path):
    _set_wiki_chapters(
        settings,
        tmp_path,
        [("01-First.md", "First Chapter"), ("02-Second.md", "Second Chapter")],
    )
    client.force_login(owner)

    response = client.get(reverse("dashboard"))
    content = response.content.decode()

    assert "First Chapter" in content
    assert "Second Chapter" in content
    assert content.index("First Chapter") < content.index("Second Chapter")


def test_dashboard_search_form_posts_to_search_route(client, owner):
    client.force_login(owner)

    response = client.get(reverse("dashboard"))
    content = response.content.decode()

    assert f'action="{reverse("wiki:search")}"' in content

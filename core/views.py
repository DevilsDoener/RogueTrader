from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import redirect, render

from sheets.models import CharacterSheet, ShipSheet
from sheets.views import _character_card
from wiki.content import get_repository

#: The dashboard's character selection only ever shows a short,
#: recency-ordered slice -- the full roster lives at ``sheets:character_list``.
DASHBOARD_CHARACTER_LIMIT = 5

#: The ``_character_card`` stat chips a compact dashboard tile keeps (labels
#: from ``sheets.views.CARD_STATS``); XP and Profit Factor stay on the roster.
DASHBOARD_TILE_STATS: tuple[str, ...] = ("Wounds", "Fate")


def _dashboard_tile(character: CharacterSheet) -> dict:
    """A character-list card, trimmed to what a dashboard tile shows."""
    card = _character_card(character)
    card["stats"] = [stat for stat in card["stats"] if stat["label"] in DASHBOARD_TILE_STATS]
    return card


def root(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return redirect("accounts:login")


def health(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    return JsonResponse({"status": "ok", "database": "ok"})


@login_required
def dashboard(request):
    """The authenticated home page, the Kommandobrücke: rulebook search, a
    selection of the caller's own characters, the shared ship and grouped
    deep links into the most-used rule tables.

    Deliberately scoped to ``request.user`` -- this must never become a
    query over every user's characters (that is what the separate
    portal-admin routes are for).
    """
    characters = list(
        CharacterSheet.objects.filter(owner=request.user).order_by("-updated_at")[
            :DASHBOARD_CHARACTER_LIMIT
        ]
    )
    ship = ShipSheet.objects.filter(is_active=True).order_by("id").first()
    try:
        shortcuts = get_repository().dashboard_shortcuts()
    except RuntimeError:
        # The wiki content repository failed to initialize at startup (see
        # WikiConfig.ready()) -- drop the shortcuts rather than 500ing the
        # whole dashboard.
        shortcuts = ()

    return render(
        request,
        "core/dashboard.html",
        {
            "characters": characters,
            "character_tiles": [_dashboard_tile(character) for character in characters],
            "ship": ship,
            "shortcuts": shortcuts,
        },
    )

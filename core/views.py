from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import redirect, render

from sheets.cards import character_card
from sheets.permissions import characters_owned_by
from sheets.services import get_active_ship
from wiki.content import get_repository_or_none

#: The dashboard's character selection only ever shows a short,
#: recency-ordered slice -- the full roster lives at ``sheets:character_list``.
DASHBOARD_CHARACTER_LIMIT = 5

#: The ``sheets.cards.CARD_STATS`` chips (by key) a compact dashboard tile
#: keeps; XP and Profit Factor stay on the roster.
DASHBOARD_TILE_STATS: tuple[str, ...] = ("wounds", "fate")


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
    characters = (
        characters_owned_by(request.user)
        .defer("field_versions")
        .order_by("-updated_at")[:DASHBOARD_CHARACTER_LIMIT]
    )
    ship = get_active_ship()
    # Without a wiki repository (startup failed to load it, see
    # WikiConfig.ready()) the shortcuts are dropped rather than 500ing the
    # whole dashboard.
    repository = get_repository_or_none()
    shortcuts = repository.dashboard_shortcuts() if repository is not None else ()

    return render(
        request,
        "core/dashboard.html",
        {
            "character_tiles": [
                character_card(character, stat_keys=DASHBOARD_TILE_STATS)
                for character in characters
            ],
            "ship": ship,
            "shortcuts": shortcuts,
        },
    )

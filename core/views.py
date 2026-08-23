from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import redirect, render

from sheets.models import CharacterSheet, ShipSheet
from wiki.content import get_repository

#: The dashboard's "your characters" panel only ever shows a short,
#: recency-ordered slice -- the full roster lives at ``sheets:character_list``.
DASHBOARD_CHARACTER_LIMIT = 5


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
    """The authenticated home page: a double command center of global
    search plus equally-weighted entries into the wiki and the caller's own
    characters, alongside the single shared ship.

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
        chapters = get_repository().chapters()
    except RuntimeError:
        # The wiki content repository failed to initialize at startup (see
        # WikiConfig.ready()) -- degrade the wiki panel to empty rather than
        # 500ing the whole dashboard.
        chapters = ()

    return render(
        request,
        "core/dashboard.html",
        {
            "characters": characters,
            "ship": ship,
            "chapters": chapters,
        },
    )

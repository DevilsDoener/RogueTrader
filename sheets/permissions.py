"""Permission checks for character/ship sheet access.

Rules (see the design spec):
  * Normal users may view and mutate only their own characters.
  * Portal admins may view every character (through their own read-only
    views, see ``sheets.views``) but may not mutate or delete a character
    owned by someone else.
  * Every authenticated user may view and mutate the shared ship sheet.
"""
from __future__ import annotations

from django.db.models import QuerySet

from .models import CharacterSheet


def can_mutate_character(user, character: CharacterSheet) -> bool:
    return character.owner_id == getattr(user, "id", None)


def characters_owned_by(user) -> QuerySet[CharacterSheet]:
    """The queryset form of :func:`can_mutate_character`.

    The single owner-scoped starting point for every owner-facing character
    lookup (character list, detail, delete, dashboard): a character owned by
    someone else is simply not in it, so it is indistinguishable from one
    that doesn't exist. The portal-admin views deliberately do *not* use it.
    """
    return CharacterSheet.objects.filter(owner=user)


def can_view_ship(user) -> bool:
    """Every authenticated user may view the shared ship sheet."""
    return bool(getattr(user, "is_authenticated", False))


def can_mutate_ship(user) -> bool:
    """Every authenticated user may mutate the shared ship sheet."""
    return bool(getattr(user, "is_authenticated", False))

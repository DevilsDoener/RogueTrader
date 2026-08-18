"""Permission checks for character/ship sheet access.

Rules (see the design spec):
  * Normal users may view and mutate only their own characters.
  * Portal admins may view every character but may not mutate or delete a
    character owned by someone else.
  * Every authenticated user may view and mutate the shared ship sheet.
"""
from __future__ import annotations

from django.db.models import QuerySet

from .models import CharacterSheet


def can_view_character(user, character: CharacterSheet) -> bool:
    return character.owner_id == getattr(user, "id", None) or bool(
        getattr(user, "can_view_all_characters", lambda: False)()
    )


def can_mutate_character(user, character: CharacterSheet) -> bool:
    return character.owner_id == getattr(user, "id", None)


def visible_characters(user, queryset: QuerySet[CharacterSheet]) -> QuerySet[CharacterSheet]:
    """Restrict ``queryset`` to the characters ``user`` is allowed to view."""
    if user.can_view_all_characters():
        return queryset
    return queryset.filter(owner=user)


def can_view_ship(user) -> bool:
    """Every authenticated user may view the shared ship sheet."""
    return bool(getattr(user, "is_authenticated", False))


def can_mutate_ship(user) -> bool:
    """Every authenticated user may mutate the shared ship sheet."""
    return bool(getattr(user, "is_authenticated", False))

"""Permission checks for character/ship sheet access.

Rules (see the design spec):
  * Normal users may view and mutate only their own characters.
  * Portal admins may view every character but may not mutate or delete a
    character owned by someone else.
  * Every authenticated user may view and mutate the shared ship sheet.
"""
from __future__ import annotations

from .models import CharacterSheet


def can_view_character(user, character: CharacterSheet) -> bool:
    return character.owner_id == getattr(user, "id", None) or bool(
        getattr(user, "can_view_all_characters", lambda: False)()
    )


def can_mutate_character(user, character: CharacterSheet) -> bool:
    return character.owner_id == getattr(user, "id", None)


def can_view_ship(user) -> bool:
    """Every authenticated user may view the shared ship sheet."""
    return bool(getattr(user, "is_authenticated", False))


def can_mutate_ship(user) -> bool:
    """Every authenticated user may mutate the shared ship sheet."""
    return bool(getattr(user, "is_authenticated", False))

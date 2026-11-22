"""The nodes of the network and how forms and the graph refer to them.

A node is a main character (a player's favourite character sheet) or a side
figure. Forms and the graph JSON address both kinds with one string key:
``c:<uuid>`` for a character sheet, ``f:<uuid>`` for a figure.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from django.db.models import QuerySet

from sheets.models import CharacterSheet
from sheets.textsafety import display_text

from .models import NetworkFigure

CHARACTER_PREFIX = "c"
FIGURE_PREFIX = "f"
NO_CONNECTION = ""
NO_CONNECTION_LABEL = "keine"


def character_key(character: CharacterSheet) -> str:
    return f"{CHARACTER_PREFIX}:{character.pk}"


def figure_key(figure: NetworkFigure) -> str:
    return f"{FIGURE_PREFIX}:{figure.pk}"


def character_name(character: CharacterSheet) -> str:
    return display_text(character.display_name or "").strip() or "Unbenannter Charakter"


def character_label(character: CharacterSheet) -> str:
    """"Name (player)" -- names alone may repeat across players."""
    return f"{character_name(character)} ({character.owner.username})"


def main_characters() -> QuerySet[CharacterSheet]:
    """Every player's favourite: the main nodes, visible to every user.

    Only the columns the network shows are loaded -- never ``values``, which
    stay private to the sheet's owner.
    """
    return (
        CharacterSheet.objects.filter(is_favorite=True)
        .select_related("owner")
        .only("id", "display_name", "is_favorite", "owner__id", "owner__username")
        .order_by("display_name", "id")
    )


def node_choices(*, include_none: bool, exclude_key: str | None = None) -> list:
    """Choices for a "Verbindung zu" dropdown: main characters, then figures."""
    mains = [
        (character_key(c), character_label(c))
        for c in main_characters()
        if character_key(c) != exclude_key
    ]
    figures = [
        (figure_key(f), f.name)
        for f in NetworkFigure.objects.only("id", "name").order_by("name", "id")
        if figure_key(f) != exclude_key
    ]
    choices: list = [(NO_CONNECTION, NO_CONNECTION_LABEL)] if include_none else []
    if mains:
        choices.append(("Hauptcharaktere", mains))
    if figures:
        choices.append(("Nebenfiguren", figures))
    return choices


@dataclass(frozen=True)
class NodeRef:
    """A resolved node key: exactly one of ``character`` / ``figure`` is set."""

    character: CharacterSheet | None = None
    figure: NetworkFigure | None = None

    @property
    def key(self) -> str:
        if self.character is not None:
            return character_key(self.character)
        return figure_key(self.figure)

    @property
    def label(self) -> str:
        if self.character is not None:
            return character_label(self.character)
        return self.figure.name


def resolve(key: str) -> NodeRef | None:
    """The node a dropdown key names, or ``None`` if it is not selectable.

    Only main characters (favourites) can be picked; a character that is not
    a favourite is not part of the network's choices.
    """
    prefix, _, raw_id = (key or "").partition(":")
    try:
        pk = uuid.UUID(raw_id)
    except ValueError:
        return None
    if prefix == CHARACTER_PREFIX:
        character = main_characters().filter(pk=pk).first()
        return NodeRef(character=character) if character else None
    if prefix == FIGURE_PREFIX:
        figure = NetworkFigure.objects.filter(pk=pk).first()
        return NodeRef(figure=figure) if figure else None
    return None

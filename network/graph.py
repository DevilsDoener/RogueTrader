"""The JSON the Netzwerk page draws (``static/js/network-graph.js``).

Nodes: every main character (favourite), every character a connection still
points at although it is no longer a favourite, and every figure. A
character's sheet link is only included for its own owner -- the sheet itself
stays private, only name and player are shared.
"""
from __future__ import annotations

from django.urls import reverse

from sheets.models import CharacterSheet

from .models import NetworkFigure, NetworkLink
from .nodes import character_key, character_name, figure_key, main_characters


def _character_node(character: CharacterSheet, user) -> dict:
    own = character.owner_id == user.id
    return {
        "id": character_key(character),
        "kind": "main" if character.is_favorite else "character",
        "label": character_name(character),
        "player": character.owner.username,
        "url": reverse("sheets:character_detail", args=[character.pk]) if own else "",
    }


def graph_data(user) -> dict:
    links = list(
        NetworkLink.objects.select_related(
            "source_figure", "target_figure", "source_character__owner", "target_character__owner"
        ).order_by("created_at", "id")
    )
    characters = {c.pk: c for c in main_characters()}
    for link in links:
        for character in (link.source_character, link.target_character):
            if character is not None:
                characters.setdefault(character.pk, character)

    nodes = [_character_node(c, user) for c in characters.values()]
    nodes += [
        {
            "id": figure_key(figure),
            "kind": "figure",
            "label": figure.name,
            "faction": figure.faction,
            "metAt": figure.met_at,
            "description": figure.description,
            "url": reverse("network:figure_detail", args=[figure.pk]),
        }
        for figure in NetworkFigure.objects.order_by("name", "id")
    ]
    edges = [
        {
            "id": str(link.pk),
            "from": figure_key(link.source_figure)
            if link.source_figure
            else character_key(link.source_character),
            "to": figure_key(link.target_figure)
            if link.target_figure
            else character_key(link.target_character),
            "label": link.relation,
        }
        for link in links
    ]
    return {"nodes": nodes, "edges": edges}

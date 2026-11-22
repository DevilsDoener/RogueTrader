"""The campaign network: side figures, their connections, and a change log.

Main characters are not stored here. They are each player's favourite
:class:`~sheets.models.CharacterSheet` (``is_favorite``), so a connection end
points either at a :class:`NetworkFigure` or at a character sheet -- exactly
one of the two, enforced by check constraints. Everything here is shared:
every signed-in user sees and edits it (see ``network/permissions.py``).
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from sheets.models import CharacterSheet

NAME_MAX_LENGTH = 120
FACTION_MAX_LENGTH = 120
MET_AT_MAX_LENGTH = 200
DESCRIPTION_MAX_LENGTH = 2000
RELATION_MAX_LENGTH = 120


class NetworkFigure(models.Model):
    """A side figure the group met: relative, contact, rival, officer ..."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=NAME_MAX_LENGTH)
    faction = models.CharField(max_length=FACTION_MAX_LENGTH, blank=True)
    met_at = models.CharField(max_length=MET_AT_MAX_LENGTH, blank=True)
    description = models.TextField(max_length=DESCRIPTION_MAX_LENGTH, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="network_figures",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.name


def _exactly_one(prefix: str) -> models.Q:
    figure = {f"{prefix}_figure__isnull": False, f"{prefix}_character__isnull": True}
    character = {f"{prefix}_figure__isnull": True, f"{prefix}_character__isnull": False}
    return models.Q(**figure) | models.Q(**character)


class NetworkLink(models.Model):
    """A directed connection: ``source`` -- ``relation`` --> ``target``.

    Read as "Kara -> Schwester von -> Elias". Each end is a figure or a
    character sheet; deleting either end deletes the connection.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_figure = models.ForeignKey(
        NetworkFigure, on_delete=models.CASCADE, null=True, blank=True, related_name="+"
    )
    source_character = models.ForeignKey(
        CharacterSheet, on_delete=models.CASCADE, null=True, blank=True, related_name="+"
    )
    target_figure = models.ForeignKey(
        NetworkFigure, on_delete=models.CASCADE, null=True, blank=True, related_name="+"
    )
    target_character = models.ForeignKey(
        CharacterSheet, on_delete=models.CASCADE, null=True, blank=True, related_name="+"
    )
    relation = models.CharField(max_length=RELATION_MAX_LENGTH)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="network_links",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=_exactly_one("source"), name="networklink_one_source"
            ),
            models.CheckConstraint(
                condition=_exactly_one("target"), name="networklink_one_target"
            ),
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.source} -> {self.relation} -> {self.target}"

    @property
    def source(self):
        return self.source_figure or self.source_character

    @property
    def target(self):
        return self.target_figure or self.target_character


class NetworkChange(models.Model):
    """Append-only log of every create/update/delete in the network.

    Stores a text snapshot (``label``, ``details``) rather than a foreign key,
    so an entry still reads correctly after its figure or link is gone.
    """

    class Action(models.TextChoices):
        CREATED = "created", "angelegt"
        UPDATED = "updated", "geändert"
        DELETED = "deleted", "gelöscht"

    class Subject(models.TextChoices):
        FIGURE = "figure", "Figur"
        LINK = "link", "Verbindung"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="network_changes",
    )
    action = models.CharField(max_length=10, choices=Action.choices)
    subject = models.CharField(max_length=10, choices=Subject.choices)
    label = models.CharField(max_length=400)
    details = models.TextField(blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at", "-id"]

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.get_subject_display()} {self.get_action_display()}: {self.label}"

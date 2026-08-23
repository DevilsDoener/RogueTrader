"""Persistence models for character and ship sheets.

Both sheet types store their field values as JSON blobs (``values``) keyed by
the field IDs defined in ``sheets/schema.py``, alongside a parallel
``field_versions`` map used for field-level optimistic concurrency (see
``sheets/services.py``). ``SheetChange`` is an append-only audit trail of
every field mutation, pointing at exactly one of the two sheet types.
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class CharacterSheet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="characters"
    )
    display_name = models.CharField(max_length=120)
    values = models.JSONField(default=dict)
    field_versions = models.JSONField(default=dict)
    version = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.display_name or str(self.id)


class ShipSheet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    display_name = models.CharField(max_length=120, default="Gemeinsames Schiff")
    values = models.JSONField(default=dict)
    field_versions = models.JSONField(default=dict)
    version = models.PositiveBigIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.display_name


class SheetChange(models.Model):
    """Append-only audit record for a single field mutation.

    Exactly one of ``character``/``ship`` must be set, enforced by the
    ``sheetchange_exactly_one_target`` check constraint.
    """

    character = models.ForeignKey(
        CharacterSheet,
        on_delete=models.CASCADE,
        related_name="changes",
        null=True,
        blank=True,
    )
    ship = models.ForeignKey(
        ShipSheet,
        on_delete=models.CASCADE,
        related_name="changes",
        null=True,
        blank=True,
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sheet_changes",
    )
    field_id = models.CharField(max_length=120)
    old_value = models.JSONField(null=True)
    new_value = models.JSONField(null=True)
    resulting_version = models.PositiveBigIntegerField()
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(character__isnull=False, ship__isnull=True)
                    | models.Q(character__isnull=True, ship__isnull=False)
                ),
                name="sheetchange_exactly_one_target",
            )
        ]

    def __str__(self) -> str:  # pragma: no cover - trivial
        target = self.character_id or self.ship_id
        return f"{target}:{self.field_id}@{self.resulting_version}"

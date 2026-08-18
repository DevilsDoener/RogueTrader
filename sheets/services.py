"""Transactional read/write services for character and ship sheets.

All mutations go through :func:`patch_character_field` / :func:`patch_ship_field`,
which enforce field-level optimistic concurrency: a write only succeeds if the
caller's ``base_version`` matches the field's current version. A same-field
conflict never silently overwrites the stored value -- it raises
:class:`FieldConflict` with the value/version that actually won.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from django.db import transaction
from django.utils import timezone

from . import schema
from .models import CharacterSheet, ShipSheet, SheetChange
from .permissions import (
    can_mutate_character,
    can_mutate_ship,
    can_view_character,
    can_view_ship,
)

__all__ = [
    "PatchResult",
    "SheetNotFound",
    "FieldValidationError",
    "FieldConflict",
    "patch_character_field",
    "patch_ship_field",
    "get_character_for_view",
    "get_ship_for_view",
    "delete_character",
]

#: The two schema pages whose fields together make up one character sheet.
CHARACTER_PAGE_IDS: tuple[str, ...] = ("character-page-1", "character-page-2")
SHIP_PAGE_ID = "ship-page"

#: Updating this field also keeps CharacterSheet.display_name in sync so it
#: can be used for listing/labelling characters without re-reading `values`.
_CHARACTER_NAME_FIELD_ID = "c1_character_name"


@dataclass(frozen=True)
class PatchResult:
    field_id: str
    value: str | bool
    version: int
    saved_at: datetime


class SheetNotFound(Exception):
    """Raised when a sheet doesn't exist, or the actor may not view it."""


class FieldValidationError(Exception):
    """Raised when ``field_id`` is unknown or ``value`` fails schema validation."""

    def __init__(self, *, field_id: str, message: str):
        self.field_id = field_id
        self.message = message
        super().__init__(message)


class FieldConflict(Exception):
    """Raised when ``base_version`` doesn't match the field's stored version."""

    def __init__(
        self,
        *,
        field_id: str,
        submitted_value: str | bool,
        current_value: str | bool,
        current_version: int,
    ):
        self.field_id = field_id
        self.submitted_value = submitted_value
        self.current_value = current_value
        self.current_version = current_version
        super().__init__(
            f"Field {field_id!r} was changed concurrently "
            f"(current version {current_version})"
        )


def _find_character_field_spec(field_id: str) -> schema.FieldSpec:
    for page_id in CHARACTER_PAGE_IDS:
        page_schema = schema.load_schema(page_id)
        for field_spec in page_schema.fields:
            if field_spec.id == field_id:
                return field_spec
    raise FieldValidationError(field_id=field_id, message=f"Unknown field id {field_id!r}")


def _validate_character_field(field_id: str, value) -> None:
    field_spec = _find_character_field_spec(field_id)
    try:
        field_spec.validate_value(value)
    except schema.SchemaError as exc:
        raise FieldValidationError(field_id=field_id, message=str(exc)) from exc


def _validate_ship_field(field_id: str, value) -> None:
    page_schema = schema.load_schema(SHIP_PAGE_ID)
    try:
        page_schema.validate_value(field_id, value)
    except schema.SchemaError as exc:
        raise FieldValidationError(field_id=field_id, message=str(exc)) from exc


def get_character_for_view(*, sheet_id: uuid.UUID, actor) -> CharacterSheet:
    """Fetch a character sheet for reading, respecting view permissions."""
    try:
        sheet = CharacterSheet.objects.get(pk=sheet_id)
    except CharacterSheet.DoesNotExist as exc:
        raise SheetNotFound(f"No character sheet {sheet_id}") from exc

    if not can_view_character(actor, sheet):
        raise SheetNotFound(f"No character sheet {sheet_id}")

    return sheet


def get_ship_for_view(*, sheet_id: uuid.UUID, actor) -> ShipSheet:
    """Fetch a ship sheet for reading. Every authenticated user may view it."""
    try:
        sheet = ShipSheet.objects.get(pk=sheet_id)
    except ShipSheet.DoesNotExist as exc:
        raise SheetNotFound(f"No ship sheet {sheet_id}") from exc

    if not can_view_ship(actor):
        raise SheetNotFound(f"No ship sheet {sheet_id}")

    return sheet


def _apply_field_patch(
    sheet,
    *,
    actor,
    field_id: str,
    value,
    base_version: int,
    validate,
    audit_kwargs: dict,
    on_value_applied=None,
) -> PatchResult:
    """Shared fetch-locked-sheet -> version-compare -> conflict -> mutate ->
    audit sequence used by both :func:`patch_character_field` and
    :func:`patch_ship_field`.

    ``sheet`` must already have been fetched with ``select_for_update()``
    inside an active transaction, and any permission check must already have
    passed -- this helper only owns the concurrency-critical part that is
    identical for both sheet types. ``validate`` raises
    :class:`FieldValidationError` for an unknown/invalid field. ``audit_kwargs``
    supplies the ``character=``/``ship=`` foreign key pair for the
    :class:`~sheets.models.SheetChange` record. ``on_value_applied``, if
    given, runs *after* the conflict check passes but *before* saving, so a
    caller can apply model-specific side effects (e.g. syncing
    ``CharacterSheet.display_name``) exactly once, only on a successful
    write -- it returns any extra field names that need to be added to
    ``update_fields``.
    """
    validate(field_id, value)

    current_version = sheet.field_versions.get(field_id, 0)
    old_value = sheet.values.get(field_id)
    if current_version != base_version:
        raise FieldConflict(
            field_id=field_id,
            submitted_value=value,
            current_value=old_value,
            current_version=current_version,
        )

    sheet.version += 1
    sheet.values[field_id] = value
    sheet.field_versions[field_id] = sheet.version
    update_fields = ["values", "field_versions", "version"]
    if on_value_applied is not None:
        update_fields.extend(on_value_applied(sheet, field_id, value) or [])
    sheet.save(update_fields=update_fields)

    SheetChange.objects.create(
        actor=actor,
        field_id=field_id,
        old_value=old_value,
        new_value=value,
        resulting_version=sheet.version,
        **audit_kwargs,
    )

    saved_at = getattr(sheet, "updated_at", None) or timezone.now()

    return PatchResult(field_id=field_id, value=value, version=sheet.version, saved_at=saved_at)


def _sync_character_display_name(sheet: CharacterSheet, field_id: str, value) -> list[str]:
    """``on_value_applied`` callback: keep ``display_name`` in sync with the
    ``c1_character_name`` field, only once the write has actually happened.
    """
    extra_fields = ["updated_at"]
    if field_id == _CHARACTER_NAME_FIELD_ID:
        sheet.display_name = value
        extra_fields.append("display_name")
    return extra_fields


@transaction.atomic
def patch_character_field(
    *, sheet_id: uuid.UUID, actor, field_id: str, value, base_version: int
) -> PatchResult:
    try:
        sheet = CharacterSheet.objects.select_for_update().get(pk=sheet_id)
    except CharacterSheet.DoesNotExist as exc:
        raise SheetNotFound(f"No character sheet {sheet_id}") from exc

    # Permission check happens before anything else is revealed about the
    # sheet's contents. Mutation is owner-only: a portal admin can *read* a
    # character they don't own (see get_character_for_view) but attempting
    # to mutate or delete it is indistinguishable from the sheet not
    # existing at all, per the brief's exact exception surface
    # (SheetNotFound / FieldValidationError / FieldConflict -- no separate
    # permission-denied exception).
    if not can_mutate_character(actor, sheet):
        raise SheetNotFound(f"No character sheet {sheet_id}")

    return _apply_field_patch(
        sheet,
        actor=actor,
        field_id=field_id,
        value=value,
        base_version=base_version,
        validate=_validate_character_field,
        audit_kwargs={"character": sheet, "ship": None},
        on_value_applied=_sync_character_display_name,
    )


@transaction.atomic
def patch_ship_field(
    *, sheet_id: uuid.UUID, actor, field_id: str, value, base_version: int
) -> PatchResult:
    try:
        sheet = ShipSheet.objects.select_for_update().get(pk=sheet_id)
    except ShipSheet.DoesNotExist as exc:
        raise SheetNotFound(f"No ship sheet {sheet_id}") from exc

    # Every authenticated user may mutate the shared ship -- there is no
    # ownership concept for it -- but the check is still made explicit
    # (rather than skipped) so the permission rule stays visible here and
    # doesn't silently rot if ship access ever needs restricting.
    if not can_mutate_ship(actor):
        raise SheetNotFound(f"No ship sheet {sheet_id}")

    return _apply_field_patch(
        sheet,
        actor=actor,
        field_id=field_id,
        value=value,
        base_version=base_version,
        validate=_validate_ship_field,
        audit_kwargs={"character": None, "ship": sheet},
    )


@transaction.atomic
def delete_character(*, sheet_id: uuid.UUID, actor) -> None:
    try:
        sheet = CharacterSheet.objects.select_for_update().get(pk=sheet_id)
    except CharacterSheet.DoesNotExist as exc:
        raise SheetNotFound(f"No character sheet {sheet_id}") from exc

    if not can_mutate_character(actor, sheet):
        raise SheetNotFound(f"No character sheet {sheet_id}")

    sheet.delete()

"""Transactional read/write services for character and ship sheets.

All mutations go through :func:`patch_character_field` / :func:`patch_ship_field`,
which enforce field-level optimistic concurrency: a write only succeeds if the
caller's ``base_version`` matches the field's current version. A same-field
conflict never silently overwrites the stored value -- it raises
:class:`FieldConflict` with the value/version that actually won.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field as dataclass_field
from datetime import datetime

from django.db import transaction
from django.utils import timezone

from . import characteristics, movement, schema
from .models import CharacterSheet, ShipSheet, SheetChange
from .permissions import (
    can_mutate_character,
    can_mutate_ship,
    can_view_ship,
)

__all__ = [
    "PatchResult",
    "SheetNotFound",
    "FieldValidationError",
    "FieldConflict",
    "patch_character_field",
    "patch_ship_field",
    "get_ship_for_view",
    "get_active_ship",
    "delete_character",
]

#: Updating this field also keeps CharacterSheet.display_name in sync so it
#: can be used for listing/labelling characters without re-reading `values`.
_CHARACTER_NAME_FIELD_ID = "c1_character_name"


@dataclass(frozen=True)
class PatchResult:
    field_id: str
    value: str | bool
    version: int
    saved_at: datetime
    calculated_fields: dict = dataclass_field(default_factory=dict)


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
    for page_id in schema.CHARACTER_PAGE_IDS:
        try:
            return schema.load_schema(page_id).field_by_id(field_id)
        except schema.SchemaError:
            continue
    raise FieldValidationError(field_id=field_id, message=f"Unknown field id {field_id!r}")


def _validate_character_field(field_id: str, value) -> None:
    field_spec = _find_character_field_spec(field_id)
    if field_spec.read_only:
        raise FieldValidationError(field_id=field_id, message="Dieses Feld wird aus Half Move berechnet.")
    try:
        field_spec.validate_value(value)
    except schema.SchemaError as exc:
        raise FieldValidationError(field_id=field_id, message=str(exc)) from exc


def _validate_ship_field(field_id: str, value) -> None:
    page_schema = schema.load_schema(schema.SHIP_PAGE_ID)
    try:
        field_spec = page_schema.field_by_id(field_id)
    except schema.SchemaError as exc:
        raise FieldValidationError(field_id=field_id, message=str(exc)) from exc
    if field_spec.read_only:
        raise FieldValidationError(field_id=field_id, message="Dieses Feld ist schreibgeschützt.")
    try:
        field_spec.validate_value(value)
    except schema.SchemaError as exc:
        raise FieldValidationError(field_id=field_id, message=str(exc)) from exc


def get_ship_for_view(*, sheet_id: uuid.UUID, actor) -> ShipSheet:
    """Fetch a ship sheet for reading. Every authenticated user may view it."""
    try:
        sheet = ShipSheet.objects.get(pk=sheet_id)
    except ShipSheet.DoesNotExist as exc:
        raise SheetNotFound(f"No ship sheet {sheet_id}") from exc

    if not can_view_ship(actor):
        raise SheetNotFound(f"No ship sheet {sheet_id}")

    return sheet


def get_active_ship() -> ShipSheet | None:
    """The shared ship the portal links to: the first active one.

    v1 always has exactly one active ``ShipSheet`` (seeded by migration
    ``0002_seed_shared_ship``), although the model supports more.
    """
    return ShipSheet.objects.filter(is_active=True).order_by("id").first()


def _record_change(sheet, *, actor, field_id: str, old_value, new_value) -> None:
    """The one place that writes a :class:`~sheets.models.SheetChange` row:
    the target foreign key (``character`` or ``ship``) follows the sheet's type,
    and the row always carries the sheet's current version.
    """
    target = {"character": sheet} if isinstance(sheet, CharacterSheet) else {"ship": sheet}
    SheetChange.objects.create(
        actor=actor,
        field_id=field_id,
        old_value=old_value,
        new_value=new_value,
        resulting_version=sheet.version,
        **target,
    )


def _saved_at(sheet) -> datetime:
    """A character's auto_now ``updated_at`` was just refreshed by ``save()``;
    the ship has no timestamp column of its own.
    """
    return sheet.updated_at if isinstance(sheet, CharacterSheet) else timezone.now()


def _apply_field_patch(
    sheet,
    *,
    actor,
    field_id: str,
    value,
    base_version: int,
    validate,
    on_value_applied=None,
    calculated_fields: dict | None = None,
    derived_consistent=None,
) -> PatchResult:
    """Shared fetch-locked-sheet -> version-compare -> conflict -> mutate ->
    audit sequence used by both :func:`patch_character_field` and
    :func:`patch_ship_field`.

    ``sheet`` must already have been fetched with ``select_for_update()``
    inside an active transaction, and any permission check must already have
    passed -- this helper only owns the concurrency-critical part that is
    identical for both sheet types. ``validate`` raises
    :class:`FieldValidationError` for an unknown/invalid field. The audit
    :class:`~sheets.models.SheetChange` is written by :func:`_record_change`.
    ``on_value_applied``, if
    given, runs *after* the conflict check passes but *before* saving, so a
    caller can apply model-specific side effects (e.g. syncing
    ``CharacterSheet.display_name``) exactly once, only on a successful
    write -- it returns any extra field names that need to be added to
    ``update_fields``. ``calculated_fields`` (filled in by that callback) is
    passed through to :attr:`PatchResult.calculated_fields`.

    Writing the value a field already holds is a no-op: nothing is saved or
    audited and the field's current version is returned. That shortcut applies
    only while ``derived_consistent(sheet, field_id, value)`` (if given) says
    every server-derived counterpart already holds its derived value; if one
    has drifted, the write goes through so the derived fields are resynced.
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

    unchanged = field_id in sheet.values and type(old_value) is type(value) and old_value == value
    if unchanged and (derived_consistent is None or derived_consistent(sheet, field_id, value)):
        return PatchResult(
            field_id=field_id,
            value=value,
            version=current_version,
            saved_at=_saved_at(sheet),
            calculated_fields={},
        )

    sheet.version += 1
    sheet.values[field_id] = value
    sheet.field_versions[field_id] = sheet.version
    update_fields = ["values", "field_versions", "version"]
    if on_value_applied is not None:
        update_fields.extend(on_value_applied(sheet, field_id, value) or [])
    sheet.save(update_fields=update_fields)

    _record_change(sheet, actor=actor, field_id=field_id, old_value=old_value, new_value=value)

    return PatchResult(
        field_id=field_id,
        value=value,
        version=sheet.version,
        saved_at=_saved_at(sheet),
        calculated_fields=calculated_fields if calculated_fields is not None else {},
    )


def _derived_character_values(field_id: str, value) -> list[tuple[str, object]]:
    """The server-derived ``(field_id, value)`` pairs a write to ``field_id``
    implies: the same characteristic on the other printed page, or the
    movement fields computed from Half Move.
    """
    derived: list[tuple[str, object]] = []
    counterpart = characteristics.counterpart(field_id)
    if counterpart is not None:
        derived.append((counterpart, value))
    if field_id == movement.SOURCE:
        derived.extend(movement.calculate(value).items())
    return derived


def _write_derived_field(
    sheet: CharacterSheet, *, actor, field_id: str, value, calculated: dict
) -> None:
    """Validate and write one derived field at the sheet's new version, audit
    it with its own :class:`~sheets.models.SheetChange` and record it in
    ``calculated`` for the response.
    """
    _find_character_field_spec(field_id).validate_value(value)
    old_value = sheet.values.get(field_id)
    sheet.values[field_id] = value
    sheet.field_versions[field_id] = sheet.version
    _record_change(sheet, actor=actor, field_id=field_id, old_value=old_value, new_value=value)
    calculated[field_id] = {"value": value, "version": sheet.version}


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
    # character they don't own (through the separate admin views) but attempting
    # to mutate or delete it is indistinguishable from the sheet not
    # existing at all -- the service only ever raises SheetNotFound /
    # FieldValidationError / FieldConflict, never a separate
    # permission-denied exception.
    if not can_mutate_character(actor, sheet):
        raise SheetNotFound(f"No character sheet {sheet_id}")

    calculated: dict = {}

    def apply_character_values(locked, changed_id, changed_value) -> list[str]:
        """``on_value_applied`` callback, run only once the write happens:
        keep ``display_name`` in sync with ``c1_character_name`` and write
        every derived field at the same new version.
        """
        extra_fields = ["updated_at"]
        if changed_id == _CHARACTER_NAME_FIELD_ID:
            locked.display_name = changed_value
            extra_fields.append("display_name")
        for target, derived_value in _derived_character_values(changed_id, changed_value):
            _write_derived_field(
                locked, actor=actor, field_id=target, value=derived_value, calculated=calculated
            )
        return extra_fields

    def derived_consistent(locked, changed_id, changed_value) -> bool:
        return all(
            target in locked.values
            and type(locked.values[target]) is type(derived_value)
            and locked.values[target] == derived_value
            for target, derived_value in _derived_character_values(changed_id, changed_value)
        )

    return _apply_field_patch(
        sheet,
        actor=actor,
        field_id=field_id,
        value=value,
        base_version=base_version,
        validate=_validate_character_field,
        on_value_applied=apply_character_values,
        calculated_fields=calculated,
        derived_consistent=derived_consistent,
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

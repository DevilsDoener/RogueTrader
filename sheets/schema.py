"""Coordinate schema for the printed character/ship sheet overlays.

Each of the three source pages (``character-page-1``, ``character-page-2``,
``ship-page``) has a JSON file under ``sheets/data/`` describing the
rectangular overlay fields that sit on top of its background image (see
``tools/extract_sheet_assets.py`` and ``tools/sheet_mapper.html``). This
module parses that JSON into frozen, validated dataclasses and exposes
``load_schema()`` for the rest of the app to consume.

Coordinates are stored as percentages of the background image's width/height
(0-100), quantized to four decimal places, so the same schema works
regardless of the pixel resolution the image is ultimately rendered at.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

DATA_DIR = Path(__file__).resolve().parent / "data"

#: The only page IDs ``load_schema`` will accept. Keeping this as an explicit
#: allow-list (rather than "whatever JSON files exist on disk") means a typo
#: in a filename fails loudly instead of silently returning nothing.
KNOWN_PAGE_IDS: tuple[str, ...] = ("character-page-1", "character-page-2", "ship-page")

FieldKind = Literal["text", "checkbox"]
_VALID_KINDS: tuple[FieldKind, ...] = ("text", "checkbox")

#: Coordinates/sizes are quantized to four decimal places (percentages of the
#: background image's width/height).
_QUANTUM = Decimal("0.0001")
_HUNDRED = Decimal("100")


class SchemaError(ValueError):
    """Raised when a schema JSON payload fails structural or value validation."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SchemaError(message)


def _quantize_coordinate(value: Any, *, field_id: str, name: str) -> Decimal:
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise SchemaError(
            f"field {field_id!r}: {name} is not a valid number: {value!r}"
        ) from exc
    return decimal_value.quantize(_QUANTUM, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class FieldSpec:
    """A single overlay field positioned on a sheet background image.

    ``x``/``y``/``width``/``height`` are percentages (0-100) of the
    background image's dimensions, quantized to four decimal places.
    """

    id: str
    kind: FieldKind
    x: Decimal
    y: Decimal
    width: Decimal
    height: Decimal
    max_length: int
    label: str

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "FieldSpec":
        for key in ("id", "kind", "x", "y", "width", "height", "max_length", "label"):
            _require(key in payload, f"field is missing required key {key!r}: {payload!r}")

        field_id = payload["id"]
        _require(
            isinstance(field_id, str) and field_id.strip() != "",
            f"field id must be a non-empty string, got {field_id!r}",
        )

        kind = payload["kind"]
        _require(
            kind in _VALID_KINDS,
            f"field {field_id!r}: kind must be one of {_VALID_KINDS}, got {kind!r}",
        )

        x = _quantize_coordinate(payload["x"], field_id=field_id, name="x")
        y = _quantize_coordinate(payload["y"], field_id=field_id, name="y")
        width = _quantize_coordinate(payload["width"], field_id=field_id, name="width")
        height = _quantize_coordinate(payload["height"], field_id=field_id, name="height")

        _require(width > 0, f"field {field_id!r}: width must be positive, got {width}")
        _require(height > 0, f"field {field_id!r}: height must be positive, got {height}")
        _require(0 <= x < _HUNDRED, f"field {field_id!r}: x out of bounds [0, 100): {x}")
        _require(0 <= y < _HUNDRED, f"field {field_id!r}: y out of bounds [0, 100): {y}")
        _require(
            x + width <= _HUNDRED,
            f"field {field_id!r}: x + width exceeds 100: {x} + {width} = {x + width}",
        )
        _require(
            y + height <= _HUNDRED,
            f"field {field_id!r}: y + height exceeds 100: {y} + {height} = {y + height}",
        )

        max_length = payload["max_length"]
        _require(
            isinstance(max_length, int) and not isinstance(max_length, bool) and max_length > 0,
            f"field {field_id!r}: max_length must be a positive integer, got {max_length!r}",
        )

        label = payload["label"]
        _require(
            isinstance(label, str) and label.strip() != "",
            f"field {field_id!r}: label must be a non-empty string, got {label!r}",
        )

        return cls(
            id=field_id,
            kind=kind,
            x=x,
            y=y,
            width=width,
            height=height,
            max_length=max_length,
            label=label,
        )

    def validate_value(self, value: Any) -> None:
        """Raise ``SchemaError`` if ``value`` is not valid for this field."""
        if self.kind == "checkbox":
            if not isinstance(value, bool):
                raise SchemaError(
                    f"field {self.id!r}: checkbox value must be a JSON boolean, got {value!r}"
                )
            return

        # kind == "text"
        if not isinstance(value, str):
            raise SchemaError(
                f"field {self.id!r}: text value must be a string, got {value!r}"
            )
        if len(value) > self.max_length:
            raise SchemaError(
                f"field {self.id!r}: text value exceeds max_length "
                f"{self.max_length} ({len(value)} characters)"
            )


@dataclass(frozen=True)
class SheetSchema:
    """The full set of overlay fields for one sheet background image."""

    page_id: str
    image_width: int
    image_height: int
    fields: tuple[FieldSpec, ...]

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SheetSchema":
        _require("page_id" in payload, "schema is missing required key 'page_id'")
        page_id = payload["page_id"]
        _require(
            isinstance(page_id, str) and page_id.strip() != "",
            f"page_id must be a non-empty string, got {page_id!r}",
        )

        _require("image" in payload, f"{page_id}: schema is missing required key 'image'")
        image = payload["image"]
        _require(
            isinstance(image, Mapping) and "width" in image and "height" in image,
            f"{page_id}: 'image' must be an object with 'width' and 'height'",
        )
        image_width = image["width"]
        image_height = image["height"]
        _require(
            isinstance(image_width, int) and not isinstance(image_width, bool) and image_width > 0,
            f"{page_id}: image.width must be a positive integer, got {image_width!r}",
        )
        _require(
            isinstance(image_height, int) and not isinstance(image_height, bool) and image_height > 0,
            f"{page_id}: image.height must be a positive integer, got {image_height!r}",
        )

        _require("fields" in payload, f"{page_id}: schema is missing required key 'fields'")
        raw_fields = payload["fields"]
        _require(
            isinstance(raw_fields, Sequence) and not isinstance(raw_fields, (str, bytes)),
            f"{page_id}: 'fields' must be a list",
        )

        fields: list[FieldSpec] = []
        seen_ids: set[str] = set()
        for raw_field in raw_fields:
            field_spec = FieldSpec.from_dict(raw_field)
            if field_spec.id in seen_ids:
                raise SchemaError(
                    f"{page_id}: duplicate field id {field_spec.id!r}"
                )
            seen_ids.add(field_spec.id)
            fields.append(field_spec)

        return cls(
            page_id=page_id,
            image_width=image_width,
            image_height=image_height,
            fields=tuple(fields),
        )

    def field_by_id(self, field_id: str) -> FieldSpec:
        for field_spec in self.fields:
            if field_spec.id == field_id:
                return field_spec
        raise SchemaError(f"{self.page_id}: unknown field id {field_id!r}")

    def validate_value(self, field_id: str, value: Any) -> None:
        """Raise ``SchemaError`` if ``value`` is not valid for ``field_id``."""
        self.field_by_id(field_id).validate_value(value)


@lru_cache(maxsize=None)
def load_schema(page_id: str) -> SheetSchema:
    """Load and cache the :class:`SheetSchema` for ``page_id``.

    Raises :class:`SchemaError` if ``page_id`` is not one of
    :data:`KNOWN_PAGE_IDS` or if the underlying JSON fails validation.
    """
    if page_id not in KNOWN_PAGE_IDS:
        raise SchemaError(
            f"Unknown page id {page_id!r}; expected one of {KNOWN_PAGE_IDS}"
        )

    path = DATA_DIR / f"{page_id}.json"
    if not path.exists():
        raise SchemaError(f"No schema file found for page id {page_id!r} at {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    return SheetSchema.from_dict(payload)

"""Coordinate schema for the printed character/ship sheet overlays.

Each source page (``character-page-1``, ``character-page-2``, ``ship-page``)
has a JSON file under ``sheets/data/`` describing the rectangular overlay
fields that sit on top of its background image. Those files are generated
from the layout sources in ``sheets/layouts/`` by ``sheets/layout.py``
(``python -m sheets.layout``). This module parses that JSON into frozen,
validated dataclasses and exposes ``load_schema()`` for the rest of the app
to consume.

Coordinates are stored as percentages of the background image's width/height
(0-100), quantized to four decimal places, so the same schema works
regardless of the pixel resolution the image is ultimately rendered at.
"""
from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from functools import cache, cached_property
from pathlib import Path
from typing import Any, Literal

from .textsafety import unsafe_text_problem

DATA_DIR = Path(__file__).resolve().parent / "data"

#: The two pages whose fields together make up one character sheet.
CHARACTER_PAGE_IDS: tuple[str, ...] = ("character-page-1", "character-page-2")

#: The single page of the shared ship sheet.
SHIP_PAGE_ID = "ship-page"

#: The only page IDs ``load_schema`` will accept. Keeping this as an explicit
#: allow-list (rather than "whatever JSON files exist on disk") means a typo
#: in a filename fails loudly instead of silently returning nothing.
KNOWN_PAGE_IDS: tuple[str, ...] = (*CHARACTER_PAGE_IDS, SHIP_PAGE_ID)

FieldKind = Literal["text", "checkbox"]
_VALID_KINDS: tuple[FieldKind, ...] = ("text", "checkbox")

#: Coordinates/sizes are quantized to four decimal places (percentages of the
#: background image's width/height).
_QUANTUM = Decimal("0.0001")
_HUNDRED = Decimal("100")


#: The 422 text for a value with control, bidi or non-UTF-8 characters
#: (see :mod:`sheets.textsafety`).
UNSAFE_TEXT_MESSAGE = (
    "Der Text enthält ungültige Zeichen (Steuerzeichen, Zeilenumbrüche, "
    "Richtungsumschalter oder nicht darstellbare Zeichen)."
)


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


def _parse_identity(payload: Mapping[str, Any]) -> tuple[str, FieldKind]:
    """The required keys, the field id and its kind."""
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
    return field_id, kind


def _parse_geometry(
    payload: Mapping[str, Any], field_id: str
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """``x``, ``y``, ``width``, ``height`` as quantized percentages inside the image."""
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
    return x, y, width, height


def _parse_content(payload: Mapping[str, Any], field_id: str) -> tuple[int, str]:
    """``max_length`` and the human ``label``."""
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
    return max_length, label


def _parse_styles(
    payload: Mapping[str, Any], field_id: str, kind: FieldKind
) -> tuple[str, str]:
    """``text_style`` and ``checkbox_style`` (and the legacy ``align`` they must agree with)."""
    text_style = payload.get(
        "text_style", "center" if payload.get("align") == "center" else "line"
    )
    _require(text_style in ("line", "center", "characteristic"),
             f"field {field_id!r}: invalid text_style {text_style!r}")
    checkbox_style = payload.get("checkbox_style", "square")
    _require(checkbox_style in ("square", "pip"),
             f"field {field_id!r}: invalid checkbox_style {checkbox_style!r}")
    # ``align`` is derived from ``text_style``; a stored ``align`` key is
    # still accepted (legacy layouts) but must agree with it.
    expected_align = "left" if text_style == "line" else "center"
    align = payload.get("align", expected_align)
    _require(
        align in ("left", "center"),
        f"field {field_id!r}: align must be 'left' or 'center', got {align!r}",
    )
    _require(align == expected_align,
             f"field {field_id!r}: align conflicts with text_style")
    _require(kind == "text" or text_style == "line",
             f"field {field_id!r}: checkbox cannot have text_style {text_style!r}")
    _require(kind == "checkbox" or checkbox_style == "square",
             f"field {field_id!r}: text field cannot have checkbox_style {checkbox_style!r}")
    return text_style, checkbox_style


def _parse_flags(
    payload: Mapping[str, Any], field_id: str, kind: FieldKind
) -> tuple[bool, str, tuple[int, int, int, int]]:
    """``read_only``, ``input_mode`` and the checkbox ``hit_padding``."""
    read_only = payload.get("read_only", False)
    _require(type(read_only) is bool and (kind == "text" or not read_only),
             f"field {field_id!r}: invalid read_only")
    input_mode = payload.get("input_mode", "text")
    _require(input_mode in ("text", "numeric"), f"field {field_id!r}: invalid input_mode")
    _require(kind == "text" or input_mode == "text", f"field {field_id!r}: checkbox input_mode")
    hit_padding = payload.get("hit_padding", [0, 0, 0, 0])
    _require(isinstance(hit_padding, (list, tuple)) and len(hit_padding) == 4
             and all(type(n) is int and 0 <= n <= 200 for n in hit_padding),
             f"field {field_id!r}: invalid hit_padding")
    _require(kind == "checkbox" or not any(hit_padding), f"field {field_id!r}: text hit_padding")
    return read_only, input_mode, tuple(hit_padding)


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
    #: How the value is styled: "line" sits bottom-left on the printed line,
    #: "center" / "characteristic" centre it in the box (see :attr:`align`).
    text_style: str = "line"
    checkbox_style: str = "square"
    input_mode: str = "text"
    read_only: bool = False
    hit_padding: tuple[int, int, int, int] = (0, 0, 0, 0)

    @property
    def align(self) -> str:
        """Horizontal text alignment, derived from :attr:`text_style`."""
        return "left" if self.text_style == "line" else "center"

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> FieldSpec:
        # The parsers run in this order, so the first failing rule wins
        # exactly as it always has (error messages and precedence are pinned
        # by the schema tests).
        field_id, kind = _parse_identity(payload)
        x, y, width, height = _parse_geometry(payload, field_id)
        max_length, label = _parse_content(payload, field_id)
        text_style, checkbox_style = _parse_styles(payload, field_id, kind)
        read_only, input_mode, hit_padding = _parse_flags(payload, field_id, kind)
        return cls(
            id=field_id,
            kind=kind,
            x=x,
            y=y,
            width=width,
            height=height,
            max_length=max_length,
            label=label,
            text_style=text_style,
            checkbox_style=checkbox_style,
            input_mode=input_mode,
            read_only=read_only,
            hit_padding=hit_padding,
        )

    def validate_value(self, value: Any) -> None:
        """Raise ``SchemaError`` if ``value`` is not valid for this field."""
        if self.kind == "checkbox":
            if not isinstance(value, bool):
                raise SchemaError(f"field {self.id!r}: checkbox value must be a JSON boolean")
            return

        # kind == "text"
        if not isinstance(value, str):
            raise SchemaError(f"field {self.id!r}: text value must be a string")
        if len(value) > self.max_length:
            raise SchemaError(
                f"field {self.id!r}: text value exceeds max_length "
                f"{self.max_length} ({len(value)} characters)"
            )
        if unsafe_text_problem(value) is not None:
            raise SchemaError(UNSAFE_TEXT_MESSAGE)
        if self.input_mode == "numeric" and value and not (value.isascii() and value.isdigit()):
            raise SchemaError(f"field {self.id!r}: enter a non-negative whole number")


@dataclass(frozen=True)
class SheetSchema:
    """The full set of overlay fields for one sheet background image."""

    page_id: str
    image_width: int
    image_height: int
    fields: tuple[FieldSpec, ...]

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> SheetSchema:
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
            isinstance(image_height, int)
            and not isinstance(image_height, bool)
            and image_height > 0,
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

    @cached_property
    def _fields_by_id(self) -> dict[str, FieldSpec]:
        return {field_spec.id: field_spec for field_spec in self.fields}

    def field_by_id(self, field_id: str) -> FieldSpec:
        try:
            return self._fields_by_id[field_id]
        except KeyError:
            raise SchemaError(f"{self.page_id}: unknown field id {field_id!r}") from None

    def validate_value(self, field_id: str, value: Any) -> None:
        """Raise ``SchemaError`` if ``value`` is not valid for ``field_id``."""
        self.field_by_id(field_id).validate_value(value)


@cache
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

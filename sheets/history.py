"""Display helpers for the ship's audit history (list rows and value text)."""
from __future__ import annotations

from django.urls import reverse

from .models import ShipSheet
from .schema import SHIP_PAGE_ID, SchemaError, load_schema
from .textsafety import display_text


def format_value(value) -> str:
    """Render a stored field value for the (privacy-conscious) audit history
    detail fragment. Booleans (checkbox fields) render as the German
    "markiert"/"nicht markiert" rather than True/False; everything else is
    rendered as plain text and left to the template to HTML-escape. ``None``
    (a field that had never been set before this change) renders as an
    em dash rather than the string "None".
    """
    if isinstance(value, bool):
        return "markiert" if value else "nicht markiert"
    if value is None:
        return "–"
    return display_text(str(value))


def history_rows(ship: ShipSheet, changes) -> list[dict]:
    """The metadata-only rows of the history list for ``changes``.

    One dict per change with the human field label (the raw field id when the
    schema no longer knows it) and the URL of its detail fragment. Never
    includes old/new values.
    """
    page_schema = load_schema(SHIP_PAGE_ID)
    rows = []
    for change in changes:
        try:
            field_label = page_schema.field_by_id(change.field_id).label
        except SchemaError:
            field_label = change.field_id
        rows.append(
            {
                "change": change,
                "field_label": field_label,
                "detail_url": reverse(
                    "sheets:ship_history_detail", args=[ship.pk, change.pk]
                ),
            }
        )
    return rows

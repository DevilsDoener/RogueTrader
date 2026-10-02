"""Template context for the sheet viewer pages.

Turns a stored sheet plus its page schemas into the dicts that
``sheets/character_detail.html``, ``sheets/ship_detail.html`` and the shared
``sheets/_sheet_viewer.html`` fragment render. Pure assembly -- no HTTP, no
writes -- so it is testable without the test client; ``sheets/views.py`` only
decides which sheet to show and whether it is read-only.
"""
from __future__ import annotations

from django.templatetags.static import static
from django.urls import reverse

from . import characteristics, movement
from .models import CharacterSheet, ShipSheet
from .schema import CHARACTER_PAGE_IDS, SHIP_PAGE_ID, load_schema
from .textsafety import display_text


def client_rules() -> dict:
    """The server-side sheet rules the viewer mirrors for its instant preview.

    Emitted as JSON next to the sheet (``_sheet_shell.html``) so the browser
    reads the same constants the server enforces instead of keeping copies.
    The server's ``calculated_fields`` answer stays authoritative.
    """
    return {
        "movement": {
            "source": movement.SOURCE,
            "factors": movement.FACTORS,
            "max_digits": movement.MAX_DIGITS,
        },
        "counterparts": characteristics.COUNTERPARTS,
    }


def page_contexts(sheet: CharacterSheet | ShipSheet, page_ids: tuple[str, ...]) -> list[dict]:
    """One dict per rendered page for ``sheets/_sheet_viewer.html``.

    ``fields`` pairs every schema field (in declared order) with the sheet's
    stored value and version for it, so the template never looks up stored
    keys itself -- unknown stored keys are simply never rendered. Stored text
    is passed through :func:`~sheets.textsafety.display_text`, so a value
    stored before the write path rejected such characters cannot break the
    page.
    """
    values = sheet.values or {}
    versions = sheet.field_versions or {}
    pages = []
    for page_id in page_ids:
        page_schema = load_schema(page_id)
        pages.append(
            {
                "page_id": page_id,
                "image_url": static(f"sheets/images/{page_id}.webp"),
                "width": page_schema.image_width,
                "height": page_schema.image_height,
                "fields": [
                    (
                        field_spec,
                        display_text(values.get(field_spec.id)),
                        versions.get(field_spec.id),
                    )
                    for field_spec in page_schema.fields
                ],
            }
        )
    return pages


def character_context(character: CharacterSheet, *, read_only: bool) -> dict:
    """Build the context consumed by ``sheets/character_detail.html`` (which
    itself includes ``sheets/_sheet_viewer.html``).

    Renders both background pages with overlay inputs; when ``read_only``
    is false those inputs are live and backed by the interactive
    autosave/conflict-resolution behaviour in ``sheet-viewer.js``.
    """
    field_update_url_template = None
    if not read_only:
        # A single reversed URL with a placeholder field id, filled in
        # client-side per field -- keeps the URL structure defined in one
        # place (urls.py) instead of duplicated in JS.
        field_update_url_template = reverse(
            "sheets:character_field_update", args=[character.pk, "__FIELD_ID__"]
        )
    return {
        "character": character,
        "read_only": read_only,
        "pages": page_contexts(character, CHARACTER_PAGE_IDS),
        "field_update_url_template": field_update_url_template,
        "client_rules": client_rules(),
    }


def ship_context(ship: ShipSheet) -> dict:
    """Build the context consumed by ``sheets/ship_detail.html`` (which
    includes the shared ``sheets/_sheet_viewer.html`` fragment). The ship
    viewer is always editable -- there is no read-only ship view.
    """
    return {
        "ship": ship,
        "read_only": False,
        "pages": page_contexts(ship, (SHIP_PAGE_ID,)),
        "field_update_url_template": reverse(
            "sheets:ship_field_update", args=[ship.pk, "__FIELD_ID__"]
        ),
    }

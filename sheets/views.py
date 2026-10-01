"""Owner-scoped character CRUD and separate read-only admin viewing.

Every owner-facing lookup starts from ``_owned_characters(request.user)`` (a thin
wrapper over ``CharacterSheet.objects.filter(owner=...)``) so a character owned by
someone else is indistinguishable from one that doesn't exist (404), matching the
permission model in ``sheets/permissions.py``.
The admin routes are entirely separate views/URLs -- they are never reused for
owner mutation -- and only ever render the sheet read-only.
"""
from __future__ import annotations

import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import QuerySet
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.views import View

from core.mixins import PortalAdminRequiredMixin

from . import characteristics, movement
from .cards import character_card
from .forms import CharacterCreateForm
from .models import CharacterSheet, SheetChange, ShipSheet
from .schema import CHARACTER_PAGE_IDS, SHIP_PAGE_ID, SchemaError, load_schema
from .services import (
    FieldConflict,
    FieldValidationError,
    SheetNotFound,
    delete_character,
    get_active_ship,
    get_ship_for_view,
    patch_character_field,
    patch_ship_field,
)

#: How many audit rows the ship history list shows per page.
SHIP_HISTORY_PAGE_SIZE = 50

#: Shared page template for both the owner and admin detail views; it includes
#: the ``_sheet_shell.html`` viewer and toggles destructive actions on
#: ``read_only``.
DETAIL_TEMPLATE_NAME = "sheets/character_detail.html"


def _character_client_rules() -> dict:
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


def _owned_characters(user) -> QuerySet[CharacterSheet]:
    """The single owner-scoped queryset every owner-facing lookup starts from."""
    return CharacterSheet.objects.filter(owner=user)


def _page_contexts(sheet: CharacterSheet | ShipSheet, page_ids: tuple[str, ...]) -> list[dict]:
    """One dict per rendered page for ``sheets/_sheet_viewer.html``.

    ``fields`` pairs every schema field (in declared order) with the sheet's
    stored value and version for it, so the template never looks up stored
    keys itself -- unknown stored keys are simply never rendered.
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
                    (field_spec, values.get(field_spec.id), versions.get(field_spec.id))
                    for field_spec in page_schema.fields
                ],
            }
        )
    return pages


def _character_viewer_context(character: CharacterSheet, *, read_only: bool) -> dict:
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
        "pages": _page_contexts(character, CHARACTER_PAGE_IDS),
        "field_update_url_template": field_update_url_template,
        "client_rules": _character_client_rules(),
    }


class CharacterListCreateView(LoginRequiredMixin, View):
    """``GET/POST /characters/`` -- list the caller's own characters, create a new one."""

    template_name = "sheets/character_list.html"

    def _render(self, request, form):
        characters = (
            _owned_characters(request.user).defer("field_versions").order_by("display_name")
        )
        return render(
            request,
            self.template_name,
            {
                "cards": [character_card(character) for character in characters],
                "form": form,
            },
        )

    def get(self, request):
        return self._render(request, CharacterCreateForm())

    def post(self, request):
        form = CharacterCreateForm(request.POST)
        if form.is_valid():
            character = form.save(commit=False)
            character.owner = request.user
            character.save()
            return redirect("sheets:character_detail", pk=character.pk)
        return self._render(request, form)


class CharacterDetailView(LoginRequiredMixin, View):
    """``GET /characters/<uuid>/`` -- read/write viewer for the caller's own character."""

    def get(self, request, pk):
        character = get_object_or_404(_owned_characters(request.user), pk=pk)
        return render(request, DETAIL_TEMPLATE_NAME, _character_viewer_context(character, read_only=False))


def _field_update_response(request, patch_fn, **patch_kwargs):
    """Shared JSON-envelope handling for the character/ship field-autosave
    endpoints. ``patch_fn`` is either :func:`patch_character_field` or
    :func:`patch_ship_field`; ``patch_kwargs`` supplies everything it needs
    except ``value``/``base_version``, which come from the parsed body.

    Only parses/validates the JSON envelope and translates the service's
    exceptions to the response contract (200/409/422/404) -- it never
    reveals whether a sheet the caller can't mutate even exists. The request
    must be ``application/json`` with exactly ``value`` and an integer
    ``base_version``. CSRF protection is enforced globally by
    ``CsrfViewMiddleware``.
    """
    if request.content_type != "application/json":
        return JsonResponse(
            {"error": "Content-Type must be application/json"}, status=400
        )

    try:
        payload = json.loads(request.body.decode("utf-8") or "null")
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "Malformed JSON body"}, status=400)

    if not isinstance(payload, dict) or set(payload.keys()) != {"value", "base_version"}:
        return JsonResponse(
            {"error": "Body must contain exactly 'value' and 'base_version'"},
            status=400,
        )

    base_version = payload["base_version"]
    if not isinstance(base_version, int) or isinstance(base_version, bool):
        return JsonResponse({"error": "base_version must be an integer"}, status=400)

    try:
        result = patch_fn(value=payload["value"], base_version=base_version, **patch_kwargs)
    except SheetNotFound as exc:
        raise Http404() from exc
    except FieldValidationError as exc:
        return JsonResponse({"field_id": exc.field_id, "error": exc.message}, status=422)
    except FieldConflict as exc:
        return JsonResponse(
            {
                "field_id": exc.field_id,
                "submitted_value": exc.submitted_value,
                "current_value": exc.current_value,
                "current_version": exc.current_version,
            },
            status=409,
        )

    body = {
        "field_id": result.field_id,
        "value": result.value,
        "version": result.version,
        "saved_at": result.saved_at.isoformat(),
    }
    if result.calculated_fields:
        body["calculated_fields"] = result.calculated_fields
    return JsonResponse(body)


class _FieldUpdateView(LoginRequiredMixin, View):
    """Strict JSON autosave endpoint: a thin HTTP wrapper around
    :attr:`patch_fn` via :func:`_field_update_response` -- all concurrency,
    permission, and validation logic lives in the service. Only ``POST`` is
    accepted (``View`` returns 405 for anything else since no other handler
    is defined).
    """

    #: :func:`sheets.services.patch_character_field` or ``patch_ship_field``.
    patch_fn = None

    def post(self, request, pk, field_id):
        return _field_update_response(
            request,
            type(self).patch_fn,
            sheet_id=pk,
            actor=request.user,
            field_id=field_id,
        )


class CharacterFieldUpdateView(_FieldUpdateView):
    """``POST /characters/<uuid>/fields/<field_id>/`` -- backed by
    :func:`sheets.services.patch_character_field`.
    """

    patch_fn = patch_character_field


class CharacterDeleteView(LoginRequiredMixin, View):
    """``GET`` shows a confirmation page; ``POST`` (CSRF-protected) deletes.

    Only the owner may reach a given character here -- the lookup is
    owner-scoped, so anyone else (including a portal admin) gets a 404.
    """

    template_name = "sheets/character_confirm_delete.html"

    def get(self, request, pk):
        character = get_object_or_404(_owned_characters(request.user), pk=pk)
        return render(request, self.template_name, {"character": character})

    def post(self, request, pk):
        character = get_object_or_404(_owned_characters(request.user), pk=pk)
        delete_character(sheet_id=character.pk, actor=request.user)
        return redirect("sheets:character_list")


class AdminCharacterListView(PortalAdminRequiredMixin, View):
    """``GET /portal-admin/characters/`` -- every character, for portal admins only."""

    template_name = "sheets/admin_character_list.html"

    def get(self, request):
        characters = (
            CharacterSheet.objects.select_related("owner")
            .defer("values", "field_versions")
            .order_by("owner__username", "display_name")
        )
        return render(request, self.template_name, {"characters": characters})


class AdminCharacterDetailView(PortalAdminRequiredMixin, View):
    """``GET /portal-admin/characters/<uuid>/`` -- read-only viewer for any character.

    This is a separate route from the owner detail view: it is never used to
    mutate or delete, has no save URLs, and always renders ``read_only=True``.
    """

    def get(self, request, pk):
        character = get_object_or_404(CharacterSheet, pk=pk)
        return render(request, DETAIL_TEMPLATE_NAME, _character_viewer_context(character, read_only=True))


# ---------------------------------------------------------------------------
# Shared ship sheet
#
# Unlike characters, the ship has no ownership: every authenticated user may
# view and mutate it (see ``sheets/permissions.py``). The first release
# creates exactly one active ``ShipSheet`` row (seeded by migration
# ``0002_seed_shared_ship``) while keeping the model shaped for more than
# one -- the list route below always resolves to "the" active ship rather
# than exposing any create/delete controls.
# ---------------------------------------------------------------------------


def _ship_or_404(pk, user) -> ShipSheet:
    """The ship ``pk`` if ``user`` may view it, else :class:`~django.http.Http404`."""
    try:
        return get_ship_for_view(sheet_id=pk, actor=user)
    except SheetNotFound as exc:
        raise Http404() from exc


def _ship_viewer_context(ship: ShipSheet) -> dict:
    """Build the context consumed by ``sheets/ship_detail.html`` (which
    includes the shared ``sheets/_sheet_viewer.html`` fragment). The ship
    viewer is always editable -- there is no read-only ship view.
    """
    return {
        "ship": ship,
        "read_only": False,
        "pages": _page_contexts(ship, (SHIP_PAGE_ID,)),
        "field_update_url_template": reverse(
            "sheets:ship_field_update", args=[ship.pk, "__FIELD_ID__"]
        ),
    }


def _format_history_value(value) -> str:
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
    return str(value)


class ShipRedirectView(LoginRequiredMixin, View):
    """``GET /ship/`` -- redirect to the single active shared ship.

    v1 always has exactly one active ``ShipSheet`` (seeded by a data
    migration); this route never lists or lets a caller choose between
    ships, even though the model itself supports more than one.
    """

    def get(self, request):
        ship = get_active_ship()
        if ship is None:
            raise Http404("No active ship sheet configured")
        return redirect("sheets:ship_detail", pk=ship.pk)


class ShipDetailView(LoginRequiredMixin, View):
    """``GET /ships/<uuid>/`` -- read/write viewer for the shared ship.

    Every authenticated user may reach this route (see
    ``sheets.permissions.can_view_ship``); there is no separate read-only
    ship view.
    """

    def get(self, request, pk):
        ship = _ship_or_404(pk, request.user)
        return render(request, "sheets/ship_detail.html", _ship_viewer_context(ship))


class ShipFieldUpdateView(_FieldUpdateView):
    """``POST /ships/<uuid>/fields/<field_id>/`` -- backed by
    :func:`sheets.services.patch_ship_field`.

    Every authenticated user may mutate the shared ship, so unlike the
    character endpoint a 404 here only ever means "no such sheet id" or "no
    such field", not "not yours".
    """

    patch_fn = patch_ship_field


class ShipHistoryListView(LoginRequiredMixin, View):
    """``GET /ships/<uuid>/history/`` -- metadata-only audit history.

    Shows timestamp, actor, and human field label for every change,
    paginated at :data:`SHIP_HISTORY_PAGE_SIZE`. Deliberately never
    includes old/new field values -- those are only ever rendered by
    :class:`ShipHistoryDetailView`, one change at a time, behind its own
    authenticated request (see that view's docstring).
    """

    template_name = "sheets/ship_history.html"

    def get(self, request, pk):
        ship = _ship_or_404(pk, request.user)

        page_schema = load_schema(SHIP_PAGE_ID)
        changes = ship.changes.select_related("actor").order_by("-changed_at", "-id")
        paginator = Paginator(changes, SHIP_HISTORY_PAGE_SIZE)
        page_obj = paginator.get_page(request.GET.get("page"))

        rows = []
        for change in page_obj.object_list:
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

        return render(
            request,
            self.template_name,
            {"ship": ship, "page_obj": page_obj, "rows": rows},
        )


class ShipHistoryDetailView(LoginRequiredMixin, View):
    """``GET /ships/<uuid>/history/<int:change_id>/`` -- one change's values.

    Returns a small HTML fragment (not a full page) with the escaped
    old/new value for exactly one :class:`~sheets.models.SheetChange`,
    fetched client-side only once a caller expands that row in the history
    list -- this is the only place old/new sheet content is ever rendered,
    and only to an authenticated request.
    """

    template_name = "sheets/_ship_history_detail.html"

    def get(self, request, pk, change_id):
        ship = _ship_or_404(pk, request.user)
        change = get_object_or_404(SheetChange, pk=change_id, ship=ship)
        return render(
            request,
            self.template_name,
            {
                "change": change,
                "old_display": _format_history_value(change.old_value),
                "new_display": _format_history_value(change.new_value),
            },
        )

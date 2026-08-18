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

from .forms import CharacterCreateForm
from .models import CharacterSheet, SheetChange, ShipSheet
from .schema import SchemaError, load_schema
from .services import (
    FieldConflict,
    FieldValidationError,
    SheetNotFound,
    delete_character,
    get_ship_for_view,
    patch_character_field,
    patch_ship_field,
)

#: The two schema pages rendered by the sheet viewer for a character.
CHARACTER_PAGE_IDS: tuple[str, ...] = ("character-page-1", "character-page-2")

#: The single schema page rendered by the sheet viewer for the shared ship.
SHIP_PAGE_IDS: tuple[str, ...] = ("ship-page",)

#: How many audit rows the ship history list shows per page.
SHIP_HISTORY_PAGE_SIZE = 50

#: Shared page template for both the owner and admin detail views; it includes
#: the ``_sheet_viewer.html`` fragment and toggles destructive actions on
#: ``read_only``.
DETAIL_TEMPLATE_NAME = "sheets/character_detail.html"


def _owned_characters(user) -> QuerySet[CharacterSheet]:
    """The single owner-scoped queryset every owner-facing lookup starts from."""
    return CharacterSheet.objects.filter(owner=user)


def _character_viewer_context(character: CharacterSheet, *, read_only: bool) -> dict:
    """Build the context consumed by ``sheets/character_detail.html`` (which
    itself includes ``sheets/_sheet_viewer.html``).

    Renders both background pages with overlay inputs; when ``read_only``
    is false those inputs are live and backed by the interactive
    autosave/conflict-resolution behaviour in ``sheet-viewer.js`` (Task 7).
    """
    pages = []
    for page_id in CHARACTER_PAGE_IDS:
        page_schema = load_schema(page_id)
        pages.append(
            {
                "page_id": page_id,
                "image_url": static(f"sheets/images/{page_id}.webp"),
                "width": page_schema.image_width,
                "height": page_schema.image_height,
                "fields": page_schema.fields,
            }
        )
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
        "sheet": character,
        "read_only": read_only,
        "pages": pages,
        "field_update_url_template": field_update_url_template,
    }


class CharacterListCreateView(LoginRequiredMixin, View):
    """``GET/POST /characters/`` -- list the caller's own characters, create a new one."""

    template_name = "sheets/character_list.html"

    def get(self, request):
        characters = _owned_characters(request.user).order_by("display_name")
        return render(
            request,
            self.template_name,
            {"characters": characters, "form": CharacterCreateForm()},
        )

    def post(self, request):
        form = CharacterCreateForm(request.POST)
        if form.is_valid():
            character = form.save(commit=False)
            character.owner = request.user
            character.save()
            return redirect("sheets:character_detail", pk=character.pk)
        characters = _owned_characters(request.user).order_by("display_name")
        return render(
            request,
            self.template_name,
            {"characters": characters, "form": form},
        )


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

    return JsonResponse(
        {
            "field_id": result.field_id,
            "value": result.value,
            "version": result.version,
            "saved_at": result.saved_at.isoformat(),
        }
    )


class CharacterFieldUpdateView(LoginRequiredMixin, View):
    """``POST /characters/<uuid>/fields/<field_id>/`` -- strict JSON autosave endpoint.

    A thin HTTP wrapper around :func:`sheets.services.patch_character_field`
    via :func:`_field_update_response`: all concurrency, permission, and
    validation logic lives in the service. Only ``POST`` is accepted
    (``View`` returns 405 for anything else since no other handler is
    defined).
    """

    def post(self, request, pk, field_id):
        return _field_update_response(
            request,
            patch_character_field,
            sheet_id=pk,
            actor=request.user,
            field_id=field_id,
        )


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
        characters = CharacterSheet.objects.select_related("owner").order_by(
            "owner__username", "display_name"
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
# creates exactly one active ``ShipSheet`` row (seeded by a Task 5 data
# migration) while keeping the model shaped for more than one -- the list
# route below always resolves to "the" active ship rather than exposing any
# create/delete controls.
# ---------------------------------------------------------------------------


def _ship_viewer_context(ship: ShipSheet) -> dict:
    """Build the context consumed by ``sheets/ship_detail.html`` (which
    includes the shared ``sheets/_sheet_viewer.html`` fragment). The ship
    viewer is always editable -- there is no read-only ship view.
    """
    pages = []
    for page_id in SHIP_PAGE_IDS:
        page_schema = load_schema(page_id)
        pages.append(
            {
                "page_id": page_id,
                "image_url": static(f"sheets/images/{page_id}.webp"),
                "width": page_schema.image_width,
                "height": page_schema.image_height,
                "fields": page_schema.fields,
            }
        )
    field_update_url_template = reverse(
        "sheets:ship_field_update", args=[ship.pk, "__FIELD_ID__"]
    )
    return {
        "ship": ship,
        "sheet": ship,
        "read_only": False,
        "pages": pages,
        "field_update_url_template": field_update_url_template,
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
        ship = ShipSheet.objects.filter(is_active=True).order_by("id").first()
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
        try:
            ship = get_ship_for_view(sheet_id=pk, actor=request.user)
        except SheetNotFound as exc:
            raise Http404() from exc
        return render(request, "sheets/ship_detail.html", _ship_viewer_context(ship))


class ShipFieldUpdateView(LoginRequiredMixin, View):
    """``POST /ships/<uuid>/fields/<field_id>/`` -- strict JSON autosave endpoint.

    Identical contract to :class:`CharacterFieldUpdateView`, backed by
    :func:`sheets.services.patch_ship_field` instead -- every authenticated
    user may mutate the shared ship, so unlike the character endpoint a 404
    here only ever means "no such sheet id" or "no such field", not "not
    yours".
    """

    def post(self, request, pk, field_id):
        return _field_update_response(
            request,
            patch_ship_field,
            sheet_id=pk,
            actor=request.user,
            field_id=field_id,
        )


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
        try:
            ship = get_ship_for_view(sheet_id=pk, actor=request.user)
        except SheetNotFound as exc:
            raise Http404() from exc

        page_schema = load_schema("ship-page")
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
        try:
            ship = get_ship_for_view(sheet_id=pk, actor=request.user)
        except SheetNotFound as exc:
            raise Http404() from exc

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

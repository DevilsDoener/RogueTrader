"""Owner-scoped character CRUD and separate read-only admin viewing.

Every owner-facing lookup starts from ``characters_owned_by(request.user)``
(``sheets/permissions.py``) so a character owned by someone else is
indistinguishable from one that doesn't exist (404).
The admin routes are entirely separate views/URLs -- they are never reused for
owner mutation -- and only ever render the sheet read-only.
"""
from __future__ import annotations

import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from core.mixins import PortalAdminRequiredMixin

from . import viewer
from .cards import character_card
from .forms import CharacterCreateForm
from .history import format_value, history_rows
from .models import CharacterSheet, SheetChange, ShipSheet
from .permissions import characters_owned_by
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


class CharacterListCreateView(LoginRequiredMixin, View):
    """``GET/POST /characters/`` -- list the caller's own characters, create a new one."""

    template_name = "sheets/character_list.html"

    def _render(self, request, form):
        characters = (
            characters_owned_by(request.user).defer("field_versions").order_by("display_name")
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
        character = get_object_or_404(characters_owned_by(request.user), pk=pk)
        return render(request, DETAIL_TEMPLATE_NAME, viewer.character_context(character, read_only=False))


#: A legitimate field-update body (``value`` of at most a few hundred
#: characters plus an integer version) is well under 1 KB; anything bigger is
#: rejected before it is parsed.
MAX_FIELD_BODY_BYTES = 4096


def _json_error(message: str, status: int) -> JsonResponse:
    return JsonResponse({"error": message}, status=status)


def _parse_patch_body(request):
    """Parse and check the field-update JSON envelope.

    Returns ``(value, base_version)``, or the :class:`JsonResponse` (400/413)
    to send back instead. The request must be ``application/json`` and at
    most :data:`MAX_FIELD_BODY_BYTES` long, with exactly ``value`` and an
    integer ``base_version``.
    """
    if request.content_type != "application/json":
        return _json_error("Content-Type must be application/json", 400)

    try:
        declared_length = int(request.META.get("CONTENT_LENGTH") or 0)
    except ValueError:
        return _json_error("Ungültige Anfrage.", 400)
    if declared_length > MAX_FIELD_BODY_BYTES:
        return _json_error("Die Anfrage ist zu groß.", 413)
    raw = request.body
    if len(raw) > MAX_FIELD_BODY_BYTES:
        return _json_error("Die Anfrage ist zu groß.", 413)

    try:
        payload = json.loads(raw.decode("utf-8") or "null")
    except (ValueError, UnicodeDecodeError, RecursionError):
        return _json_error("Malformed JSON body", 400)

    if not isinstance(payload, dict) or set(payload.keys()) != {"value", "base_version"}:
        return _json_error("Body must contain exactly 'value' and 'base_version'", 400)

    base_version = payload["base_version"]
    if not isinstance(base_version, int) or isinstance(base_version, bool):
        return _json_error("base_version must be an integer", 400)
    return payload["value"], base_version


def _field_update_response(request, patch_fn, **patch_kwargs):
    """Shared JSON-envelope handling for the character/ship field-autosave
    endpoints. ``patch_fn`` is either :func:`patch_character_field` or
    :func:`patch_ship_field`; ``patch_kwargs`` supplies everything it needs
    except ``value``/``base_version``, which come from the parsed body.

    Parses the envelope (:func:`_parse_patch_body`), calls the service and
    translates its exceptions to the response contract (200/409/422/404) --
    it never reveals whether a sheet the caller can't mutate even exists.
    CSRF protection is enforced globally by ``CsrfViewMiddleware``.
    """
    parsed = _parse_patch_body(request)
    if isinstance(parsed, JsonResponse):
        return parsed
    value, base_version = parsed

    try:
        result = patch_fn(value=value, base_version=base_version, **patch_kwargs)
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
        character = get_object_or_404(characters_owned_by(request.user), pk=pk)
        return render(request, self.template_name, {"character": character})

    def post(self, request, pk):
        character = get_object_or_404(characters_owned_by(request.user), pk=pk)
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
        return render(request, DETAIL_TEMPLATE_NAME, viewer.character_context(character, read_only=True))


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
        return render(request, "sheets/ship_detail.html", viewer.ship_context(ship))


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

        changes = ship.changes.select_related("actor").order_by("-changed_at", "-id")
        paginator = Paginator(changes, SHIP_HISTORY_PAGE_SIZE)
        page_obj = paginator.get_page(request.GET.get("page"))
        rows = history_rows(ship, page_obj.object_list)

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
                "old_display": format_value(change.old_value),
                "new_display": format_value(change.new_value),
            },
        )

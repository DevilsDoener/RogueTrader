"""Owner-scoped character CRUD and separate read-only admin viewing.

Every owner-facing lookup starts from ``CharacterSheet.objects.filter(owner=request.user)``
so a character owned by someone else is indistinguishable from one that
doesn't exist (404), matching the permission model in ``sheets/permissions.py``.
The admin routes are entirely separate views/URLs -- they are never reused for
owner mutation -- and only ever render the sheet read-only.
"""
from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.views import View

from .forms import CharacterCreateForm
from .models import CharacterSheet
from .schema import load_schema
from .services import delete_character

#: The two schema pages rendered by the sheet viewer for a character.
CHARACTER_PAGE_IDS: tuple[str, ...] = ("character-page-1", "character-page-2")


def _character_viewer_context(character: CharacterSheet, *, read_only: bool) -> dict:
    """Build the context consumed by ``sheets/_sheet_viewer.html``.

    This stub renders both background pages with disabled overlay inputs;
    Task 7 extends the same include with editing/save behaviour.
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
    return {"character": character, "read_only": read_only, "pages": pages}


class CharacterListCreateView(LoginRequiredMixin, View):
    """``GET/POST /characters/`` -- list the caller's own characters, create a new one."""

    template_name = "sheets/character_list.html"

    def _owned_characters(self, request):
        return CharacterSheet.objects.filter(owner=request.user).order_by("display_name")

    def get(self, request):
        return render(
            request,
            self.template_name,
            {"characters": self._owned_characters(request), "form": CharacterCreateForm()},
        )

    def post(self, request):
        form = CharacterCreateForm(request.POST)
        if form.is_valid():
            character = form.save(commit=False)
            character.owner = request.user
            character.save()
            return redirect("sheets:character_detail", pk=character.pk)
        return render(
            request,
            self.template_name,
            {"characters": self._owned_characters(request), "form": form},
        )


class CharacterDetailView(LoginRequiredMixin, View):
    """``GET /characters/<uuid>/`` -- read/write viewer for the caller's own character."""

    template_name = "sheets/_sheet_viewer.html"

    def get(self, request, pk):
        character = get_object_or_404(CharacterSheet.objects.filter(owner=request.user), pk=pk)
        return render(request, self.template_name, _character_viewer_context(character, read_only=False))


class CharacterDeleteView(LoginRequiredMixin, View):
    """``GET`` shows a confirmation page; ``POST`` (CSRF-protected) deletes.

    Only the owner may reach a given character here -- the lookup is
    owner-scoped, so anyone else (including a portal admin) gets a 404.
    """

    template_name = "sheets/character_confirm_delete.html"

    def get(self, request, pk):
        character = get_object_or_404(CharacterSheet.objects.filter(owner=request.user), pk=pk)
        return render(request, self.template_name, {"character": character})

    def post(self, request, pk):
        character = get_object_or_404(CharacterSheet.objects.filter(owner=request.user), pk=pk)
        delete_character(sheet_id=character.pk, actor=request.user)
        return redirect("sheets:character_list")


class PortalAdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    raise_exception = True

    def test_func(self):
        return self.request.user.is_portal_admin


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

    template_name = "sheets/_sheet_viewer.html"

    def get(self, request, pk):
        character = get_object_or_404(CharacterSheet, pk=pk)
        return render(request, self.template_name, _character_viewer_context(character, read_only=True))

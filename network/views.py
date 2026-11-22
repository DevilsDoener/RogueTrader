"""Netzwerk: the shared campaign graph and the pages to maintain it.

Every signed-in user sees and edits everything here (like the shared ship);
all writes go through :mod:`network.services`, which logs them.
"""
from __future__ import annotations

import uuid

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from . import services
from .forms import FigureCreateForm, FigureForm, LinkForm
from .graph import graph_data
from .models import NetworkChange, NetworkFigure, NetworkLink
from .nodes import figure_key, main_characters, resolve
from .services import node_label

HISTORY_PAGE_SIZE = 50


def _factions() -> list[str]:
    """Existing factions, for the <datalist> suggestions."""
    return list(
        NetworkFigure.objects.exclude(faction="")
        .order_by("faction")
        .values_list("faction", flat=True)
        .distinct()
    )


def _figure_data(form) -> dict:
    return {name: form.cleaned_data.get(name, "") for name, _ in services.FIGURE_FIELDS}


class GraphView(LoginRequiredMixin, View):
    """``GET /network/`` -- the graph, plus a plain list of every figure."""

    def get(self, request):
        figures = NetworkFigure.objects.order_by("name", "id")
        return render(
            request,
            "network/graph.html",
            {
                "figures": figures,
                "main_characters": main_characters(),
                "link_count": NetworkLink.objects.count(),
            },
        )


class GraphDataView(LoginRequiredMixin, View):
    """``GET /network/graph.json`` -- nodes and edges for the drawing."""

    def get(self, request):
        return JsonResponse(graph_data(request.user))


class FigureCreateView(LoginRequiredMixin, View):
    """``GET/POST /network/figures/new/`` -- a figure with an optional first connection."""

    template_name = "network/figure_form.html"

    def _render(self, request, form):
        return render(
            request,
            self.template_name,
            {"form": form, "factions": _factions(), "is_create": True},
        )

    def get(self, request):
        initial = {}
        if resolve(request.GET.get("zu", "")) is not None:
            initial["connect_to"] = request.GET["zu"]
        return self._render(request, FigureCreateForm(initial=initial))

    def post(self, request):
        form = FigureCreateForm(request.POST)
        if not form.is_valid():
            return self._render(request, form)
        figure = services.create_figure(
            actor=request.user,
            data=_figure_data(form),
            connect_to=form.cleaned_data["connect_node"],
            relation=form.cleaned_data.get("relation", ""),
        )
        return redirect("network:figure_detail", pk=figure.pk)


class FigureDetailView(LoginRequiredMixin, View):
    """``GET /network/figures/<uuid>/`` -- a figure, its connections, "add connection"."""

    def get(self, request, pk):
        figure = get_object_or_404(NetworkFigure, pk=pk)
        return render(
            request,
            "network/figure_detail.html",
            {
                "figure": figure,
                "connections": _connections(figure),
                "link_form": LinkForm(initial={"source": figure_key(figure)}),
            },
        )


def _connections(figure: NetworkFigure) -> list[dict]:
    """Both directions, each read from this figure's point of view."""
    links = NetworkLink.objects.filter(
        Q(source_figure=figure) | Q(target_figure=figure)
    ).select_related(
        "source_figure", "target_figure", "source_character__owner", "target_character__owner"
    ).order_by("created_at", "id")
    rows = []
    for link in links:
        outgoing = link.source_figure_id == figure.pk
        other_figure = link.target_figure if outgoing else link.source_figure
        other_character = link.target_character if outgoing else link.source_character
        rows.append(
            {
                "link": link,
                "outgoing": outgoing,
                "other_label": node_label(other_figure, other_character),
                "other_figure": other_figure,
            }
        )
    return rows


class FigureEditView(LoginRequiredMixin, View):
    """``GET/POST /network/figures/<uuid>/edit/``."""

    template_name = "network/figure_form.html"

    def _render(self, request, figure, form):
        return render(
            request,
            self.template_name,
            {"form": form, "figure": figure, "factions": _factions(), "is_create": False},
        )

    def get(self, request, pk):
        figure = get_object_or_404(NetworkFigure, pk=pk)
        initial = {name: getattr(figure, name) for name, _ in services.FIGURE_FIELDS}
        return self._render(request, figure, FigureForm(initial=initial))

    def post(self, request, pk):
        figure = get_object_or_404(NetworkFigure, pk=pk)
        form = FigureForm(request.POST)
        if not form.is_valid():
            return self._render(request, figure, form)
        services.update_figure(actor=request.user, figure=figure, data=_figure_data(form))
        return redirect("network:figure_detail", pk=figure.pk)


class FigureDeleteView(LoginRequiredMixin, View):
    """``GET`` asks for confirmation; ``POST`` deletes the figure and its connections."""

    def get(self, request, pk):
        figure = get_object_or_404(NetworkFigure, pk=pk)
        link_count = NetworkLink.objects.filter(
            Q(source_figure=figure) | Q(target_figure=figure)
        ).count()
        return render(
            request,
            "network/figure_confirm_delete.html",
            {"figure": figure, "link_count": link_count},
        )

    def post(self, request, pk):
        figure = get_object_or_404(NetworkFigure, pk=pk)
        services.delete_figure(actor=request.user, figure=figure)
        return redirect("network:graph")


class LinkCreateView(LoginRequiredMixin, View):
    """``GET/POST /network/links/new/`` -- a connection between any two nodes."""

    template_name = "network/link_form.html"

    def get(self, request):
        initial = {}
        if resolve(request.GET.get("von", "")) is not None:
            initial["source"] = request.GET["von"]
        return render(request, self.template_name, {"form": LinkForm(initial=initial)})

    def post(self, request):
        form = LinkForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})
        source = form.cleaned_data["source_node"]
        services.create_link(
            actor=request.user,
            source=source,
            target=form.cleaned_data["target_node"],
            relation=form.cleaned_data["relation"],
        )
        if source.figure is not None:
            return redirect("network:figure_detail", pk=source.figure.pk)
        return redirect("network:graph")


class LinkDeleteView(LoginRequiredMixin, View):
    """``POST /network/links/<uuid>/delete/`` -- back to the figure it was opened from."""

    def post(self, request, pk):
        link = get_object_or_404(
            NetworkLink.objects.select_related(
                "source_figure",
                "target_figure",
                "source_character__owner",
                "target_character__owner",
            ),
            pk=pk,
        )
        back_to = request.POST.get("figure", "")
        services.delete_link(actor=request.user, link=link)
        figure = NetworkFigure.objects.filter(pk=back_to).first() if _is_uuid(back_to) else None
        if figure is not None:
            return redirect("network:figure_detail", pk=figure.pk)
        return redirect("network:graph")


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


class HistoryView(LoginRequiredMixin, View):
    """``GET /network/history/`` -- every change, newest first."""

    def get(self, request):
        changes = NetworkChange.objects.select_related("actor")
        page = Paginator(changes, HISTORY_PAGE_SIZE).get_page(request.GET.get("page"))
        return render(request, "network/history.html", {"page_obj": page})


from django.urls import path

from . import views

app_name = "network"

urlpatterns = [
    path("network/", views.GraphView.as_view(), name="graph"),
    path("network/graph.json", views.GraphDataView.as_view(), name="graph_data"),
    path("network/history/", views.HistoryView.as_view(), name="history"),
    path("network/figures/new/", views.FigureCreateView.as_view(), name="figure_create"),
    path("network/figures/<uuid:pk>/", views.FigureDetailView.as_view(), name="figure_detail"),
    path("network/figures/<uuid:pk>/edit/", views.FigureEditView.as_view(), name="figure_edit"),
    path(
        "network/figures/<uuid:pk>/delete/", views.FigureDeleteView.as_view(), name="figure_delete"
    ),
    path("network/links/new/", views.LinkCreateView.as_view(), name="link_create"),
    path("network/links/<uuid:pk>/delete/", views.LinkDeleteView.as_view(), name="link_delete"),
]

from django.urls import path

from . import views

app_name = "sheets"

urlpatterns = [
    path("characters/", views.CharacterListCreateView.as_view(), name="character_list"),
    path("characters/<uuid:pk>/", views.CharacterDetailView.as_view(), name="character_detail"),
    path(
        "characters/<uuid:pk>/fields/<str:field_id>/",
        views.CharacterFieldUpdateView.as_view(),
        name="character_field_update",
    ),
    path("characters/<uuid:pk>/delete/", views.CharacterDeleteView.as_view(), name="character_delete"),
    path(
        "portal-admin/characters/",
        views.AdminCharacterListView.as_view(),
        name="admin_character_list",
    ),
    path(
        "portal-admin/characters/<uuid:pk>/",
        views.AdminCharacterDetailView.as_view(),
        name="admin_character_detail",
    ),
    path("ship/", views.ShipRedirectView.as_view(), name="ship_redirect"),
    path("ships/<uuid:pk>/", views.ShipDetailView.as_view(), name="ship_detail"),
    path(
        "ships/<uuid:pk>/fields/<str:field_id>/",
        views.ShipFieldUpdateView.as_view(),
        name="ship_field_update",
    ),
    path(
        "ships/<uuid:pk>/history/",
        views.ShipHistoryListView.as_view(),
        name="ship_history",
    ),
    path(
        "ships/<uuid:pk>/history/<int:change_id>/",
        views.ShipHistoryDetailView.as_view(),
        name="ship_history_detail",
    ),
]

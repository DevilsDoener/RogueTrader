from django.urls import path

from . import views

app_name = "sheets"

urlpatterns = [
    path("characters/", views.CharacterListCreateView.as_view(), name="character_list"),
    path("characters/<uuid:pk>/", views.CharacterDetailView.as_view(), name="character_detail"),
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
]

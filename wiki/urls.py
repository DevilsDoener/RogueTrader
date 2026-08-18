from django.urls import path

from . import views

app_name = "wiki"

urlpatterns = [
    path("wiki/", views.WikiIndexView.as_view(), name="index"),
    path("wiki/<slug:chapter_slug>/", views.WikiChapterView.as_view(), name="chapter"),
    path("search/", views.WikiSearchView.as_view(), name="search"),
]

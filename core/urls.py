from django.urls import path

from .views import dashboard, health, root


urlpatterns = [
    path("", root, name="root"),
    path("dashboard/", dashboard, name="dashboard"),
    path("healthz/", health, name="health"),
]

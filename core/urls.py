from django.urls import path

from .views import dashboard, health


urlpatterns = [
    path("dashboard/", dashboard, name="dashboard"),
    path("healthz/", health, name="health"),
]

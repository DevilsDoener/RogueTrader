"""Root URLconf: every app's own routes at the site root."""
from django.urls import include, path

urlpatterns = [
    path('', include('accounts.urls')),
    path('', include('core.urls')),
    path('', include('sheets.urls')),
    path('', include('wiki.urls')),
]

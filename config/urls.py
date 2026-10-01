"""Root URLconf: Django's admin under admin/, every app's own routes at the site root."""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('accounts.urls')),
    path('', include('core.urls')),
    path('', include('sheets.urls')),
    path('', include('wiki.urls')),
]

from django.db import connection
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required


def health(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    return JsonResponse({"status": "ok", "database": "ok"})


@login_required
def dashboard(request):
    return JsonResponse({"status": "ok"})

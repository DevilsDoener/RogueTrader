import pytest
from django.db import connection
from django.test import Client


@pytest.mark.django_db
def test_health_reports_process_and_database_ready(client: Client):
    response = client.get("/healthz/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


@pytest.mark.django_db
def test_health_does_not_require_login(client: Client):
    assert client.get("/healthz/").status_code == 200

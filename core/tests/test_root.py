"""Redirect behavior for the portal root (``GET /``)."""

from django.urls import reverse


def test_root_redirects_anonymous_visitors_to_login(client):
    """A missing authentication guard must not expose a public landing page."""
    response = client.get("/")

    assert response.status_code == 302
    assert response.url == reverse("accounts:login")


def test_root_redirects_authenticated_users_to_dashboard(client, owner):
    """A wrong root target must not bypass the authenticated command center."""
    client.force_login(owner)

    response = client.get("/")

    assert response.status_code == 302
    assert response.url == reverse("dashboard")


def test_root_then_dashboard_redirects_password_change_required_users(client, user_factory):
    """Password-change users enter through root before the dashboard is intercepted."""
    user = user_factory(must_change_password=True)
    client.force_login(user)

    root_response = client.get("/")

    assert root_response.status_code == 302
    assert root_response.url == reverse("dashboard")

    dashboard_response = client.get(root_response.url)

    assert dashboard_response.status_code == 302
    assert dashboard_response.url == reverse("accounts:change_required")

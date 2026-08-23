import pytest
from django.urls import reverse

from wiki.content import WikiRepository, set_repository_for_tests


@pytest.mark.django_db
@pytest.mark.parametrize("url_name, kwargs", [("wiki:index", {}), ("wiki:chapter", {"chapter_slug": "chapter"}), ("wiki:search", {})])
def test_wiki_routes_require_login(client, url_name, kwargs):
    response = client.get(reverse(url_name, kwargs=kwargs))

    assert response.status_code == 302
    assert response.url.startswith("/account/login/?next=")


@pytest.mark.django_db
def test_empty_chapter_displays_placeholder_for_logged_in_user(client, user_factory, tmp_path, settings):
    (tmp_path / "09-Placeholder.md").write_text("# Placeholder", encoding="utf-8")
    settings.WIKI_CONTENT_ROOT = tmp_path
    settings.WIKI_CONTENT_ALLOWLIST = ["09-Placeholder.md"]
    set_repository_for_tests(WikiRepository.load())
    client.force_login(user_factory())

    response = client.get(reverse("wiki:chapter", kwargs={"chapter_slug": "placeholder"}))

    assert response.status_code == 200
    assert "Dieses Kapitel ist noch nicht ausgearbeitet." in response.content.decode()

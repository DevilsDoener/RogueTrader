"""The chapter tree in the primary nav comes from a context processor.

It is only filled on wiki pages; elsewhere the nav stays short and the
repository is not touched.
"""
import pytest
from django.test import RequestFactory
from django.urls import resolve, reverse

from wiki import content
from wiki.content import WikiRepository, set_repository_for_tests
from wiki.context_processors import wiki_navigation


@pytest.fixture
def two_chapters(tmp_path, settings):
    (tmp_path / "01-One.md").write_text("# One\n\n## Alpha\na\n", encoding="utf-8")
    (tmp_path / "02-Two.md").write_text("# Two\n\n## Beta\nb\n", encoding="utf-8")
    settings.WIKI_CONTENT_ROOT = tmp_path
    settings.WIKI_CONTENT_ALLOWLIST = ["01-One.md", "02-Two.md"]
    set_repository_for_tests(WikiRepository.load())


def _request(path):
    request = RequestFactory().get(path)
    request.resolver_match = resolve(path)
    return request


def test_a_wiki_page_gets_the_chapters(two_chapters):
    path = reverse("wiki:chapter", kwargs={"chapter_slug": "two"})

    chapters = wiki_navigation(_request(path))["wiki_nav_chapters"]

    assert [chapter.slug for chapter in chapters] == ["one", "two"]


def test_the_search_page_counts_as_a_wiki_page(two_chapters):
    chapters = wiki_navigation(_request(reverse("wiki:search")))["wiki_nav_chapters"]

    assert len(chapters) == 2


def test_the_dashboard_gets_no_chapters(two_chapters):
    assert wiki_navigation(_request(reverse("dashboard"))) == {"wiki_nav_chapters": ()}


def test_a_request_without_a_resolver_match_gets_no_chapters(two_chapters):
    request = RequestFactory().get("/nowhere/")

    assert wiki_navigation(request) == {"wiki_nav_chapters": ()}


def test_an_uninitialised_repository_yields_no_chapters(monkeypatch):
    monkeypatch.setattr(content, "_repository", None)
    path = reverse("wiki:index")

    assert wiki_navigation(_request(path)) == {"wiki_nav_chapters": ()}


def test_it_is_registered_last(settings):
    processors = settings.TEMPLATES[0]["OPTIONS"]["context_processors"]

    assert processors[-1] == "wiki.context_processors.wiki_navigation"

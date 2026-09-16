"""WIKI_STRICT_CONTENT must catch the failure that actually happens.

A wrong content mount does not raise: ``WikiRepository.load()`` logs each
unreadable file and returns an empty repository. Guarding only against
exceptions therefore let a container boot and serve a wiki with no chapters --
precisely what strict mode is supposed to prevent. Verified against the built
image before this test existed.
"""
import pytest
from django.apps import apps
from django.core.exceptions import ImproperlyConfigured

from wiki.content import WikiRepository, set_repository_for_tests


@pytest.fixture
def wiki_config():
    return apps.get_app_config("wiki")


def _restore_after(repository):
    set_repository_for_tests(repository)


def test_strict_mode_refuses_an_empty_wiki(tmp_path, settings, wiki_config):
    from wiki.content import get_repository

    original = get_repository()
    settings.WIKI_CONTENT_ROOT = tmp_path / "missing"
    settings.WIKI_CONTENT_ALLOWLIST = ["01-Chapter.md"]
    settings.WIKI_STRICT_CONTENT = True

    try:
        with pytest.raises(ImproperlyConfigured, match="no chapters"):
            wiki_config.ready()
    finally:
        _restore_after(original)


def test_without_strict_mode_an_empty_wiki_is_tolerated(tmp_path, settings, wiki_config):
    """Locally a broken chapter must not block unrelated work."""
    from wiki.content import get_repository

    original = get_repository()
    settings.WIKI_CONTENT_ROOT = tmp_path / "missing"
    settings.WIKI_CONTENT_ALLOWLIST = ["01-Chapter.md"]
    settings.WIKI_STRICT_CONTENT = False

    try:
        wiki_config.ready()
        assert get_repository().chapters() == ()
    finally:
        _restore_after(original)


def test_strict_mode_accepts_a_healthy_tree(tmp_path, settings, wiki_config):
    from wiki.content import get_repository

    original = get_repository()
    (tmp_path / "01-Chapter.md").write_text("# Chapter\n\n## Rule\nBody.\n", encoding="utf-8")
    settings.WIKI_CONTENT_ROOT = tmp_path
    settings.WIKI_CONTENT_ALLOWLIST = ["01-Chapter.md"]
    settings.WIKI_STRICT_CONTENT = True

    try:
        wiki_config.ready()
        assert len(get_repository().chapters()) == 1
    finally:
        _restore_after(original)


def test_an_empty_allowlist_is_not_treated_as_a_failure(tmp_path, settings, wiki_config):
    """Serving nothing on purpose is a choice, not a broken mount."""
    from wiki.content import get_repository

    original = get_repository()
    settings.WIKI_CONTENT_ROOT = tmp_path
    settings.WIKI_CONTENT_ALLOWLIST = []
    settings.WIKI_STRICT_CONTENT = True

    try:
        wiki_config.ready()
        assert get_repository().chapters() == ()
    finally:
        _restore_after(original)

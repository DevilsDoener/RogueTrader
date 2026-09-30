"""Loading the content tree: the allowlist, broken files, and strict mode.

``WikiRepository.load()`` serves only allow-listed files and skips any file it
cannot read, so one bad chapter never hides the rest. A wrong content mount
therefore does not raise -- it yields an empty repository -- which is why
``WIKI_STRICT_CONTENT`` checks for an empty wiki rather than for exceptions.
"""
import pytest
from django.apps import apps
from django.core.exceptions import ImproperlyConfigured

from wiki.content import get_repository


@pytest.fixture
def wiki_config():
    return apps.get_app_config("wiki")


def test_allowlist_excludes_progress_file(tmp_path, make_repository):
    (tmp_path / "00-FORTSCHRITT.md").write_text("# Secret work notes", encoding="utf-8")

    repo = make_repository({"01-Chapter.md": "# Chapter\nAllowed"})

    assert [chapter.source_name for chapter in repo.chapters()] == ["01-Chapter.md"]


def test_invalid_utf8_file_does_not_hide_valid_allowlisted_chapter(make_repository):
    repo = make_repository({"01-Valid.md": "# Valid\nContent", "02-Broken.md": b"\xff\xfe\x00"})

    assert [chapter.slug for chapter in repo.chapters()] == ["valid"]


def test_strict_mode_refuses_an_empty_wiki(tmp_path, settings, wiki_config):
    settings.WIKI_CONTENT_ROOT = tmp_path / "missing"
    settings.WIKI_CONTENT_ALLOWLIST = ["01-Chapter.md"]
    settings.WIKI_STRICT_CONTENT = True

    with pytest.raises(ImproperlyConfigured, match="no chapters"):
        wiki_config.ready()


def test_without_strict_mode_an_empty_wiki_is_tolerated(tmp_path, settings, wiki_config):
    """Locally a broken chapter must not block unrelated work."""
    settings.WIKI_CONTENT_ROOT = tmp_path / "missing"
    settings.WIKI_CONTENT_ALLOWLIST = ["01-Chapter.md"]
    settings.WIKI_STRICT_CONTENT = False

    wiki_config.ready()

    assert get_repository().chapters() == ()


def test_strict_mode_accepts_a_healthy_tree(tmp_path, settings, wiki_config):
    (tmp_path / "01-Chapter.md").write_text("# Chapter\n\n## Rule\nBody.\n", encoding="utf-8")
    settings.WIKI_CONTENT_ROOT = tmp_path
    settings.WIKI_CONTENT_ALLOWLIST = ["01-Chapter.md"]
    settings.WIKI_STRICT_CONTENT = True

    wiki_config.ready()

    assert len(get_repository().chapters()) == 1


def test_an_empty_allowlist_is_not_treated_as_a_failure(tmp_path, settings, wiki_config):
    """Serving nothing on purpose is a choice, not a broken mount."""
    settings.WIKI_CONTENT_ROOT = tmp_path
    settings.WIKI_CONTENT_ALLOWLIST = []
    settings.WIKI_STRICT_CONTENT = True

    wiki_config.ready()

    assert get_repository().chapters() == ()

"""The chapter manifest is the single source of truth.

The list used to live in four places -- config/settings.py, .env, .env.example
and compose.yaml -- and doubled as both the security filter and the ordering,
with no test comparing it against what is actually on disk.
"""
import pytest
from django.conf import settings
from django.core.checks import Error
from django.core.checks import Warning as CheckWarning

from wiki import manifest
from wiki.checks import MISSING_FILE, MISSING_ROOT, UNLISTED_FILE, check_wiki_content


def test_settings_take_their_default_allowlist_from_the_manifest():
    assert settings.WIKI_DEFAULT_CONTENT_ALLOWLIST == manifest.ALLOWLIST


def test_slugs_are_unique():
    slugs = [entry.slug for entry in manifest.CHAPTERS]

    assert len(slugs) == len(set(slugs))
    assert all(slugs)


def test_source_names_are_unique():
    names = [entry.source_name for entry in manifest.CHAPTERS]

    assert len(names) == len(set(names))


def test_every_chapter_belongs_to_a_part():
    assert all(entry.part for entry in manifest.CHAPTERS)


def test_chapter_xiv_keeps_its_four_files_together():
    """The book's chapter XIV was split along the PDF's own bookmarks."""
    parts = [entry.part for entry in manifest.CHAPTERS]

    assert parts.count("Kapitel XIV") == 4
    first = parts.index("Kapitel XIV")
    assert parts[first : first + 4] == ["Kapitel XIV"] * 4


def test_an_unknown_source_name_gets_a_neutral_entry():
    entry = manifest.entry_for("99-Nonexistent.md")

    assert entry.slug == ""
    assert entry.part == ""
    assert entry.search_weight == 1.0


def test_navigation_only_chapters_are_down_weighted_for_search():
    """The page-number index outranked real rules for common words."""
    weights = {entry.source_name: entry.search_weight for entry in manifest.CHAPTERS}

    assert weights["16-Index.md"] < 1.0
    assert weights["00-Foreword.md"] < 1.0
    assert weights["03-Skills.md"] == 1.0


# --- startup checks -------------------------------------------------------


def _ids(problems):
    return sorted(problem.id for problem in problems)


def test_a_healthy_tree_reports_nothing(tmp_path, settings):
    (tmp_path / "01-One.md").write_text("# One", encoding="utf-8")
    settings.WIKI_CONTENT_ROOT = tmp_path
    settings.WIKI_CONTENT_ALLOWLIST = ["01-One.md"]

    assert check_wiki_content(None) == []


def test_a_missing_chapter_is_an_error(tmp_path, settings):
    settings.WIKI_CONTENT_ROOT = tmp_path
    settings.WIKI_CONTENT_ALLOWLIST = ["01-Missing.md"]

    problems = check_wiki_content(None)

    assert _ids(problems) == [MISSING_FILE]
    assert all(isinstance(problem, Error) for problem in problems)


def test_a_missing_content_root_is_an_error(settings, tmp_path):
    settings.WIKI_CONTENT_ROOT = tmp_path / "nope"
    settings.WIKI_CONTENT_ALLOWLIST = ["01-One.md"]

    assert _ids(check_wiki_content(None)) == [MISSING_ROOT]


def test_an_unlisted_markdown_file_is_a_warning(tmp_path, settings):
    (tmp_path / "01-One.md").write_text("# One", encoding="utf-8")
    (tmp_path / "02-Forgotten.md").write_text("# Forgotten", encoding="utf-8")
    settings.WIKI_CONTENT_ROOT = tmp_path
    settings.WIKI_CONTENT_ALLOWLIST = ["01-One.md"]

    problems = check_wiki_content(None)

    assert _ids(problems) == [UNLISTED_FILE]
    assert all(isinstance(problem, CheckWarning) for problem in problems)


def test_deliberately_excluded_files_do_not_warn(tmp_path, settings):
    (tmp_path / "01-One.md").write_text("# One", encoding="utf-8")
    for name in manifest.KNOWN_EXCLUDED:
        (tmp_path / name).write_text("# Not a chapter", encoding="utf-8")
    settings.WIKI_CONTENT_ROOT = tmp_path
    settings.WIKI_CONTENT_ALLOWLIST = ["01-One.md"]

    assert check_wiki_content(None) == []


@pytest.mark.skipif(
    not (settings.WIKI_CONTENT_ROOT / "03-Skills.md").exists(),
    reason="real wiki content is not available in this checkout",
)
def test_the_real_content_tree_passes_its_own_checks():
    assert check_wiki_content(None) == []

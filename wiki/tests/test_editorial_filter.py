"""Transcription bookkeeping is hidden from readers.

Eleven of the book chapters end with a "## Status" section, and four carry a
page-audit section, all of it provenance for the PDF transcription rather than
rules. They are filtered at parse time so the Markdown sources -- which are the
audit trail -- stay untouched.
"""
import pytest

from wiki.content import WikiRepository

EDITORIAL_HEADINGS = (
    "Status",
    "Page Inventory and Cross-Check",
    # Chapter I spells it differently; a plain equality filter would miss it.
    "Page Coverage and Cross-check",
)


def _chapter(tmp_path, settings, body):
    (tmp_path / "01-Chapter.md").write_text(body, encoding="utf-8")
    settings.WIKI_CONTENT_ROOT = tmp_path
    settings.WIKI_CONTENT_ALLOWLIST = ["01-Chapter.md"]
    return WikiRepository.load().get_chapter("chapter")


@pytest.mark.parametrize("heading", EDITORIAL_HEADINGS)
def test_editorial_sections_are_hidden(tmp_path, settings, heading):
    chapter = _chapter(
        tmp_path, settings, f"# Chapter\n\n## Rules\nReal content.\n\n## {heading}\nAudit.\n"
    )

    assert [section.title for section in chapter.outline] == ["Rules"]


def test_the_whole_subtree_is_dropped_with_its_parent(tmp_path, settings):
    """03-Skills.md nests "### Final Audit" inside its "## Status" section."""
    chapter = _chapter(
        tmp_path,
        settings,
        "# Chapter\n\n## Rules\nReal.\n\n## Status\nAudit.\n\n"
        "### Final Audit (gameplay-critical tables)\nMore audit.\n",
    )

    titles = [section.title for section in chapter.sections]
    assert titles == ["Rules"]
    assert "Final Audit (gameplay-critical tables)" not in titles


def test_a_deeper_status_heading_is_kept(tmp_path, settings):
    """Filtering is depth-1 only, so real content named "Status" survives."""
    chapter = _chapter(
        tmp_path, settings, "# Chapter\n\n## Conditions\nBody.\n\n### Status\nA real rule.\n"
    )

    assert [section.title for section in chapter.sections] == ["Conditions", "Status"]


def test_hidden_sections_are_absent_from_the_search_index(tmp_path, settings):
    (tmp_path / "01-Chapter.md").write_text(
        "# Chapter\n\n## Rules\nReal content.\n\n## Status\nUnmistakable audit token.\n",
        encoding="utf-8",
    )
    settings.WIKI_CONTENT_ROOT = tmp_path
    settings.WIKI_CONTENT_ALLOWLIST = ["01-Chapter.md"]

    repository = WikiRepository.load()

    assert repository.search("unmistakable") == ()
    assert repository.search("real content")


def test_filtering_is_off_when_no_patterns_are_configured(tmp_path, settings):
    settings.WIKI_EDITORIAL_SECTION_PATTERNS = ()
    chapter = _chapter(tmp_path, settings, "# Chapter\n\n## Status\nAudit.\n")

    assert [section.title for section in chapter.outline] == ["Status"]

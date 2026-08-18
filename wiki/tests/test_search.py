from wiki.content import WikiRepository


def test_heading_matches_rank_before_body_matches(tmp_path, settings):
    (tmp_path / "01-First.md").write_text("# First\nA plasma weapon is rare.", encoding="utf-8")
    (tmp_path / "02-Second.md").write_text("# Plasma Doctrine\nOrdinary notes.", encoding="utf-8")
    settings.WIKI_CONTENT_ROOT = tmp_path
    settings.WIKI_CONTENT_ALLOWLIST = ["01-First.md", "02-Second.md"]

    results = WikiRepository.load().search("plasma")

    assert [result.chapter_slug for result in results] == ["second", "first"]


def test_search_returns_escaped_highlighted_snippet_around_first_match(tmp_path, settings):
    (tmp_path / "01-Chapter.md").write_text(
        "# Chapter\nBefore <tag> plasma & after", encoding="utf-8"
    )
    settings.WIKI_CONTENT_ROOT = tmp_path
    settings.WIKI_CONTENT_ALLOWLIST = ["01-Chapter.md"]

    result = WikiRepository.load().search("plasma")[0]

    assert "&lt;tag&gt;" in result.snippet
    assert "<mark>plasma</mark>" in result.snippet
    assert "&amp;" in result.snippet


def test_search_rejects_one_character_query(tmp_path, settings):
    (tmp_path / "01-Chapter.md").write_text("# Chapter\nPlasma", encoding="utf-8")
    settings.WIKI_CONTENT_ROOT = tmp_path
    settings.WIKI_CONTENT_ALLOWLIST = ["01-Chapter.md"]

    assert WikiRepository.load().search("p") == ()

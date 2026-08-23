from wiki.content import WikiRepository


def test_allowlist_excludes_progress_file(tmp_path, settings):
    (tmp_path / "01-Chapter.md").write_text("# Chapter\nAllowed", encoding="utf-8")
    (tmp_path / "00-FORTSCHRITT.md").write_text("# Secret work notes", encoding="utf-8")
    settings.WIKI_CONTENT_ROOT = tmp_path
    settings.WIKI_CONTENT_ALLOWLIST = ["01-Chapter.md"]

    repo = WikiRepository.load()

    assert [chapter.source_name for chapter in repo.chapters()] == ["01-Chapter.md"]


def test_duplicate_headings_receive_stable_collision_suffixes(tmp_path, settings):
    (tmp_path / "03-Skills.md").write_text(
        "# Skills\n\n## Skills\nFirst section\n\n## Skills\nSecond section",
        encoding="utf-8",
    )
    settings.WIKI_CONTENT_ROOT = tmp_path
    settings.WIKI_CONTENT_ALLOWLIST = ["03-Skills.md"]

    chapter = WikiRepository.load().get_chapter("skills")

    assert [section.id for section in chapter.sections] == ["skills", "skills-2"]


def test_invalid_utf8_file_does_not_hide_valid_allowlisted_chapter(tmp_path, settings):
    (tmp_path / "01-Valid.md").write_text("# Valid\nContent", encoding="utf-8")
    (tmp_path / "02-Broken.md").write_bytes(b"\xff\xfe\x00")
    settings.WIKI_CONTENT_ROOT = tmp_path
    settings.WIKI_CONTENT_ALLOWLIST = ["01-Valid.md", "02-Broken.md"]

    repo = WikiRepository.load()

    assert [chapter.slug for chapter in repo.chapters()] == ["valid"]

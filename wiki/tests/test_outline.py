"""Heading-tree structure.

The previous splitter recognised ``##`` only, which collapsed whole chapters
into one section when their sub-sections were written as ``#`` (the career
paths chapter) and made ``###``/``####`` invisible to navigation entirely.
"""
from wiki.content import WikiRepository


def _chapter(tmp_path, settings, body, name="01-Chapter.md", slug="chapter"):
    (tmp_path / name).write_text(body, encoding="utf-8")
    settings.WIKI_CONTENT_ROOT = tmp_path
    settings.WIKI_CONTENT_ALLOWLIST = [name]
    return WikiRepository.load().get_chapter(slug)


def _titles(sections):
    return [section.title for section in sections]


def test_h1_after_the_title_becomes_a_top_level_section(tmp_path, settings):
    """The shape of 02-Karrierewege.md: careers written as H1, not H2."""
    chapter = _chapter(
        tmp_path,
        settings,
        "# Chapter II: Career Paths\n\n"
        "## Basics\nShared rules.\n\n"
        "# Rogue Trader\nA captain.\n\n"
        "### Starting Skills\nSkills.\n\n"
        "# Arch-militant\nA soldier.\n\n"
        "### Starting Skills\nMore skills.\n",
    )

    assert chapter.title == "Chapter II: Career Paths"
    assert _titles(chapter.outline) == ["Basics", "Rogue Trader", "Arch-militant"]
    # The stray H1s are clamped to the section level, not treated as a second
    # chapter title, and their H3s hang underneath them.
    assert {section.level for section in chapter.outline} == {2}
    assert _titles(chapter.outline[1].children) == ["Starting Skills"]
    assert _titles(chapter.outline[2].children) == ["Starting Skills"]


def test_deeper_headings_nest_by_level(tmp_path, settings):
    chapter = _chapter(
        tmp_path,
        settings,
        "# Chapter\n\n## Traits\nT\n\n### Descriptions\nD\n\n#### Amphibious\nA\n\n"
        "#### Armoured\nB\n\n## Next\nN\n",
    )

    traits, following = chapter.outline
    assert following.title == "Next"
    descriptions, = traits.children
    assert descriptions.level == 3
    assert _titles(descriptions.children) == ["Amphibious", "Armoured"]
    assert {child.level for child in descriptions.children} == {4}


def test_content_before_the_first_heading_becomes_an_intro_section(tmp_path, settings):
    chapter = _chapter(
        tmp_path, settings, "# Chapter\n\nStanding text.\n\n## Real\nBody.\n"
    )

    intro = chapter.outline[0]
    assert intro.is_intro
    assert intro.title == "Chapter"
    assert "Standing text." in intro.plain_text


def test_an_empty_intro_is_not_emitted(tmp_path, settings):
    chapter = _chapter(tmp_path, settings, "# Chapter\n\n## Real\nBody.\n")

    assert _titles(chapter.outline) == ["Real"]


def test_flat_sections_are_the_tree_in_depth_first_order(tmp_path, settings):
    chapter = _chapter(
        tmp_path,
        settings,
        "# Chapter\n\n## A\na\n\n### A1\na1\n\n### A2\na2\n\n## B\nb\n",
    )

    assert _titles(chapter.sections) == ["A", "A1", "A2", "B"]
    assert [section.ordinal for section in chapter.sections] == [0, 1, 2, 3]


def test_headings_inside_a_blockquote_do_not_split_sections(tmp_path, settings):
    chapter = _chapter(
        tmp_path, settings, "# Chapter\n\n## Real\nBody.\n\n> ## Quoted\n> Inside.\n"
    )

    assert _titles(chapter.outline) == ["Real"]
    assert "Quoted" in chapter.outline[0].html


def test_a_hash_inside_a_table_cell_does_not_split_sections(tmp_path, settings):
    chapter = _chapter(
        tmp_path,
        settings,
        "# Chapter\n\n## Real\n\n| Code | Note |\n|---|---|\n| ## 4 | fine |\n",
    )

    assert _titles(chapter.outline) == ["Real"]


def test_a_chapter_without_an_h1_keeps_its_heading_structure(tmp_path, settings):
    """Previously the filename became the title; the sections must survive."""
    chapter = _chapter(
        tmp_path,
        settings,
        "Leading text.\n\n## One\nBody one.\n\n## Two\nBody two.\n",
        name="05-Armoury.md",
        slug="armoury",
    )

    assert chapter.title == "05-Armoury"
    assert _titles(chapter.outline) == ["05-Armoury", "One", "Two"]
    assert chapter.outline[0].is_intro

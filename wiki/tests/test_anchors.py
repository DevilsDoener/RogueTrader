"""Anchor stability.

A duplicated heading is qualified with its parent's anchor rather than
numbered. The career-paths chapter repeats "Starting Skills, Talents & Gear"
once per career; numbering those ``-2`` … ``-8`` would make every anchor
depend on the order the careers happen to appear in, so reordering one career
would silently move seven bookmarks and seven search-result links.
"""

CAREERS = ("Rogue Trader", "Arch-militant", "Explorator", "Navigator")


def _chapter(make_repository, body):
    return make_repository({"02-Careers.md": body}).get_chapter("careers")


def _careers_document(order):
    parts = ["# Chapter II: Career Paths\n"]
    for career in order:
        parts.append(f"\n# {career}\nDescription.\n\n### Starting Skills\nSkills.\n")
    return "".join(parts)


def _anchors_by_parent(chapter):
    return {
        section.title: tuple(child.id for child in section.children)
        for section in chapter.outline
    }


def test_repeated_child_headings_are_qualified_by_their_parent(make_repository):
    chapter = _chapter(make_repository, _careers_document(CAREERS))

    anchors = [child.id for section in chapter.outline for child in section.children]

    assert anchors == [
        "rogue-trader--starting-skills",
        "arch-militant--starting-skills",
        "explorator--starting-skills",
        "navigator--starting-skills",
    ]
    assert len(set(anchors)) == len(anchors)


def test_reordering_the_parents_does_not_move_any_anchor(make_repository):
    original = _anchors_by_parent(_chapter(make_repository, _careers_document(CAREERS)))

    shuffled_order = tuple(reversed(CAREERS))
    shuffled = _anchors_by_parent(
        _chapter(make_repository, _careers_document(shuffled_order))
    )

    assert original == shuffled


def test_duplicate_top_level_headings_still_fall_back_to_numbering(make_repository):
    """No parent to qualify with, so the historical suffix behaviour stands."""
    chapter = _chapter(
        make_repository, "# Skills\n\n## Skills\nFirst.\n\n## Skills\nSecond.\n"
    )

    assert [section.id for section in chapter.outline] == ["skills", "skills-2"]


def test_a_unique_heading_keeps_its_bare_slug(make_repository):
    chapter = _chapter(
        make_repository, "# Chapter\n\n## Alpha\na\n\n### Unique Child\nc\n"
    )

    assert chapter.outline[0].id == "alpha"
    assert chapter.outline[0].children[0].id == "unique-child"


def test_an_unslugifiable_heading_falls_back_to_section(make_repository):
    chapter = _chapter(make_repository, "# Chapter\n\n## ???\nBody.\n")

    assert chapter.outline[0].id == "section"


def test_the_intro_anchor_is_derived_from_the_chapter_title(make_repository):
    """The intro has no heading of its own; it must not collapse to "section"."""
    chapter = _chapter(
        make_repository, "# Plasma Doctrine\nIntro body.\n\n## Details\nMore.\n"
    )

    intro = chapter.outline[0]
    assert intro.is_intro
    assert intro.id == "plasma-doctrine"


def test_anchors_are_stored_without_the_render_time_prefix(make_repository):
    """`sec-` is added by the template, so stored ids stay comparable."""
    chapter = _chapter(make_repository, "# Chapter\n\n## Alpha\na\n")

    assert not chapter.outline[0].id.startswith("sec-")

"""Invariants checked against the real book corpus, not a fixture.

The unit tests above pin behaviour on small synthetic chapters. This file is
the net that catches a future *content* edit -- a renamed heading, a new
chapter, a stray H1 -- silently breaking navigation. It skips when the content
directory is unavailable, so a checkout without it still runs green.
"""
import collections

import pytest
from django.conf import settings

from wiki.content import WikiRepository

pytestmark = pytest.mark.skipif(
    not (settings.WIKI_CONTENT_ROOT / "03-Skills.md").exists(),
    reason="real wiki content is not available in this checkout",
)


@pytest.fixture(scope="module")
def repository():
    return WikiRepository.load()


def test_every_allow_listed_chapter_loads(repository):
    loaded = {chapter.source_name for chapter in repository.chapters()}

    assert loaded == set(settings.WIKI_CONTENT_ALLOWLIST)


def test_anchors_are_unique_within_each_chapter(repository):
    duplicates = {}
    for chapter in repository.chapters():
        counts = collections.Counter(section.id for section in chapter.sections)
        repeated = [anchor for anchor, count in counts.items() if count > 1]
        if repeated:
            duplicates[chapter.slug] = repeated

    assert duplicates == {}


def test_every_chapter_has_navigable_sections(repository):
    """A chapter with no outline node is unreachable below its own title."""
    empty = [
        chapter.slug for chapter in repository.chapters() if not chapter.outline
    ]

    assert empty == []


def test_no_section_is_an_unnavigable_monolith(repository):
    """Guards the regression this rework exists to fix.

    Before the heading tree, 02-Karrierewege.md rendered ~150 KB into a single
    section because its careers are H1 and the splitter only knew H2.
    """
    oversized = [
        (chapter.slug, section.title, len(section.html))
        for chapter in repository.chapters()
        for section in chapter.sections
        if len(section.html) > 60_000
    ]

    assert oversized == []


def test_the_career_paths_chapter_exposes_each_career(repository):
    chapter = repository.get_chapter("karrierewege")
    titles = [section.title for section in chapter.outline]

    for career in ("Rogue Trader", "Arch-militant", "Explorator", "Void-master"):
        assert career in titles


def test_transcription_sections_are_not_served(repository):
    visible = [
        section.title
        for chapter in repository.chapters()
        for section in chapter.sections
        if section.title.casefold().startswith(("status", "page inventory", "page coverage"))
    ]

    assert visible == []


def test_heading_levels_stay_within_the_document_outline(repository):
    levels = {
        section.level
        for chapter in repository.chapters()
        for section in chapter.sections
    }

    assert levels <= {2, 3, 4, 5, 6}

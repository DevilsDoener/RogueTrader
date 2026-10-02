"""Record types of the wiki: the immutable chapter and section dataclasses.

This is the shared vocabulary of the wiki -- the chapter builder
(``wiki.chapters``) produces these records, the repository (``wiki.content``)
holds them, and the search index, views and templates read them.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cached_property
from typing import Dict, Tuple

from django.conf import settings

from .manifest import BAND_CHAPTERS
from .outline import MIN_SECTION_LEVEL

_CHAPTER_PREFIX_RE = re.compile(r"^Chapter\s+[0-9IVXLC]+\s*[:\-–]\s*", re.IGNORECASE)


@dataclass(frozen=True)
class WikiSection:
    id: str
    title: str
    plain_text: str
    html: str
    ordinal: int
    #: Heading level as rendered (2-6). Drives both the heading tag and the
    #: indent level in the table of contents.
    level: int = MIN_SECTION_LEVEL
    #: The heading's inline markup, already sanitized. Falls back to the plain
    #: title. Rendered by the template so no `id` attribute ever has to pass
    #: through the Bleach allowlist.
    title_html: str = ""
    children: Tuple["WikiSection", ...] = ()
    #: Titles of the enclosing headings, outermost first. The intro node is
    #: not a heading and never appears here.
    parent_titles: Tuple[str, ...] = ()
    #: True for the single implicit section built from the content between the
    #: H1 title and the first following heading. Its title always equals the
    #: chapter title, so templates use this flag -- not string comparison
    #: between `id` and the chapter slug, which only coincide by accident -- to
    #: avoid rendering a redundant heading.
    is_intro: bool = False

    @property
    def is_glossary(self) -> bool:
        """True for a section that is really a list of entries.

        "Detailed Talent Descriptions" has 147 leaf children, "Skill
        Descriptions" 48, "Trait Descriptions" 32. Rendering those as a nested
        table-of-contents list buries the rest of the chapter, so the template
        shows them as a compact index instead.
        """
        threshold = settings.WIKI_TOC_GLOSSARY_THRESHOLD
        if not threshold or len(self.children) < threshold:
            return False
        return all(not child.children for child in self.children)


@dataclass(frozen=True)
class WikiChapter:
    """One chapter. Immutable, so the derived views below are cached."""

    slug: str
    title: str
    source_name: str
    sections: Tuple[WikiSection, ...]
    ordinal: int
    #: Top-level sections only; each carries its own ``children``.
    outline: Tuple[WikiSection, ...] = ()
    #: Roman numeral and Bibliothek band from wiki/manifest.py.
    numeral: str = ""
    band: str = BAND_CHAPTERS
    search_weight: float = 1.0

    @cached_property
    def short_title(self) -> str:
        """The title without its leading "Chapter V:" style label."""
        stripped = _CHAPTER_PREFIX_RE.sub("", self.title).strip()
        return stripped or self.title

    @cached_property
    def navigable_sections(self) -> Tuple[WikiSection, ...]:
        """Top-level sections a reader can jump to, excluding the intro.

        The intro carries the chapter title and no heading of its own, so
        listing it on the overview would just repeat the chapter link.
        """
        return tuple(section for section in self.outline if not section.is_intro)

    @cached_property
    def sections_by_id(self) -> Dict[str, WikiSection]:
        """Every section keyed by its anchor id (the first one wins)."""
        by_id: Dict[str, WikiSection] = {}
        for section in self.sections:
            by_id.setdefault(section.id, section)
        return by_id

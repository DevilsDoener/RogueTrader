"""Immutable in-memory content repository for the read-only wiki.

The book's Markdown chapters are mounted read-only into the container. On
Django startup (``WikiConfig.ready()``), the allow-listed files are parsed
once into immutable ``WikiChapter``/``WikiSection`` records and a search
index, and held in a module-level singleton. Requests never touch disk.

Sectioning lives in ``wiki.outline``: each chapter is parsed a single time
into a heading tree. ``WikiChapter.outline`` holds the top-level nodes for
navigation; ``WikiChapter.sections`` is the same nodes flattened depth-first,
which is what the search index consumes.
"""
from __future__ import annotations

import logging
from functools import cached_property
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from django.conf import settings

from .chapters import editorial_patterns as load_editorial_patterns, parse_chapter
from .manifest import (
    BANDS,
    DASHBOARD_SHORTCUTS,
    QUICK_LINKS,
    QuickLink,
    ShortcutGroup,
)
from .markdown import SafeMarkdownRenderer
from .records import WikiChapter, WikiSection
from .index import PREFIX_MIN_LENGTH, SearchIndex, build_search_index

logger = logging.getLogger(__name__)

__all__ = [
    "WikiChapter",
    "WikiRepository",
    "WikiSection",
    "get_repository",
    "get_repository_or_none",
    "initialize_repository",
    "set_repository_for_tests",
]


def _library_card(chapter: WikiChapter) -> dict:
    """One overview card: the chapter plus the text the live filter matches.

    The filter string is built here (not in the template) so autoescape stays
    in charge of quotes and angle brackets in section titles. It covers the
    chapter title and its level-1 and level-2 sections, casefolded; the
    template nests each level-1 section's children under it, so a level-2
    match can be shown and marked too.
    """
    sections = chapter.navigable_sections
    words = [chapter.short_title, chapter.title]
    for section in sections:
        words.append(section.title)
        words.extend(child.title for child in section.children)
    return {
        "chapter": chapter,
        "sections": sections,
        "filter_text": " ".join(words).casefold(),
    }


class WikiRepository:
    """Immutable, in-memory view over the allow-listed wiki chapters."""

    def __init__(self, chapters: Tuple[WikiChapter, ...], search_index: SearchIndex):
        self._chapters = tuple(chapters)
        self._by_slug = {chapter.slug: chapter for chapter in self._chapters}
        self._search_index = search_index

    @classmethod
    def load(cls) -> "WikiRepository":
        root = Path(settings.WIKI_CONTENT_ROOT)
        allowlist = list(settings.WIKI_CONTENT_ALLOWLIST)
        renderer = SafeMarkdownRenderer()
        editorial_patterns = load_editorial_patterns()
        chapter_slugs_seen: Dict[str, int] = {}
        chapters: List[WikiChapter] = []
        dropped_total = 0

        for ordinal, filename in enumerate(allowlist):
            path = root / filename
            try:
                text = path.read_text(encoding="utf-8")
            except FileNotFoundError:
                logger.error("Wiki content file not found, skipping: %s", filename)
                continue
            except (OSError, UnicodeDecodeError) as exc:
                logger.error(
                    "Skipping unreadable wiki content file %s (%s)", filename, exc.__class__.__name__
                )
                continue

            try:
                chapter, dropped = parse_chapter(
                    filename, text, ordinal, renderer, chapter_slugs_seen, editorial_patterns
                )
            except Exception:  # noqa: BLE001 - one bad chapter must not break the rest
                logger.exception("Failed to parse wiki content file, skipping: %s", filename)
                continue

            chapters.append(chapter)
            dropped_total += dropped

        if dropped_total:
            logger.info(
                "Hid %d editorial section(s) from the wiki (transcription bookkeeping).",
                dropped_total,
            )

        search_index = build_search_index(chapters)
        return cls(tuple(chapters), search_index)

    def chapters(self) -> Tuple[WikiChapter, ...]:
        return self._chapters

    @cached_property
    def library_bands(self) -> List[dict]:
        """The manifest's bands in order, each with its chapters' cards.

        Every numbered chapter (I-XV, including the four files of XIV) shares
        the one "Chapters" grid. The repository is immutable, so the result is
        built once per repository; templates only read it.
        """
        cards = {name: [] for name in BANDS}
        for chapter in self._chapters:
            cards[chapter.band].append(_library_card(chapter))
        return [{"name": name, "cards": cards[name]} for name in BANDS if cards[name]]

    def get_chapter(self, slug: str) -> Optional[WikiChapter]:
        return self._by_slug.get(slug)

    def neighbours(self, slug: str) -> Tuple[Optional[WikiChapter], Optional[WikiChapter]]:
        """The chapters before and after ``slug`` in reading order."""
        chapter = self._by_slug.get(slug)
        if chapter is None:
            return None, None
        index = self._chapters.index(chapter)
        previous = self._chapters[index - 1] if index > 0 else None
        following = (
            self._chapters[index + 1] if index + 1 < len(self._chapters) else None
        )
        return previous, following

    def search(
        self,
        query: str,
        limit: Optional[int] = 30,
        prefix_min_length: int = PREFIX_MIN_LENGTH,
    ):
        return self._search_index.search(
            query, limit=limit, prefix_min_length=prefix_min_length
        )

    def highlight_terms(self, query: str) -> Tuple[str, ...]:
        return self._search_index.highlight_terms(query)

    def _resolve_links(
        self, links: Tuple[QuickLink, ...]
    ) -> Tuple[Tuple[QuickLink, WikiChapter], ...]:
        """``links`` paired with their chapter, minus any whose target is gone."""
        resolved = []
        for link in links:
            chapter = self._by_slug.get(link.chapter_slug)
            if chapter is None or link.section_id not in chapter.sections_by_id:
                logger.debug("Dropping quick link with missing target: %s", link)
                continue
            resolved.append((link, chapter))
        return tuple(resolved)

    def quick_links(self) -> Tuple[Tuple[QuickLink, WikiChapter], ...]:
        """Curated quick links whose target still exists in the loaded book."""
        return self._resolve_links(QUICK_LINKS)

    def dashboard_shortcuts(
        self,
    ) -> Tuple[Tuple[ShortcutGroup, Tuple[Tuple[QuickLink, WikiChapter], ...]], ...]:
        """The dashboard's shortcut groups with their resolvable links.

        Same rule as ``quick_links()``: a link whose target is missing is
        dropped, and a group left without any link is dropped with it.
        """
        resolved = []
        for group in DASHBOARD_SHORTCUTS:
            links = self._resolve_links(group.links)
            if links:
                resolved.append((group, links))
        return tuple(resolved)


_repository: Optional[WikiRepository] = None


def initialize_repository() -> None:
    """Load the wiki content once at Django startup."""
    global _repository
    _repository = WikiRepository.load()


def get_repository() -> WikiRepository:
    if _repository is None:
        raise RuntimeError(
            "Wiki repository has not been initialized. Ensure WikiConfig.ready() ran, "
            "or call set_repository_for_tests() in tests."
        )
    return _repository


def get_repository_or_none() -> Optional[WikiRepository]:
    """The repository, or ``None`` where startup did not initialise it."""
    return _repository


def set_repository_for_tests(repository: WikiRepository) -> None:
    """Test-only hook to replace the process-wide repository singleton."""
    global _repository
    _repository = repository

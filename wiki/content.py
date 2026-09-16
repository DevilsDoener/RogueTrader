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
import re
from dataclasses import dataclass, field
from itertools import count
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

from django.conf import settings
from django.utils.text import slugify

from .markdown import SafeMarkdownRenderer
from .outline import MIN_SECTION_LEVEL, OutlineNode, parse_outline
from .search import SearchIndex, build_search_index

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WikiSection:
    id: str
    chapter_slug: str
    chapter_title: str
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
    # True for the single implicit section built from the content between the
    # H1 title and the first following heading. Its title always equals the
    # chapter title, so templates use this flag -- not string comparison
    # between `id` and `chapter_slug`, which only coincide by accident -- to
    # avoid rendering a redundant heading.
    is_intro: bool = False


@dataclass(frozen=True)
class WikiChapter:
    slug: str
    title: str
    source_name: str
    sections: Tuple[WikiSection, ...]
    ordinal: int
    #: Top-level sections only; each carries its own ``children``.
    outline: Tuple[WikiSection, ...] = ()


def _editorial_patterns() -> Tuple[re.Pattern, ...]:
    return tuple(
        re.compile(pattern)
        for pattern in getattr(settings, "WIKI_EDITORIAL_SECTION_PATTERNS", ())
    )


def _unique_slug(base_slug: str, seen: Dict[str, int]) -> str:
    count_so_far = seen.get(base_slug, 0)
    seen[base_slug] = count_so_far + 1
    if count_so_far == 0:
        return base_slug
    return f"{base_slug}-{count_so_far + 1}"


def _flatten(sections: Tuple[WikiSection, ...]) -> Iterator[WikiSection]:
    for section in sections:
        yield section
        yield from _flatten(section.children)


def _parse_chapter(
    source_name: str,
    text: str,
    ordinal: int,
    renderer: SafeMarkdownRenderer,
    chapter_slugs_seen: Dict[str, int],
    editorial_patterns: Tuple[re.Pattern, ...] = (),
) -> Tuple[WikiChapter, int]:
    def should_drop(title: str) -> bool:
        folded = title.casefold().strip()
        return any(pattern.match(folded) for pattern in editorial_patterns)

    title, nodes, dropped = parse_outline(
        text,
        renderer,
        source_name=source_name,
        should_drop_section=should_drop if editorial_patterns else None,
    )

    # The chapter slug (and thus its URL) is derived from the filename, not
    # the heading text: book filenames follow "<order>-<Name>.md", and using
    # the name portion keeps URLs stable even if a chapter's heading text is
    # edited later.
    file_stem = Path(source_name).stem
    name_part = re.sub(r"^\d+-", "", file_stem)
    chapter_slug = _unique_slug(
        slugify(name_part) or slugify(file_stem) or "chapter", chapter_slugs_seen
    )

    ordinals = count()

    def convert(node: OutlineNode) -> WikiSection:
        # Pre-order, so a section's ordinal matches its position in the
        # flattened tuple the search index sorts on.
        section_ordinal = next(ordinals)
        return WikiSection(
            id=node.anchor,
            chapter_slug=chapter_slug,
            chapter_title=title,
            title=node.title,
            title_html=node.title_html,
            plain_text=node.plain_text,
            html=node.html,
            ordinal=section_ordinal,
            level=node.level,
            children=tuple(convert(child) for child in node.children),
            is_intro=node.is_intro,
        )

    outline = tuple(convert(node) for node in nodes)
    chapter = WikiChapter(
        slug=chapter_slug,
        title=title,
        source_name=source_name,
        sections=tuple(_flatten(outline)),
        ordinal=ordinal,
        outline=outline,
    )
    return chapter, dropped


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
        editorial_patterns = _editorial_patterns()
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
                chapter, dropped = _parse_chapter(
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

    def search(self, query: str, limit: int = 30):
        return self._search_index.search(query, limit=limit)


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


def set_repository_for_tests(repository: WikiRepository) -> None:
    """Test-only hook to replace the process-wide repository singleton."""
    global _repository
    _repository = repository

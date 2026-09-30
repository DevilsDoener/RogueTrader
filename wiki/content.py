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
from dataclasses import dataclass
from functools import cached_property
from itertools import count
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

from django.conf import settings
from django.utils.text import slugify

from .manifest import (
    BAND_CHAPTERS,
    DASHBOARD_SHORTCUTS,
    QUICK_LINKS,
    QuickLink,
    ShortcutGroup,
    entry_for,
)
from .markdown import SafeMarkdownRenderer
from .outline import MIN_SECTION_LEVEL, OutlineNode, parse_outline
from .search import SearchIndex, build_search_index

logger = logging.getLogger(__name__)

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


def _editorial_patterns() -> Tuple[re.Pattern, ...]:
    return tuple(
        re.compile(pattern)
        for pattern in settings.WIKI_EDITORIAL_SECTION_PATTERNS
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

    # The slug comes from the manifest so that renaming a Markdown file cannot
    # silently move a page. A file without a manifest entry (a
    # WIKI_CONTENT_ALLOWLIST override or a test fixture) gets a slug derived
    # from its filename.
    entry = entry_for(source_name)
    if entry.slug:
        chapter_slug = _unique_slug(entry.slug, chapter_slugs_seen)
    else:
        file_stem = Path(source_name).stem
        name_part = re.sub(r"^\d+-", "", file_stem)
        chapter_slug = _unique_slug(
            slugify(name_part) or slugify(file_stem) or "chapter", chapter_slugs_seen
        )

    ordinals = count()

    def convert(node: OutlineNode, parent_titles: Tuple[str, ...] = ()) -> WikiSection:
        # Pre-order, so a section's ordinal matches its position in the
        # flattened tuple the search index sorts on.
        section_ordinal = next(ordinals)
        child_path = parent_titles if node.is_intro else parent_titles + (node.title,)
        return WikiSection(
            id=node.anchor,
            title=node.title,
            title_html=node.title_html,
            plain_text=node.plain_text,
            html=node.html,
            ordinal=section_ordinal,
            level=node.level,
            children=tuple(convert(child, child_path) for child in node.children),
            is_intro=node.is_intro,
            parent_titles=parent_titles,
        )

    outline = tuple(convert(node) for node in nodes)
    chapter = WikiChapter(
        slug=chapter_slug,
        title=title,
        source_name=source_name,
        sections=tuple(_flatten(outline)),
        ordinal=ordinal,
        outline=outline,
        numeral=entry.numeral,
        band=entry.band,
        search_weight=entry.search_weight,
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

    def search(self, query: str, limit: Optional[int] = 30):
        return self._search_index.search(query, limit=limit)

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

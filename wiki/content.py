"""Immutable in-memory content repository for the read-only wiki.

The book's Markdown chapters are mounted read-only into the container. On
Django startup (``WikiConfig.ready()``), the allow-listed files are parsed
once into immutable ``WikiChapter``/``WikiSection`` records and a search
index, and held in a module-level singleton. Requests never touch disk.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from django.conf import settings
from django.utils.text import slugify
from markdown_it import MarkdownIt

from .markdown import SafeMarkdownRenderer
from .search import SearchIndex, build_search_index

logger = logging.getLogger(__name__)

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")

_plain_text_parser = MarkdownIt("gfm-like", {"html": False, "linkify": False, "typographer": False})


@dataclass(frozen=True)
class WikiSection:
    id: str
    chapter_slug: str
    chapter_title: str
    title: str
    plain_text: str
    html: str
    ordinal: int


@dataclass(frozen=True)
class WikiChapter:
    slug: str
    title: str
    source_name: str
    sections: Tuple[WikiSection, ...]
    ordinal: int


def _unique_slug(base_slug: str, seen: Dict[str, int]) -> str:
    count = seen.get(base_slug, 0)
    seen[base_slug] = count + 1
    if count == 0:
        return base_slug
    return f"{base_slug}-{count + 1}"


def _extract_plain_text(markdown_text: str) -> str:
    tokens = _plain_text_parser.parse(markdown_text or "")
    fragments: List[str] = []
    for token in tokens:
        if token.type != "inline" or not token.children:
            continue
        for child in token.children:
            if child.type in ("text", "code_inline"):
                fragments.append(child.content)
            elif child.type in ("softbreak", "hardbreak"):
                fragments.append(" ")
    return " ".join("".join(fragments).split())


def _split_into_sections(lines: List[str]) -> List[Tuple[Optional[str], List[str]]]:
    """Split lines after the H1 title into (heading_text_or_None, body_lines).

    The first entry (heading_text is None) is the chapter's own front matter
    -- any content between the H1 title and the first H2 heading. Every
    subsequent entry corresponds to one H2 heading.
    """
    sections: List[Tuple[Optional[str], List[str]]] = []
    current_heading: Optional[str] = None
    current_lines: List[str] = []
    for line in lines:
        match = _HEADING_RE.match(line)
        if match and len(match.group(1)) == 2:
            sections.append((current_heading, current_lines))
            current_heading = match.group(2)
            current_lines = []
        else:
            current_lines.append(line)
    sections.append((current_heading, current_lines))
    return sections


def _parse_chapter(
    source_name: str,
    text: str,
    ordinal: int,
    renderer: SafeMarkdownRenderer,
    chapter_slugs_seen: Dict[str, int],
) -> WikiChapter:
    lines = text.splitlines()

    title = None
    title_index = None
    for index, line in enumerate(lines):
        match = _HEADING_RE.match(line)
        if match and len(match.group(1)) == 1:
            title = match.group(2)
            title_index = index
            break

    if title is None:
        title = Path(source_name).stem
        body_lines = lines
    else:
        body_lines = lines[title_index + 1 :]

    # The chapter slug (and thus its URL) is derived from the filename, not
    # the heading text: book filenames follow "<order>-<Name>.md", and using
    # the name portion keeps URLs stable even if a chapter's heading text is
    # edited later.
    file_stem = Path(source_name).stem
    name_part = re.sub(r"^\d+-", "", file_stem)
    chapter_slug = _unique_slug(slugify(name_part) or slugify(file_stem) or "chapter", chapter_slugs_seen)

    sections: List[WikiSection] = []
    section_slugs_seen: Dict[str, int] = {}
    section_ordinal = 0
    for heading_text, section_lines in _split_into_sections(body_lines):
        section_markdown = "\n".join(section_lines)
        plain_text = _extract_plain_text(section_markdown)

        if heading_text is None:
            if not plain_text.strip():
                continue
            section_title = title
        else:
            section_title = heading_text

        section_id = _unique_slug(slugify(section_title) or "section", section_slugs_seen)
        section_html = renderer.render(section_markdown)
        sections.append(
            WikiSection(
                id=section_id,
                chapter_slug=chapter_slug,
                chapter_title=title,
                title=section_title,
                plain_text=plain_text,
                html=section_html,
                ordinal=section_ordinal,
            )
        )
        section_ordinal += 1

    return WikiChapter(
        slug=chapter_slug,
        title=title,
        source_name=source_name,
        sections=tuple(sections),
        ordinal=ordinal,
    )


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
        chapter_slugs_seen: Dict[str, int] = {}
        chapters: List[WikiChapter] = []

        for ordinal, filename in enumerate(allowlist):
            path = root / filename
            try:
                text = path.read_text(encoding="utf-8")
            except FileNotFoundError:
                logger.warning("Wiki content file not found, skipping: %s", filename)
                continue
            except (OSError, UnicodeDecodeError) as exc:
                logger.warning(
                    "Skipping unreadable wiki content file %s (%s)", filename, exc.__class__.__name__
                )
                continue

            try:
                chapter = _parse_chapter(filename, text, ordinal, renderer, chapter_slugs_seen)
            except Exception:  # noqa: BLE001 - one bad chapter must not break the rest
                logger.exception("Failed to parse wiki content file, skipping: %s", filename)
                continue

            chapters.append(chapter)

        search_index = build_search_index(chapters)
        return cls(tuple(chapters), search_index)

    def chapters(self) -> Tuple[WikiChapter, ...]:
        return self._chapters

    def get_chapter(self, slug: str) -> Optional[WikiChapter]:
        return self._by_slug.get(slug)

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

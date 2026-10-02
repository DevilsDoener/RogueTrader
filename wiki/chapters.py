"""Chapter builder: one Markdown file in, one ``WikiChapter`` out.

The content rules live here -- which slug a chapter gets, how sections are
numbered, which editorial sections are hidden. ``wiki.content`` only decides
which files to read and keeps the result.
"""
from __future__ import annotations

import re
from itertools import count
from pathlib import Path
from typing import Dict, Iterator, Tuple

from django.conf import settings
from django.utils.text import slugify

from .manifest import ChapterEntry, entry_for
from .markdown import SafeMarkdownRenderer
from .outline import OutlineNode, parse_outline
from .records import WikiChapter, WikiSection


def editorial_patterns() -> Tuple[re.Pattern, ...]:
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


def _chapter_slug(entry: ChapterEntry, source_name: str, seen: Dict[str, int]) -> str:
    """The chapter's URL slug, unique among the chapters seen so far.

    The slug comes from the manifest so that renaming a Markdown file cannot
    silently move a page. A file without a manifest entry (a
    WIKI_CONTENT_ALLOWLIST override or a test fixture) gets a slug derived
    from its filename.
    """
    if entry.slug:
        return _unique_slug(entry.slug, seen)
    file_stem = Path(source_name).stem
    name_part = re.sub(r"^\d+-", "", file_stem)
    return _unique_slug(slugify(name_part) or slugify(file_stem) or "chapter", seen)


def _flatten(sections: Tuple[WikiSection, ...]) -> Iterator[WikiSection]:
    for section in sections:
        yield section
        yield from _flatten(section.children)


def _to_section(
    node: OutlineNode, ordinals: Iterator[int], parent_titles: Tuple[str, ...] = ()
) -> WikiSection:
    # Pre-order, so a section's ordinal matches its position in the flattened
    # tuple the search index sorts on.
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
        children=tuple(_to_section(child, ordinals, child_path) for child in node.children),
        is_intro=node.is_intro,
        parent_titles=parent_titles,
    )


def parse_chapter(
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

    entry = entry_for(source_name)
    chapter_slug = _chapter_slug(entry, source_name, chapter_slugs_seen)

    ordinals = count()
    outline = tuple(_to_section(node, ordinals) for node in nodes)
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

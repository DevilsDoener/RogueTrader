"""Suggestions for the Auspex command palette.

Pure functions over a ``WikiRepository`` so they can be tested without HTTP.
Everything returned is plain data: titles and paths are raw strings for the
client to render as text, and ``snippet_html`` is the one field that carries
markup (already escaped by ``wiki.search``, with ``<mark>`` around the match).
"""
from __future__ import annotations

from typing import List, Set
from urllib.parse import urlencode

from django.urls import reverse

from .search import is_searchable, tokenize

MAX_CHAPTERS = 4
MAX_SECTIONS = 6
MAX_HITS = 6

#: Full-text candidates fetched before the ones repeating a listed section are
#: dropped, so that a few overlaps do not leave the hit list short.
HIT_CANDIDATES = 12

#: The palette expands word prefixes from three letters ("hit loc" finds
#: "Hit Locations"), one fewer than the search page, because it is typed
#: into live and shows only a handful of hits.
SUGGEST_PREFIX_MIN_LENGTH = 3


def _section_url(chapter_slug: str, section_id: str, query: str) -> str:
    base = reverse("wiki:chapter", args=[chapter_slug])
    return f"{base}?{urlencode({'q': query})}#sec-{section_id}"


def _section_rank(title: str, query: str, first_token: str) -> int:
    folded = title.casefold()
    if folded.startswith(query):
        return 0
    if any(word.startswith(first_token) for word in tokenize(title)):
        return 1
    return 2


def _contains_all(tokens: List[str], text: str) -> bool:
    folded = text.casefold()
    return all(token in folded for token in tokens)


def _matching_chapters(repository, tokens: List[str]) -> list:
    found = []
    for chapter in repository.chapters():
        if _contains_all(tokens, chapter.title):
            found.append(chapter)
            if len(found) == MAX_CHAPTERS:
                break
    return found


def _repeats_chapter(chapter, section) -> bool:
    """True for a section that is just its chapter again (the intro or a twin)."""
    return section.is_intro or section.title.casefold() == chapter.title.casefold()


def _matching_sections(
    repository, tokens: List[str], query: str, listed: Set[str]
) -> list:
    """The best ``MAX_SECTIONS`` (chapter, section) pairs for the title match.

    ``listed`` holds the slugs of the chapters already suggested; their own
    chapter-titled rows would only repeat that suggestion.
    """
    ranked = []
    for chapter in repository.chapters():
        for section in chapter.sections:
            if section.is_intro:
                continue
            if chapter.slug in listed and _repeats_chapter(chapter, section):
                continue
            if _contains_all(tokens, section.title):
                rank = _section_rank(section.title, query, tokens[0])
                ranked.append((rank, chapter.ordinal, section.ordinal, chapter, section))
    ranked.sort(key=lambda item: item[:3])
    return [(chapter, section) for *_key, chapter, section in ranked[:MAX_SECTIONS]]


def suggest(repository, query: str) -> dict:
    """JSON-ready suggestions for ``query``: chapters, sections and full-text hits."""
    result = {
        "query": query,
        "chapters": [],
        "sections": [],
        "hits": [],
    }
    if not is_searchable(query):
        return result

    tokens = query.casefold().split()

    chapters = _matching_chapters(repository, tokens)
    listed_chapters = {chapter.slug for chapter in chapters}
    result["chapters"] = [
        {
            "title": chapter.title,
            "short_title": chapter.short_title,
            "numeral": chapter.numeral,
            "url": reverse("wiki:chapter", args=[chapter.slug]),
        }
        for chapter in chapters
    ]

    matched = _matching_sections(
        repository, tokens, query.casefold().strip(), listed_chapters
    )
    listed = {(chapter.slug, section.id) for chapter, section in matched}
    result["sections"] = [
        {
            "title": section.title,
            "chapter": chapter.short_title,
            "numeral": chapter.numeral,
            "path": list(section.parent_titles),
            "url": _section_url(chapter.slug, section.id, query),
        }
        for chapter, section in matched
    ]

    hits = []
    for hit in repository.search(
        query, limit=HIT_CANDIDATES, prefix_min_length=SUGGEST_PREFIX_MIN_LENGTH
    ):
        if (hit.chapter_slug, hit.section_id) in listed:
            continue
        chapter = repository.get_chapter(hit.chapter_slug)
        if hit.chapter_slug in listed_chapters:
            section = chapter.sections_by_id.get(hit.section_id)
            if section is not None and _repeats_chapter(chapter, section):
                continue
        hits.append(
            {
                "title": hit.title,
                "chapter": chapter.short_title,
                "numeral": chapter.numeral,
                "path": list(hit.path),
                "snippet_html": hit.snippet,
                "url": _section_url(hit.chapter_slug, hit.section_id, query),
            }
        )
        if len(hits) == MAX_HITS:
            break
    result["hits"] = hits
    return result

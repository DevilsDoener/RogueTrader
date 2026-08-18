"""In-memory full-text search index over wiki sections."""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple

TITLE_WEIGHT = 4
BODY_WEIGHT = 1
SNIPPET_RADIUS = 90
SNIPPET_MAX_LENGTH = 180
MIN_QUERY_LENGTH = 2

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


@dataclass(frozen=True)
class SearchResult:
    chapter_slug: str
    chapter_title: str
    section_id: str
    title: str
    snippet: str
    score: int


def tokenize(text: str) -> List[str]:
    """Casefolded Unicode word tokens."""
    return _TOKEN_RE.findall((text or "").casefold())


def _count_tokens(tokens: Iterable[str]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1
    return counts


def _make_snippet(plain_text: str, terms: Sequence[str]) -> str:
    casefolded = plain_text.casefold()
    match_start = None
    match_end = None
    for term in terms:
        index = casefolded.find(term)
        if index != -1 and (match_start is None or index < match_start):
            match_start = index
            match_end = index + len(term)

    if match_start is None:
        return html.escape(plain_text[:SNIPPET_MAX_LENGTH])

    # Keep the whole window (prefix + match + suffix) within
    # SNIPPET_MAX_LENGTH regardless of how long the matched term itself is,
    # rather than always padding by a fixed radius on each side.
    context_budget = max(0, SNIPPET_MAX_LENGTH - (match_end - match_start))
    radius = min(SNIPPET_RADIUS, context_budget // 2)
    start = max(0, match_start - radius)
    end = min(len(plain_text), match_end + radius)
    prefix = html.escape(plain_text[start:match_start])
    matched = html.escape(plain_text[match_start:match_end])
    suffix = html.escape(plain_text[match_end:end])
    return f"{prefix}<mark>{matched}</mark>{suffix}"


class SearchIndex:
    """Ranks wiki sections against a query using weighted term intersection."""

    def __init__(self, entries: Sequence[Tuple[object, object, Dict[str, int], Dict[str, int]]]):
        # Each entry: (chapter, section, title_token_counts, body_token_counts)
        self._entries = tuple(entries)

    def search(self, query: str, limit: int = 30) -> Tuple[SearchResult, ...]:
        if len((query or "").replace(" ", "")) < MIN_QUERY_LENGTH:
            return ()

        terms = sorted(set(tokenize(query)))
        if not terms:
            return ()

        scored: List[Tuple[int, int, int, object, object]] = []
        for chapter, section, title_tokens, body_tokens in self._entries:
            if not all(term in title_tokens or term in body_tokens for term in terms):
                continue
            score = sum(
                title_tokens.get(term, 0) * TITLE_WEIGHT + body_tokens.get(term, 0) * BODY_WEIGHT
                for term in terms
            )
            if score <= 0:
                continue
            scored.append((score, chapter.ordinal, section.ordinal, chapter, section))

        scored.sort(key=lambda item: (-item[0], item[1], item[2]))

        results = []
        for score, _chapter_ordinal, _section_ordinal, chapter, section in scored[:limit]:
            results.append(
                SearchResult(
                    chapter_slug=chapter.slug,
                    chapter_title=chapter.title,
                    section_id=section.id,
                    title=section.title,
                    snippet=_make_snippet(section.plain_text, terms),
                    score=score,
                )
            )
        return tuple(results)


def build_search_index(chapters: Iterable[object]) -> SearchIndex:
    entries = []
    for chapter in chapters:
        for section in chapter.sections:
            title_tokens = _count_tokens(tokenize(section.title))
            body_tokens = _count_tokens(tokenize(section.plain_text))
            entries.append((chapter, section, title_tokens, body_tokens))
    return SearchIndex(entries)

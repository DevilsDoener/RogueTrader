"""In-memory full-text search index over wiki sections.

Three things shape the ranking here, each chosen against the real corpus:

- **German queries go through an alias table.** The interface is German, the
  group speaks German, and the book is English -- without it "Stärke",
  "Waffe", "Schiff" and "Deckung" score zero hits. Diacritic folding does not
  help (only 35 of ~101,000 tokens carry an umlaut); a curated alias table
  (``wiki.aliases``) does.
- **Term frequency saturates.** Raw counts let one very long section win
  almost any term it happens to repeat. True length normalisation
  (sqrt/log/BM25) over-corrects on this corpus: it promotes a statblock that
  mentions a word once over the rules section actually about it, and pushes
  the section literally titled "Profit Factor" off the top spot. Saturating
  the body count keeps the wins and avoids that.
- **Some chapters are navigation, not rules.** The page-number index and the
  foreword would take top spots for ordinary words; their lower weight comes
  from ``wiki/manifest.py``.
"""
from __future__ import annotations

import bisect
from collections import Counter
from typing import Dict, Iterable, List, NamedTuple, Optional, Sequence, Set, Tuple

from .aliases import QUERY_ALIASES
from .records import WikiChapter, WikiSection
from .search import (
    MIN_QUERY_LENGTH,
    SearchResult,
    clamp_query,
    is_searchable,
    query_tokens,
    tokenize,
)
from .snippets import make_snippet

TITLE_WEIGHT = 4
BODY_WEIGHT = 1

#: Saturation constant for body term frequency: f * (k + 1) / (f + k). Higher
#: k means counts keep mattering for longer; 1.5 caps a runaway repeat while
#: still ranking three mentions above one.
TF_SATURATION = 1.5

#: Shortest query term that may expand to longer words sharing its prefix.
#: Below this almost everything matches and the expansion is noise.
PREFIX_MIN_LENGTH = 4

#: Prefix matches count for less than the word the reader actually typed.
PREFIX_WEIGHT = 0.5


class IndexedSection(NamedTuple):
    """One section with its token counts, as the index holds it."""

    chapter: WikiChapter
    section: WikiSection
    title_tokens: Dict[str, int]
    body_tokens: Dict[str, int]


class _Scored(NamedTuple):
    score: float
    chapter_ordinal: int
    section_ordinal: int
    entry: IndexedSection
    matched: Tuple[str, ...]


def _saturate(count: int) -> float:
    """Diminishing returns for repeated body mentions."""
    if count <= 0:
        return 0.0
    return count * (TF_SATURATION + 1) / (count + TF_SATURATION)


def _score_entry(
    entry: IndexedSection, expanded: Sequence[Dict[str, float]]
) -> Optional[Tuple[float, Tuple[str, ...]]]:
    """Score one section against the expanded query terms.

    Returns ``(weighted score, matched variants)`` or ``None`` when some query
    term matches nothing in the section. Every query term must match
    something: AND semantics are preserved across terms, the alias set only
    widens what counts as a match for one term.
    """
    total = 0.0
    matched: Set[str] = set()
    for variants in expanded:
        best = 0.0
        best_variant = None
        for variant, weight in variants.items():
            title_count = entry.title_tokens.get(variant, 0)
            body_count = entry.body_tokens.get(variant, 0)
            if not title_count and not body_count:
                continue
            value = (
                title_count * TITLE_WEIGHT + _saturate(body_count) * BODY_WEIGHT
            ) * weight
            if value > best:
                best = value
                best_variant = variant
        if best <= 0:
            return None
        total += best
        matched.add(best_variant)
    weighted = total * entry.chapter.search_weight
    if weighted <= 0:
        return None
    return weighted, tuple(sorted(matched))


class SearchIndex:
    """Ranks wiki sections against a query using weighted term intersection."""

    def __init__(
        self,
        entries: Sequence[IndexedSection],
        vocabulary: Sequence[str] = (),
    ):
        self._entries = tuple(entries)
        self._vocabulary = tuple(vocabulary)

    def _expand(
        self, term: str, prefix_min_length: int = PREFIX_MIN_LENGTH
    ) -> Dict[str, float]:
        """Query term -> {variant: weight}.

        The typed word and any curated alias count fully; words that merely
        start with it count for less, so "laspistol" still ranks an exact
        "laspistol" above "laspistols". ``prefix_min_length`` is the shortest term
        that expands this way; the search page keeps ``PREFIX_MIN_LENGTH``.
        """
        variants: Dict[str, float] = {term: 1.0}
        for alias in QUERY_ALIASES.get(term, ()):
            variants.setdefault(alias, 1.0)

        if len(term) >= prefix_min_length and self._vocabulary:
            start = bisect.bisect_left(self._vocabulary, term)
            for candidate in self._vocabulary[start:]:
                if not candidate.startswith(term):
                    break
                if candidate not in variants:
                    variants[candidate] = PREFIX_WEIGHT
        return variants

    def highlight_terms(self, query: str) -> Tuple[str, ...]:
        """Words a results page should mark in a section for ``query``.

        The typed words plus their curated aliases, deliberately without the
        prefix expansion ``search`` applies: highlighting every word that merely
        starts with the query would paint half a page for a short term.
        """
        query = clamp_query(query)
        if not is_searchable(query):
            return ()
        terms: Set[str] = set()
        for token in query_tokens(query):
            terms.add(token)
            terms.update(QUERY_ALIASES.get(token, ()))
        return tuple(sorted(term for term in terms if len(term) >= MIN_QUERY_LENGTH))

    def search(
        self,
        query: str,
        limit: Optional[int] = 30,
        prefix_min_length: int = PREFIX_MIN_LENGTH,
    ) -> Tuple[SearchResult, ...]:
        query = clamp_query(query)
        if not is_searchable(query):
            return ()

        terms = sorted(set(query_tokens(query)))
        if not terms:
            return ()

        expanded = [self._expand(term, prefix_min_length) for term in terms]

        scored: List[_Scored] = []
        for entry in self._entries:
            outcome = _score_entry(entry, expanded)
            if outcome is None:
                continue
            score, matched = outcome
            scored.append(
                _Scored(score, entry.chapter.ordinal, entry.section.ordinal, entry, matched)
            )

        scored.sort(key=lambda item: (-item.score, item.chapter_ordinal, item.section_ordinal))

        results = []
        for item in scored[:limit]:
            section = item.entry.section
            results.append(
                SearchResult(
                    chapter_slug=item.entry.chapter.slug,
                    section_id=section.id,
                    title=section.title,
                    snippet=make_snippet(section.plain_text, item.matched),
                    score=item.score,
                    path=section.parent_titles,
                )
            )
        return tuple(results)


def build_search_index(chapters: Iterable[WikiChapter]) -> SearchIndex:
    entries = []
    vocabulary: Set[str] = set()
    for chapter in chapters:
        for section in chapter.sections:
            title_tokens = Counter(tokenize(section.title))
            body_tokens = Counter(tokenize(section.plain_text))
            vocabulary.update(title_tokens)
            vocabulary.update(body_tokens)
            entries.append(IndexedSection(chapter, section, title_tokens, body_tokens))
    return SearchIndex(entries, sorted(vocabulary))

"""Assembly of the search results page.

A pure function over a ``WikiRepository`` (like ``wiki.suggest``), so the
facet and filter rules are testable without HTTP. The view only adds the
request's two query parameters.
"""
from __future__ import annotations

from collections import Counter

from .search import MIN_QUERY_LENGTH, clamp_query, is_searchable

#: Hits shown on the results page; the rest are reachable via the chapter facets.
SEARCH_RESULTS_LIMIT = 50


def build_search_page(repository, query: str, requested_chapter: str = "") -> dict:
    """The template context of the search page for ``query``.

    ``requested_chapter`` is the ``?kapitel=`` slug; an unknown or hit-less one
    is ignored rather than producing an empty page the reader cannot explain.
    """
    query = clamp_query(query)
    all_results = repository.search(query, limit=None) if query else ()

    # One facet per chapter with at least one hit, in book order.
    counts = Counter(result.chapter_slug for result in all_results)
    facets = [
        {"chapter": chapter, "count": counts[chapter.slug]}
        for chapter in repository.chapters()
        if counts[chapter.slug]
    ]
    active_chapter = next(
        (f["chapter"] for f in facets if f["chapter"].slug == requested_chapter), None
    )
    filtered = (
        [r for r in all_results if r.chapter_slug == active_chapter.slug]
        if active_chapter
        else list(all_results)
    )
    shown = filtered[:SEARCH_RESULTS_LIMIT]

    return {
        "query": query,
        # (result, chapter) pairs: templates cannot index a dict by a variable,
        # and each card shows its chapter's numeral and short title.
        "hits": [
            (result, repository.get_chapter(result.chapter_slug)) for result in shown
        ],
        "total_count": len(filtered),
        "all_count": len(all_results),
        "facets": facets,
        "active_chapter": active_chapter,
        "results_capped": len(filtered) > SEARCH_RESULTS_LIMIT,
        "search_results_limit": SEARCH_RESULTS_LIMIT,
        "quick_links": repository.quick_links(),
        # Distinguishes "too short to search" from "searched, found nothing",
        # which the template could not tell apart from an empty result tuple.
        "query_too_short": bool(query) and not is_searchable(query),
        "min_query_length": MIN_QUERY_LENGTH,
    }

"""Query rules and result type shared by search, suggestions and highlighting.

What counts as a searchable query (length, word count, tokenisation) is
decided here once; ``wiki.index`` ranks sections against it, ``wiki.suggest``
and the views call it. Alias table: ``wiki.aliases``; snippets:
``wiki.snippets``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

MIN_QUERY_LENGTH = 2

#: A query is cut to this many characters and this many words before anything
#: is tokenised, expanded or scanned. Nobody types more; a script posting a
#: few thousand distinct terms would otherwise make every request scan the
#: whole corpus for each of them. Over-long input is truncated, not rejected.
MAX_QUERY_LENGTH = 200
MAX_QUERY_TOKENS = 10

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_WORD_RE = re.compile(r"\S+")


def clamp_query(query: Optional[str]) -> str:
    """``query`` cut to ``MAX_QUERY_LENGTH`` characters and ``MAX_QUERY_TOKENS`` words."""
    query = (query or "")[:MAX_QUERY_LENGTH]
    words = list(_WORD_RE.finditer(query))
    if len(words) > MAX_QUERY_TOKENS:
        query = query[: words[MAX_QUERY_TOKENS - 1].end()]
    return query


def is_searchable(query: Optional[str]) -> bool:
    """Whether ``query`` has enough non-whitespace characters to search for.

    The one length rule shared by search, suggestions and the search page.
    """
    return len("".join((query or "").split())) >= MIN_QUERY_LENGTH


def tokenize(text: str) -> List[str]:
    """Casefolded Unicode word tokens."""
    return _TOKEN_RE.findall((text or "").casefold())


def query_tokens(query: Optional[str]) -> List[str]:
    """The first ``MAX_QUERY_TOKENS`` word tokens of the (clamped) query."""
    return tokenize(clamp_query(query))[:MAX_QUERY_TOKENS]


@dataclass(frozen=True)
class SearchResult:
    chapter_slug: str
    section_id: str
    title: str
    snippet: str
    score: float
    #: Ancestor headings of the section, outermost first (empty for a top-level
    #: section or the intro).
    path: Tuple[str, ...] = ()

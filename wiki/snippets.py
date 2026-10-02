"""Search-result snippets: an escaped window around the first match.

This is the one place that turns section text into markup for the search page
and the Auspex palette, so it is kept apart for review: every slice of the text
is escaped on its own, after slicing, and the only markup ever added is a
literal ``<mark>``. The result is returned as ``SafeString`` from the single
``mark_safe`` call at the end of ``make_snippet``; templates need no ``|safe``.
"""
from __future__ import annotations

import html
from collections.abc import Sequence

from django.utils.safestring import SafeString, mark_safe

SNIPPET_RADIUS = 90
SNIPPET_MAX_LENGTH = 180
SNIPPET_ELLIPSIS = "…"


def _casefold_with_offsets(text: str) -> tuple[str, list[int]]:
    """Casefold ``text`` and map every folded index back to its source index.

    Casefolding can lengthen a string ("ß" becomes "ss"), so an offset
    found in the folded text must not be used to slice the original directly.
    The returned list has one entry per folded character plus a final
    ``len(text)`` sentinel.
    """
    folded = text.casefold()
    if len(folded) == len(text):
        # casefold never yields an empty string for a character, so equal
        # lengths mean every character folded to exactly one.
        return folded, list(range(len(text) + 1))
    pieces: list[str] = []
    origin: list[int] = []
    for index, char in enumerate(text):
        piece = char.casefold()
        pieces.append(piece)
        origin.extend([index] * len(piece))
    origin.append(len(text))
    return "".join(pieces), origin


def _trim_start(text: str, start: int, limit: int) -> int:
    """Move ``start`` forward to the next word start, never past ``limit``."""
    if start <= 0 or text[start - 1].isspace():
        return start
    for index in range(start, limit):
        if text[index].isspace():
            while index < limit and text[index].isspace():
                index += 1
            return index
    return limit


def _trim_end(text: str, end: int, limit: int) -> int:
    """Move ``end`` back to the previous word end, never before ``limit``."""
    if end >= len(text) or text[end].isspace():
        return end
    for index in range(end - 1, limit - 1, -1):
        if text[index].isspace():
            while index > limit and text[index - 1].isspace():
                index -= 1
            return index
    return limit


def make_snippet(plain_text: str, terms: Sequence[str]) -> SafeString:
    """Escaped window around the first match; only ``<mark>`` is markup.

    The window is cut at word boundaries, and an ellipsis marks each side
    where text was left out.
    """
    # The one place that declares the result safe: ``_snippet_markup`` builds it
    # from escaped segments and a literal <mark> pair, nothing else.
    return mark_safe(_snippet_markup(plain_text, terms))  # noqa: S308


def _snippet_markup(plain_text: str, terms: Sequence[str]) -> str:
    casefolded, origin = _casefold_with_offsets(plain_text)
    match_start = None
    match_end = None
    for term in terms:
        if not term:
            continue
        index = casefolded.find(term)
        if index == -1:
            continue
        start_in_text = origin[index]
        end_in_text = origin[index + len(term) - 1] + 1
        if match_start is None or start_in_text < match_start:
            match_start = start_in_text
            match_end = end_in_text

    if match_start is None:
        end = min(len(plain_text), SNIPPET_MAX_LENGTH)
        if end < len(plain_text):
            end = _trim_end(plain_text, end, 0) or end
        text = html.escape(plain_text[:end])
        return text + SNIPPET_ELLIPSIS if end < len(plain_text) else text

    # Keep the whole window (prefix + match + suffix) within
    # SNIPPET_MAX_LENGTH regardless of how long the matched term itself is,
    # rather than always padding by a fixed radius on each side.
    context_budget = max(0, SNIPPET_MAX_LENGTH - (match_end - match_start))
    radius = min(SNIPPET_RADIUS, context_budget // 2)
    start = _trim_start(plain_text, max(0, match_start - radius), match_start)
    end = _trim_end(plain_text, min(len(plain_text), match_end + radius), match_end)
    prefix = html.escape(plain_text[start:match_start])
    matched = html.escape(plain_text[match_start:match_end])
    suffix = html.escape(plain_text[match_end:end])
    lead = SNIPPET_ELLIPSIS if start > 0 else ""
    tail = SNIPPET_ELLIPSIS if end < len(plain_text) else ""
    return f"{lead}{prefix}<mark>{matched}</mark>{suffix}{tail}"

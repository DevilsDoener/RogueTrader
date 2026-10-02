"""Which characters a sheet text value may contain, and display-time cleanup.

One definition for both directions: :func:`unsafe_text_problem` is what the
write path (``FieldSpec.validate_value``) rejects, and :func:`display_text`
makes any value that is *already stored* harmless to render (a lone UTF-16
surrogate raises ``UnicodeEncodeError`` when a page is encoded, which would
turn every page showing the value into a 500).

Rejected: lone surrogates (not UTF-8 encodable), C0/C1 control characters
(NUL, newline, tab, ESC, ...; every sheet input is single-line) and the bidi
embedding/override/isolate characters U+202A-202E and U+2066-2069, which can
make one user's value read differently in the admin list and the history.
"""
from __future__ import annotations

import re

_UNSAFE = re.compile("[\x00-\x1f\x7f-\x9f‪-‮⁦-⁩\ud800-\udfff]")

_BIDI_CONTROLS = frozenset("‪‫‬‭‮⁦⁧⁨⁩")

#: Shown instead of a stored lone surrogate.
REPLACEMENT = "�"


def _is_surrogate(char: str) -> bool:
    return "\ud800" <= char <= "\udfff"


def unsafe_text_problem(text: str) -> str | None:
    """A short English reason ``text`` is not allowed in a sheet field, or ``None``."""
    match = _UNSAFE.search(text)
    if match is None:
        return None
    char = match.group()
    if _is_surrogate(char):
        return "not valid UTF-8 text"
    if char in _BIDI_CONTROLS:
        return "bidirectional control character"
    return "control character"


def display_text(value):
    """``value`` made safe to render: unsafe characters in a string are dropped
    (lone surrogates become U+FFFD); anything that is not a string is returned
    unchanged.
    """
    if not isinstance(value, str) or _UNSAFE.search(value) is None:
        return value
    return _UNSAFE.sub(
        lambda match: REPLACEMENT if _is_surrogate(match.group()) else "", value
    )

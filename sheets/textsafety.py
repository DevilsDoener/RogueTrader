"""Which characters a sheet text value may contain, and display-time cleanup.

One definition for both directions: :func:`unsafe_text_problem` is what the
write path (``FieldSpec.validate_value``) rejects, and :func:`display_text`
makes any value that is *already stored* harmless to render (a lone UTF-16
surrogate raises ``UnicodeEncodeError`` when a page is encoded, which would
turn every page showing the value into a 500).

Rejected: lone surrogates (not UTF-8 encodable), C0/C1 control characters
(NUL, newline, tab, ESC, ...; every sheet input is single-line), the bidi
embedding/override/isolate characters U+202A-202E and U+2066-2069, which can
make one user's value read differently in the admin list and the history, and
the other invisible or line-breaking characters: U+061C, U+200B, U+200E,
U+200F (marks and zero-width space), U+2028/U+2029 (line and paragraph
separator) and U+FEFF. U+200C/U+200D (zero-width non-joiner / joiner) stay
allowed because emoji sequences and some scripts need them.

The source holds these characters only as backslash-u escapes, never literally.
"""
from __future__ import annotations

import re

_UNSAFE = re.compile(
    "[\x00-\x1f\x7f-\x9f"  # C0 / C1 controls
    "\u061c\u200b\u200e\u200f"  # Arabic letter mark, zero-width space, LRM, RLM
    "\u2028\u2029"  # line and paragraph separator
    "\u202a-\u202e\u2066-\u2069"  # bidi embedding, override and isolate controls
    "\ufeff"  # byte order mark / zero-width no-break space
    "\ud800-\udfff]"  # lone surrogates
)

_BIDI_CONTROLS = frozenset(
    "\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069"
)
_INVISIBLE = frozenset("\u200b\ufeff")

#: Shown instead of a stored lone surrogate.
REPLACEMENT = "\ufffd"


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
    if char in _INVISIBLE:
        return "invisible character"
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

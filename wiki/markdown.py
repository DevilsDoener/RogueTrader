"""Safe Markdown rendering for wiki content.

Renders trusted-but-external Markdown content (book chapters mounted
read-only into the container) to HTML while refusing to execute raw HTML or
unsafe link protocols. Safety is enforced in one place, deliberately:

- ``markdown-it-py`` is configured with ``html`` disabled, so raw HTML in the
  source is treated as literal text (auto-escaped on render), and its own
  link-destination validator is overridden to always accept (see
  ``_build_parser``) so that link syntax always parses into a real ``<a>``
  tag instead of silently falling back to literal bracket text for
  "unsafe-looking" URLs.
- Bleach then cleans the rendered HTML against a small allowlist of
  tags/attributes/protocols. This is the *only* layer that decides which
  link protocols are permitted, so the rule stays in one auditable place
  instead of being split between two libraries with different opinions.
  ``img`` is deliberately not in ``ALLOWED_TAGS`` below -- image syntax is
  parsed the same permissive way as links (see ``_build_parser``), but
  Bleach then strips the resulting ``<img>`` tag entirely, so Markdown
  image syntax currently renders as nothing rather than a picture.

Two table-specific passes sit either side of Bleach:

- *Before*, a core rule rewrites markdown-it's column-alignment ``style``
  attribute into one of three fixed class names (``_table_alignment_to_class``).
  Bleach has no ``style`` in ``ALLOWED_ATTRIBUTES``, so the alignment declared
  by ``|---:|`` used to be dropped silently. The class names are generated
  here, never copied from the document, and ``ALLOWED_ATTRIBUTES`` admits
  them through a *value*-checking callable rather than a bare attribute name.
- *After*, ``_wrap_tables`` puts each table in a horizontally scrollable
  container. It runs on already-sanitized HTML on purpose: the wrapper is
  entirely our own markup and therefore never needs ``div`` or a general
  ``class`` attribute in the allowlist.
"""
from __future__ import annotations

import re

import bleach
from markdown_it import MarkdownIt

ALLOWED_TAGS = [
    "h1", "h2", "h3", "h4", "h5", "h6",
    "p", "br", "hr",
    "strong", "em",
    "ul", "ol", "li",
    "code", "pre",
    "blockquote",
    "table", "thead", "tbody", "tr", "th", "td",
    "a",
]

#: markdown-it expresses a table column's alignment as an inline style on each
#: cell. Map those three values onto class names we control.
_ALIGNMENT_CLASSES = {
    "text-align:left": "wiki-col-left",
    "text-align:center": "wiki-col-center",
    "text-align:right": "wiki-col-right",
}
_ALIGNMENT_CLASS_VALUES = frozenset(_ALIGNMENT_CLASSES.values())


def _allow_column_alignment_class(tag: str, name: str, value: str) -> bool:
    """Admit only the exact alignment classes this module generates.

    Bleach accepts a callable per tag, which lets the allowlist constrain the
    *value* and not merely the attribute name -- a bare ``{"td": ["class"]}``
    would let any class through.
    """
    return name == "class" and value in _ALIGNMENT_CLASS_VALUES


ALLOWED_ATTRIBUTES = {
    "a": ["href", "title"],
    "th": _allow_column_alignment_class,
    "td": _allow_column_alignment_class,
}

ALLOWED_PROTOCOLS = ["http", "https", "mailto"]

#: At and above this column count a table is laid out at its natural width
#: inside a scrolling container instead of being squeezed into the article.
#: Measured against the corpus: every table with this many columns holds only
#: short codes, while narrower tables can carry multi-sentence prose cells that
#: must be allowed to wrap.
WIDE_TABLE_MIN_COLUMNS = 7

_TABLE_RE = re.compile(r"<table>.*?</table>", re.DOTALL)
_FIRST_ROW_RE = re.compile(r"<tr>(.*?)</tr>", re.DOTALL)
_CELL_RE = re.compile(r"<t[hd][\s>]")


def _table_alignment_to_class(state) -> None:
    """Rewrite markdown-it's alignment ``style`` into a fixed class name.

    Table cell tokens are top-level in the token stream (not ``inline``
    children), so one flat pass reaches every cell. Clearing ``attrs`` first
    means any attribute a future markdown-it version adds is dropped here by
    construction rather than relying on Bleach to catch it.
    """
    for token in state.tokens:
        if token.type not in ("th_open", "td_open"):
            continue
        style = (token.attrGet("style") or "").replace(" ", "")
        token.attrs = {}
        css_class = _ALIGNMENT_CLASSES.get(style)
        if css_class:
            token.attrSet("class", css_class)


def _wrap_tables(html: str) -> str:
    """Wrap each table in a horizontally scrollable container.

    Runs *after* Bleach, so the input is already sanitized and this wrapper is
    entirely our own markup. That is what keeps ``div`` and a general ``class``
    attribute out of the allowlist. Two properties make the string-level match
    safe: Bleach strips every attribute from ``<table>``, so the opening tag is
    always exactly ``<table>``; and a literal ``<table>`` in the Markdown source
    is escaped to text by ``html: False`` long before it could look like a tag.
    GFM tables cannot nest, so the non-greedy match cannot straddle two tables.
    """

    def _wrap(match: "re.Match[str]") -> str:
        table_html = match.group(0)
        first_row = _FIRST_ROW_RE.search(table_html)
        columns = len(_CELL_RE.findall(first_row.group(1))) if first_row else 0
        mode = "wide" if columns >= WIDE_TABLE_MIN_COLUMNS else "flow"
        return (
            f'<div class="wiki-table-scroll" data-table-mode="{mode}">'
            f"{table_html}</div>"
        )

    return _TABLE_RE.sub(_wrap, html)


def _build_parser() -> MarkdownIt:
    parser = MarkdownIt("gfm-like", {"html": False, "linkify": False, "typographer": False})
    # Always parse link/image syntax into real <a>/<img> tags, even for
    # unsafe-looking destinations, so that Bleach -- our single source of
    # truth for protocol filtering -- gets a chance to strip the attribute.
    # Otherwise markdown-it-py's own validator silently falls back to
    # rendering the raw "[text](javascript:...)" syntax as literal text,
    # which still leaks the dangerous string into the page.
    parser.validateLink = lambda url: True
    parser.core.ruler.push("wiki_table_alignment", _table_alignment_to_class)
    return parser


def _clean(raw_html: str) -> str:
    return bleach.clean(
        raw_html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    )


class SafeMarkdownRenderer:
    """Renders Markdown source to sanitized HTML.

    ``render`` handles a whole document. The token-level entry points exist so
    a chapter can be parsed *once* and then rendered in per-heading slices (see
    ``wiki.outline``) instead of being re-split and re-parsed per section.
    """

    def __init__(self) -> None:
        self._parser = _build_parser()

    def parse(self, text: str):
        """Token stream for ``text``, alignment classes already applied."""
        return self._parser.parse(text or "")

    def render(self, text: str) -> str:
        return _wrap_tables(_clean(self._parser.render(text or "")))

    def render_tokens(self, tokens) -> str:
        """Render an already-parsed block-token slice."""
        tokens = list(tokens)
        if not tokens:
            return ""
        raw_html = self._parser.renderer.render(tokens, self._parser.options, {})
        return _wrap_tables(_clean(raw_html))

    def render_inline(self, inline_token) -> str:
        """Render a heading's inline children (bold, code, ...) to safe HTML.

        No table wrapping: inline content cannot contain a table.
        """
        children = getattr(inline_token, "children", None) or []
        if not children:
            return ""
        raw_html = self._parser.renderer.renderInline(
            children, self._parser.options, {}
        )
        return _clean(raw_html)

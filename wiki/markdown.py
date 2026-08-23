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
"""
from __future__ import annotations

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

ALLOWED_ATTRIBUTES = {
    "a": ["href", "title"],
}

ALLOWED_PROTOCOLS = ["http", "https", "mailto"]


def _build_parser() -> MarkdownIt:
    parser = MarkdownIt("gfm-like", {"html": False, "linkify": False, "typographer": False})
    # Always parse link/image syntax into real <a>/<img> tags, even for
    # unsafe-looking destinations, so that Bleach -- our single source of
    # truth for protocol filtering -- gets a chance to strip the attribute.
    # Otherwise markdown-it-py's own validator silently falls back to
    # rendering the raw "[text](javascript:...)" syntax as literal text,
    # which still leaks the dangerous string into the page.
    parser.validateLink = lambda url: True
    return parser


class SafeMarkdownRenderer:
    """Renders Markdown source to sanitized HTML."""

    def __init__(self) -> None:
        self._parser = _build_parser()

    def render(self, text: str) -> str:
        raw_html = self._parser.render(text or "")
        return bleach.clean(
            raw_html,
            tags=ALLOWED_TAGS,
            attributes=ALLOWED_ATTRIBUTES,
            protocols=ALLOWED_PROTOCOLS,
            strip=True,
        )

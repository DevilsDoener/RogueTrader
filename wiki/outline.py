"""Build a navigable heading tree for one chapter.

Replaces the previous line-regex splitter, which recognised ``##`` only. Two
things follow from that limitation and are fixed here:

- Chapters whose sub-sections are ``#`` rather than ``##`` collapsed into a
  single enormous section. ``02-Karrierewege.md`` is the extreme case: its
  eight career paths are H1, so ~93 KB and 1,400 table rows ended up under one
  anchor with no way to link to any individual career. The rule below is *the
  first H1 is the chapter title; every later heading counts as
  ``max(level, 2)``* -- which turns that file into twelve sections with their
  own children without editing a single Markdown file.
- ``###`` and ``####`` headings were invisible to navigation entirely. They
  are now nodes, so a chapter's table of contents can nest.

The tree is keyed on *nesting*, not on the absolute heading level, so files
that wrap their entries in one extra container (``14-Traits.md`` uses
``## > ### > ####`` where ``04-Talents.md`` uses ``## > ###``) come out with
the same shape and need no normalisation.

Working from the token stream rather than from lines also means fenced code,
indented code, setext headings and a ``#`` inside a table cell are handled
correctly by construction -- the old splitter carried hand-written fence
tracking for exactly one of those cases.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence, Tuple

from django.utils.text import slugify

#: Headings below the chapter title are clamped to this level, so a stray H1
#: in the body becomes a top-level section rather than a second chapter title.
MIN_SECTION_LEVEL = 2

#: Separator between a parent anchor and a child's own slug. Two hyphens so a
#: qualified anchor cannot be confused with a slug that merely contains one.
ANCHOR_SEPARATOR = "--"


@dataclass(frozen=True)
class OutlineNode:
    """One heading and the content that belongs to it, plus its sub-headings."""

    anchor: str
    level: int
    title: str
    title_html: str
    plain_text: str
    html: str
    is_intro: bool
    children: Tuple["OutlineNode", ...]


@dataclass
class _Draft:
    """Mutable node used while the tree is still being assembled."""

    level: int
    title: str
    title_token: object
    body: List[object]
    children: List["_Draft"]
    is_intro: bool = False
    base_slug: str = ""
    anchor: str = ""


def _heading_level(tag: str) -> int:
    try:
        return int(tag[1:])
    except (ValueError, IndexError):  # pragma: no cover - markdown-it always sets hN
        return MIN_SECTION_LEVEL


def _plain_text(tokens: Sequence[object]) -> str:
    """Readable text of a block-token slice, for the search index."""
    fragments: List[str] = []
    for token in tokens:
        if getattr(token, "type", None) != "inline":
            continue
        for child in getattr(token, "children", None) or []:
            if child.type in ("text", "code_inline"):
                fragments.append(child.content)
            elif child.type in ("softbreak", "hardbreak"):
                fragments.append(" ")
    return " ".join("".join(fragments).split())


def _split_headings(tokens: Sequence[object]) -> Tuple[Optional[object], List[_Draft]]:
    """Return the chapter-title inline token and a flat list of heading drafts.

    Only headings at the top nesting level split content; a ``##`` inside a
    blockquote or a list item keeps ``token.level > 0`` and stays part of the
    body it sits in.
    """
    title_token: Optional[object] = None
    title_seen = False
    drafts: List[_Draft] = []
    current: Optional[_Draft] = None
    intro = _Draft(
        level=MIN_SECTION_LEVEL,
        title="",
        title_token=None,
        body=[],
        children=[],
        is_intro=True,
    )
    index = 0
    total = len(tokens)

    while index < total:
        token = tokens[index]
        is_heading = (
            getattr(token, "type", None) == "heading_open"
            and getattr(token, "level", 0) == 0
        )
        if not is_heading:
            (current.body if current is not None else intro.body).append(token)
            index += 1
            continue

        inline_token = tokens[index + 1] if index + 1 < total else None
        # Plain *text*, not the raw Markdown source: a heading carrying inline
        # code would otherwise keep its backticks in the search index, the
        # page title and the permalink's aria-label.
        heading_text = _plain_text([inline_token]) if inline_token is not None else ""
        level = _heading_level(token.tag)

        if not title_seen and level == 1 and not drafts:
            # The chapter title. Anything before it is front matter, so the
            # intro restarts here rather than carrying that text along.
            title_token = inline_token
            title_seen = True
            intro.body.clear()
        else:
            current = _Draft(
                level=max(level, MIN_SECTION_LEVEL),
                title=heading_text.strip(),
                title_token=inline_token,
                body=[],
                children=[],
            )
            drafts.append(current)

        # Skip heading_open, inline and heading_close.
        index += 3 if inline_token is not None else 1

    if intro.body:
        drafts.insert(0, intro)
    return title_token, drafts


def _nest(drafts: Sequence[_Draft]) -> List[_Draft]:
    """Turn the flat heading list into a tree using a level stack."""
    roots: List[_Draft] = []
    stack: List[_Draft] = []
    for draft in drafts:
        if draft.is_intro:
            roots.append(draft)
            continue
        while stack and stack[-1].level >= draft.level:
            stack.pop()
        if stack:
            stack[-1].children.append(draft)
        else:
            roots.append(draft)
        stack.append(draft)
    return roots


def _walk(drafts: Sequence[_Draft]):
    for draft in drafts:
        yield draft
        yield from _walk(draft.children)


def _assign_anchors(roots: Sequence[_Draft]) -> None:
    """Give every node a stable, chapter-unique anchor.

    A duplicated heading is qualified with its parent's anchor rather than
    numbered: the eight ``Starting Skills, Talents & Gear`` headings in the
    career-paths chapter would otherwise become ``-2`` … ``-8``, whose meaning
    depends on the order the careers happen to appear in -- reordering one
    career would silently move seven bookmarks. Numbering stays as the
    last-resort tiebreak, which is also what keeps two duplicate *top-level*
    headings behaving exactly as they did before.
    """
    counts: dict[str, int] = {}
    for draft in _walk(roots):
        draft.base_slug = slugify(draft.title) or "section"
        counts[draft.base_slug] = counts.get(draft.base_slug, 0) + 1

    taken: dict[str, int] = {}

    def assign(drafts: Sequence[_Draft], parent_anchor: str) -> None:
        for draft in drafts:
            candidate = draft.base_slug
            if counts[draft.base_slug] > 1 and parent_anchor:
                candidate = f"{parent_anchor}{ANCHOR_SEPARATOR}{draft.base_slug}"
            seen = taken.get(candidate, 0)
            taken[candidate] = seen + 1
            draft.anchor = candidate if seen == 0 else f"{candidate}-{seen + 1}"
            assign(draft.children, draft.anchor)

    assign(roots, "")


def _drop_editorial(
    drafts: List[_Draft], should_drop: Callable[[str], bool]
) -> Tuple[List[_Draft], int]:
    """Remove top-level editorial sections, subtree and all.

    Only depth 1 is considered: a legitimately-named deeper heading (a "Status"
    subsection inside real rules content) must not disappear silently.
    """
    kept: List[_Draft] = []
    dropped = 0
    for draft in drafts:
        if not draft.is_intro and should_drop(draft.title):
            dropped += 1 + sum(1 for _ in _walk(draft.children))
            continue
        kept.append(draft)
    return kept, dropped


def _build(drafts: Sequence[_Draft], renderer, chapter_title: str) -> Tuple[OutlineNode, ...]:
    nodes: List[OutlineNode] = []
    for draft in drafts:
        children = _build(draft.children, renderer, chapter_title)
        title = chapter_title if draft.is_intro else draft.title
        title_html = "" if draft.is_intro else renderer.render_inline(draft.title_token)
        nodes.append(
            OutlineNode(
                anchor=draft.anchor,
                level=draft.level,
                title=title,
                title_html=title_html or title,
                plain_text=_plain_text(draft.body),
                html=renderer.render_tokens(draft.body),
                is_intro=draft.is_intro,
                children=children,
            )
        )
    return tuple(nodes)


def parse_outline(
    text: str,
    renderer,
    *,
    source_name: str = "",
    should_drop_section: Optional[Callable[[str], bool]] = None,
) -> Tuple[str, Tuple[OutlineNode, ...], int]:
    """Parse one chapter into ``(title, top_level_nodes, dropped_count)``.

    ``title`` falls back to ``source_name``'s stem when the file has no H1,
    matching the previous behaviour.
    """
    tokens = renderer.parse(text)
    title_token, drafts = _split_headings(tokens)

    if title_token is not None:
        chapter_title = _plain_text([title_token]).strip()
    else:
        # No H1 anywhere: keep the heading structure we found and fall back to
        # the filename for the chapter title, as the previous parser did.
        chapter_title = re.sub(r"\.md$", "", source_name) or "Chapter"

    # The intro has no heading of its own, so it borrows the chapter title --
    # both for display and, importantly, for its anchor, which is what it was
    # derived from before the tree existed.
    for draft in drafts:
        if draft.is_intro:
            draft.title = chapter_title

    # Nest first: the editorial filter drops a section together with its
    # subtree, which only exists once the tree is built.
    roots = _nest(drafts)

    dropped = 0
    if should_drop_section is not None:
        roots, dropped = _drop_editorial(roots, should_drop_section)

    # An intro with no readable text is noise, not a section.
    roots = [
        node for node in roots if not node.is_intro or _plain_text(node.body).strip()
    ]

    _assign_anchors(roots)
    return chapter_title, _build(roots, renderer, chapter_title), dropped

"""Check rendered pages by structure instead of by exact markup strings.

Built on ``django.test.html.parse_html`` (the parser behind Django's
``assertHTMLEqual``), so it needs no extra dependency. A test asks for an
element by a small CSS-like selector and checks its text or attributes;
reordering attributes, adding a class or reflowing whitespace no longer
breaks it.

Selector grammar (deliberately small): compound selectors joined by spaces
(descendant). A compound is an optional tag name followed by any of
``#id``, ``.class`` and ``[attr]`` / ``[attr=value]`` / ``[attr="value"]``.
Examples: ``"nav#primary-nav a[aria-current=page]"``, ``".crew-card h2"``.

Escaping checks (``&lt;script&gt;`` and the like) stay plain string
assertions on purpose: they are about the exact bytes sent to the browser.
"""
from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field

from django.test.html import Element, parse_html

_COMPOUND = re.compile(
    r"""
    (?P<tag>[a-zA-Z][\w-]*)?
    (?P<rest>(?:\#[\w-]+|\.[\w-]+|\[[\w-]+(?:=(?:"[^"]*"|'[^']*'|[^\]]*))?\])*)
    """,
    re.VERBOSE,
)
_PART = re.compile(r"""\#([\w-]+)|\.([\w-]+)|\[([\w-]+)(?:=("[^"]*"|'[^']*'|[^\]]*))?\]""")


@dataclass(frozen=True)
class _Compound:
    tag: str | None = None
    id: str | None = None
    classes: tuple[str, ...] = ()
    attrs: tuple[tuple[str, str | None], ...] = field(default_factory=tuple)

    def matches(self, element: Element) -> bool:
        if self.tag and element.name != self.tag:
            return False
        if self.id and attr(element, "id") != self.id:
            return False
        own_classes = (attr(element, "class") or "").split()
        if any(cls not in own_classes for cls in self.classes):
            return False
        for name, value in self.attrs:
            if not has_attr(element, name):
                return False
            if value is not None and attr(element, name) != value:
                return False
        return True


def _parse_selector(selector: str) -> list[_Compound]:
    compounds = []
    for token in selector.split():
        match = _COMPOUND.fullmatch(token)
        if not match:
            raise ValueError(f"unsupported selector part: {token!r}")
        element_id, classes, attrs = None, [], []
        for part in _PART.finditer(match.group("rest") or ""):
            id_, cls, name, value = part.groups()
            if id_:
                element_id = id_
            elif cls:
                classes.append(cls)
            else:
                if value is not None and value[:1] in "\"'":
                    value = value[1:-1]
                attrs.append((name, value))
        compounds.append(_Compound(match.group("tag"), element_id, tuple(classes), tuple(attrs)))
    return compounds


def _walk(node) -> Iterator[Element]:
    for child in getattr(node, "children", ()):
        if isinstance(child, Element):
            yield child
            yield from _walk(child)


def _parse(html):
    return html if isinstance(html, Element) else parse_html(_as_text(html))


def _as_text(html) -> str:
    if hasattr(html, "content"):  # a test-client response
        return html.content.decode()
    return html


def select(html, selector: str) -> list[Element]:
    """Every element matching ``selector`` (document order, no duplicates)."""
    compounds = _parse_selector(selector)
    found: list[Element] = []

    def descend(node, remaining):
        head, tail = remaining[0], remaining[1:]
        for element in _walk(node):
            if head.matches(element):
                if tail:
                    descend(element, tail)
                elif not any(element is seen for seen in found):
                    found.append(element)

    descend(_parse(html), compounds)
    return found


def select_one(html, selector: str) -> Element:
    """The single element matching ``selector``; fails if there are 0 or several."""
    matches = select(html, selector)
    assert len(matches) == 1, f"{selector!r}: expected 1 element, found {len(matches)}"
    return matches[0]


def text(element: Element) -> str:
    """All text inside ``element``, whitespace collapsed to single spaces."""
    parts: list[str] = []

    def collect(node):
        for child in node.children:
            if isinstance(child, Element):
                collect(child)
            else:
                parts.append(str(child))

    collect(element)
    return " ".join(" ".join(parts).split())


def texts(html, selector: str) -> list[str]:
    """``text`` of every element matching ``selector``."""
    return [text(element) for element in select(html, selector)]


def has_attr(element: Element, name: str) -> bool:
    return any(key == name for key, _value in element.attributes)


def attr(element: Element, name: str) -> str | None:
    """The attribute's value; ``None`` if it is absent (or a bare boolean attribute)."""
    for key, value in element.attributes:
        if key == name:
            return value
    return None


def links(html, href: str) -> list[Element]:
    """Every ``<a>`` pointing at exactly ``href``."""
    return [a for a in select(html, "a") if attr(a, "href") == href]


def has_link(html, href: str, label: str | None = None) -> bool:
    """Whether there is an ``<a href=href>``, optionally with exactly that text."""
    return any(label is None or text(a) == label for a in links(html, href))

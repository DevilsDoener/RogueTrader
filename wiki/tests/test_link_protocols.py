"""Link destinations: http(s), mailto and same-site stay; everything else loses its href.

Audit finding I1: a scheme allowlist alone let a protocol-relative
``//host/x`` and the digit-only pseudo scheme ``tel:123`` through.
"""
import pytest

from wiki.markdown import SafeMarkdownRenderer


def _render(destination: str) -> str:
    return SafeMarkdownRenderer().render(f"[x](<{destination}>)")


@pytest.mark.parametrize(
    "destination",
    [
        "//evil.example/x",
        "///evil.example/x",
        " //evil.example",
        "\t//evil.example",
        "tel:123",
        "javascript:1",
        "JaVaScRiPt:alert(1)",
        "&#106;avascript:alert(1)",
        "data:text/html,boom",
        "vbscript:x",
        "file:///etc/passwd",
    ],
)
def test_links_outside_the_allowed_destinations_lose_their_href(destination):
    html = _render(destination)

    assert "href=" not in html
    assert "<a>x</a>" in html


@pytest.mark.parametrize(
    "destination", ["/\\evil.example", "\\\\evil.example", "java\tscript:alert(1)"]
)
def test_backslash_and_tab_tricks_reach_the_page_only_percent_encoded(destination):
    """markdown-it encodes them first, so the browser reads a plain relative path."""
    html = _render(destination)

    assert "\\" not in html
    assert "\t" not in html
    assert 'href="//' not in html


@pytest.mark.parametrize(
    "destination",
    [
        "https://example.test/a?b=1",
        "http://example.test/",
        "mailto:gm@example.test",
        "/wiki/skills/",
        "#sec-combat",
        "chapter-2",
        "?q=weapon",
    ],
)
def test_allowed_links_keep_their_href(destination):
    assert f'href="{destination}"' in _render(destination)


def test_an_uppercase_allowed_scheme_is_kept():
    assert 'href="HTTPS://example.test/"' in _render("HTTPS://example.test/")


def test_a_title_is_kept_next_to_a_safe_href():
    html = SafeMarkdownRenderer().render('[x](/wiki/ "Hint")')

    assert 'href="/wiki/"' in html
    assert 'title="Hint"' in html


def test_a_protocol_relative_link_in_a_larger_document():
    html = SafeMarkdownRenderer().render(
        "# T\n\nSee [a](//evil.example/x) and [b](/wiki/skills/)."
    )

    assert "evil.example" not in html
    assert 'href="/wiki/skills/"' in html

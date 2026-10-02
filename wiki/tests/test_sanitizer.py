"""The sanitizer (nh3) applied directly to hostile HTML.

``html: False`` in markdown-it already turns raw HTML in the source into text,
so these payloads cannot normally reach the sanitizer. They are fed to
``_clean`` directly because that is the layer the module documents as the one
that decides what is safe: it must hold even if the parser configuration ever
changes. Markdown-level behaviour (links, tables, headings) is covered by
``test_link_protocols``, ``test_markdown_rendering`` and the heading tests.
"""
import re

import pytest

from wiki.markdown import ALLOWED_TAGS, SafeMarkdownRenderer, _clean

_TAG_NAME_RE = re.compile(r"</?([a-zA-Z][a-zA-Z0-9]*)")

#: Substrings that must never appear in sanitized output, whatever the input.
_FORBIDDEN = (
    "<script", "<style", "<svg", "<math", "<img", "<iframe", "<object", "<embed",
    "<form", "<input", "<button", "<link", "<meta", "<base", "<video", "<template",
    "<details", "<textarea", "<noscript", "<plaintext", "<xmp", "<marquee",
    "onerror", "onclick", "onload", "ontoggle", "onstart",
    "javascript:", "vbscript:", "data:text", "style=", " id=", " name=",
    " target=", " rel=", "<!--",
)

HOSTILE = [
    "<script>alert(1)</script>",
    "<svg><script>alert(1)</script></svg>",
    "<svg onload=alert(1)><circle/></svg>",
    "<svg><a xlink:href='javascript:alert(1)'><text>x</text></a></svg>",
    "<svg><foreignObject><p>x</p></foreignObject></svg>",
    "<svg><style><img src=x onerror=alert(1)></style></svg>",
    "<math><mi xlink:href='javascript:alert(1)'>x</mi></math>",
    "<math href='javascript:1'>m</math>",
    "<math><annotation-xml encoding='text/html'><script>x</script></annotation-xml></math>",
    # mXSS: namespace confusion between math/table/style/img
    "<math><mtext><table><mglyph><style><!--</style>"
    "<img title='--&gt;&lt;img src=1 onerror=alert(1)&gt;'>",
    "<noscript><p title='</noscript><img src=x onerror=alert(1)>'></noscript>",
    "<img src=x onerror=alert(1)>",
    "<iframe src='javascript:alert(1)'></iframe>",
    "<object data=x></object><embed src=x>",
    "<form action=x><input name=y id=z></form>",
    "<button onclick=x>b</button>",
    "<details open ontoggle=alert(1)>d</details>",
    "<video src=x onerror=y>",
    "<marquee onstart=x>m</marquee>",
    "<style>p{background:url(javascript:1)}</style>",
    "<link rel=stylesheet href=x><meta http-equiv=refresh content=0><base href=//evil>",
    "<template><script>x</script></template>",
    "<textarea><script>x</script></textarea>",
    "<xmp><script>x</script></xmp>",
    "<plaintext>x",
    "<!-- c --><p>x</p><!--[if IE]><script>x</script><![endif]-->",
    # malformed / split tags
    "<<script>script>alert(1)<</script>/script>",
    "<scr<script>ipt>alert(1)</scr</script>ipt>",
    "<script/x>alert(1)</script>",
    "<script\n>alert(1)</script\n>",
    "<ScRiPt>alert(1)</sCrIpT>",
    "<a href='x'<b>y</b>",
    "<a/href='javascript:1'>slash</a>",
    "<a href=javascript:alert(1)>unquoted</a>",
    "<a href='x' href='javascript:1'>duplicate</a>",
    "<a href='https://ok.test' onclick='x()' target='_blank' rel='opener' download>x</a>",
    "<p><b>nested</p></b><i>",
    "<p id='x' name='y' style='color:red' onclick='x'>p</p>",
    "<p>unterminated <a href='javascript:1",
    "<p>\x00<script>\x00alert(1)</script></p>",
]


@pytest.mark.parametrize("payload", HOSTILE)
def test_hostile_html_is_neutralised(payload):
    cleaned = _clean(payload)
    lowered = cleaned.lower()

    for needle in _FORBIDDEN:
        assert needle not in lowered, f"{needle!r} survived in {cleaned!r}"
    assert {name.lower() for name in _TAG_NAME_RE.findall(cleaned)} <= ALLOWED_TAGS


@pytest.mark.parametrize(
    "href",
    [
        "javascript:alert(1)",
        "JAVASCRIPT:alert(1)",
        "  javascript:alert(1)",
        "\tjavascript:alert(1)",
        "java&#09;script:alert(1)",
        "&#106;avascript:alert(1)",
        "&#x6A;avascript:alert(1)",
        "data:text/html;base64,PHNjcmlwdD4=",
        "vbscript:msgbox(1)",
        "file:///etc/passwd",
        "ftp://example.test/",
        "tel:123",
        "tel:+4912345",
        "foo:bar",
        "//evil.example/x",
        "///evil.example/x",
        "\\\\evil.example",
        "/\\evil.example",
    ],
)
def test_a_raw_anchor_loses_a_destination_outside_the_allowed_ones(href):
    cleaned = _clean(f'<a href="{href}">x</a>')

    assert "href" not in cleaned
    assert "<a>x</a>" in cleaned


def test_a_raw_anchor_keeps_allowed_destinations_without_gaining_a_rel():
    cleaned = _clean(
        '<a href="https://a.test/?x=1&amp;y=2" title="t">a</a>'
        '<a href="mailto:gm@example.test">b</a>'
        '<a href="/wiki/">c</a>'
    )

    assert 'href="https://a.test/?x=1&amp;y=2"' in cleaned
    assert 'href="mailto:gm@example.test"' in cleaned
    assert 'href="/wiki/"' in cleaned
    # Links used to come out of the old sanitizer without a rel attribute, and
    # the output is meant to stay byte-identical.
    assert "rel=" not in cleaned


def test_no_id_or_name_survives_so_nothing_can_clobber_the_dom():
    cleaned = _clean(
        '<h2 id="__proto__">h</h2><a id="x" name="location" href="/y">a</a>'
        '<p id="document" name="cookie">p</p>'
    )

    assert " id=" not in cleaned
    assert " name=" not in cleaned
    assert "<p>p</p>" in cleaned


def test_a_cell_class_must_be_exactly_one_generated_value():
    cleaned = _clean(
        '<table><tr><td class="evil wiki-col-right">a</td>'
        '<td class="wiki-col-right wiki-col-left">b</td>'
        '<td class="WIKI-COL-RIGHT">c</td>'
        '<td class="wiki-col-center">d</td></tr></table>'
    )

    assert cleaned.count("class=") == 1
    assert '<td class="wiki-col-center">d</td>' in cleaned


def test_class_is_not_allowed_outside_table_cells():
    cleaned = _clean(
        '<p class="wiki-col-right">p</p><a class="wiki-col-left" href="/x">a</a>'
        '<tr class="wiki-col-right"><td>x</td></tr>'
    )

    assert "class=" not in cleaned


def test_content_of_a_script_is_not_kept_as_visible_text():
    assert _clean("<p>a</p><script>alert(document.cookie)</script><p>b</p>") == "<p>a</p><p>b</p>"


def test_unknown_tags_are_unwrapped_and_their_text_kept():
    assert _clean("<custom-el>kept</custom-el><u>u</u>") == "keptu"


# -- byte compatibility with the previous sanitizer ---------------------------


def test_a_double_quote_in_text_stays_an_entity():
    """nh3 writes a text ``"`` literally; the corpus expects ``&quot;``."""
    html = SafeMarkdownRenderer().render('He said "go" -- **"bold"**')

    assert "&quot;go&quot;" in html
    assert "<strong>&quot;bold&quot;</strong>" in html
    assert '"' not in re.sub(r"<[^<>]*>", "", html)


def test_a_double_quote_in_a_title_attribute_stays_an_entity():
    html = SafeMarkdownRenderer().render('[x](/wiki/ "say \\"hi\\"")')

    assert 'title="say &quot;hi&quot;"' in html


def test_a_no_break_space_stays_a_character():
    html = SafeMarkdownRenderer().render("a b &nbsp; c")

    assert "&nbsp;" not in html
    assert "a b   c" in html


def test_ampersand_angle_brackets_and_apostrophe_are_escaped_like_before():
    html = SafeMarkdownRenderer().render("a & b < c > d 'e'")

    assert html == "<p>a &amp; b &lt; c &gt; d 'e'</p>\n"


def test_raw_html_in_markdown_text_is_escaped_not_sanitised_away():
    html = SafeMarkdownRenderer().render("<svg><script>alert(1)</script></svg>")

    assert "<svg" not in html
    assert "&lt;svg&gt;&lt;script&gt;" in html

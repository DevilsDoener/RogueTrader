"""Table rendering: scroll wrapper, layout mode, and column alignment.

Markdown tables parsed fine before these were added -- what was missing was
every piece of presentation. There was no CSS rule for a bare ``<table>``
anywhere in the project, and the column alignment declared by ``|---:|`` was
silently destroyed because markdown-it expresses it as an inline ``style``
that Bleach stripped. Both are regressions worth pinning.
"""
import pytest
from django.conf import settings

from wiki.markdown import WIDE_TABLE_MIN_COLUMNS, SafeMarkdownRenderer


def _table(columns: int, separator: str | None = None) -> str:
    header = " | ".join(f"c{index}" for index in range(columns))
    rule = separator or "|".join(["---"] * columns)
    body = " | ".join(f"v{index}" for index in range(columns))
    return f"| {header} |\n|{rule}|\n| {body} |"


def test_table_is_wrapped_in_a_scroll_container():
    html = SafeMarkdownRenderer().render(_table(3))

    assert '<div class="wiki-table-scroll" data-table-mode="flow"><table>' in html
    assert html.count("wiki-table-scroll") == html.count("<table>") == 1


@pytest.mark.parametrize(
    ("columns", "expected_mode"),
    (
        (WIDE_TABLE_MIN_COLUMNS - 1, "flow"),
        (WIDE_TABLE_MIN_COLUMNS, "wide"),
    ),
)
def test_layout_mode_switches_at_the_column_threshold(columns, expected_mode):
    html = SafeMarkdownRenderer().render(_table(columns))

    assert f'data-table-mode="{expected_mode}"' in html


def test_right_aligned_column_becomes_a_class_on_header_and_body_cells():
    html = SafeMarkdownRenderer().render(_table(2, separator="---|---:"))

    assert '<th class="wiki-col-right">c1</th>' in html
    assert '<td class="wiki-col-right">v1</td>' in html
    # The alignment used to arrive as style="text-align:right" and be dropped.
    assert "style=" not in html


def test_left_and_center_alignment_produce_their_own_classes():
    html = SafeMarkdownRenderer().render(_table(2, separator=":---|:---:"))

    assert "wiki-col-left" in html
    assert "wiki-col-center" in html


def test_a_cell_class_we_did_not_generate_is_stripped():
    """The allowlist checks the class *value*, not just the attribute name."""
    import bleach

    from wiki.markdown import ALLOWED_ATTRIBUTES, ALLOWED_PROTOCOLS, ALLOWED_TAGS

    cleaned = bleach.clean(
        '<table><tr><td class="evil">x</td><td class="wiki-col-right">y</td></tr></table>',
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    )

    assert 'class="evil"' not in cleaned
    assert 'class="wiki-col-right"' in cleaned


def test_literal_table_markup_in_the_source_is_escaped_and_not_wrapped():
    """The wrapper runs after Bleach on a string match, so this must hold."""
    html = SafeMarkdownRenderer().render("<table><tr><td>raw</td></tr></table>")

    assert "wiki-table-scroll" not in html
    assert "&lt;table&gt;" in html


def test_two_tables_each_get_their_own_wrapper():
    html = SafeMarkdownRenderer().render(f"{_table(2)}\n\ntext\n\n{_table(2)}")

    assert html.count("wiki-table-scroll") == 2
    assert "</table></div>" in html


@pytest.mark.skipif(
    not (settings.WIKI_CONTENT_ROOT / "03-Skills.md").exists(),
    reason="real wiki content is not available in this checkout",
)
def test_every_table_in_the_real_corpus_is_wrapped():
    """Catches a renderer change that emits an attributed <table> tag, which
    would silently break the string match in ``_wrap_tables``."""
    from wiki.content import WikiRepository

    html = "".join(
        section.html
        for chapter in WikiRepository.load().chapters()
        for section in chapter.sections
    )

    assert html.count("<table>") > 0
    assert html.count("<table>") == html.count("wiki-table-scroll")
    assert "style=" not in html

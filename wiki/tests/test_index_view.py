"""The overview page (Bibliothek), and the login every wiki page requires.

A reader reaches every chapter *and* its sections from here, grouped into the
manifest's bands.
"""
import re

import pytest
from django.urls import reverse

from wiki.content import WikiRepository, set_repository_for_tests
from wiki.manifest import ALLOWLIST


def _get(client, user_factory):
    client.force_login(user_factory())
    response = client.get(reverse("wiki:index"))
    assert response.status_code == 200
    return response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url_name, kwargs",
    [("wiki:index", {}), ("wiki:chapter", {"chapter_slug": "chapter"}), ("wiki:search", {})],
)
def test_wiki_routes_require_login(client, url_name, kwargs):
    response = client.get(reverse(url_name, kwargs=kwargs))

    assert response.status_code == 302
    assert response.url.startswith("/account/login/?next=")


@pytest.mark.django_db
def test_sections_are_linkable_straight_from_the_overview(
    client, user_factory, make_repository
):
    make_repository(
        {"01-Charaktererschaffung.md": "# One\n\n## Alpha\na\n\n## Beta\nb\n"}, install=True
    )

    content = _get(client, user_factory)
    chapter_url = reverse("wiki:chapter", kwargs={"chapter_slug": "charaktererschaffung"})

    assert f'href="{chapter_url}#sec-alpha"' in content
    assert f'href="{chapter_url}#sec-beta"' in content


@pytest.mark.django_db
def test_all_top_level_sections_are_listed_in_the_collapsible_contents(
    client, user_factory, make_repository
):
    sections = "\n\n".join(f"## Section {index}\nBody." for index in range(10))
    make_repository({"01-Charaktererschaffung.md": f"# One\n\n{sections}\n"}, install=True)

    content = _get(client, user_factory)

    assert content.count("#sec-section-") == 10
    assert "10 Abschnitte" in content
    assert '<details class="library-card-contents">' in content


@pytest.mark.django_db
def test_level_two_sections_are_nested_under_their_parent_for_the_filter(
    client, user_factory, make_repository
):
    make_repository(
        {
            "01-Charaktererschaffung.md": (
                "# One\n\n## Injury\na\n\n### Critical Damage\nb\n\n## Other\nc\n"
            )
        },
        install=True,
    )

    content = _get(client, user_factory)
    chapter_url = reverse("wiki:chapter", kwargs={"chapter_slug": "charaktererschaffung"})

    nested = re.search(
        r'<a href="[^"]*#sec-injury">Injury</a>\s*<ul class="library-card-subsections">(.*?)</ul>',
        content,
        re.S,
    )
    assert nested, "the level-2 list sits inside its level-1 entry"
    assert f'href="{chapter_url}#sec-critical-damage">Critical Damage</a>' in nested.group(1)
    # A level-1 entry without children gets no empty sub-list.
    assert content.count('class="library-card-subsections"') == 1
    # The card still counts level-1 sections only.
    assert "2 Abschnitte" in content


@pytest.mark.django_db
def test_the_page_is_the_bibliothek_with_a_filter_and_fulltext_form(
    client, user_factory, make_repository
):
    make_repository({"01-Charaktererschaffung.md": "# One\n\n## Alpha\na\n"}, install=True)

    content = _get(client, user_factory)

    assert "<h1>Bibliothek</h1>" in content
    assert 'id="library-filter"' in content
    assert reverse("wiki:search") in content
    assert "Weiterlesen" in content
    assert "js/wiki-library.js" in content


@pytest.mark.django_db
def test_cards_show_the_roman_numeral_and_the_short_title(
    client, user_factory, make_repository
):
    make_repository(
        {
            "00-Foreword.md": "# Foreword\n\nText.\n",
            "04-Talents.md": "# Chapter IV: Talents\n\n## Alpha\na\n",
        },
        install=True,
    )

    content = _get(client, user_factory)

    assert '<span class="library-card-numeral" aria-hidden="true">IV</span>' in content
    assert ">Talents</a>" in content
    assert "Chapter IV:" not in content
    assert "library-card-numeral--word" not in content


@pytest.mark.django_db
def test_quick_links_are_rendered_when_their_targets_exist(
    client, user_factory, make_repository
):
    make_repository(
        {"04-Talents.md": "# Chapter IV: Talents\n\n## Detailed Talent Descriptions\nx\n"},
        install=True,
    )

    content = _get(client, user_factory)
    chapter_url = reverse("wiki:chapter", kwargs={"chapter_slug": "talents"})

    assert "Quick Links" in content
    assert f'href="{chapter_url}#sec-detailed-talent-descriptions"' in content
    assert ">Talents</a>" in content


@pytest.mark.django_db
def test_filter_text_is_casefolded_and_autoescaped(
    client, user_factory, make_repository
):
    make_repository(
        {
            "01-Charaktererschaffung.md": (
                '# One\n\n## Der "Große" <b>Plan</b>\na\n\n### Unter Abschnitt\nb\n'
            )
        },
        install=True,
    )

    content = _get(client, user_factory)

    assert 'data-filter-text="' in content
    # casefold: "Große" -> "grosse"; the level-2 title is part of the text.
    assert "grosse" in content
    assert "unter abschnitt" in content
    # Quotes and tags in a title cannot break out of the attribute.
    assert "&quot;grosse&quot;" in content
    assert "&lt;b&gt;plan&lt;/b&gt;" in content
    assert "<b>plan</b>" not in content


@pytest.mark.django_db
def test_chapters_are_grouped_into_three_bands_with_one_chapters_grid(
    client, user_factory, make_repository
):
    """Front Matter, Chapters (all numbered chapters incl. the XIV files), Appendix."""
    make_repository(
        {
            "00-Foreword.md": "# Foreword\n\nText.\n",
            "01-Charaktererschaffung.md": "# One\n\n## Alpha\na\n",
            "14-Mutations.md": "# Mutations\n\n## M\nm\n",
            "14-Traits.md": "# Traits\n\n## T\nt\n",
            "16-Index.md": "# Index\n\nText.\n",
        },
        install=True,
    )

    content = _get(client, user_factory)

    headings = re.findall(r'<h2 class="library-band-heading"[^>]*>([^<]+)</h2>', content)
    assert headings == ["Front Matter", "Chapters", "Appendix"]
    assert content.count('<section class="library-band"') == 3
    assert content.count('<ul class="library-grid">') == 3
    # No per-part headings any more, in particular none for chapter XIV.
    assert "Chapter XIV" not in content
    sections = re.split(r'<section class="library-band"', content)[1:]
    kapitel = sections[1]
    for title in ("One", "Mutations", "Traits"):
        assert f">{title}</a>" in kapitel
    assert kapitel.count('class="library-card"') == 3
    assert "Foreword" not in kapitel
    assert "Index" not in kapitel


@pytest.mark.django_db
def test_unnumbered_cards_show_the_section_glyph_in_the_numeral_slot(
    client, user_factory, make_repository
):
    make_repository({"00-Foreword.md": "# Foreword\n\nText.\n"}, install=True)

    content = _get(client, user_factory)

    assert '<span class="library-card-numeral" aria-hidden="true">&sect;</span>' in content


@pytest.mark.django_db
def test_the_search_placeholder_does_not_promise_a_live_filter_without_js(
    client, user_factory, make_repository
):
    make_repository({"01-Charaktererschaffung.md": "# One\n\n## Alpha\na\n"}, install=True)

    content = _get(client, user_factory)

    assert 'placeholder="Kapitel, Abschnitte oder Regeln suchen&hellip;"' in content


@pytest.mark.django_db
def test_the_empty_state_is_shown_when_nothing_loads(
    client, user_factory, make_repository
):
    make_repository({}, install=True)

    content = _get(client, user_factory)

    assert "empty-state" in content


@pytest.mark.django_db
def test_chapters_keep_the_manifest_order(client, user_factory, make_repository):
    make_repository(
        {
            "01-Charaktererschaffung.md": "# First\n\n## A\na\n",
            "02-Karrierewege.md": "# Second\n\n## B\nb\n",
        },
        install=True,
    )

    content = _get(client, user_factory)

    assert content.index("First") < content.index("Second")


#: What the real book renders, band by band: each card's numeral in book order.
REAL_BOOK_BANDS = [
    ("Front Matter", ["&sect;", "&sect;"]),
    (
        "Chapters",
        ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII"]
        + ["XIV"] * 4
        + ["XV"],
    ),
    ("Appendix", ["&sect;"]),
]


@pytest.mark.django_db
def test_the_real_book_renders_its_numerals_in_their_bands(client, user_factory, settings):
    settings.WIKI_CONTENT_ROOT = settings.BASE_DIR / "content"
    settings.WIKI_CONTENT_ALLOWLIST = list(ALLOWLIST)
    set_repository_for_tests(WikiRepository.load())

    content = _get(client, user_factory)

    heading = re.compile(r'<h2 class="library-band-heading"[^>]*>([^<]+)</h2>')
    numeral = re.compile(r'<span class="library-card-numeral" aria-hidden="true">([^<]+)</span>')
    rendered = [
        (heading.search(band).group(1), numeral.findall(band))
        for band in re.split(r'<section class="library-band"', content)[1:]
    ]
    assert rendered == REAL_BOOK_BANDS

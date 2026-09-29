"""The overview page.

It used to be a flat list of 21 chapter titles and nothing else. The point of
the rework is that a reader can reach a *section* from here -- roughly 180 of
them -- instead of only a chapter.
"""
import pytest
from django.urls import reverse

from wiki.content import WikiRepository, set_repository_for_tests


def _publish(tmp_path, settings, bodies):
    for name, body in bodies.items():
        (tmp_path / name).write_text(body, encoding="utf-8")
    settings.WIKI_CONTENT_ROOT = tmp_path
    settings.WIKI_CONTENT_ALLOWLIST = list(bodies)
    set_repository_for_tests(WikiRepository.load())


def _get(client, user_factory):
    client.force_login(user_factory())
    response = client.get(reverse("wiki:index"))
    assert response.status_code == 200
    return response.content.decode()


@pytest.mark.django_db
def test_sections_are_linkable_straight_from_the_overview(
    client, user_factory, tmp_path, settings
):
    _publish(
        tmp_path,
        settings,
        {"01-Charaktererschaffung.md": "# One\n\n## Alpha\na\n\n## Beta\nb\n"},
    )

    content = _get(client, user_factory)
    chapter_url = reverse("wiki:chapter", kwargs={"chapter_slug": "charaktererschaffung"})

    assert f'href="{chapter_url}#sec-alpha"' in content
    assert f'href="{chapter_url}#sec-beta"' in content


@pytest.mark.django_db
def test_all_top_level_sections_are_listed_in_the_collapsible_contents(
    client, user_factory, tmp_path, settings
):
    sections = "\n\n".join(f"## Section {index}\nBody." for index in range(10))
    _publish(tmp_path, settings, {"01-Charaktererschaffung.md": f"# One\n\n{sections}\n"})

    content = _get(client, user_factory)

    assert content.count("#sec-section-") == 10
    assert "10 Abschnitte" in content
    assert '<details class="library-card-contents">' in content


@pytest.mark.django_db
def test_the_page_is_the_bibliothek_with_a_filter_and_fulltext_form(
    client, user_factory, tmp_path, settings
):
    _publish(tmp_path, settings, {"01-Charaktererschaffung.md": "# One\n\n## Alpha\na\n"})

    content = _get(client, user_factory)

    assert "<h1>Bibliothek</h1>" in content
    assert 'id="library-filter"' in content
    assert reverse("wiki:search") in content
    assert "Weiterlesen" in content
    assert "js/wiki-library.js" in content


@pytest.mark.django_db
def test_cards_show_the_roman_numeral_and_the_short_title(
    client, user_factory, tmp_path, settings
):
    _publish(
        tmp_path,
        settings,
        {
            "00-Foreword.md": "# Foreword\n\nText.\n",
            "04-Talents.md": "# Chapter IV: Talents\n\n## Alpha\na\n",
        },
    )

    content = _get(client, user_factory)

    assert '<span class="library-card-numeral" aria-hidden="true">IV</span>' in content
    assert ">Talents</a>" in content
    assert "Chapter IV:" not in content
    # Front matter has no numeral, so the part name stands in for it.
    assert "library-card-numeral library-card-numeral--word" in content
    assert "Vorspann" in content


@pytest.mark.django_db
def test_quick_links_are_rendered_when_their_targets_exist(
    client, user_factory, tmp_path, settings
):
    _publish(
        tmp_path,
        settings,
        {"04-Talents.md": "# Chapter IV: Talents\n\n## Detailed Talent Descriptions\nx\n"},
    )

    content = _get(client, user_factory)
    chapter_url = reverse("wiki:chapter", kwargs={"chapter_slug": "talents"})

    assert "Schnellzugriff" in content
    assert f'href="{chapter_url}#sec-detailed-talent-descriptions"' in content
    assert ">Talente</a>" in content


@pytest.mark.django_db
def test_filter_text_is_casefolded_and_autoescaped(
    client, user_factory, tmp_path, settings
):
    _publish(
        tmp_path,
        settings,
        {
            "01-Charaktererschaffung.md": (
                '# One\n\n## Der "Große" <b>Plan</b>\na\n\n### Unter Abschnitt\nb\n'
            )
        },
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
def test_a_multi_file_part_gets_a_heading(client, user_factory, tmp_path, settings):
    """Chapter XIV is four files; the numbered single-file chapters are not."""
    _publish(
        tmp_path,
        settings,
        {
            "01-Charaktererschaffung.md": "# One\n\n## Alpha\na\n",
            "14-Mutations.md": "# Mutations\n\n## M\nm\n",
            "14-Traits.md": "# Traits\n\n## T\nt\n",
        },
    )

    content = _get(client, user_factory)

    assert "Kapitel XIV" in content
    # A part holding a single chapter would only repeat the chapter title.
    assert "Kapitel I<" not in content


@pytest.mark.django_db
def test_the_empty_state_is_shown_when_nothing_loads(
    client, user_factory, tmp_path, settings
):
    settings.WIKI_CONTENT_ROOT = tmp_path
    settings.WIKI_CONTENT_ALLOWLIST = []
    set_repository_for_tests(WikiRepository.load())

    content = _get(client, user_factory)

    assert "empty-state" in content


@pytest.mark.django_db
def test_chapters_keep_the_manifest_order(client, user_factory, tmp_path, settings):
    _publish(
        tmp_path,
        settings,
        {
            "01-Charaktererschaffung.md": "# First\n\n## A\na\n",
            "02-Karrierewege.md": "# Second\n\n## B\nb\n",
        },
    )

    content = _get(client, user_factory)

    assert content.index("First") < content.index("Second")

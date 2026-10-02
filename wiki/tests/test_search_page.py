"""``build_search_page`` and ``WikiRepository.library_bands`` without HTTP."""
import pytest

from wiki.search_page import SEARCH_RESULTS_LIMIT, build_search_page


@pytest.fixture
def repository(make_repository):
    return make_repository(
        {
            "04-Talents.md": "# Chapter IV: Talents\n\n## Weapon Training\nWeapon drills.\n",
            "05-Armoury.md": "# Chapter V: Armoury\n\n## Bolters\nThe bolter is a weapon.\n",
        }
    )


def test_facets_list_each_chapter_with_hits_in_book_order(repository):
    page = build_search_page(repository, "weapon")

    assert [(f["chapter"].slug, f["count"]) for f in page["facets"]] == [
        ("talents", 1),
        ("armoury", 1),
    ]
    assert page["total_count"] == page["all_count"] == 2
    assert page["active_chapter"] is None


def test_a_chapter_filter_narrows_the_hits_but_not_the_facets(repository):
    page = build_search_page(repository, "weapon", "armoury")

    assert page["active_chapter"].slug == "armoury"
    assert [chapter.slug for _result, chapter in page["hits"]] == ["armoury"]
    assert page["total_count"] == 1
    assert page["all_count"] == 2
    assert len(page["facets"]) == 2


@pytest.mark.parametrize("requested", ["nonexistent", ""])
def test_an_unknown_chapter_filter_is_ignored(repository, requested):
    page = build_search_page(repository, "weapon", requested)

    assert page["active_chapter"] is None
    assert page["total_count"] == 2


def test_a_chapter_without_hits_is_ignored_as_a_filter(repository):
    page = build_search_page(repository, "bolter", "talents")

    assert page["active_chapter"] is None


def test_empty_and_too_short_queries_are_told_apart(repository):
    assert build_search_page(repository, "")["query_too_short"] is False
    assert build_search_page(repository, "a")["query_too_short"] is True
    assert build_search_page(repository, "a")["hits"] == []


def test_the_result_list_is_capped(make_repository):
    sections = "".join(
        f"## Entry {index}\nweapon text\n\n" for index in range(SEARCH_RESULTS_LIMIT + 5)
    )
    repository = make_repository({"01-Chapter.md": f"# Chapter\n\n{sections}"})

    page = build_search_page(repository, "weapon")

    assert len(page["hits"]) == SEARCH_RESULTS_LIMIT
    assert page["total_count"] == SEARCH_RESULTS_LIMIT + 5
    assert page["results_capped"] is True


def test_library_bands_are_built_once_per_repository(make_repository):
    first = make_repository({"01-Chapter.md": "# One\n\n## A\ntext\n"})
    second = make_repository({"02-Other.md": "# Two\n\n## B\ntext\n"})

    assert first.library_bands is first.library_bands
    assert first.library_bands is not second.library_bands
    titles = [card["chapter"].title for band in first.library_bands for card in band["cards"]]
    assert titles == ["One"]

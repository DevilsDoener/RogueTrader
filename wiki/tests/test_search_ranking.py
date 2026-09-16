"""Search ranking, alias expansion and prefix matching.

The corpus is English and the interface is German, so before the alias table
the queries this group would actually type -- "Waffe", "Schiff", "Deckung" --
returned nothing at all. Ranking uses a saturating term frequency rather than
length normalisation: on this corpus true normalisation promotes a statblock
that mentions a word once over the section the rules are actually in.
"""
import pytest
from django.conf import settings as django_settings

from wiki.content import WikiRepository
from wiki.search import PREFIX_MIN_LENGTH, QUERY_ALIASES


def _repository(tmp_path, settings, bodies):
    for name, body in bodies.items():
        (tmp_path / name).write_text(body, encoding="utf-8")
    settings.WIKI_CONTENT_ROOT = tmp_path
    settings.WIKI_CONTENT_ALLOWLIST = list(bodies)
    return WikiRepository.load()


def _titles(results):
    return [result.title for result in results]


# --- ranking --------------------------------------------------------------


def test_a_repetitive_section_does_not_outrank_the_focused_one(tmp_path, settings):
    """The 150 KB "basics" section used to win almost every term it repeated."""
    repository = _repository(
        tmp_path,
        settings,
        {
            "01-Long.md": "# Long\n\n## Everything\n" + ("Dodge is mentioned. " * 40),
            "02-Focused.md": "# Focused\n\n## Dodge\nHow dodging works.\n",
        },
    )

    results = repository.search("dodge")

    assert _titles(results)[0] == "Dodge"


def test_more_mentions_still_rank_higher_all_else_equal(tmp_path, settings):
    """Saturation caps runaway counts; it must not flatten them entirely."""
    repository = _repository(
        tmp_path,
        settings,
        {
            "01-Few.md": "# Few\n\n## Alpha\nPlasma.\n",
            "02-Many.md": "# Many\n\n## Beta\nPlasma plasma plasma.\n",
        },
    )

    assert _titles(repository.search("plasma")) == ["Beta", "Alpha"]


def test_scores_are_floats_and_ties_break_on_reading_order(tmp_path, settings):
    repository = _repository(
        tmp_path,
        settings,
        {
            "01-Charaktererschaffung.md": "# One\n\n## Alpha\nPlasma.\n",
            "02-Karrierewege.md": "# Two\n\n## Beta\nPlasma.\n",
        },
    )

    results = repository.search("plasma")

    assert all(isinstance(result.score, float) for result in results)
    assert results[0].score == results[1].score
    assert [result.chapter_slug for result in results] == [
        "charaktererschaffung",
        "karrierewege",
    ]


# --- German aliases -------------------------------------------------------


@pytest.mark.parametrize(
    ("query", "body"),
    (
        ("Waffe", "The weapon is loaded."),
        ("Schiff", "The starship departs."),
        ("Deckung", "Taking cover is wise."),
        ("Rüstung", "Heavy armour protects."),
        ("Wahnsinn", "Insanity grows."),
    ),
)
def test_german_queries_find_the_english_text(tmp_path, settings, query, body):
    repository = _repository(tmp_path, settings, {"01-Chapter.md": f"# Chapter\n\n## Rule\n{body}\n"})

    assert repository.search(query), f"{query!r} found nothing"


def test_an_alias_does_not_loosen_the_and_between_terms(tmp_path, settings):
    """Both concepts must still occur in the same section."""
    repository = _repository(
        tmp_path,
        settings,
        {
            "01-Chapter.md": "# Chapter\n\n## Weapons\nThe weapon fires.\n\n## Cover\nTake cover.\n",
        },
    )

    assert repository.search("Waffe")
    assert repository.search("Deckung")
    assert repository.search("Waffe Deckung") == ()


def test_every_alias_target_is_lowercase_and_non_empty():
    for term, targets in QUERY_ALIASES.items():
        assert term == term.casefold(), term
        assert targets, term
        assert all(target == target.casefold() and target for target in targets), term


# --- prefix expansion -----------------------------------------------------


def test_a_prefix_finds_the_longer_word(tmp_path, settings):
    repository = _repository(
        tmp_path, settings, {"01-Chapter.md": "# Chapter\n\n## Guns\nLaspistols are common.\n"}
    )

    assert repository.search("laspistol")


def test_an_exact_match_outranks_a_prefix_match(tmp_path, settings):
    repository = _repository(
        tmp_path,
        settings,
        {
            "01-Prefix.md": "# Prefix\n\n## Alpha\nLaspistols everywhere.\n",
            "02-Exact.md": "# Exact\n\n## Beta\nLaspistol here.\n",
        },
    )

    assert _titles(repository.search("laspistol")) == ["Beta", "Alpha"]


def test_a_short_query_does_not_expand_by_prefix(tmp_path, settings):
    """Below the minimum length nearly everything would match."""
    short = "x" * (PREFIX_MIN_LENGTH - 1)
    repository = _repository(
        tmp_path, settings, {"01-Chapter.md": f"# Chapter\n\n## Alpha\n{short}ylophone\n"}
    )

    assert repository.search(short) == ()


# --- chapter weighting ----------------------------------------------------


def test_navigation_chapters_rank_below_rules(tmp_path, settings):
    """Identical content either side, so only the chapter weight can decide.

    The foreword comes first in reading order, which is the tie-break, so
    without its lower weight it would win.
    """
    section = "## Cover\nTaking cover helps.\n"
    repository = _repository(
        tmp_path,
        settings,
        {
            "00-Foreword.md": f"# Foreword\n\n{section}",
            "09-Playing-The-Game.md": f"# Playing\n\n{section}",
        },
    )

    results = repository.search("cover")

    assert [result.chapter_slug for result in results] == [
        "playing-the-game",
        "foreword",
    ]


@pytest.mark.skipif(
    not (django_settings.WIKI_CONTENT_ROOT / "16-Index.md").exists(),
    reason="real wiki content is not available in this checkout",
)
def test_the_page_number_index_no_longer_tops_a_common_word():
    """Against the real corpus: "cover" used to return the back-cover advert
    from 16-Index.md as its second hit."""
    repository = WikiRepository.load()

    results = repository.search("cover")

    assert results
    assert results[0].chapter_slug != "index"

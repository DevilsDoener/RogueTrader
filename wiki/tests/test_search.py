import pytest

from wiki.search import SNIPPET_ELLIPSIS, SNIPPET_MAX_LENGTH, _make_snippet, is_searchable
from wiki.suggest import suggest


@pytest.fixture
def one_chapter(make_repository):
    def load(text):
        return make_repository({"01-Chapter.md": text})

    return load


def test_heading_matches_rank_before_body_matches(make_repository):
    repository = make_repository(
        {
            "01-First.md": "# First\nA plasma weapon is rare.",
            "02-Second.md": "# Plasma Doctrine\nOrdinary notes.",
        }
    )

    results = repository.search("plasma")

    assert [result.chapter_slug for result in results] == ["second", "first"]


def test_search_returns_escaped_highlighted_snippet_around_first_match(one_chapter):
    result = one_chapter("# Chapter\nBefore <tag> plasma & after").search("plasma")[0]

    assert "&lt;tag&gt;" in result.snippet
    assert "<mark>plasma</mark>" in result.snippet
    assert "&amp;" in result.snippet


def test_search_rejects_one_character_query(one_chapter):
    assert one_chapter("# Chapter\nPlasma").search("p") == ()


# --- Snippet window: word boundaries, ellipses, casefold offsets -------------


def _words(count, stem="word"):
    return " ".join(f"{stem}{index}" for index in range(count))


def _visible(snippet):
    return snippet.replace("<mark>", "").replace("</mark>", "")


def test_a_short_text_snippet_has_no_ellipsis():
    snippet = _make_snippet("A plasma weapon is rare.", ["plasma"])

    assert snippet == "A <mark>plasma</mark> weapon is rare."


def test_a_window_inside_long_text_is_cut_at_words_with_ellipses_on_both_sides():
    text = f"{_words(60, 'lead')} plasma {_words(60, 'tail')}"

    snippet = _make_snippet(text, ["plasma"])

    assert snippet.startswith(SNIPPET_ELLIPSIS)
    assert snippet.endswith(SNIPPET_ELLIPSIS)
    assert "<mark>plasma</mark>" in snippet
    body = _visible(snippet)[1:-1]
    # No word was cut: every visible word is a whole word of the source.
    source_words = set(text.split())
    assert all(word in source_words for word in body.split())
    assert not body.startswith(" ") and not body.endswith(" ")
    assert len(body) <= SNIPPET_MAX_LENGTH


def test_a_match_near_the_start_gets_only_a_trailing_ellipsis():
    text = f"Plasma {_words(80)}"

    snippet = _make_snippet(text, ["plasma"])

    assert snippet.startswith("<mark>Plasma</mark>")
    assert snippet.endswith(SNIPPET_ELLIPSIS)
    assert _visible(snippet)[:-1].split()[-1] in text.split()


def test_a_match_near_the_end_gets_only_a_leading_ellipsis():
    text = f"{_words(80)} plasma."

    snippet = _make_snippet(text, ["plasma"])

    assert snippet.startswith(SNIPPET_ELLIPSIS)
    assert snippet.endswith("<mark>plasma</mark>.")
    assert _visible(snippet)[1:].split()[0] in text.split()


def test_a_snippet_without_a_match_is_cut_at_a_word_with_a_trailing_ellipsis():
    text = _words(80)

    snippet = _make_snippet(text, ["absent"])

    assert snippet.endswith(SNIPPET_ELLIPSIS)
    assert "<mark>" not in snippet
    assert all(word in text.split() for word in snippet[:-1].split())
    assert len(snippet) - 1 <= SNIPPET_MAX_LENGTH


def test_length_changing_casefold_keeps_the_mark_on_the_matched_word():
    # "ß" folds to "ss", so folded offsets run one ahead after each "ß".
    text = "Die Straße, die Straße und dann ein Laserpistol am Ende."

    snippet = _make_snippet(text, ["laserpistol"])

    assert "<mark>Laserpistol</mark>" in snippet
    assert "Straße" in snippet


def test_a_folded_term_marks_the_original_sharp_s_word():
    snippet = _make_snippet("Auf der Straße liegt nichts.", ["strasse"])

    assert "<mark>Straße</mark>" in snippet


def test_snippet_escaping_survives_the_word_trimming():
    text = f"{_words(60, 'a')} <b>&amp; plasma</b> {_words(60, 'z')}"

    snippet = _make_snippet(text, ["plasma"])

    assert "&lt;b&gt;&amp;amp; <mark>plasma</mark>&lt;/b&gt;" in snippet
    assert "<b>" not in snippet


@pytest.mark.parametrize(
    "query",
    ["", None, "a", " a ", "\ta\t", "\u00a0a\u00a0", " \t\u00a0 "],
)
def test_whitespace_of_any_kind_does_not_count_towards_the_minimum_length(query, one_chapter):
    repository = one_chapter("# Chapter\nA plasma weapon.")

    assert not is_searchable(query)
    assert repository.search(query) == ()
    assert repository.highlight_terms(query) == ()
    assert suggest(repository, query or "")["hits"] == []


def test_two_visible_characters_are_searchable():
    assert is_searchable("pl")
    assert is_searchable(" p l ")

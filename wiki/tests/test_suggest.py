"""The JSON endpoint behind the Auspex command palette."""
from urllib.parse import parse_qs, urlsplit

import pytest
from django.conf import settings as django_settings
from django.urls import reverse

from wiki.content import set_repository_for_tests
from wiki.search import MIN_QUERY_LENGTH
from wiki.suggest import MAX_CHAPTERS, MAX_HITS, MAX_SECTIONS, suggest


@pytest.fixture
def repository(make_repository):
    """Manifest file names, so the chapters get real slugs and numerals."""
    return make_repository(
        {
            "04-Talents.md": (
                "# Chapter IV: Talents\nIntro text.\n\n"
                "## Weapon Training\nBody about training.\n\n"
                "### Basic Weapon Training\nBasic drills.\n\n"
                "## Advanced Weapon Training\nMore drills.\n\n"
                "## Combat Sense\nA sense of combat.\n\n"
                "## Reflexes\nTraining of the reflexes.\n"
            ),
            "05-Armoury.md": (
                "# Chapter V: Armoury\nIntro.\n\n"
                "## Bolters\nThe bolter is a weapon of war.\n"
            ),
        },
    )


@pytest.fixture
def installed(repository):
    set_repository_for_tests(repository)
    return repository


def _query_of(url):
    return parse_qs(urlsplit(url).query)["q"][0]


def _anchor_of(url):
    return url.split("#sec-", 1)[1]


def test_short_query_returns_empty_lists_but_a_search_url(repository):
    result = suggest(repository, "w" * (MIN_QUERY_LENGTH - 1))

    assert result["chapters"] == []
    assert result["sections"] == []
    assert result["hits"] == []
    assert result["search_url"] == reverse("wiki:search") + "?q=w"


def test_spaces_do_not_count_towards_the_minimum_length(repository):
    result = suggest(repository, "  w ")

    assert result["chapters"] == result["sections"] == result["hits"] == []


def test_the_query_is_echoed_as_given(repository):
    assert suggest(repository, " Talents ")["query"] == " Talents "


def test_chapters_match_on_every_token_of_the_title(repository):
    result = suggest(repository, "chap talent")

    assert result["chapters"] == [
        {
            "title": "Chapter IV: Talents",
            "short_title": "Talents",
            "numeral": "IV",
            "url": reverse("wiki:chapter", args=["talents"]),
        }
    ]


def test_chapter_tokens_are_casefolded_and_all_required(repository):
    assert suggest(repository, "TALENTS")["chapters"]
    assert suggest(repository, "talents armoury")["chapters"] == []


def test_sections_rank_a_title_prefix_before_a_word_prefix(repository):
    titles = [s["title"] for s in suggest(repository, "weapon")["sections"]]

    # "Weapon Training" starts with the query (0); the other two only contain
    # the word (1) and keep their book order.
    assert titles == [
        "Weapon Training",
        "Basic Weapon Training",
        "Advanced Weapon Training",
    ]


def test_a_word_start_outranks_a_mid_word_match(make_repository):
    repository = make_repository(
        {"04-Talents.md": "# Talents\n\n## Unarmed\nx.\n\n## Arm Guard\ny.\n"},
    )

    titles = [s["title"] for s in suggest(repository, "arm")["sections"]]

    assert titles == ["Arm Guard", "Unarmed"]


def test_a_later_title_prefix_match_beats_an_earlier_word_match(make_repository):
    repository = make_repository(
        {"04-Talents.md": "# Talents\n\n## Basic Drill\nx.\n\n## Drill Sergeant\ny.\n"},
    )

    titles = [s["title"] for s in suggest(repository, "drill")["sections"]]

    assert titles == ["Drill Sergeant", "Basic Drill"]


def test_sections_carry_chapter_short_title_numeral_path_and_url(repository):
    (section,) = suggest(repository, "basic weapon")["sections"]

    assert section["title"] == "Basic Weapon Training"
    assert section["chapter"] == "Talents"
    assert section["numeral"] == "IV"
    assert section["path"] == ["Weapon Training"]
    chapter_url = reverse("wiki:chapter", args=["talents"])
    assert section["url"].startswith(chapter_url + "?q=basic+weapon#sec-")
    assert _anchor_of(section["url"])


def test_section_url_has_the_query_and_a_section_anchor(repository):
    url = suggest(repository, "combat sense")["sections"][0]["url"]

    assert "?q=" in url and "#sec-" in url
    assert _query_of(url) == "combat sense"


def test_a_whitespace_only_query_is_treated_as_too_short(repository):
    result = suggest(repository, "\t\t \t")

    assert result["chapters"] == result["sections"] == result["hits"] == []


def test_a_matched_chapter_is_not_repeated_as_a_hit_or_section(repository):
    result = suggest(repository, "talents")

    assert [c["short_title"] for c in result["chapters"]] == ["Talents"]
    rows = result["sections"] + result["hits"]
    assert all(row["title"].casefold() != "chapter iv: talents" for row in rows)


def test_dropping_chapter_repeats_still_fills_the_hit_list(make_repository):
    repository = make_repository(
        {
            "04-Talents.md": "# Talents\nIntro.\n\n"
            + "".join(f"## Drill {i}\ntalents everywhere.\n\n" for i in range(8)),
        },
    )

    result = suggest(repository, "talents")

    assert len(result["chapters"]) == 1
    assert len(result["hits"]) == MAX_HITS
    assert all(hit["title"] != "Talents" for hit in result["hits"])


def test_the_intro_is_never_a_section_suggestion(repository):
    assert suggest(repository, "talents")["sections"] == []


def test_a_full_text_hit_is_listed_with_its_snippet(repository):
    result = suggest(repository, "war")

    assert [hit["title"] for hit in result["hits"]] == ["Bolters"]
    hit = result["hits"][0]
    assert hit["chapter"] == "Armoury"
    assert hit["numeral"] == "V"
    assert hit["path"] == []
    assert "<mark>" in hit["snippet_html"]
    assert "#sec-" in hit["url"] and _query_of(hit["url"]) == "war"


def test_hits_never_repeat_a_listed_section(repository):
    result = suggest(repository, "weapon")

    section_urls = {s["url"] for s in result["sections"]}
    assert section_urls
    assert not section_urls & {hit["url"] for hit in result["hits"]}
    # "Bolters" only mentions the word in its body, so it is a hit.
    assert "Bolters" in [hit["title"] for hit in result["hits"]]


def test_caps_are_respected(make_repository):
    chapters = {
        f"{number:02d}-{name}.md": f"# Chapter {roman}: Zeta {name}\n\n"
        + "".join(f"## Zeta part {i}\nzeta text.\n\n" for i in range(9))
        for number, roman, name in [
            (1, "I", "Charaktererschaffung"),
            (2, "II", "Karrierewege"),
            (3, "III", "Skills"),
            (4, "IV", "Talents"),
            (5, "V", "Armoury"),
            (6, "VI", "Psychic-Powers"),
        ]
    }
    # Full-text-only matches: "zeta" never appears in their titles.
    chapters["07-Navigator-Powers.md"] = "# Navigator\n\n" + "".join(
        f"## Other {i}\nzeta zeta zeta.\n\n" for i in range(12)
    )
    repository = make_repository(chapters)

    result = suggest(repository, "zeta")

    assert (MAX_CHAPTERS, MAX_SECTIONS, MAX_HITS) == (4, 6, 6)
    assert len(result["chapters"]) == MAX_CHAPTERS
    assert len(result["sections"]) == MAX_SECTIONS
    assert len(result["hits"]) == MAX_HITS
    assert not {s["url"] for s in result["sections"]} & {
        hit["url"] for hit in result["hits"]
    }
    assert [c["numeral"] for c in result["chapters"]] == ["I", "II", "III", "IV"]


# -- the view ---------------------------------------------------------------


@pytest.mark.django_db
def test_anonymous_requests_are_redirected_to_login(client, installed):
    response = client.get(reverse("wiki:suggest"), {"q": "weapon"})

    assert response.status_code == 302
    assert django_settings.LOGIN_URL in response["Location"]


@pytest.mark.django_db
def test_short_query_over_http_is_ok_and_empty(client, user_factory, installed):
    client.force_login(user_factory())

    response = client.get(reverse("wiki:suggest"), {"q": "w"})

    assert response.status_code == 200
    data = response.json()
    assert data["chapters"] == data["sections"] == data["hits"] == []
    assert data["search_url"] == reverse("wiki:search") + "?q=w"


@pytest.mark.django_db
def test_missing_query_is_treated_as_empty(client, user_factory, installed):
    client.force_login(user_factory())

    response = client.get(reverse("wiki:suggest"))

    assert response.status_code == 200
    assert response.json()["query"] == ""


@pytest.mark.django_db
def test_response_is_json_privately_cached_and_not_compressed(
    client, user_factory, installed
):
    client.force_login(user_factory())

    response = client.get(
        reverse("wiki:suggest"), {"q": "weapon"}, headers={"accept-encoding": "gzip"}
    )

    assert response["Content-Type"].startswith("application/json")
    assert response["Cache-Control"] == "private, max-age=60"
    assert "Content-Encoding" not in response


@pytest.mark.django_db
def test_markup_in_the_query_comes_back_only_as_json_data(
    client, user_factory, installed
):
    client.force_login(user_factory())
    query = "<script>alert(1)</script>"

    response = client.get(reverse("wiki:suggest"), {"q": query})

    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/json")
    data = response.json()
    assert data["query"] == query
    assert _query_of(data["search_url"]) == query
    assert "<script>" not in data["search_url"]


@pytest.mark.django_db
def test_a_title_with_markup_is_returned_as_a_plain_string(
    client, user_factory, make_repository
):
    make_repository(
        {"04-Talents.md": "# Talents\n\n## Use <b>Bold</b> Moves\nText.\n"}, install=True
    )
    client.force_login(user_factory())

    response = client.get(reverse("wiki:suggest"), {"q": "moves"})

    assert response["Content-Type"].startswith("application/json")
    (section,) = response.json()["sections"]
    # The server neither escapes nor wraps the title: the client decides how to
    # render it, and it renders strings as text.
    assert section["title"] == "Use <b>Bold</b> Moves"
    assert "&lt;" not in section["title"] and "<mark>" not in section["title"]

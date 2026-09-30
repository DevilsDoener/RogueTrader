"""Server-side data behind the Auspex navigation: ancestry, numerals, search
paths, unlimited search, highlight terms and curated quick links."""
import pytest
from django.conf import settings as django_settings

from wiki.content import WikiChapter, WikiRepository, WikiSection
from wiki.manifest import DASHBOARD_SHORTCUTS, QUICK_LINKS, QuickLink, ShortcutGroup
from wiki.search import MIN_QUERY_LENGTH


def _load(tmp_path, settings, files):
    for name, text in files.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    settings.WIKI_CONTENT_ROOT = tmp_path
    settings.WIKI_CONTENT_ALLOWLIST = list(files)
    return WikiRepository.load()


def _chapter(part="", title="Title"):
    return WikiChapter(
        slug="x", title=title, source_name="x.md", sections=(), ordinal=0, part=part
    )


# -- parent_titles ----------------------------------------------------------


def test_parent_titles_follow_the_heading_ancestry(tmp_path, settings):
    repository = _load(
        tmp_path,
        settings,
        {
            "01-Tree.md": (
                "# Tree\nIntro text.\n\n"
                "## Alpha\nA.\n\n### Beta\nB.\n\n#### Gamma\nG.\n\n## Delta\nD.\n"
            )
        },
    )
    chapter = repository.get_chapter("tree")
    by_title = {section.title: section for section in chapter.sections}

    assert by_title["Alpha"].parent_titles == ()
    assert by_title["Beta"].parent_titles == ("Alpha",)
    assert by_title["Gamma"].parent_titles == ("Alpha", "Beta")
    assert by_title["Delta"].parent_titles == ()


def test_intro_contributes_nothing_to_the_ancestry(tmp_path, settings):
    repository = _load(
        tmp_path, settings, {"01-Tree.md": "# Tree\nIntro text.\n\n## Alpha\nA.\n"}
    )
    chapter = repository.get_chapter("tree")
    intro = next(section for section in chapter.sections if section.is_intro)
    alpha = next(section for section in chapter.sections if section.title == "Alpha")

    assert intro.parent_titles == ()
    assert alpha.parent_titles == ()


def test_wiki_section_parent_titles_defaults_to_empty():
    section = WikiSection(
        id="a", chapter_slug="c", chapter_title="C", title="A",
        plain_text="", html="", ordinal=0,
    )

    assert section.parent_titles == ()


# -- numeral / short_title --------------------------------------------------


@pytest.mark.parametrize(
    ("part", "numeral"),
    [
        ("Chapter IV", "IV"),
        ("Chapter XIV", "XIV"),
        ("Chapter   IX", "IX"),
        ("Front Matter", ""),
        ("Appendix", ""),
        ("", ""),
    ],
)
def test_numeral_comes_from_the_part(part, numeral):
    assert _chapter(part=part).numeral == numeral


@pytest.mark.parametrize(
    ("title", "short"),
    [
        ("Chapter V: Armoury", "Armoury"),
        ("Chapter 14 - Adversaries & Aliens", "Adversaries & Aliens"),
        ("Chapter XIV – Traits", "Traits"),
        ("chapter iv: Talents", "Talents"),
        ("Traits", "Traits"),
        ("Chapter V:", "Chapter V:"),
    ],
)
def test_short_title_drops_the_chapter_prefix(title, short):
    assert _chapter(title=title).short_title == short


def test_front_matter_chapter_has_no_numeral_and_keeps_its_title(tmp_path, settings):
    repository = _load(tmp_path, settings, {"00-Foreword.md": "# Foreword\nHello.\n"})
    chapter = repository.get_chapter("foreword")

    assert chapter.numeral == ""
    assert chapter.short_title == "Foreword"


# -- search result path, limit, highlight terms -----------------------------


def test_search_result_carries_the_section_path(tmp_path, settings):
    repository = _load(
        tmp_path,
        settings,
        {"01-Tree.md": "# Tree\n\n## Alpha\nA.\n\n### Beta\nA zebrafish swims.\n"},
    )

    result = repository.search("zebrafish")[0]

    assert result.title == "Beta"
    assert result.path == ("Alpha",)


def test_search_result_path_defaults_to_empty():
    from wiki.search import SearchResult

    result = SearchResult("c", "C", "s", "t", "", 1.0)

    assert result.path == ()


@pytest.fixture
def many_matches(tmp_path, settings):
    body = "".join(f"## Entry {index}\nA plasma note.\n\n" for index in range(45))
    return _load(tmp_path, settings, {"01-Many.md": f"# Many\n\n{body}"})


def test_search_default_limit_is_still_thirty(many_matches):
    assert len(many_matches.search("plasma")) == 30


def test_search_with_limit_none_returns_everything(many_matches):
    assert len(many_matches.search("plasma", limit=None)) == 45


def test_highlight_terms_include_aliases_without_prefix_expansion(tmp_path, settings):
    repository = _load(
        tmp_path, settings, {"01-Weapons.md": "# Weapons\nWeaponsmith and weapons.\n"}
    )

    terms = repository.highlight_terms("Waffe")

    assert "waffe" in terms
    assert "weapon" in terms
    assert "weaponsmith" not in terms
    assert terms == tuple(sorted(set(terms)))


def test_highlight_terms_are_empty_for_a_short_query(tmp_path, settings):
    repository = _load(tmp_path, settings, {"01-Weapons.md": "# Weapons\nx\n"})

    assert repository.highlight_terms("x") == ()
    assert repository.highlight_terms("") == ()
    assert MIN_QUERY_LENGTH == 2


def test_highlight_terms_drop_single_character_tokens(tmp_path, settings):
    repository = _load(tmp_path, settings, {"01-Weapons.md": "# Weapons\nx\n"})

    assert repository.highlight_terms("a plasma") == ("plasma",)


# -- quick links ------------------------------------------------------------


def test_quick_link_is_a_frozen_value():
    link = QuickLink("Tests", "playing-the-game", "tests-the-basic-mechanic")

    assert (link.label, link.chapter_slug, link.section_id) == (
        "Tests", "playing-the-game", "tests-the-basic-mechanic",
    )
    with pytest.raises(Exception):
        link.label = "x"


def test_quick_links_drop_entries_whose_target_is_missing(tmp_path, settings, monkeypatch):
    repository = _load(
        tmp_path, settings, {"01-Tree.md": "# Tree\n\n## Alpha\nA.\n"}
    )
    good = QuickLink("Alpha", "tree", "alpha")
    monkeypatch.setattr(
        "wiki.content.QUICK_LINKS",
        (
            good,
            QuickLink("No Chapter", "nope", "alpha"),
            QuickLink("No Section", "tree", "missing"),
        ),
    )

    assert repository.quick_links() == ((good, repository.get_chapter("tree")),)


@pytest.mark.skipif(
    not (django_settings.BASE_DIR / "content" / "03-Skills.md").exists(),
    reason="real wiki content is not available in this checkout",
)
def test_every_curated_quick_link_resolves_against_the_real_corpus(settings):
    from wiki.manifest import ALLOWLIST

    settings.WIKI_CONTENT_ROOT = settings.BASE_DIR / "content"
    settings.WIKI_CONTENT_ALLOWLIST = list(ALLOWLIST)
    # ``load`` builds a fresh repository and never touches the process-wide
    # singleton, so there is nothing to restore afterwards.
    repository = WikiRepository.load()

    assert len(repository.quick_links()) == len(QUICK_LINKS)


# -- dashboard shortcuts ----------------------------------------------------


def test_dashboard_shortcuts_drop_missing_links_and_empty_groups(
    tmp_path, settings, monkeypatch
):
    repository = _load(
        tmp_path, settings, {"01-Tree.md": "# Tree\n\n## Alpha\nA.\n\n## Beta\nB.\n"}
    )
    alpha = QuickLink("Alpha", "tree", "alpha")
    beta = QuickLink("Beta", "tree", "beta")
    kept = ShortcutGroup(
        "Kept", "combat", (alpha, QuickLink("No Section", "tree", "missing"), beta)
    )
    emptied = ShortcutGroup("Emptied", "trade", (QuickLink("No Chapter", "nope", "alpha"),))
    monkeypatch.setattr("wiki.content.DASHBOARD_SHORTCUTS", (kept, emptied))
    tree = repository.get_chapter("tree")

    assert repository.dashboard_shortcuts() == ((kept, ((alpha, tree), (beta, tree))),)


def test_dashboard_shortcut_groups_are_non_empty_and_uniquely_titled():
    titles = [group.title for group in DASHBOARD_SHORTCUTS]

    assert len(titles) == len(set(titles))
    assert all(group.links and group.glyph for group in DASHBOARD_SHORTCUTS)


@pytest.mark.skipif(
    not (django_settings.BASE_DIR / "content" / "03-Skills.md").exists(),
    reason="real wiki content is not available in this checkout",
)
def test_every_dashboard_shortcut_resolves_against_the_real_corpus(settings):
    from wiki.manifest import ALLOWLIST

    settings.WIKI_CONTENT_ROOT = settings.BASE_DIR / "content"
    settings.WIKI_CONTENT_ALLOWLIST = list(ALLOWLIST)
    repository = WikiRepository.load()

    resolved = {
        group.title: [link for link, _chapter in links]
        for group, links in repository.dashboard_shortcuts()
    }

    assert resolved == {group.title: list(group.links) for group in DASHBOARD_SHORTCUTS}

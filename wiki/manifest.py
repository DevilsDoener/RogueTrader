"""The book's chapters, in reading order -- the single source of truth.

``settings.WIKI_DEFAULT_CONTENT_ALLOWLIST`` is generated from ``CHAPTERS``; the
``WIKI_CONTENT_ALLOWLIST`` environment override still wins.

- **Ordering** is the tuple order below. The ``NN-`` filename prefixes are not
  unique (``00-`` appears three times, ``14-`` four, because chapter XIV was
  split along the PDF's own bookmarks), so it cannot come from filenames.
- **Slugs** are explicit, so renaming a file cannot move a page.
- **Numerals and bands** follow the printed book: front matter, the numbered
  chapters, and the appendix. Titles are never set here -- each chapter's
  displayed name is the H1 from its own Markdown file.

This module is imported by ``config/settings.py``, so it must stay importable
without ``django.setup()``: no Django imports at module scope.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

#: The Bibliothek bands, in the order the overview shows them.
BAND_FRONT_MATTER = "Front Matter"
BAND_CHAPTERS = "Chapters"
BAND_APPENDIX = "Appendix"
BANDS: Tuple[str, ...] = (BAND_FRONT_MATTER, BAND_CHAPTERS, BAND_APPENDIX)


@dataclass(frozen=True)
class ChapterEntry:
    #: File name under ``WIKI_CONTENT_ROOT``.
    source_name: str
    #: URL slug. Explicit, so renaming the file cannot move the page.
    slug: str
    #: Roman numeral of a numbered book chapter; empty for front matter and
    #: the appendix. Shown on cards, in the nav and in search results.
    numeral: str = ""
    #: Which Bibliothek band (one of ``BANDS``) lists the chapter.
    band: str = BAND_CHAPTERS
    #: Relative weight in search ranking. Lowered for chapters that are
    #: navigation aids rather than rules: the page-number index and the
    #: foreword otherwise surface above the rules that answer the query.
    search_weight: float = 1.0


CHAPTERS: Tuple[ChapterEntry, ...] = (
    ChapterEntry(
        "00-Foreword.md", "foreword", band=BAND_FRONT_MATTER, search_weight=0.3
    ),
    ChapterEntry(
        "00-Inhaltsverzeichnis-und-Einleitung.md",
        "inhaltsverzeichnis-und-einleitung",
        band=BAND_FRONT_MATTER,
        search_weight=0.3,
    ),
    ChapterEntry("01-Charaktererschaffung.md", "charaktererschaffung", "I"),
    ChapterEntry("02-Karrierewege.md", "karrierewege", "II"),
    ChapterEntry("03-Skills.md", "skills", "III"),
    ChapterEntry("04-Talents.md", "talents", "IV"),
    ChapterEntry("05-Armoury.md", "armoury", "V"),
    ChapterEntry("06-Psychic-Powers.md", "psychic-powers", "VI"),
    ChapterEntry("07-Navigator-Powers.md", "navigator-powers", "VII"),
    ChapterEntry("08-Starships.md", "starships", "VIII"),
    ChapterEntry("09-Playing-The-Game.md", "playing-the-game", "IX"),
    ChapterEntry("10-The-Game-Master.md", "the-game-master", "X"),
    ChapterEntry("11-The-Imperium.md", "the-imperium", "XI"),
    ChapterEntry("12-Rogue-Traders.md", "rogue-traders", "XII"),
    ChapterEntry("13-The-Koronus-Expanse.md", "the-koronus-expanse", "XIII"),
    # Chapter XIV is four files because the PDF bookmarks split it that way.
    ChapterEntry("14-Adversaries-and-Aliens.md", "adversaries-and-aliens", "XIV"),
    ChapterEntry("14-Allies-Enemies-and-Rivals.md", "allies-enemies-and-rivals", "XIV"),
    ChapterEntry("14-Mutations.md", "mutations", "XIV"),
    ChapterEntry("14-Traits.md", "traits", "XIV"),
    ChapterEntry("15-Into-The-Maw.md", "into-the-maw", "XV"),
    ChapterEntry("16-Index.md", "index", band=BAND_APPENDIX, search_weight=0.3),
)

#: Markdown files under the content root that are deliberately not served
#: (listed here so ``check_wiki_content`` does not warn about them). Every
#: file currently under ``content/`` is a chapter, so this is empty.
KNOWN_EXCLUDED: frozenset = frozenset()

ALLOWLIST: Tuple[str, ...] = tuple(entry.source_name for entry in CHAPTERS)

_BY_SOURCE: Dict[str, ChapterEntry] = {entry.source_name: entry for entry in CHAPTERS}


def entry_for(source_name: str) -> ChapterEntry:
    """The manifest entry for a file, or a neutral default.

    A file reaching the parser without a manifest entry can only come from an
    explicit ``WIKI_CONTENT_ALLOWLIST`` override (or a test fixture), so it
    still renders -- without a numeral or a curated slug, in the chapters band.
    """
    known = _BY_SOURCE.get(source_name)
    if known is not None:
        return known
    return ChapterEntry(source_name=source_name, slug="")


@dataclass(frozen=True)
class QuickLink:
    label: str
    chapter_slug: str
    section_id: str


#: Links listed both in QUICK_LINKS and in DASHBOARD_SHORTCUTS, declared once so
#: a moved book anchor is fixed in one place.
_DEGREES_OF_SUCCESS = QuickLink(
    "Degrees of Success", "playing-the-game", "degrees-of-success-and-failure"
)
_COMBAT_ACTIONS = QuickLink("Combat Actions", "playing-the-game", "table-9-4-combat-actions")
_HIT_LOCATIONS = QuickLink("Hit Locations", "playing-the-game", "table-9-6-hit-locations")
_RANGED_WEAPONS = QuickLink("Ranged Weapons", "armoury", "table-5-4-ranged-weapons")
_WEAPON_QUALITIES = QuickLink("Weapon Qualities", "armoury", "weapon-special-qualities")
_PERILS_OF_THE_WARP = QuickLink(
    "Perils of the Warp", "psychic-powers", "table-6-3-perils-of-the-warp"
)
_STARSHIP_COMBAT = QuickLink("Starship Combat", "starships", "starship-combat")

#: Rules the table looks up mid-session. Labels are English (book content); targets are
#: section anchors (``sec-<id>``) checked against the real corpus by
#: wiki/tests/test_navigation_data.py.
QUICK_LINKS: Tuple[QuickLink, ...] = (
    QuickLink("Tests", "playing-the-game", "tests-the-basic-mechanic"),
    _DEGREES_OF_SUCCESS,
    _COMBAT_ACTIONS,
    _HIT_LOCATIONS,
    QuickLink("Critical Damage", "playing-the-game", "critical-effect-tables-tables-9-11-to-9-26"),
    _RANGED_WEAPONS,
    _WEAPON_QUALITIES,
    QuickLink("Armour", "armoury", "armour"),
    QuickLink("Skills", "skills", "skill-descriptions"),
    QuickLink("Talents", "talents", "detailed-talent-descriptions"),
    _PERILS_OF_THE_WARP,
    _STARSHIP_COMBAT,
)


@dataclass(frozen=True)
class ShortcutGroup:
    #: Group heading, English like the labels (book content).
    title: str
    #: Icon key the dashboard maps to an inline SVG (core/_shortcut_glyph.html).
    glyph: str
    links: Tuple[QuickLink, ...]


#: The Kommandobrücke's rule shortcuts: the tables looked up most at the table,
#: grouped by what is being resolved. Same rules as QUICK_LINKS -- English
#: labels, ``sec-<id>`` targets, checked against the real corpus by
#: wiki/tests/test_navigation_data.py; unresolvable links are dropped by
#: ``WikiRepository.dashboard_shortcuts()``.
DASHBOARD_SHORTCUTS: Tuple[ShortcutGroup, ...] = (
    ShortcutGroup(
        "Combat",
        "combat",
        (
            _COMBAT_ACTIONS,
            _HIT_LOCATIONS,
            QuickLink(
                "Combat Difficulty", "playing-the-game", "table-9-8-combat-difficulty-summary"
            ),
            QuickLink("Cover", "playing-the-game", "table-9-7-cover-examples"),
            QuickLink("Multiple Hits", "playing-the-game", "table-9-5-multiple-hits"),
            QuickLink(
                "Critical Effects",
                "playing-the-game",
                "critical-effect-tables-tables-9-11-to-9-26",
            ),
            QuickLink(
                "Conditions & Special Damage", "playing-the-game", "conditions-and-special-damage"
            ),
            QuickLink("Fatigue", "playing-the-game", "fatigue"),
            QuickLink("Healing", "playing-the-game", "healing"),
        ),
    ),
    ShortcutGroup(
        "Psychic Powers",
        "psychic",
        (
            QuickLink("Psychic Strength", "psychic-powers", "table-6-1-psychic-strength"),
            QuickLink("Psychic Phenomena", "psychic-powers", "table-6-2-psychic-phenomena"),
            _PERILS_OF_THE_WARP,
        ),
    ),
    ShortcutGroup(
        "Weapons & Armour",
        "armoury",
        (
            _RANGED_WEAPONS,
            QuickLink("Melee Weapons", "armoury", "table-5-8-melee-weapons"),
            QuickLink("Grenades & Missiles", "armoury", "table-5-6-grenades-and-missiles"),
            _WEAPON_QUALITIES,
            QuickLink("Armour", "armoury", "table-5-12-armour"),
            QuickLink("Ammo", "armoury", "table-5-10-ammo"),
        ),
    ),
    ShortcutGroup(
        "Tests & Fate",
        "tests",
        (
            QuickLink("Test Difficulty", "playing-the-game", "table-9-3-test-difficulty"),
            _DEGREES_OF_SUCCESS,
            QuickLink("Fate Points", "playing-the-game", "the-role-of-fate"),
            QuickLink("Fear Tests", "the-game-master", "fear-tests"),
            QuickLink(
                "Insanity & Corruption",
                "the-game-master",
                "insanity-points-and-corruption-points",
            ),
        ),
    ),
    ShortcutGroup(
        "Starship Combat",
        "starship",
        (
            _STARSHIP_COMBAT,
            QuickLink("Manoeuvre Actions", "starships", "manoeuvre-actions-table-8-10"),
            QuickLink("Extended Actions", "starships", "extended-actions-table-8-11"),
            QuickLink("Ship Critical Hits", "starships", "table-8-12-critical-hits"),
            QuickLink("Morale", "starships", "table-8-14-morale"),
        ),
    ),
    ShortcutGroup(
        "Trade & Acquisition",
        "trade",
        (
            QuickLink("Acquisition", "playing-the-game", "acquisition"),
            QuickLink(
                "Acquisition Modifiers", "playing-the-game", "table-9-35-acquisition-modifiers"
            ),
            QuickLink("Misfortunes", "playing-the-game", "table-9-41-misfortunes"),
        ),
    ),
)

"""The book's chapters, in reading order -- the single source of truth.

Before this module the chapter list lived in four places (``config/settings.py``,
``.env``, ``.env.example``, ``compose.yaml``) and did double duty as both the
security filter and the ordering. It is now declared once, here, and
``settings.WIKI_DEFAULT_CONTENT_ALLOWLIST`` is generated from it; the
``WIKI_CONTENT_ALLOWLIST`` environment override still works and still wins.

Three things this fixes:

- **Ordering.** The ``NN-`` filename prefixes are not unique -- ``00-`` appears
  three times and ``14-`` four, because chapter XIV was split along the PDF's
  own bookmarks. Reading order therefore cannot be derived from filenames and
  is the tuple order below.
- **Slugs.** They used to be derived from the filename, so renaming a file
  silently changed a URL. They are now explicit. The values are exactly the
  ones the derivation produced, so no existing link breaks.
- **Grouping.** ``part`` follows the printed book: front matter, the numbered
  chapters in order, and the appendix. Chapter XIV is one part holding its four
  files. Titles are never invented here -- each chapter's displayed name is the
  H1 from its own Markdown file.

This module is imported by ``config/settings.py``, so it must stay importable
without ``django.setup()``: no Django imports at module scope.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

#: Front matter and appendix parts, named for what the book calls them.
PART_FRONT_MATTER = "Front Matter"
PART_APPENDIX = "Appendix"


@dataclass(frozen=True)
class ChapterEntry:
    #: File name under ``WIKI_CONTENT_ROOT``.
    source_name: str
    #: URL slug. Explicit, so renaming the file cannot move the page.
    slug: str
    #: Grouping key for the overview page.
    part: str
    #: Relative weight in search ranking. Lowered for chapters that are
    #: navigation aids rather than rules: the page-number index and the
    #: foreword otherwise surface above the rules that answer the query.
    search_weight: float = 1.0


CHAPTERS: Tuple[ChapterEntry, ...] = (
    ChapterEntry("00-Foreword.md", "foreword", PART_FRONT_MATTER, search_weight=0.3),
    ChapterEntry(
        "00-Inhaltsverzeichnis-und-Einleitung.md",
        "inhaltsverzeichnis-und-einleitung",
        PART_FRONT_MATTER,
        search_weight=0.3,
    ),
    ChapterEntry("01-Charaktererschaffung.md", "charaktererschaffung", "Chapter I"),
    ChapterEntry("02-Karrierewege.md", "karrierewege", "Chapter II"),
    ChapterEntry("03-Skills.md", "skills", "Chapter III"),
    ChapterEntry("04-Talents.md", "talents", "Chapter IV"),
    ChapterEntry("05-Armoury.md", "armoury", "Chapter V"),
    ChapterEntry("06-Psychic-Powers.md", "psychic-powers", "Chapter VI"),
    ChapterEntry("07-Navigator-Powers.md", "navigator-powers", "Chapter VII"),
    ChapterEntry("08-Starships.md", "starships", "Chapter VIII"),
    ChapterEntry("09-Playing-The-Game.md", "playing-the-game", "Chapter IX"),
    ChapterEntry("10-The-Game-Master.md", "the-game-master", "Chapter X"),
    ChapterEntry("11-The-Imperium.md", "the-imperium", "Chapter XI"),
    ChapterEntry("12-Rogue-Traders.md", "rogue-traders", "Chapter XII"),
    ChapterEntry("13-The-Koronus-Expanse.md", "the-koronus-expanse", "Chapter XIII"),
    # Chapter XIV is four files because the PDF bookmarks split it that way.
    ChapterEntry("14-Adversaries-and-Aliens.md", "adversaries-and-aliens", "Chapter XIV"),
    ChapterEntry(
        "14-Allies-Enemies-and-Rivals.md", "allies-enemies-and-rivals", "Chapter XIV"
    ),
    ChapterEntry("14-Mutations.md", "mutations", "Chapter XIV"),
    ChapterEntry("14-Traits.md", "traits", "Chapter XIV"),
    ChapterEntry("15-Into-The-Maw.md", "into-the-maw", "Chapter XV"),
    ChapterEntry("16-Index.md", "index", PART_APPENDIX, search_weight=0.3),
)

#: Markdown files under the content root that are deliberately not served.
#: ``00-FORTSCHRITT.md`` is the transcription work log; ``00-INDEX.md`` is a
#: hand-written routing aid that the generated overview replaces.
KNOWN_EXCLUDED: frozenset = frozenset(
    {"00-FORTSCHRITT.md", "00-INDEX.md"}
)

ALLOWLIST: Tuple[str, ...] = tuple(entry.source_name for entry in CHAPTERS)

_BY_SOURCE: Dict[str, ChapterEntry] = {entry.source_name: entry for entry in CHAPTERS}


def entry_for(source_name: str) -> ChapterEntry:
    """The manifest entry for a file, or a neutral default.

    A file reaching the parser without a manifest entry can only come from an
    explicit ``WIKI_CONTENT_ALLOWLIST`` override, so it still renders -- just
    without grouping or a curated slug.
    """
    known = _BY_SOURCE.get(source_name)
    if known is not None:
        return known
    return ChapterEntry(source_name=source_name, slug="", part="")


@dataclass(frozen=True)
class QuickLink:
    label: str
    chapter_slug: str
    section_id: str


#: Rules the table looks up mid-session. Labels are English (book content); targets are
#: section anchors (``sec-<id>``) checked against the real corpus by
#: wiki/tests/test_navigation_data.py.
QUICK_LINKS: Tuple[QuickLink, ...] = (
    QuickLink("Tests", "playing-the-game", "tests-the-basic-mechanic"),
    QuickLink("Degrees of Success", "playing-the-game", "degrees-of-success-and-failure"),
    QuickLink("Combat Actions", "playing-the-game", "table-9-4-combat-actions"),
    QuickLink("Hit Locations", "playing-the-game", "table-9-6-hit-locations"),
    QuickLink("Critical Damage", "playing-the-game", "critical-effect-tables-tables-9-11-to-9-26"),
    QuickLink("Ranged Weapons", "armoury", "table-5-4-ranged-weapons"),
    QuickLink("Weapon Qualities", "armoury", "weapon-special-qualities"),
    QuickLink("Armour", "armoury", "armour"),
    QuickLink("Skills", "skills", "skill-descriptions"),
    QuickLink("Talents", "talents", "detailed-talent-descriptions"),
    QuickLink("Perils of the Warp", "psychic-powers", "table-6-3-perils-of-the-warp"),
    QuickLink("Starship Combat", "starships", "starship-combat"),
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
            QuickLink("Combat Actions", "playing-the-game", "table-9-4-combat-actions"),
            QuickLink("Hit Locations", "playing-the-game", "table-9-6-hit-locations"),
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
            QuickLink("Perils of the Warp", "psychic-powers", "table-6-3-perils-of-the-warp"),
        ),
    ),
    ShortcutGroup(
        "Weapons & Armour",
        "armoury",
        (
            QuickLink("Ranged Weapons", "armoury", "table-5-4-ranged-weapons"),
            QuickLink("Melee Weapons", "armoury", "table-5-8-melee-weapons"),
            QuickLink("Grenades & Missiles", "armoury", "table-5-6-grenades-and-missiles"),
            QuickLink("Weapon Qualities", "armoury", "weapon-special-qualities"),
            QuickLink("Armour", "armoury", "table-5-12-armour"),
            QuickLink("Ammo", "armoury", "table-5-10-ammo"),
        ),
    ),
    ShortcutGroup(
        "Tests & Fate",
        "tests",
        (
            QuickLink("Test Difficulty", "playing-the-game", "table-9-3-test-difficulty"),
            QuickLink(
                "Degrees of Success", "playing-the-game", "degrees-of-success-and-failure"
            ),
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
            QuickLink("Starship Combat", "starships", "starship-combat"),
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

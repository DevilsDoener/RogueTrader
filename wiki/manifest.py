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
PART_FRONT_MATTER = "Vorspann"
PART_APPENDIX = "Anhang"


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
    ChapterEntry("01-Charaktererschaffung.md", "charaktererschaffung", "Kapitel I"),
    ChapterEntry("02-Karrierewege.md", "karrierewege", "Kapitel II"),
    ChapterEntry("03-Skills.md", "skills", "Kapitel III"),
    ChapterEntry("04-Talents.md", "talents", "Kapitel IV"),
    ChapterEntry("05-Armoury.md", "armoury", "Kapitel V"),
    ChapterEntry("06-Psychic-Powers.md", "psychic-powers", "Kapitel VI"),
    ChapterEntry("07-Navigator-Powers.md", "navigator-powers", "Kapitel VII"),
    ChapterEntry("08-Starships.md", "starships", "Kapitel VIII"),
    ChapterEntry("09-Playing-The-Game.md", "playing-the-game", "Kapitel IX"),
    ChapterEntry("10-The-Game-Master.md", "the-game-master", "Kapitel X"),
    ChapterEntry("11-The-Imperium.md", "the-imperium", "Kapitel XI"),
    ChapterEntry("12-Rogue-Traders.md", "rogue-traders", "Kapitel XII"),
    ChapterEntry("13-The-Koronus-Expanse.md", "the-koronus-expanse", "Kapitel XIII"),
    # Chapter XIV is four files because the PDF bookmarks split it that way.
    ChapterEntry("14-Adversaries-and-Aliens.md", "adversaries-and-aliens", "Kapitel XIV"),
    ChapterEntry(
        "14-Allies-Enemies-and-Rivals.md", "allies-enemies-and-rivals", "Kapitel XIV"
    ),
    ChapterEntry("14-Mutations.md", "mutations", "Kapitel XIV"),
    ChapterEntry("14-Traits.md", "traits", "Kapitel XIV"),
    ChapterEntry("15-Into-The-Maw.md", "into-the-maw", "Kapitel XV"),
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

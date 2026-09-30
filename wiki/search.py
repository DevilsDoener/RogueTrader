"""In-memory full-text search index over wiki sections.

Three things shape the ranking here, each chosen against the real corpus:

- **German queries go through an alias table.** The interface is German, the
  group speaks German, and the book is English -- without it "Stärke",
  "Waffe", "Schiff" and "Deckung" score zero hits. Diacritic folding does not
  help (only 35 of ~101,000 tokens carry an umlaut); a curated alias table does.
- **Term frequency saturates.** Raw counts let one very long section win
  almost any term it happens to repeat. True length normalisation
  (sqrt/log/BM25) over-corrects on this corpus: it promotes a statblock that
  mentions a word once over the rules section actually about it, and pushes
  the section literally titled "Profit Factor" off the top spot. Saturating
  the body count keeps the wins and avoids that.
- **Some chapters are navigation, not rules.** The page-number index and the
  foreword would take top spots for ordinary words; their lower weight comes
  from ``wiki/manifest.py``.
"""
from __future__ import annotations

import bisect
import html
import re
from collections import Counter
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

TITLE_WEIGHT = 4
BODY_WEIGHT = 1
SNIPPET_RADIUS = 90
SNIPPET_MAX_LENGTH = 180
MIN_QUERY_LENGTH = 2

#: Saturation constant for body term frequency: f * (k + 1) / (f + k). Higher
#: k means counts keep mattering for longer; 1.5 caps a runaway repeat while
#: still ranking three mentions above one.
TF_SATURATION = 1.5

#: Shortest query term that may expand to longer words sharing its prefix.
#: Below this almost everything matches and the expansion is noise.
PREFIX_MIN_LENGTH = 4

#: Prefix matches count for less than the word the reader actually typed.
PREFIX_WEIGHT = 0.5

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)

#: German query terms mapped onto the English vocabulary of the book. Meant to
#: grow: add whatever your table actually says out loud. Keys are casefolded
#: and umlaut variants are listed explicitly, because the tokenizer does not
#: fold them.
QUERY_ALIASES: Dict[str, Tuple[str, ...]] = {
    # Characteristics
    "stärke": ("strength",),
    "staerke": ("strength",),
    "widerstand": ("toughness",),
    "zähigkeit": ("toughness",),
    "gewandtheit": ("agility",),
    "beweglichkeit": ("agility",),
    "intelligenz": ("intelligence",),
    "wahrnehmung": ("perception",),
    "willenskraft": ("willpower",),
    "charisma": ("fellowship",),
    "kampfgeschick": ("weapon", "skill"),
    # Core play
    "fertigkeit": ("skill",),
    "fertigkeiten": ("skill",),
    "talent": ("talent",),
    "talente": ("talent",),
    "merkmal": ("trait",),
    "merkmale": ("trait",),
    "probe": ("test",),
    "würfel": ("dice", "roll"),
    "wuerfel": ("dice", "roll"),
    "erfahrung": ("experience",),
    "rang": ("rank",),
    "karriere": ("career",),
    "karrierewege": ("career",),
    "charakter": ("character",),
    "charaktererschaffung": ("character", "creation"),
    "schicksalspunkt": ("fate",),
    "schicksalspunkte": ("fate",),
    "profitfaktor": ("profit",),
    # Combat
    "waffe": ("weapon",),
    "waffen": ("weapon",),
    "rüstung": ("armour", "armor"),
    "ruestung": ("armour", "armor"),
    "schaden": ("damage",),
    "treffer": ("hit",),
    "angriff": ("attack",),
    "deckung": ("cover",),
    "ausweichen": ("dodge",),
    "parieren": ("parry",),
    "initiative": ("initiative",),
    "reichweite": ("range",),
    "munition": ("ammunition", "clip"),
    "wunde": ("wound",),
    "wunden": ("wound",),
    "erschöpfung": ("fatigue",),
    "erschoepfung": ("fatigue",),
    "furcht": ("fear",),
    "bewegung": ("movement",),
    "geschwindigkeit": ("speed",),
    "kritisch": ("critical",),
    "kritischer": ("critical",),
    "gift": ("toxic", "poison"),
    "feuer": ("fire",),
    "heilung": ("healing", "medicae"),
    # Corruption and the warp
    "korruption": ("corruption",),
    "verderbnis": ("corruption",),
    "wahnsinn": ("insanity",),
    "mutation": ("mutation",),
    "psioniker": ("psyker",),
    "psi": ("psychic",),
    "warp": ("warp",),
    "navigator": ("navigator",),
    # Ships and trade
    "schiff": ("ship", "starship", "voidship"),
    "schiffe": ("ship", "starship", "voidship"),
    "raumschiff": ("starship", "voidship"),
    "rumpf": ("hull",),
    "schild": ("shield",),
    "schilde": ("shield",),
    "antrieb": ("drive", "engine"),
    "besatzung": ("crew",),
    "kapitän": ("captain",),
    "kapitaen": ("captain",),
    "händler": ("trader",),
    "haendler": ("trader",),
    "handel": ("trade",),
    "planet": ("planet",),
    "gegner": ("adversary", "enemy"),
    "verbündete": ("allies",),
    "verbuendete": ("allies",),
}


@dataclass(frozen=True)
class SearchResult:
    chapter_slug: str
    section_id: str
    title: str
    snippet: str
    score: float
    #: Ancestor headings of the section, outermost first (empty for a top-level
    #: section or the intro).
    path: Tuple[str, ...] = ()


def tokenize(text: str) -> List[str]:
    """Casefolded Unicode word tokens."""
    return _TOKEN_RE.findall((text or "").casefold())


def _saturate(count: int) -> float:
    """Diminishing returns for repeated body mentions."""
    if count <= 0:
        return 0.0
    return count * (TF_SATURATION + 1) / (count + TF_SATURATION)


SNIPPET_ELLIPSIS = "…"


def _casefold_with_offsets(text: str) -> Tuple[str, List[int]]:
    """Casefold ``text`` and map every folded index back to its source index.

    Casefolding can lengthen a string ("ß" becomes "ss"), so an offset
    found in the folded text must not be used to slice the original directly.
    The returned list has one entry per folded character plus a final
    ``len(text)`` sentinel.
    """
    folded = text.casefold()
    if len(folded) == len(text):
        # casefold never yields an empty string for a character, so equal
        # lengths mean every character folded to exactly one.
        return folded, list(range(len(text) + 1))
    pieces: List[str] = []
    origin: List[int] = []
    for index, char in enumerate(text):
        piece = char.casefold()
        pieces.append(piece)
        origin.extend([index] * len(piece))
    origin.append(len(text))
    return "".join(pieces), origin


def _trim_start(text: str, start: int, limit: int) -> int:
    """Move ``start`` forward to the next word start, never past ``limit``."""
    if start <= 0 or text[start - 1].isspace():
        return start
    for index in range(start, limit):
        if text[index].isspace():
            while index < limit and text[index].isspace():
                index += 1
            return index
    return limit


def _trim_end(text: str, end: int, limit: int) -> int:
    """Move ``end`` back to the previous word end, never before ``limit``."""
    if end >= len(text) or text[end].isspace():
        return end
    for index in range(end - 1, limit - 1, -1):
        if text[index].isspace():
            while index > limit and text[index - 1].isspace():
                index -= 1
            return index
    return limit


def _make_snippet(plain_text: str, terms: Sequence[str]) -> str:
    """Escaped window around the first match; only ``<mark>`` is markup.

    The window is cut at word boundaries, and an ellipsis marks each side
    where text was left out.
    """
    casefolded, origin = _casefold_with_offsets(plain_text)
    match_start = None
    match_end = None
    for term in terms:
        if not term:
            continue
        index = casefolded.find(term)
        if index == -1:
            continue
        start_in_text = origin[index]
        end_in_text = origin[index + len(term) - 1] + 1
        if match_start is None or start_in_text < match_start:
            match_start = start_in_text
            match_end = end_in_text

    if match_start is None:
        end = min(len(plain_text), SNIPPET_MAX_LENGTH)
        if end < len(plain_text):
            end = _trim_end(plain_text, end, 0) or end
        text = html.escape(plain_text[:end])
        return text + SNIPPET_ELLIPSIS if end < len(plain_text) else text

    # Keep the whole window (prefix + match + suffix) within
    # SNIPPET_MAX_LENGTH regardless of how long the matched term itself is,
    # rather than always padding by a fixed radius on each side.
    context_budget = max(0, SNIPPET_MAX_LENGTH - (match_end - match_start))
    radius = min(SNIPPET_RADIUS, context_budget // 2)
    start = _trim_start(plain_text, max(0, match_start - radius), match_start)
    end = _trim_end(plain_text, min(len(plain_text), match_end + radius), match_end)
    prefix = html.escape(plain_text[start:match_start])
    matched = html.escape(plain_text[match_start:match_end])
    suffix = html.escape(plain_text[match_end:end])
    lead = SNIPPET_ELLIPSIS if start > 0 else ""
    tail = SNIPPET_ELLIPSIS if end < len(plain_text) else ""
    return f"{lead}{prefix}<mark>{matched}</mark>{suffix}{tail}"


class SearchIndex:
    """Ranks wiki sections against a query using weighted term intersection."""

    def __init__(
        self,
        entries: Sequence[Tuple[object, object, Dict[str, int], Dict[str, int]]],
        vocabulary: Sequence[str] = (),
    ):
        # Each entry: (chapter, section, title_token_counts, body_token_counts)
        self._entries = tuple(entries)
        self._vocabulary = tuple(vocabulary)

    def _expand(self, term: str) -> Dict[str, float]:
        """Query term -> {variant: weight}.

        The typed word and any curated alias count fully; words that merely
        start with it count for less, so "laspistol" still ranks an exact
        "laspistol" above "laspistols".
        """
        variants: Dict[str, float] = {term: 1.0}
        for alias in QUERY_ALIASES.get(term, ()):
            variants.setdefault(alias, 1.0)

        if len(term) >= PREFIX_MIN_LENGTH and self._vocabulary:
            start = bisect.bisect_left(self._vocabulary, term)
            for candidate in self._vocabulary[start:]:
                if not candidate.startswith(term):
                    break
                if candidate not in variants:
                    variants[candidate] = PREFIX_WEIGHT
        return variants

    def highlight_terms(self, query: str) -> Tuple[str, ...]:
        """Words a results page should mark in a section for ``query``.

        The typed words plus their curated aliases, deliberately without the
        prefix expansion ``search`` applies: highlighting every word that merely
        starts with the query would paint half a page for a short term.
        """
        if len((query or "").replace(" ", "")) < MIN_QUERY_LENGTH:
            return ()
        terms: Set[str] = set()
        for token in tokenize(query):
            terms.add(token)
            terms.update(QUERY_ALIASES.get(token, ()))
        return tuple(sorted(term for term in terms if len(term) >= 2))

    def search(self, query: str, limit: Optional[int] = 30) -> Tuple[SearchResult, ...]:
        if len((query or "").replace(" ", "")) < MIN_QUERY_LENGTH:
            return ()

        terms = sorted(set(tokenize(query)))
        if not terms:
            return ()

        expanded = [self._expand(term) for term in terms]

        scored: List[Tuple[float, int, int, object, object, Tuple[str, ...]]] = []
        for chapter, section, title_tokens, body_tokens in self._entries:
            total = 0.0
            matched: Set[str] = set()
            for variants in expanded:
                best = 0.0
                best_variant = None
                for variant, weight in variants.items():
                    title_count = title_tokens.get(variant, 0)
                    body_count = body_tokens.get(variant, 0)
                    if not title_count and not body_count:
                        continue
                    value = (
                        title_count * TITLE_WEIGHT + _saturate(body_count) * BODY_WEIGHT
                    ) * weight
                    if value > best:
                        best = value
                        best_variant = variant
                if best <= 0:
                    # Every query term must match something: AND semantics are
                    # preserved across terms, the alias set only widens what
                    # counts as a match for one term.
                    break
                total += best
                matched.add(best_variant)
            else:
                weighted = total * chapter.search_weight
                if weighted > 0:
                    scored.append(
                        (
                            weighted,
                            chapter.ordinal,
                            section.ordinal,
                            chapter,
                            section,
                            tuple(sorted(matched)),
                        )
                    )

        scored.sort(key=lambda item: (-item[0], item[1], item[2]))

        results = []
        for score, _chapter_ordinal, _section_ordinal, chapter, section, matched in scored[:limit]:
            results.append(
                SearchResult(
                    chapter_slug=chapter.slug,
                    section_id=section.id,
                    title=section.title,
                    snippet=_make_snippet(section.plain_text, matched),
                    score=score,
                    path=section.parent_titles,
                )
            )
        return tuple(results)


def build_search_index(chapters: Iterable[object]) -> SearchIndex:
    entries = []
    vocabulary: Set[str] = set()
    for chapter in chapters:
        for section in chapter.sections:
            title_tokens = Counter(tokenize(section.title))
            body_tokens = Counter(tokenize(section.plain_text))
            vocabulary.update(title_tokens)
            vocabulary.update(body_tokens)
            entries.append((chapter, section, title_tokens, body_tokens))
    return SearchIndex(entries, sorted(vocabulary))

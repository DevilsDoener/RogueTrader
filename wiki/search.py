"""In-memory full-text search index over wiki sections.

Three things shape the ranking here, each chosen against the real corpus:

- **German queries used to return nothing at all.** The interface is German,
  the group speaks German, and the book is English -- "Stärke", "Waffe",
  "Schiff" and "Deckung" all scored zero hits. Diacritic folding does not help
  (only 35 of ~101,000 tokens carry an umlaut); a curated alias table does.
- **Term frequency saturates.** Raw counts let one very long section win
  almost any term it happens to repeat. True length normalisation
  (sqrt/log/BM25) over-corrects on this corpus: it promotes a statblock that
  mentions a word once over the rules section actually about it, and pushes
  the section literally titled "Profit Factor" off the top spot. Saturating
  the body count keeps the wins and avoids that.
- **Some chapters are navigation, not rules.** The page-number index and the
  foreword were taking top spots for ordinary words; their weight comes from
  ``wiki/manifest.py``.
"""
from __future__ import annotations

import bisect
import html
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Set, Tuple

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
    chapter_title: str
    section_id: str
    title: str
    snippet: str
    score: float


def tokenize(text: str) -> List[str]:
    """Casefolded Unicode word tokens."""
    return _TOKEN_RE.findall((text or "").casefold())


def _count_tokens(tokens: Iterable[str]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1
    return counts


def _saturate(count: int) -> float:
    """Diminishing returns for repeated body mentions."""
    if count <= 0:
        return 0.0
    return count * (TF_SATURATION + 1) / (count + TF_SATURATION)


def _make_snippet(plain_text: str, terms: Sequence[str]) -> str:
    casefolded = plain_text.casefold()
    match_start = None
    match_end = None
    for term in terms:
        index = casefolded.find(term)
        if index != -1 and (match_start is None or index < match_start):
            match_start = index
            match_end = index + len(term)

    if match_start is None:
        return html.escape(plain_text[:SNIPPET_MAX_LENGTH])

    # Keep the whole window (prefix + match + suffix) within
    # SNIPPET_MAX_LENGTH regardless of how long the matched term itself is,
    # rather than always padding by a fixed radius on each side.
    context_budget = max(0, SNIPPET_MAX_LENGTH - (match_end - match_start))
    radius = min(SNIPPET_RADIUS, context_budget // 2)
    start = max(0, match_start - radius)
    end = min(len(plain_text), match_end + radius)
    prefix = html.escape(plain_text[start:match_start])
    matched = html.escape(plain_text[match_start:match_end])
    suffix = html.escape(plain_text[match_end:end])
    return f"{prefix}<mark>{matched}</mark>{suffix}"


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

    def search(self, query: str, limit: int = 30) -> Tuple[SearchResult, ...]:
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
                if best_variant:
                    matched.add(best_variant)
            else:
                weighted = total * getattr(chapter, "search_weight", 1.0)
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
                    chapter_title=chapter.title,
                    section_id=section.id,
                    title=section.title,
                    snippet=_make_snippet(section.plain_text, matched or terms),
                    score=score,
                )
            )
        return tuple(results)


def build_search_index(chapters: Iterable[object]) -> SearchIndex:
    entries = []
    vocabulary: Set[str] = set()
    for chapter in chapters:
        for section in chapter.sections:
            title_tokens = _count_tokens(tokenize(section.title))
            body_tokens = _count_tokens(tokenize(section.plain_text))
            vocabulary.update(title_tokens)
            vocabulary.update(body_tokens)
            entries.append((chapter, section, title_tokens, body_tokens))
    return SearchIndex(entries, sorted(vocabulary))

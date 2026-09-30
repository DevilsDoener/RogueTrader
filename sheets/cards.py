"""Read-only character summary cards for the character list and the dashboard.

:func:`character_card` maps a :class:`~sheets.models.CharacterSheet` to the
plain dict that ``sheets/character_list.html`` (one card per character) and
``core/dashboard.html`` (one compact tile per character) render.
"""
from __future__ import annotations

from collections.abc import Collection

from .models import CharacterSheet

#: The nine characteristics shown on a card, in sheet order.
#: Labels are the book's English abbreviations.
CARD_CHARACTERISTICS: tuple[tuple[str, str], ...] = (
    ("WS", "c1_ws_value"),
    ("BS", "c1_bs_value"),
    ("S", "c1_s_value"),
    ("T", "c1_t_value"),
    ("Ag", "c1_ag_value"),
    ("Int", "c1_int_value"),
    ("Per", "c1_per_value"),
    ("WP", "c1_wp_value"),
    ("Fel", "c1_fel_value"),
)

#: Stat chips on a card: a stable key (for selecting chips in code), the
#: display label, then one field id for a single value or two (current,
#: total) for a "current / total" pair.
CARD_STATS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("wounds", "Wounds", ("c2_wounds_current", "c2_wounds_total")),
    ("fate", "Fate", ("c2_fate_points_current", "c2_fate_points_total")),
    ("xp_to_spend", "XP to Spend", ("c1_xp_to_spend",)),
    ("profit_factor", "Profit Factor", ("c1_profit_factor_current",)),
)

#: Placeholder for one missing half of a "current / total" chip.
_MISSING = "–"


def _card_value(values: dict, field_id: str) -> str:
    """One sheet value as display text; missing, empty or non-text is ``""``."""
    value = values.get(field_id)
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return ""
    return str(value).strip()


def character_card(
    character: CharacterSheet, *, stat_keys: Collection[str] | None = None
) -> dict:
    """Map a character to the plain dict one card renders.

    ``stat_keys`` restricts the stat chips to those :data:`CARD_STATS` keys;
    ``None`` keeps all of them.

    Read-only presentation: it never writes to ``character``. Every part is
    optional -- a fresh character with empty ``values`` yields a card with
    only its name, dates and actions.
    """
    values = character.values if isinstance(character.values, dict) else {}
    name = (character.display_name or "").strip() or "Unbenannter Charakter"

    career = _card_value(values, "c1_career_path")
    rank = _card_value(values, "c1_rank")
    rank_label = f"Rank {rank}" if rank else ""
    subtitle = [
        part
        for part in (career, rank_label, _card_value(values, "c1_home_world"))
        if part
    ]

    characteristics = [
        {"label": label, "value": _card_value(values, field_id)}
        for label, field_id in CARD_CHARACTERISTICS
    ]

    stats = []
    for key, label, field_ids in CARD_STATS:
        if stat_keys is not None and key not in stat_keys:
            continue
        parts = [_card_value(values, field_id) for field_id in field_ids]
        if not any(parts):
            continue
        stats.append(
            {"label": label, "value": " / ".join(part or _MISSING for part in parts)}
        )

    return {
        "pk": character.pk,
        "name": name,
        "initial": name[0].upper(),
        "subtitle": subtitle,
        # Career and rank alone, for the dashboard's compact tiles (no home world).
        "career_rank": [part for part in (career, rank_label) if part],
        "characteristics": characteristics,
        "has_characteristics": any(c["value"] for c in characteristics),
        "stats": stats,
        "updated_at": character.updated_at,
    }

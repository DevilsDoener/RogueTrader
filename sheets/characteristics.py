"""Field relationships shared by both character-sheet pages."""

CHARACTERISTICS = ("ws", "bs", "s", "t", "ag", "int", "per", "wp", "fel")
SLOTS = ("value", "adv_1", "adv_2", "adv_3", "adv_4")

#: Each shared field id mapped to the same field on the other page
#: (``3 - page`` flips page 1 <-> 2).
COUNTERPARTS = {
    f"c{page}_{characteristic}_{slot}": f"c{3 - page}_{characteristic}_{slot}"
    for page in (1, 2)
    for characteristic in CHARACTERISTICS
    for slot in SLOTS
}


def counterpart(field_id: str) -> str | None:
    """Return the same characteristic field on the other printed page."""
    return COUNTERPARTS.get(field_id)

"""Printed movement formulas, using Half Move as AB."""

SOURCE = "c2_movement_half_move"
FACTORS = {"c2_movement_full_move": 2, "c2_movement_charge": 3, "c2_movement_run": 6}

#: Longest Half Move accepted; mirrors the ``max_length`` of the
#: ``c2_movement_half_move`` schema field (pinned by a test), which is
#: validated before :func:`calculate` ever runs.
MAX_DIGITS = 6


def calculate(value):
    """Map a Half Move value to the derived Full Move / Charge / Run values.

    An empty value clears every derived field; anything but a whole number
    of at most :data:`MAX_DIGITS` digits raises ``ValueError``.
    """
    if value == "":
        return {field: "" for field in FACTORS}
    if (
        not isinstance(value, str)
        or not value.isascii()
        or not value.isdigit()
        or len(value) > MAX_DIGITS
    ):
        raise ValueError("Half Move must be a non-negative whole number")
    return {field: str(int(value) * factor) for field, factor in FACTORS.items()}

"""Printed movement formulas, using Half Move as AB."""
SOURCE = "c2_movement_half_move"
FACTORS = {"c2_movement_full_move": 2, "c2_movement_charge": 3, "c2_movement_run": 6}

def calculate(value):
    if value == "":
        return {field: "" for field in FACTORS}
    if not isinstance(value, str) or not value.isascii() or not value.isdigit() or len(value)>6:
        raise ValueError("Half Move must be a non-negative whole number")
    return {field: str(int(value)*factor) for field, factor in FACTORS.items()}

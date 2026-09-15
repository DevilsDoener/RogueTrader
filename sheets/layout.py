"""Compile editable section layouts to the flat schemas used by the portal.

Run ``python -m sheets.layout`` after editing layouts, or add ``--check`` to
verify generated files without writing. Coordinates are page percentages;
section origins translate fields without scaling them.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path

from sheets.schema import DATA_DIR, KNOWN_PAGE_IDS, SchemaError, SheetSchema

LAYOUT_DIR = Path(__file__).resolve().parent / "layouts"
FIELD_KEYS = {"id", "label", "kind", "x", "y", "width", "height", "max_length",
              "align", "text_style", "checkbox_style", "input_mode", "hit_padding", "read_only"}


def _object(value, allowed, context):
    if not isinstance(value, dict):
        raise SchemaError(f"{context}: expected an object")
    unknown = value.keys() - allowed
    if unknown:
        raise SchemaError(f"{context}: unknown keys {sorted(unknown)}")


def _number(value):
    try:
        result = Decimal(str(value))
        if not result.is_finite():
            raise ValueError("non-finite coordinate")
        return result
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise SchemaError(f"Invalid layout coordinate {value!r}") from exc


def compile_layout(payload: dict) -> dict:
    """Resolve slot defaults and section origins; validate the complete result."""
    _object(payload, {"page_id", "image", "templates", "sections"}, "layout")
    templates = payload.get("templates", {})
    if not isinstance(templates, dict):
        raise SchemaError("templates must be an object")
    for name, slots in templates.items():
        if not isinstance(slots, dict):
            raise SchemaError(f"template {name!r}: slots must be an object")
        for slot, defaults in slots.items():
            _object(defaults, FIELD_KEYS - {"id", "label"}, f"template {name}/{slot}")
    sections = payload.get("sections")
    if not isinstance(sections, list) or not sections:
        raise SchemaError("sections must be a non-empty list")
    fields = []
    section_ids = set()
    for section in sections:
        _object(section, {"id", "origin", "template", "fields"}, "section")
        section_id = section.get("id")
        if not isinstance(section_id, str) or not section_id.strip() or section_id in section_ids:
            raise SchemaError(f"Invalid or duplicate section id {section_id!r}")
        section_ids.add(section_id)
        origin = section.get("origin")
        if not isinstance(origin, list) or len(origin) != 2:
            raise SchemaError(f"{section_id}: origin must contain x and y")
        ox, oy = map(_number, origin)
        template_name = section.get("template")
        if template_name is not None and (
            not isinstance(template_name, str) or template_name not in templates
        ):
            raise SchemaError(f"{section_id}: unknown template {template_name!r}")
        slots = templates.get(template_name, {})
        entries = section.get("fields")
        if not isinstance(entries, list) or not entries:
            raise SchemaError(f"{section_id}: fields must be a non-empty list")
        for entry in entries:
            _object(entry, FIELD_KEYS | {"slot"}, f"{section_id} field")
            slot = entry.get("slot")
            if "slot" in entry and (not isinstance(slot, str) or slot not in slots):
                raise SchemaError(f"{section_id}: unknown slot {slot!r}")
            field = deepcopy(slots.get(slot, {}))
            field.update({key: value for key, value in entry.items() if key != "slot"})
            for axis, offset in (("x", ox), ("y", oy)):
                if axis not in field:
                    raise SchemaError(f"{section_id}: missing {axis}")
                field[axis] = float(_number(field[axis]) + offset)
            fields.append(field)
    result = {key: deepcopy(payload[key]) for key in ("page_id", "image") if key in payload}
    result["fields"] = fields
    SheetSchema.from_dict(result)
    return result


def build_layouts(source_dir: Path, output_dir: Path, *, check: bool = False) -> list[str]:
    """Validate every page before writing; return stale page IDs in check mode."""
    compiled = {}
    for page_id in KNOWN_PAGE_IDS:
        payload = json.loads((source_dir / f"{page_id}.json").read_text(encoding="utf-8"))
        result = compile_layout(payload)
        if result["page_id"] != page_id:
            raise SchemaError(f"{page_id}: source page_id does not match filename")
        compiled[page_id] = result
    stale = []
    for page_id, result in compiled.items():
        path = output_dir / f"{page_id}.json"
        if check:
            if not path.exists() or json.loads(path.read_text(encoding="utf-8")) != result:
                stale.append(page_id)
        else:
            output_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return stale


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        stale = build_layouts(LAYOUT_DIR, DATA_DIR, check=args.check)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Layout error: {exc}\n")
    if stale:
        print("Stale generated schemas: " + ", ".join(stale))
        print("Run: python -m sheets.layout")
        return 1
    print("Layouts are current." if args.check else "Generated all three sheet schemas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Render measured field outlines on the original artwork for visual review.

Run from the repository root: python tools/render_field_coverage.py
Red = existing text; blue = existing marking; green = corrected or added field
when --baseline points at an earlier directory of flat page JSON files.
The background images are never modified.
"""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
PAGES = ("character-page-1", "character-page-2", "ship-page")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "tmp/field-coverage")
    parser.add_argument("--baseline", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for page in PAGES:
        schema = json.loads((ROOT / f"sheets/data/{page}.json").read_text(encoding="utf-8"))
        old = {}
        if args.baseline:
            old = {f["id"]: f for f in json.loads((args.baseline / f"{page}.json").read_text(encoding="utf-8"))["fields"]}
        im = Image.open(ROOT / f"sheets/static/sheets/images/{page}.webp").convert("RGB")
        draw = ImageDraw.Draw(im)
        changed = 0
        for field in schema["fields"]:
            different = bool(args.baseline) and any(field.get(k) != old.get(field["id"], {}).get(k)
                for k in ("x", "y", "width", "height", "checkbox_style"))
            changed += different
            color = (0, 150, 40) if different else (20, 90, 220) if field["kind"] == "checkbox" else (220, 40, 40)
            rect = (round(field["x"] * im.width / 100), round(field["y"] * im.height / 100),
                    round((field["x"] + field["width"]) * im.width / 100) - 1,
                    round((field["y"] + field["height"]) * im.height / 100) - 1)
            if field.get("checkbox_style") == "pip":
                draw.ellipse(rect, outline=color, width=2)
            else:
                draw.rectangle(rect, outline=color, width=2)
        im.save(args.output / f"{page}-full.png")
        im.thumbnail((1400, 1800))
        im.save(args.output / f"{page}-overview.png")
        print(f"{page}: {len(schema['fields'])} fields, {changed} corrected/added")


if __name__ == "__main__":
    main()

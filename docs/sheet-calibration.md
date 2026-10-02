# Sheet calibration

How the sheet overlay is calibrated; the dated record of past calibration
rounds is in [sheet-calibration-record-2026-09.md](sheet-calibration-record-2026-09.md).
Field conventions live in
[charakterbogen-feld-anforderungen.md](charakterbogen-feld-anforderungen.md);
the layout format lives in [sheet-layout.md](sheet-layout.md).

> **Counts are not documented here.** The number of fields, checkboxes and
> measured rectangles changes with every calibration round. The authoritative
> sources are the generated schemas (`sheets/data/*.json`), the measured
> fixtures under `tests/fixtures/`, the SHA manifest, and the pinned
> expectations in `sheets/tests/test_schema.py`. Read them with the check
> commands below rather than trusting a number in prose. Dated entries in
> [sheet-calibration-record-2026-09.md](sheet-calibration-record-2026-09.md)
> keep the numbers that were true on their date.

## Check commands

```bash
.venv/Scripts/python.exe -m sheets.layout --check
```

```bash
.venv/Scripts/python.exe -m pytest -q sheets/tests
```

```bash
.venv/Scripts/python.exe -m pytest -q
```

The first verifies that `sheets/data/` is in sync with `sheets/layouts/`
(exit 1 = stale, 2 = invalid source). The second runs the schema contract,
layout and field-calibration tests that hold the current counts and geometry
pins. The third adds the browser and visual-regression checks.

## Layout authoring

Edit `sheets/layouts/*.json` and run `.venv/Scripts/python.exe -m sheets.layout`
to regenerate the flat schemas in `sheets/data/`. Section origins and reusable
slot defaults preserve the calibrated page coordinates. `--check` and the layout
tests catch stale generated files. See [sheet-layout.md](sheet-layout.md) for
coordinates, overrides and explicit text/checkbox presentation styles.

## Background sources

The two character pages come from the complete two-page standalone
`Rogue Trader Character Sheet.pdf`, rendered at 300 DPI with PDF annotations
hidden. This preserves the full decorative frame and prevents values stored in
the PDF form from being baked into the backgrounds. The ship page still comes
from page 403 of the core rulebook and is rotated to landscape.

Recreate the assets with `tools/extract_sheet_assets.py`, passing the core PDF
as `--pdf` and the standalone sheet as `--character-pdf`. The character images
must both be 2691 × 3435 pixels. Their layouts were transferred from the older
cropped scans by page-specific affine registration and then checked with full
coverage maps from `tools/render_field_coverage.py`.

## Rendering model (scaling)

Field coordinates are stored as percentages of the page (see `sheets/schema.py`)
and never change with this model. What changed (2026-08-26) is *how* the
calibrated layer is scaled to the screen:

- `.sheet-canvas` is pinned to the background image's intrinsic pixel size
  (`data-natural-width/height`, from the schema `image` block) and the whole
  layer -- background plus every field, text and checkbox -- is scaled by a
  single `transform: scale(var(--sheet-scale))`. `sheet-zoom.js` computes
  `scale = (available column width / natural width) * (zoom% / 100)`, sets it,
  and pins each `.sheet-page` to the resulting on-screen box (a transform does
  not change layout size). It also adds `.is-scaled` to `#sheet-viewer-root`.
- Because one transform moves the whole layer as a unit, fields cannot drift
  relative to the artwork on zoom or at any desktop width -- the previous model
  (fluid `%` positions + `cqw` font + a wrapper-width zoom) scaled the image and
  the fields through independent roundings, which visibly drifted the small
  checkboxes. The transform lives on `.sheet-canvas`, never on
  `.sheet-canvas-wrapper` (which stays `transform: none`).
- Before JS runs (or if it fails) the canvas falls back to a fluid
  `width:100%` + `aspect-ratio` render, so the sheet is always usable.
- `--sheet-scale` is the source of truth for the on-screen scale. e2e tests
  that need a rendered ("what the user sees") size multiply a computed length
  by it; `getBoundingClientRect` already returns post-transform pixels.

## Checkbox and text-line rectangles

The authoritative review fixture is `tests/fixtures/checkbox-rectangles.json`.
It records source-pixel `[left, top, right, bottom]` edges for every printed
marking surface, keyed by page and then by field ID -- so the per-page counts
and the field order are read from the fixture itself, never from prose.
`tests/fixtures/text-line-rectangles.json` does the same for the measured
printed text lines.

`tools/render_checkbox_contacts.py` reads the checkbox fixture and the three
original WebP assets, but never the production schemas. It creates full-page
overlays and original-pixel contact crops in `tests/visual/checkbox-contacts/`.
That folder is git-ignored output: it is not tracked, so regenerate it with the tool
whenever you need the images.
`tools/render_field_coverage.py` draws the full field coverage map over the
original artwork.

`tests/fixtures/checkbox-calibration-manifest.json` pins the SHA-256 digest
of the rectangle fixture and each original WebP. Both the schema test and
the contact renderer reject changed calibration inputs until they have been
reviewed and the manifest is deliberately updated. This makes the static
reference and its three source images auditable independently of schema
loading. The schema test compares every schema checkbox rect against that
reference at a **0 px per-edge tolerance** (tightened from 2 px on
2026-08-25).

> Note: HEAD stores `checkbox-rectangles.json` with LF, but the manifest
> records the digest of its **CRLF** form. `.gitattributes` pins that one
> file to `eol=crlf`, so every checkout (Windows with `core.autocrlf=true`,
> Linux CI) materialises the CRLF bytes the digest was computed over. Keep
> that attribute, and compute a new digest from the CRLF working-tree file,
> when re-touching the fixture. The WebP sources are binary and hashed as-is.

## Checked-state appearance

Specified in [charakterbogen-feld-anforderungen.md](charakterbogen-feld-anforderungen.md)
("Checkbox-Darstellung"); the checkmarks are `data:` SVGs and the native
checkbox chrome is suppressed in `sheets/static/sheets/sheet-viewer.css`.

## Typography

`tests/fixtures/font-calibration.json` records dark connected-component glyph
heights from isolated normal-label crops in the original artwork:

- character page 1, "Character Name": 26 px on the previous 2444 px scan
- character page 2, "Name": 26 px on the previous 2484 px scan
- ship page, "Name": 23 px on a 3238 px canvas

The median normalized visible-glyph size is 1.047% of canvas width. Testing
started at the requested `1cqw`, whose rendered Times New Roman glyphs were
about one third too small. The final shared CSS size is `1.53cqw`; browser
pixel-difference measurements put its visible glyph height within two
original pixels of the normalized source median on all three pages. The
shrink-to-fit of ship text fields on top of this base size is described in
[charakterbogen-feld-anforderungen.md](charakterbogen-feld-anforderungen.md).

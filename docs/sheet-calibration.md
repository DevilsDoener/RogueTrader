# Sheet calibration record

## Checkbox rectangles

The authoritative review fixture is
`tests/fixtures/checkbox-rectangles.json`. It records source-pixel
`[left, top, right, bottom]` edges for all 424 printed marking surfaces:

- character page 1: 351 (36 characteristic circles, 315 skill cells)
- character page 2: 36 characteristic circles
- ship page: 37 (9 capacity boxes, 8 weapon-type circles, 20 location circles)

`tools/render_checkbox_contacts.py` reads this fixture and the three original
WebP assets, but never the production schemas. It creates full-page overlays
and original-pixel contact crops in `tests/visual/checkbox-contacts/`.

`tests/fixtures/checkbox-calibration-manifest.json` pins the SHA-256 digest
of that rectangle fixture and each original WebP. Both the schema test and
the contact renderer reject changed calibration inputs until they have been
reviewed and the manifest is deliberately updated. This makes the static
reference and its three source images auditable independently of schema
loading.

The 2026-08-23 review checked every crop. Rectangles consistently cover the
free marking surface while leaving the printed circle or box border outside
the overlay. No group exceeded the two-pixel-per-edge tolerance, so this
review required no schema-coordinate corrections. Consequently there are no
corrected groups requiring separate before/after plates.

## Typography

`tests/fixtures/font-calibration.json` records dark connected-component glyph
heights from isolated normal-label crops in the original artwork:

- character page 1, “Character Name”: 26 px on a 2444 px canvas
- character page 2, “Name”: 26 px on a 2484 px canvas
- ship page, “Name”: 23 px on a 3238 px canvas

The median normalized visible-glyph size is 1.047% of canvas width. Testing
started at the requested `1cqw`, whose rendered Times New Roman glyphs were
about one third too small. The final shared CSS size is `1.53cqw`; browser
pixel-difference measurements put its visible glyph height within two
original pixels of the normalized source median on all three pages.

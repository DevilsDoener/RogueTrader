# Sheet calibration record

## Layout authoring (2026-09-14)

Edit `sheets/layouts/*.json` and run `python -m sheets.layout` to regenerate
the flat schemas in `sheets/data/`. Section origins and reusable slot defaults
preserve the calibrated page coordinates. `python -m sheets.layout --check`
and the layout tests catch stale generated files. See [sheet-layout.md](sheet-layout.md)
for coordinates, overrides and explicit text/checkbox presentation styles.

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

`sheets/tests/test_schema.py::test_all_424_checkbox_rectangles_match_independent_pixel_reference`
tightened this to a 0px-per-edge tolerance on 2026-08-25 (re-verified,
including all 72 "Adv. Taken" pips on both character pages): every schema
checkbox rect already matched the independent reference exactly, so no
coordinate changes were needed to pass at 0px.

Checked checkboxes render as a solid black inset block (`.sheet-checkbox:checked`
in `sheet-viewer.css`), not a golden tick -- same 70%-centered inset, same
position, only the fill changed.

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

## Characteristic value boxes

Owner convention (`docs/charakterbogen-feld-anforderungen.md`): every
characteristic value box spans the **full** printed box (like WS/BS), with
the value **centred** (`align: "center"`), rather than the older layout that
kept the field clear of the printed bonus circle in the box's left half.

- Character page 1 was widened to full box on 2026-08-26.
- Character page 2 followed on 2026-08-27: `c2_s_value` … `c2_fel_value`
  widths were measured from the printed box borders (detected right-edge
  columns at 34.52 / 44.85 / 55.19 / 65.54 / 75.85 / 86.21 / 96.56 % of the
  2484 px canvas) and extended to ~9.1–9.2 %, matching the WS/BS boxes, while
  keeping the existing left `x` (already at the box's left border).
  `sheets/tests/test_field_calibration.py::test_characteristic_value_field_covers_full_box`
  now guards this against re-narrowing.

## Page 2 field additions & value-box centring (2026-08-28)

Owner review of the page-2 coverage map added 8 text fields (167 → 175) so
every printed writable line carries a field (full-line length):

- **Weapon "Special Rules" — two lines each.** Every weapon block has two
  printed rule lines. The existing field sat on the lower (continuation) line
  only; the line beside the "Special Rules" label was empty. The single
  `c2_weapon_N_special_rules` was renamed to `…_special_rules_2` (continuation)
  and a new `…_special_rules_1` added on the label line, starting after the
  printed label and running to the block's right edge.
- **Corruption:** two continuation lines under "Malignancies" now have
  `c2_corruption_malignancies_2` / `…_3` (full column width, no label).
- **Insanity:** the continuation line under "Disorders" now has
  `c2_insanity_disorders_2`.

The value boxes with **no printed line** (page-2 movement ×6, lifting ×3,
fate ×2) were switched to `align: "center"` so their single value centres in
the box like the characteristics (they keep the normal font size; the
`2.6cqw` rule is scoped to `*_value` only). Page 2 now has 20 centred fields;
`_all_text_metrics` (e2e) excludes all `.sheet-text--center` fields, so the
shared bottom-anchored line-text contract now covers 202 character fields.

**Adv.-Taken pips levelled.** Owner asked for a flat pip row; the printed pips
drift ~8px down left-to-right, so all 36 page-2 `*_adv_*` were set to a common
`y=22.7357` (top=738/bottom=753 px, the drift-range midpoint, worst case ~4px
off a printed circle). Fixture `checkbox-rectangles.json` + manifest SHA and
the `c2_ws_adv_1` geometry pin were updated to match.

**Full-line coverage review (owner emphasis).** Every page-2 text field must
span the whole printed line — from just after its label to the line end /
section edge — not sit short. Audit found two groups starting too far right:
- **Wounds + Insanity** value fields began ~65–105px right of their labels,
  leaving the front of each printed line bare. Moved left to start just after
  the label (same right edge at x=2350px), covering the full line.
- **Armour TYPE** fields began ~30–64px after "TYPE:" and overshot the box's
  right border. Repositioned to start just after "TYPE:" and end at the box's
  inner right edge (full line within each location box).
Weapon sub-fields, gear/acquisitions/mutations, corruption and the added
continuation lines already reached their line ends. Pinned expectations in
`test_page_2_right_column_fields_start_after_their_printed_labels` updated.


## 2026-09-14: Ausrichtung an der tatsächlichen Vorlage

Die frühere Begradigung der Seite-2-Pips ist abgelöst: alle 36 Kreise folgen
nun ihren individuellen gedruckten Mittelpunkten. Die Originalbilder bleiben
unverändert. 28 runde Waffenmarkierungen des Schiffsbogens verwenden runde
Füllungen. Eckige Kästchen bleiben eckig.

Textfelder wurden anhand der sichtbaren Linienanfänge und -enden vermessen.
Gear und Acquisitions belegen jede gedruckte Zeile mit einem durchgehenden
Feld; die bisher ausgelassene erste Zeile wird genutzt und die bisher geteilte
letzte Zeile entfällt. Bestehende IDs und Werte bleiben erhalten.
44 Fertigkeitsnotizfelder, die erste Talentzeile und die fehlende vierte
Essential-Component-Zeile sind zusätzlich beschreibbar. Die neuen Felder werden
an die bestehende Schema-Reihenfolge angehängt, um deren Vertrag zu erhalten.

Feldzahlen: Charakterseite 1: 490, Charakterseite 2: 175, Schiff: 86.
Gemessene Textrechtecke: `tests/fixtures/text-line-rectangles.json`.
Checkbox-Referenz und SHA-Manifest sind auf die vermessenen Rechtecke aktualisiert.
`tools/render_field_coverage.py` erstellt Abdeckungskarten direkt über der
Originalgrafik; `tools/render_checkbox_contacts.py` erstellt 424 Detailausschnitte.

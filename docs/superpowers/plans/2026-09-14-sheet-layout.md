# Sheet Layout Implementation Plan

> Execute inline using executing-plans; the user authorized the recommended change.

**Goal:** Make the existing sheet layout maintainable without changing its appearance.
**Architecture:** Section/template authoring compiled to the existing flat schemas;
explicit field presentation passed through the existing Django viewer.
**Tech Stack:** Python, JSON, Django templates, existing CSS and pytest/Playwright.
**Spec:** `docs/superpowers/specs/2026-09-14-sheet-layout.md`

## Global Constraints

- Preserve current field IDs, order, geometry, labels, limits and all existing edits.
- Retain original images, zoom behavior, save API and desktop scope.
- No new runtime dependencies.

## Tasks

- [x] Add failing tests in `sheets/tests/test_layout.py` for section offsets,
  template overrides, invalid slots, duplicate IDs, invalid field presentation,
  and generation checks. Use a field at local (2,3) under origin (10,20) and
  assert its output is (12,23); template widths must survive unless overridden.
- [x] Add `sheets/layout.py`: `compile_layout(payload)` returns a flat validated
  schema; CLI `python -m sheets.layout --check` compares generated output.
  Reject malformed structures and unknown references before writing files.
- [x] Extend `FieldSpec` with explicit text/checkbox styles, validation and legacy
  alignment compatibility. Pass classes through `_sheet_viewer.html`; replace
  ID-pattern selectors in `sheet-viewer.css` with presentation classes.
- [x] Convert all three current schemas into `sheets/layouts/`, grouping contiguous
  logical areas and sharing weapon slot defaults with per-instance corrections.
  Generate flat schemas and compare every original field property before/after.
- [x] Run focused tests, full suite and same-browser pre/post visual comparisons;
  inspect differences rather than updating visual baselines to hide failures.
- [x] Document source editing, origin units, overrides, generation and verification
  in `docs/sheet-layout.md`; link from existing calibration documentation.

Baseline: 105 schema/calibration tests passed before changes. Work continues on
`improve/sheet-layout`, retaining the user's existing uncommitted calibration work.

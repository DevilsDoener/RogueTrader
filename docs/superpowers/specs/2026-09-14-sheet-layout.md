# Maintainable sheet layouts

Approved direction: preserve the original artwork and calibrated rendering while
introducing sections, reusable field templates and explicit presentation metadata.

Authoring files live in `sheets/layouts/`. Each section has a page-percentage origin;
its field coordinates are offsets in the same units, not percentages of the section.
Optional named templates supply slot defaults. Instances retain explicit persistent
IDs and labels, and may override geometry for irregular printed lines.

The compiler emits the existing flat `sheets/data/` format. Runtime code, calibration
tools and saving continue consuming that format. Compilation validates all pages
before writing anything; `--check` and tests detect stale generated files.

Field presentation uses `text_style: line|center|characteristic` and
`checkbox_style: square|pip`. No presentation depends on IDs. Legacy `align` is
accepted for existing callers; generated files carry compatible alignment too.

Constraints: no field ID, ordering, value limit, coordinate, artwork, zoom behavior,
permission or save API changes. Preserve existing uncommitted work. No new runtime
dependencies. Desktop scope stays unchanged. No visual editor in this iteration.

Verify with compiler failure cases, template overrides, source/output agreement,
existing schema/calibration tests and browser checks. Compare pre/post rendered
sheets using the same browser, zoom and filled data.

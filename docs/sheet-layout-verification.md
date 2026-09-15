# Layout verification — 2026-09-14

Compared against the working files at the start of this change, including the
user's previously uncommitted field calibrations (not the older Git HEAD).

- Baseline: 105 existing schema/calibration tests passed.
- Full suite after implementation: **393 passed**, 177.10 seconds.
  Command: `.venv/Scripts/python.exe -m pytest -q --basetemp=tmp/layout-20260914/pytest-full-1`.
- 126 test warnings identify the missing local `staticfiles/` directory; no test
  failures. Browser tests ran with local Chromium outside the process sandbox.
- `python -m sheets.layout --check`: all three generated schemas current.
- `git diff --check`: no whitespace errors.
- Independent read-only code review: no actionable findings.

## Data compatibility

Compared every original property of all 705 fields against the pre-change JSON:
IDs, kinds, ordering, coordinates, dimensions, labels, length limits and existing
alignment are unchanged. The new text/checkbox styles reproduce the old selectors.
No save API or database migration was introduced.

## Same-browser visual comparison

Chromium 151.0.7922.34, device scale factor 1, filled text and checked checkboxes:

| Pages | Widths | Zoom levels | Result |
|---|---|---|---|
| Character 1, Character 2, Ship | 1024, 1440 px | 30%, 50%, 100% | 18/18 pixel-identical |

The 1024 px comparisons use disabled/read-only fields; 1440 px uses editable
fields. Rendered input geometry, font sizes, alignment and checkbox images also
match exactly. This compares the old and new templates/CSS in the same browser,
with the existing zoom controller, original artwork and identical sample values.
It is evidence for these tested configurations, not a cross-browser guarantee.

Local comparison script, JSON results, and full-size before/after images are in
the ignored `tmp/layout-20260914/` directory. The regular suite additionally
covers server-backed editing, autosave, permissions, zoom and visual regression.

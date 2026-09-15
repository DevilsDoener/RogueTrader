---
name: project-conventions
description: Rogue Trader Portal conventions -- document precedence, Bruecken-Hybrid design system, desktop-only scope, permission model, sheet architecture, and file boundaries. Load this before touching templates, portal.css, sheet layouts, or permission-checking code.
user-invocable: false
---

# Rogue Trader Portal Conventions

Background knowledge for this repo. Not a workflow -- read it before making
design, template, sheet-layout, or permission-related changes so you don't
have to rediscover these decisions from old spec files each session.

## Document precedence

`AGENTS.md` in the repo root is the binding entry point and lists the full
precedence order. The short version: the owner's live instructions, then
`AGENTS.md`, then the active subject documents listed there, then the code,
schemas and tests. Everything under `docs/superpowers/specs/`,
`docs/superpowers/plans/`, `.superpowers/brainstorm/`, `docs/archive/` and
every dated report (`docs/*-2026-*.md`) is **history, not instruction** --
useful for "why", never authoritative for "what is true now".

## Visual identity: "Bruecken-Hybrid"

- Dark blue-green command-deck shell with restrained brass/gold accents,
  defined as CSS custom properties in `static/css/portal.css` (`--rt-bg`,
  `--rt-gold`, `--rt-danger`, etc.). Reuse these tokens -- never hardcode hex
  colors in templates or new CSS.
- A separate warm parchment surface (`--rt-parchment*`) is reserved for
  long-form wiki reading only (`wiki-article`). Don't apply it elsewhere.
- `portal.css` styles the shell (topbar, nav, dashboard, forms, tables, wiki
  article surface). It explicitly MUST NOT reach into
  `sheets/static/sheets/sheet-viewer.css` selectors (`.sheet-viewer-root`,
  `.sheet-canvas*`, `.sheet-field`, `.sheet-input`, `.sheet-checkbox`) --
  that's the pixel-calibrated character/ship sheet overlay and is
  intentionally an independent system. See the comment block at the top of
  `portal.css` before editing either file.
- Destructive actions (delete, deactivate) use `.button-danger` (combine
  with the base `.button` class: `class="button button-danger"`). Primary/
  safe actions use `.button-primary`. Note `button[type="submit"]` has a
  default gold style, so a danger submit button needs
  `button[type="submit"].button-danger` specificity to win -- see the
  existing rule in `portal.css` for the pattern.
- Django's default `form.as_p` / `non_field_errors` renders a plain
  `<ul class="errorlist">` -- this has a real style rule in `portal.css`,
  don't reintroduce unstyled error output.

## Desktop-only scope (deliberate, not an oversight)

The original design spec
(`docs/superpowers/specs/2026-08-16-rogue-trader-portal-design.md`) states:
"Die Webanwendung unterstuetzt Desktop-Browser ab 1024 px." `.app-shell` is
a fixed two-column grid with no responsive breakpoints by design. Do not
add mobile/responsive support to the portal shell without an explicit,
separate decision from the project owner -- past audits have flagged the
missing breakpoints as a bug when it is actually intentional scope.

## Sheet overlay architecture

- **Layout source of truth is `sheets/layouts/*.json`.** The flat files in
  `sheets/data/*.json` that the app, the calibration tests and the tools read
  are *generated*: `.venv/Scripts/python.exe -m sheets.layout` regenerates
  them, `-m sheets.layout --check` fails on stale output. A hand-edited
  `sheets/data/*.json` is overwritten on the next generate. Details and the
  section/template/coordinate model: `docs/sheet-layout.md`.
- **Field IDs are persistent data keys.** Move or restyle a field freely;
  never rename its `id` without a dedicated data migration.
- **Presentation is explicit metadata, not naming convention.**
  `text_style: line|center|characteristic` and `checkbox_style: square|pip`
  drive rendering; field names such as `_value` or `_adv_` no longer do.
  `input_mode: "numeric"`, `read_only: true` and `hit_padding` are the other
  schema-level presentation/behaviour flags.
- **One transform, no drift.** `sheet-zoom.js` pins `.sheet-canvas` to the
  artwork's intrinsic pixel size and applies a single
  `transform: scale(var(--sheet-scale))` combining fit-to-width with the
  user's zoom level. The transform lives on `.sheet-canvas`, never on
  `.sheet-canvas-wrapper`. Without JS the canvas falls back to a fluid
  `width:100%` render.
- **Derived and shared fields exist server-side.** The nine characteristics
  and their advance pips are shared across character pages 1 and 2
  (`docs/characteristic-sync.md`); Full Move / Charge / Run are computed and
  read-only (`sheets/movement.py`, `docs/movement-calculation.md`). Both are
  written atomically with their source field and rejected on direct API
  writes to the derived side.
- Owner-facing field and overlay conventions (line coverage, alignment, pip
  look, review workflow): `docs/charakterbogen-feld-anforderungen.md`.

## Permission model

- **Users** only ever see/mutate their own characters. Every query and
  mutation is scoped server-side to the owner's user ID.
- **Portal admins** can manage accounts (create/deactivate/reactivate/reset
  password) and view (never edit or delete) all characters in a read-only
  view. Admin write/delete endpoints only ever accept characters the admin
  themself owns -- admin status never grants write access to someone
  else's character.
- **Shared ship sheet(s)**: every authenticated user may view and
  field-edit the shared ship sheet(s). Every field mutation is written to
  an append-only `SheetChange` audit log (actor, timestamp, old/new value).
- Login is throttled per account+source address without revealing whether
  a username exists (`accounts/models.py: LoginThrottle`).
- No self-registration. The first admin is created via a management
  command; admin-created accounts get a temporary password and must change
  it on first login (`ForcePasswordChangeMiddleware`).

When touching `services.py`, `permissions.py`, or any view mixin under
`accounts/` or `sheets/`, preserve these boundaries exactly -- this is the
highest-consequence bug class in this app.

## Tests and file boundaries

- Run tests with the project venv from the repo root:
  `.venv/Scripts/python.exe -m pytest -q`. `pytest.ini` is already
  configured. Per-app suites live in `accounts/tests/`, `core/tests/`,
  `sheets/tests/` and `wiki/tests/`; Playwright e2e and visual-regression
  tests live under `tests/e2e/` and `tests/visual/`. See
  `.claude/skills/run-tests/SKILL.md`.
- `.env` is never edited by an agent (a `PreToolUse` hook denies it);
  `.env.example` is the documented template.
- `Notizbuch oeffnen.onetoc2` files (OneNote) and `graphify-out/` are
  foreign artifacts: never edit them and never stage them.

# Rogue Trader Portal

A self-hosted Django portal for a private Rogue Trader game group: a
read-only Markdown wiki of the rulebook, isolated per-user character
sheets, and one shared ship sheet, all rendered as pixel-aligned overlays
on the original character-sheet artwork.

## Documentation

Start at **[`AGENTS.md`](AGENTS.md)** — the binding entry point. It defines the
document precedence, who owns which subject, and the test duties. The active
subject documents are:

- **Sheet field & overlay conventions:** [`docs/charakterbogen-feld-anforderungen.md`](docs/charakterbogen-feld-anforderungen.md)
- **Layout format (sections, templates, coordinates):** [`docs/sheet-layout.md`](docs/sheet-layout.md)
- **Calibration, fixtures, manifest:** [`docs/sheet-calibration.md`](docs/sheet-calibration.md)
- **Shared characteristics:** [`docs/characteristic-sync.md`](docs/characteristic-sync.md)
- **Computed movement fields:** [`docs/movement-calculation.md`](docs/movement-calculation.md)
- **Open skill-checkbox mapping:** [`docs/checkbox-row-mapping.md`](docs/checkbox-row-mapping.md)
- **Operations (Proxmox deployment, backups, restores, account recovery):** [`docs/operations.md`](docs/operations.md)

The original design spec
([`docs/superpowers/specs/2026-08-16-rogue-trader-portal-design.md`](docs/superpowers/specs/2026-08-16-rogue-trader-portal-design.md))
and the implementation plans under `docs/superpowers/plans/` are **history**:
useful for *why* a decision was made, never authoritative for what is true now.

## Background assets

`sheets/static/sheets/images/character-page-1.webp`,
`character-page-2.webp`, and `ship-page.webp` are extracted directly from
the user's source character-sheet PDF (pages 401 and 402 for the two
character-sheet pages, page 403 for the ship sheet). The ship page is
rotated to landscape for display; the two character pages keep their
original portrait orientation. No other artwork on any page is interactive.

The editable layout source is `sheets/layouts/*.json`;
`.venv/Scripts/python.exe -m sheets.layout` compiles it into the flat
`sheets/data/*.json` schemas the application, the calibration tests and the
tools read. Those schemas define, per page, the stable field IDs, the
`text`/`checkbox` types, each field's position and size as percentages of that
page's original image, and the explicit presentation metadata — so overlays
stay pixel-aligned with the artwork at every zoom level and canvas width. The
schemas and the pinned expectations in `sheets/tests/` are the only source of
truth for how many fields exist and where they sit; never a number in prose.

Field IDs are persistent data keys and stay in their declared order. Moving or
restyling a field is free; renaming its `id` requires a dedicated data
migration.

## Sheet viewer behaviour

- **Zoom:** the toolbar offers 30 %–100 % in 10 % steps (default 100 %,
  remembered per browser). The level is combined with fit-to-column-width into
  a single `transform: scale()` on `.sheet-canvas`, so the artwork and every
  field move as one unit and cannot drift apart. There is no pan mode; pages
  scroll with the document. Without JavaScript the canvas falls back to a
  fluid full-width render.
- **Checked state:** square checkboxes draw a black X, advance pips and the
  ship's round weapon markings draw a filled black circle. An unchecked
  control draws nothing — the printed sheet looks untouched.
- **Shared characteristics:** the nine characteristic values and their advance
  pips are one field across character pages 1 and 2. An edit shows up on the
  other page immediately and is saved atomically with the same field version.
- **Computed movement:** Half Move is the only input; Full Move (×2),
  Charge (×3) and Run (×6) are read-only, previewed live in the browser and
  written server-side in one transaction. Direct API writes to the results are
  rejected.
- **Numeric fields:** the ship's resource/capacity fields and the character
  values accept only empty input or non-negative integers.
- **Concurrency:** every field edit is versioned; a conflicting edit opens the
  conflict panel instead of overwriting. Every ship-sheet mutation is recorded
  in an append-only audit log.

## Local setup

```powershell
py -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python -m playwright install chromium
.\.venv\Scripts\python manage.py migrate
.\.venv\Scripts\python manage.py bootstrap_admin --username <admin-username>
.\.venv\Scripts\python manage.py runserver
```

These direct `manage.py` commands do not read `.env` — it is consumed by
Docker Compose only. No extra environment variable is needed for the wiki:
`WIKI_CONTENT_ROOT` defaults to this checkout's own `content/` directory, and
the Compose deployment overrides it to the read-only mount point. For a
Compose deployment, copy `.env.example` to `.env`, edit its deployment
values, and follow [`docs/operations.md`](docs/operations.md).

The wiki reads its chapters from `WIKI_CONTENT_ROOT` (an allow-listed set
of `NN-Chapter-Name.md` files under `content/`, see
`WIKI_CONTENT_ALLOWLIST` in `.env.example`) rather than from any database
table. In the Docker deployment only that same `content/` directory (never
the whole repository) is mounted read-only into the container, at
`/content/wiki` (see `compose.yaml` and `docs/operations.md`).

The whole corpus is parsed once at process start and held in memory, so
**editing a Markdown file under `content/` requires a server restart** to
take effect — `runserver`'s autoreloader watches Python files only.

Every account is admin-created (`bootstrap_admin` creates the first one);
there is no self-registration. A newly-created account gets a temporary
password and must set its own password on first login.

## Running the acceptance suite

All commands below assume the project's own `.venv`
(`.\.venv\Scripts\python`) and must be run from Git Bash or plain
PowerShell -- not WSL, which cannot resolve this checkout's git worktree
layout.

```powershell
# Full automated suite: unit, integration, end-to-end (Playwright/Chromium),
# and deterministic visual-regression tests.
.\.venv\Scripts\python -m pytest -q

# Single app while iterating (accounts | core | sheets | wiki).
.\.venv\Scripts\python -m pytest -q sheets/tests

# Generated schemas are in sync with the layout sources.
.\.venv\Scripts\python -m sheets.layout --check

# Production-shaped Django deployment check (run with DJANGO_DEBUG=false
# and the other production env vars from .env.example set).
.\.venv\Scripts\python manage.py check --deploy

# Validate the Compose file (env interpolation, the fail-fast
# DJANGO_ALLOWED_HOSTS contract, volumes/ports) without needing a Docker
# daemon.
docker compose config

# Full clean-container round trip (requires a running Docker daemon).
docker compose build --no-cache
docker compose up -d
docker compose exec portal python manage.py migrate --check
docker compose exec portal python manage.py check --deploy
Invoke-RestMethod http://127.0.0.1:8000/healthz/
docker compose logs --no-color portal
```

Per-app suites live in `accounts/tests/`, `core/tests/`, `sheets/tests/` and
`wiki/tests/`; the browser tests live in `tests/e2e/` and their captured
baselines in `tests/visual/`. Run the app you touched while iterating and the
full suite before a build, a push, or calling the work done.

`tests/e2e/test_complete_journey.py` drives one continuous, real end-to-end
session (bootstrap admin, create and force-change two users' passwords,
private characters, mutual invisibility, read-only admin visibility,
shared-ship editing and conflict resolution, wiki search, and persistence
across a simulated restart) against a real headless Chromium browser and a
real HTTP server. `tests/e2e/test_visual_regression.py` compares each
sheet page's rendered canvas against its extracted background image
(`tests/visual/*.png` are the latest captured renders) and checks that
every schema field -- checkboxes specifically included -- stays correctly
positioned inside the scaled canvas at the minimum and wide supported
desktop sizes. `tests/e2e/test_sheet_zoom.py` covers the zoom controller.

## Manual acceptance checklist

> ### ⚠️ MUST DO FIRST: re-verify the checkboxes by eye
>
> **Before this portal is used for a real game session, a human must sit
> down with both character pages and the ship page and check every single
> printed checkbox and marking circle against its overlay control.**
>
> This is not routine caution — checkbox rendering broke **four separate
> times** during development, each time in a different way, and each time
> it was invisible to the test suite that was green at that moment:
>
> 1. **Coordinate calibration** — whole regions of checkboxes were
>    mapped to the wrong printed rows because of a wrong row-pitch constant.
>    Two rounds of fixes were needed. All structural tests passed throughout.
> 2. **Global CSS leak** — a generic `input[type=checkbox]` rule in
>    the new site-wide stylesheet resized every sheet checkbox, breaking the
>    pixel geometry.
> 3. **Idle appearance** — unchecked checkboxes rendered as large
>    solid grey squares covering the printed artwork, because Chromium's
>    native unchecked control fills a box stretched to the schema
>    rectangle's size.
> 4. **Missing coverage** — the *checked* state and the
>    admin read-only view had no visual test at all, on any page.
>
> All four are fixed and now have automated coverage. But the pattern is
> clear: this is the part of the system where "the tests are green" has
> repeatedly failed to mean "it looks right on the page". The automated
> checks verify position and idle appearance; they cannot tell you that a
> control sits on *the checkbox a player expects to tick*.
>
> **What to actually check**, per page (1, 2, ship), at representative wide
> and narrow content widths and at several zoom levels while scrolling the
> document vertically:
> - Every printed circle/square has exactly one control on it — none missed,
>   none doubled up, none shifted to a neighbour.
> - Ticking a box marks *that* box, not the one above/below/beside it.
> - An unticked box adds no visible chrome — the printed artwork looks
>   exactly as it does with the overlay disabled.
> - The dense repeating grids deserve the most scrutiny: the Skills table's
>   Basic/Trained/+10%/+20% columns, the 4-pip "Adv. Taken" rows under each
>   characteristic, and the ship's weapon-table location circles
>   (Dorsal/Prow/Keel/Port/Starboard). These were all placed from measured
>   grid pitches — one wrong constant silently shifts an entire block.
>
> Note that some persistent skill-checkbox IDs are known to name the wrong
> printed row; that is a deliberate open data question, not a geometry bug.
> See [`docs/checkbox-row-mapping.md`](docs/checkbox-row-mapping.md) before
> reporting it.

The acceptance checklist has three explicit categories. Items marked
**automated** are covered by the Playwright suite above. Items marked
**verified-host** were rehearsed on a real Docker host. Items marked **manual**
still require physical-device acceptance by a person.

1. **[automated]** Bootstrap an admin and create two normal accounts.
2. **[automated]** Create multiple characters on both accounts and confirm
   mutual invisibility.
3. **[automated]** As the admin, view every character read-only and
   confirm mutation/delete attempts on someone else's character fail.
4. **[automated]** Edit the shared ship from both accounts; confirm the
   audit history and the same-field conflict dialog.
5. **[automated]** Browse a wiki chapter's section navigation and confirm
   search finds it.
6. **[manual, desktop acceptance]** In supported desktop browsers at widths
   from 1024 px, and across the 30–100 % zoom range: confirm every
   printed line, value box, and checkbox/marking circle has exactly one
   aligned control sitting on it, that every other mark on the page
   (borders, decorative art, static labels) is inert (does not respond to
   click or focus), that the ship page reads upright in landscape, and
   that normal vertical scrolling feels natural and no page creates
   horizontal document overflow.
7. **[verified-host, 2026-08-23]** Clean-container persistence rehearsal: an
   isolated Compose project with a disposable volume was rebuilt from a
   clean image and forcibly recreated; account, character, and ship data
   remained intact. On a fresh volume, follow the documented explicit
   `manage.py migrate` step after first boot/deploy before using the app.
8. **[verified-host, 2026-08-23]** Backup-and-restore rehearsal: against
   disposable test data, `scripts/backup.ps1` created a manifest and passed
   SQLite integrity checking; `scripts/restore.ps1` restored the expected
   pre-backup state and the application data passed integrity checking.

The 2026-08-23 rehearsal used an isolated Compose project and disposable
volume; the existing port-8000 container and its data were not touched.
Production deployments still require the documented explicit migration step
after first boot/deploy.

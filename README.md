# Rogue Trader Portal

A self-hosted Django portal for a private Rogue Trader game group: a
read-only Markdown wiki of the rulebook, isolated per-user character
sheets, and one shared ship sheet, all rendered as pixel-aligned overlays
on the original character-sheet artwork.

- **Design spec:** [`docs/superpowers/specs/2026-08-16-rogue-trader-portal-design.md`](docs/superpowers/specs/2026-08-16-rogue-trader-portal-design.md)
- **Implementation plan:** [`docs/superpowers/plans/2026-08-16-rogue-trader-portal.md`](docs/superpowers/plans/2026-08-16-rogue-trader-portal.md)
- **Operations guide (Proxmox deployment, backups, restores, account recovery):** [`docs/operations.md`](docs/operations.md)

## Background assets

`sheets/static/sheets/images/character-page-1.webp`,
`character-page-2.webp`, and `ship-page.webp` are extracted directly from
the user's source character-sheet PDF (pages 401 and 402 for the two
character-sheet pages, page 403 for the ship sheet). The ship page is
rotated to landscape for display; the two character pages keep their
original portrait orientation. `sheets/data/*.json` defines, per page, the
stable field IDs, `text`/`checkbox` types, and each field's position/size
as percentages of that page's original image so overlays stay
pixel-aligned with the artwork at every zoom level. No other artwork on
any page is interactive.

## Local setup

```powershell
py -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python -m playwright install chromium
Copy-Item .env.example .env   # then edit values for your machine
.\.venv\Scripts\python manage.py migrate
.\.venv\Scripts\python manage.py bootstrap_admin --username <admin-username>
.\.venv\Scripts\python manage.py runserver
```

The wiki reads its chapters from `WIKI_CONTENT_ROOT` (an allow-listed set
of the repository's own `NN-Chapter-Name.md` files, see
`WIKI_CONTENT_ALLOWLIST` in `.env.example`) rather than from any database
table, so pointing `WIKI_CONTENT_ROOT` at a checkout of this repository is
enough for local development. In the Docker deployment this directory is
instead mounted read-only into the container (see `compose.yaml` and
`docs/operations.md`).

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
.\.venv\Scripts\python -m pytest -v

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
docker compose exec web python manage.py migrate --check
docker compose exec web python manage.py check --deploy
Invoke-RestMethod http://127.0.0.1:8000/healthz/
docker compose logs --no-color web
```

`tests/e2e/test_complete_journey.py` drives one continuous, real end-to-end
session (bootstrap admin, create and force-change two users' passwords,
private characters, mutual invisibility, read-only admin visibility,
shared-ship editing and conflict resolution, wiki search, and persistence
across a simulated restart) against a real headless Chromium browser and a
real HTTP server. `tests/e2e/test_visual_regression.py` compares each
sheet page's rendered canvas against its extracted background image
(`tests/visual/*.png` are the latest captured renders) and checks that
every schema field -- checkboxes specifically included -- stays correctly
positioned inside the canvas at 50%/100%/150%/300% zoom and at mobile
fit-width.

## Manual acceptance checklist

Some of the design spec's acceptance criteria need a human (and, for two
items, a physical smartphone) rather than a browser automation script.
Items marked **automated** are already covered by the Playwright suite
above and are listed here only for completeness against the spec's
checklist (`docs/superpowers/specs/2026-08-16-rogue-trader-portal-design.md`,
"Tests und Abnahme"); items marked **manual** genuinely require a person.

1. **[automated]** Bootstrap an admin and create two normal accounts.
2. **[automated]** Create multiple characters on both accounts and confirm
   mutual invisibility.
3. **[automated]** As the admin, view every character read-only and
   confirm mutation/delete attempts on someone else's character fail.
4. **[automated]** Edit the shared ship from both accounts; confirm the
   audit history and the same-field conflict dialog.
5. **[automated]** Browse a wiki chapter's section navigation and confirm
   search finds it.
6. **[manual, physical device recommended]** On an actual desktop browser
   and an actual smartphone (not just a resized desktop window -- real
   touch input and real device pixel ratio matter here): confirm every
   printed line, value box, and checkbox/marking circle has exactly one
   aligned control sitting on it, that every other mark on the page
   (borders, decorative art, static labels) is inert (does not respond to
   click/tap/focus), that the ship page reads upright in landscape, and
   that pinch-zoom/pan feels natural rather than janky.
7. **[manual]** Recreate the container from a clean image
   (`docker compose build --no-cache && docker compose up -d`) and confirm
   accounts, character data, and ship data all survived -- this
   specifically exercises the real Docker/SQLite-volume persistence path
   that an in-process test cannot.
8. **[manual]** Run one backup-and-restore rehearsal against disposable
   test data with `scripts/backup.ps1` / `scripts/restore.ps1` (see
   `docs/operations.md`, sections 7-8) and confirm the application starts
   normally against the restored database.

Items 7 and 8 need a real Docker daemon, which was not available in the
environment this suite was last verified in -- see the operations guide
and the Task 11 acceptance report for exactly what was and wasn't
verified there.

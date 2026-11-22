---
name: deploy
description: Rebuild the portal Docker image, back up the live container database, run migrations with the new image, restart the container and verify it. Use /deploy after the full test suite is green.
disable-model-invocation: true
---

# Deploy

Brings the running portal (`docker compose`, service `portal`, container
`wissensdatenbank-portal-1`, http://127.0.0.1:8000) up to the checked-out
code. Its data lives in the Docker volume `portal-data`, not in
`data/db.sqlite3` (that is only the dev database). Run every step from the
repo root, in this order, and stop at the first failure.

## Before

- The full suite must be green (`AGENTS.md`, "Tests"): build and push need it.
  If it has not run since the last code change, run it first (see the
  `run-tests` skill) and do not deploy on a red run.
- `.env` must exist (never edit it; `docker compose` reads it).

## Steps

1. **Build** the image:

   ```bash
   docker compose build
   ```

   It must end with `Image rogue-trader-portal Built`. `collectstatic` runs
   inside the build; a missing static file fails here.

2. **Back up** the live database (online backup, the portal keeps running).
   The destination folder must already exist:

   ```powershell
   powershell -NoProfile -File scripts/backup.ps1 -Destination "<repo>\backups"
   ```

   It must report `Integrity: ok`. Note the backup file name for the report.

3. **Migrate** with the *new* image before switching over, so the new code
   never meets an unmigrated database (the old container keeps serving
   meanwhile; added columns with defaults do not disturb it):

   ```bash
   docker compose run --rm -T portal python manage.py migrate
   ```

4. **Restart** on the new image (the volume stays):

   ```bash
   docker compose up -d
   ```

5. **Verify**:
   - container health becomes `healthy`
     (`docker inspect -f '{{.State.Health.Status}}' wissensdatenbank-portal-1`,
     poll a few times, it takes ~10 s);
   - `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/healthz/` is `200`;
   - `docker compose exec -T portal python manage.py migrate --check` exits 0;
   - `docker compose logs --no-color --since 2m portal` shows no `Error`/`Traceback`.

## Report

Say what was deployed (latest commit), the backup file, which migrations ran
(or "none"), and the verification results. Say explicitly what was *not*
checked, e.g. that new pages were not clicked through in the browser.

## If something fails

- Build fails: nothing changed on the running portal; fix and rerun.
- Migration fails: the old container is still running on the old schema;
  do not run `up -d`. Report the error. Restore only on the owner's request
  (`scripts/restore.ps1`, `docs/operations.md`).
- Unhealthy after restart: show `docker compose logs portal`; rolling back
  means rebuilding the previous commit, and restoring the backup if a
  migration already ran -- ask the owner first.

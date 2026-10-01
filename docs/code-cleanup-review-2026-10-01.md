# Code cleanup: final review, 2026-10-01

Historical verification record for `chore/code-cleanup`, based on `main`
at `c0d8e42`. This records the checks performed on that branch; it is not an
instruction or a substitute for the active project documents.

## Scope and review

The cleanup consolidates character-card construction, sheet-view rendering,
derived-field writes, wiki metadata and lookups, browser helpers, test fixtures,
account-management queries and login-throttle code. It removes unused code,
obsolete tooling and redundant tests, corrects stale documentation, and separates
development dependencies from the runtime lock used by the Docker image.

Two fresh read-only reviews covered the application/authentication/sheet logic
and the wiki/browser code. One regression was identified: the chapter reader
had stopped writing the `ts` timestamp in its `rt-wiki-recent` entries. The
timestamp and its documented storage shape were restored. The existing browser
test now verifies a positive integer timestamp; it failed with `KeyError: 'ts'`
before the fix and passed afterward. The reviewer confirmed the fix and reported
no other actionable findings in that scope. The application reviewer reported
no actionable findings in its scope.

## Verification

- Full suite: `700 passed in 478.75s` with a fresh temporary test directory.
- Timestamp regression: the targeted browser test passed after the fix.
- Separate visual check: the dashboard, characters, library, search, chapter and
  Auspex palette were rendered with an isolated test database. Screenshots are
  local outputs under `tmp/codex-cleanup-preview/`, not committed assets.
- `python -m sheets.layout --check`: layouts are current.
- `python manage.py check`: no issues.
- `python manage.py makemigrations --check --dry-run`: no changes detected.
- `git diff --check`: no whitespace errors in the implementation changes.
- Docker image build succeeded, including production-mode `collectstatic`.
- Runtime checks inside the image used a temporary copy of the existing
  database. Dashboard, characters, library, search, chapter, administrative
  account/character lists, both character sheets, the ship sheet and suggest
  JSON all returned HTTP 200.
- The recreated Compose container became healthy; the host login URL returned
  HTTP 200.

The first sandboxed test attempt could not access the previous session's
temporary pytest directory. The complete successful run used a fresh directory
and permission to run local Chromium outside the sandbox. No application change
was needed for that environment issue.

## Data and boundaries

No changes to `content/`, applied migrations, sheet layout/data JSON, calibrated
sheet CSS, or calibration fixtures were included. Test-generated visual PNGs
were restored after the run. The owner's `AGENTS.md`, `.agents/`, `.codex/` and
`.env` were left untouched.

Before and after recreating the portal container, read-only SQLite checks
confirmed integrity and the same data fingerprint across the user, character,
ship and sheet-change tables:

`69144ba13e6ccb8504d736d583638c51eddec55b818c93a83beb27d7f755eeb3`

There were two characters, one ship, 483 sheet-change rows and one account.
Production-data checks and runtime smoke tests did not alter those rows.

Items requiring a behavior or compatibility decision were retained: tracked
visual outputs, permission helpers, search-response keys, whitespace-query
semantics, the mirrored client movement factors, login-throttle cleanup and
legacy password verifiers. No such redesign is part of this cleanup.

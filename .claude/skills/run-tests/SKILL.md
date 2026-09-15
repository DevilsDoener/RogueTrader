---
name: run-tests
description: Run the Django test suite via the project's venv Python (pytest + pytest-django). Use /run-tests, optionally with pytest args, e.g. /run-tests sheets/tests -k character
disable-model-invocation: true
---

# Run Tests

Runs the project's test suite with the correct interpreter -- no need to
hunt for the venv path each time.

```bash
.venv/Scripts/python.exe -m pytest -q $ARGUMENTS
```

If `$ARGUMENTS` is empty, run the full suite:

```bash
.venv/Scripts/python.exe -m pytest -q
```

## Test groups

| Group | Path |
|---|---|
| Accounts (auth, user admin, audit) | `accounts/tests` |
| Core (dashboard, health, mixins) | `core/tests` |
| Sheets (schema, layout, calibration, patch service) | `sheets/tests` |
| Wiki (Markdown loading, search) | `wiki/tests` |
| Browser end-to-end (Playwright/Chromium) | `tests/e2e` |
| Visual regression | `tests/e2e/test_visual_regression.py` |

The full run (no path argument) includes every group above, browser tests
included. While iterating, run just the app you touched; run the full suite
before a build, a push, and before claiming the work is done.

## Notes

- `pytest.ini` already sets `DJANGO_SETTINGS_MODULE` and excludes `.git`,
  `.venv`, `.worktrees`, `tmp/` and pytest cache dirs from collection.
- Playwright needs its browser once per checkout:
  `.venv/Scripts/python.exe -m playwright install chromium`.
- After a layout change also run
  `.venv/Scripts/python.exe -m sheets.layout --check` -- it writes nothing
  and exits 1 on stale generated files, 2 on an invalid source.
- A `PostToolUse` hook already runs the affected app's tests after any
  Python edit under `accounts/`, `core/`, `sheets/` or `wiki/`.
- Run from Git Bash or plain PowerShell, not WSL -- WSL cannot resolve this
  checkout's git worktree layout.

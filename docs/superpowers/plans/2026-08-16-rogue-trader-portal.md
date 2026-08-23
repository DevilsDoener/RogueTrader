# Rogue-Trader Portal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Dockerized, publicly deployable Django portal that serves the existing Markdown knowledge base, isolates private two-page character sheets per user, and provides one shared editable starship sheet using pixel-aligned overlays on the original PDF artwork.

**Architecture:** A server-rendered Django monolith owns authentication, authorization, Markdown indexing, SQLite persistence, and field-level concurrency. Character and ship values are stored as validated JSON keyed by a versioned field schema; browser inputs are absolutely positioned over pre-rendered page images with percentage coordinates. Docker Compose runs one Gunicorn application container behind an external HTTPS reverse proxy.

**Tech Stack:** Python 3.13, Django 5.2 LTS, SQLite, Gunicorn, HTMX, minimal vanilla JavaScript, markdown-it-py, Bleach, Pillow, pytest/pytest-django, and Playwright.

## Global Constraints

- Normal users can view and mutate only their own characters.
- Portal admins can manage accounts and view every character, but cannot mutate or delete characters owned by another user.
- Every authenticated user can view and mutate the shared ship sheet.
- There is no public registration or anonymous wiki access.
- The first release creates exactly one shared ship while retaining a multi-ship database model.
- PDF pages 401 and 402 are the character sheet backgrounds; page 403 is the ship background and must be normalized to landscape orientation.
- Only printed text lines/value boxes and printed checkboxes/marking circles are interactive. All other original artwork remains inert.
- The application supports desktop browsers from 1024 px; sheet geometry never reflows.
- Markdown files remain read-only source files and are reindexed after a container restart.
- Raw HTML from Markdown is never executed.
- Use field-level optimistic concurrency; never silently overwrite a same-field conflict.
- Do not log passwords, sessions, or sheet content.
- Initialize Git before the first commit because the current workspace is not yet a repository.

---

## Planned File Structure

```text
.
├── manage.py
├── pyproject.toml
├── requirements.in
├── requirements.txt
├── pytest.ini
├── Dockerfile
├── compose.yaml
├── .dockerignore
├── .env.example
├── config/
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── core/
│   ├── views.py
│   ├── urls.py
│   ├── templates/core/dashboard.html
│   └── tests/test_health.py
├── accounts/
│   ├── models.py
│   ├── forms.py
│   ├── services.py
│   ├── middleware.py
│   ├── views.py
│   ├── urls.py
│   ├── management/commands/bootstrap_admin.py
│   ├── templates/accounts/
│   └── tests/
├── wiki/
│   ├── content.py
│   ├── markdown.py
│   ├── search.py
│   ├── views.py
│   ├── urls.py
│   ├── templates/wiki/
│   └── tests/
├── sheets/
│   ├── models.py
│   ├── schema.py
│   ├── services.py
│   ├── permissions.py
│   ├── views.py
│   ├── urls.py
│   ├── data/character-page-1.json
│   ├── data/character-page-2.json
│   ├── data/ship-page.json
│   ├── static/sheets/images/
│   ├── static/sheets/sheet-viewer.css
│   ├── static/sheets/sheet-viewer.js
│   ├── templates/sheets/
│   └── tests/
├── static/css/portal.css
├── templates/base.html
├── tools/extract_sheet_assets.py
├── tools/sheet_mapper.html
├── tests/e2e/
└── docs/operations.md
```

Each Django app owns its models, routes, templates, and tests. `sheets/schema.py` is the sole reader and validator of coordinate schemas; `sheets/services.py` is the sole mutation boundary for field values. Browser code never decides authorization.

---

### Task 1: Project Foundation, Dependency Lock, and Container Health

**Files:**
- Create: `.gitignore`, `.dockerignore`, `pyproject.toml`, `requirements.in`, `requirements.txt`, `pytest.ini`
- Create: `manage.py`, `config/settings.py`, `config/urls.py`, `config/wsgi.py`
- Create: `accounts/__init__.py`, `accounts/apps.py`, `accounts/models.py`
- Create: `core/views.py`, `core/urls.py`, `core/tests/test_health.py`
- Create: `Dockerfile`, `compose.yaml`, `.env.example`

**Interfaces:**
- Produces: `GET /healthz/ -> 200 {"status":"ok","database":"ok"}` when SQLite is reachable.
- Produces: settings `WIKI_CONTENT_ROOT`, `WIKI_CONTENT_ALLOWLIST`, `SHEET_SOURCE_PDF`, `PUBLIC_BASE_URL`, and `APP_BIND_ADDRESS`.

- [ ] **Step 1: Initialize version control and the minimal Django package layout**

Run:

```powershell
git init
python -m venv .venv
.\.venv\Scripts\python -m pip install "Django>=5.2,<5.3" pytest pytest-django pip-tools
.\.venv\Scripts\django-admin startproject config .
.\.venv\Scripts\python manage.py startapp core
.\.venv\Scripts\python manage.py startapp accounts
```

Preserve the existing Markdown and `docs/` files. Add `.venv/`, `.env`, `data/`, `.pytest_cache/`, `__pycache__/`, `tmp/`, and `.superpowers/` to `.gitignore`. Define the initial custom-user boundary before any migration:

```python
# accounts/models.py
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    pass
```

Add `accounts` to `INSTALLED_APPS` and set `AUTH_USER_MODEL = "accounts.User"` immediately.

- [ ] **Step 2: Write the failing health tests**

```python
# core/tests/test_health.py
import pytest
from django.db import connection
from django.test import Client

@pytest.mark.django_db
def test_health_reports_process_and_database_ready(client: Client):
    response = client.get("/healthz/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}

@pytest.mark.django_db
def test_health_does_not_require_login(client: Client):
    assert client.get("/healthz/").status_code == 200
```

- [ ] **Step 3: Run the focused test and confirm the missing route failure**

Run: `.\.venv\Scripts\python -m pytest core/tests/test_health.py -v`

Expected: FAIL with a 404 for `/healthz/`.

- [ ] **Step 4: Implement the health endpoint and environment-backed settings**

```python
# core/views.py
from django.db import connection
from django.http import JsonResponse

def health(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    return JsonResponse({"status": "ok", "database": "ok"})
```

Wire `core.urls` into `config.urls`. In `config/settings.py`, read secrets from `os.environ`, use `/data/db.sqlite3` in containers, and default local development to `BASE_DIR / "data" / "db.sqlite3"`.

- [ ] **Step 5: Lock dependencies and create the production container**

`requirements.in` must contain the bounded direct dependencies:

```text
Django>=5.2,<5.3
argon2-cffi>=23,<26
bleach>=6,<7
gunicorn>=23,<24
markdown-it-py>=3,<5
Pillow>=11,<13
pytest>=8,<10
pytest-django>=4,<6
playwright>=1.50,<2
```

Compile an exact `requirements.txt` with hashes using `pip-tools`. Build from `python:3.13-slim`, install only the locked file, run as an unprivileged `app` user, collect static files during build, and start Gunicorn on `0.0.0.0:8000`. `compose.yaml` binds `${APP_BIND_ADDRESS:-127.0.0.1}:8000:8000`, mounts `portal-data:/data`, and mounts the workspace Markdown directory read-only at `/content/wiki`.

- [ ] **Step 6: Run local and container verification**

Run:

```powershell
.\.venv\Scripts\python -m pytest core/tests/test_health.py -v
docker compose build
docker compose up -d
Invoke-RestMethod http://127.0.0.1:8000/healthz/
docker compose down
```

Expected: tests pass, image builds, and health returns the exact JSON contract.

- [ ] **Step 7: Commit the foundation**

```powershell
git add .gitignore .dockerignore pyproject.toml requirements.in requirements.txt pytest.ini manage.py config core accounts Dockerfile compose.yaml .env.example
git commit -m "build: bootstrap Django portal and Docker runtime"
```

---

### Task 2: Custom Users, Forced Password Change, and Admin Account Management

**Files:**
- Modify: `accounts/models.py`, `accounts/apps.py`
- Create: `accounts/forms.py`, `accounts/services.py`, `accounts/middleware.py`, `accounts/views.py`, `accounts/urls.py`
- Create: `accounts/management/commands/bootstrap_admin.py`
- Create: `accounts/templates/accounts/login.html`, `force_password_change.html`, `user_list.html`, `user_form.html`
- Create: `accounts/tests/test_auth.py`, `test_admin_accounts.py`, `test_login_throttle.py`
- Modify: `config/settings.py`, `config/urls.py`

**Interfaces:**
- Produces: `accounts.User(AbstractUser)` with `is_portal_admin: bool` and `must_change_password: bool`.
- Produces: `create_managed_user(*, actor, username, temporary_password) -> User`.
- Produces: `set_user_active(*, actor, user, active) -> User` and `reset_temporary_password(...) -> User`.
- Produces: `PortalAdminRequiredMixin` and forced-password-change middleware.

- [ ] **Step 1: Write failing authorization and password lifecycle tests**

```python
# accounts/tests/test_auth.py
@pytest.mark.django_db
def test_temporary_password_forces_change(client, user_factory):
    user = user_factory(password="Temp-Only-42!", must_change_password=True)
    assert client.login(username=user.username, password="Temp-Only-42!")
    response = client.get("/dashboard/")
    assert response.status_code == 302
    assert response.url == "/account/change-required/"

@pytest.mark.django_db
def test_inactive_user_cannot_keep_using_session(client, user_factory):
    user = user_factory(password="Valid-Password-42!")
    client.force_login(user)
    user.is_active = False
    user.save(update_fields=["is_active"])
    assert client.get("/dashboard/").status_code == 302
```

Add tests proving a normal user gets 403 from every `/portal-admin/` route, an admin can create/deactivate/reactivate/reset accounts, and account creation never accepts `is_superuser` from request data.

- [ ] **Step 2: Run tests to confirm models and routes are missing**

Run: `.\.venv\Scripts\python -m pytest accounts/tests -v`

Expected: collection or import failures for `accounts.User` and account routes.

- [ ] **Step 3: Implement the custom user before creating initial migrations**

```python
class User(AbstractUser):
    is_portal_admin = models.BooleanField(default=False)
    must_change_password = models.BooleanField(default=True)

    def can_view_all_characters(self) -> bool:
        return self.is_authenticated and self.is_portal_admin
```

Use Django password validators and `Argon2PasswordHasher` first in `PASSWORD_HASHERS`. The management command accepts `--username`, prompts securely for a password when omitted, creates `is_portal_admin=True`, `is_staff=False`, `is_superuser=False`, and sets `must_change_password=False`.

- [ ] **Step 4: Implement account services and views**

All mutations must call service functions that assert `actor.is_portal_admin`. Account forms expose only username and active state; temporary passwords are write-only and never redisplayed. Deactivation calls `update_session_auth_hash` only for the currently changing user and relies on Django's inactive-user backend check to invalidate other sessions.

- [ ] **Step 5: Add persistent login throttling**

Create `LoginThrottle` with `key_hash`, `window_started_at`, `failure_count`, and `blocked_until`. Hash normalized username plus source IP with an HMAC derived from `SECRET_KEY`. Block after 5 failures within 15 minutes for 15 minutes, reset after a successful login, and return the same login error for unknown, wrong-password, and blocked identifiers.

- [ ] **Step 6: Run migrations and account tests**

Run:

```powershell
.\.venv\Scripts\python manage.py makemigrations accounts
.\.venv\Scripts\python manage.py migrate
.\.venv\Scripts\python -m pytest accounts/tests -v
```

Expected: all account, password, permission, and throttle tests pass.

- [ ] **Step 7: Commit account management**

```powershell
git add accounts config
git commit -m "feat: add managed portal accounts and secure login"
```

---

### Task 3: Markdown Allowlist, Rendering, Navigation, and Search

**Files:**
- Create: `wiki/content.py`, `wiki/markdown.py`, `wiki/search.py`, `wiki/views.py`, `wiki/urls.py`
- Create: `wiki/templates/wiki/chapter.html`, `wiki/templates/wiki/search_results.html`
- Create: `wiki/tests/test_content.py`, `test_markdown.py`, `test_search.py`, `test_views.py`
- Modify: `config/settings.py`, `config/urls.py`

**Interfaces:**
- Produces: `WikiSection(id, chapter_slug, chapter_title, title, plain_text, html, ordinal)`.
- Produces: `WikiRepository.load()`, `.chapters()`, `.get_chapter(slug)`, `.search(query, limit=30)`.
- Consumes: ordered `settings.WIKI_CONTENT_ALLOWLIST`; excludes every other Markdown file.

- [ ] **Step 1: Write failing repository and sanitizer tests**

```python
def test_allowlist_excludes_progress_file(tmp_path, settings):
    (tmp_path / "01-Chapter.md").write_text("# Chapter\nAllowed", encoding="utf-8")
    (tmp_path / "00-FORTSCHRITT.md").write_text("# Secret work notes", encoding="utf-8")
    settings.WIKI_CONTENT_ROOT = tmp_path
    settings.WIKI_CONTENT_ALLOWLIST = ["01-Chapter.md"]
    repo = WikiRepository.load()
    assert [c.source_name for c in repo.chapters()] == ["01-Chapter.md"]

def test_raw_html_is_not_executed(renderer):
    html = renderer.render("# Safe\n<script>alert(1)</script>")
    assert "<script" not in html
```

Add tests for duplicate heading slugs (`skills`, `skills-2`), empty placeholder chapters, a broken UTF-8 file that does not remove valid chapters, heading-weighted search, highlighted snippets, and login requirement on all wiki routes.

- [ ] **Step 2: Run the tests and verify missing repository failures**

Run: `.\.venv\Scripts\python -m pytest wiki/tests -v`

Expected: imports fail for the repository and renderer.

- [ ] **Step 3: Implement immutable content records and safe Markdown rendering**

Configure markdown-it-py with HTML disabled. Generate stable ASCII slugs with collision suffixes. Sanitize the rendered result with a small Bleach allowlist for headings, paragraphs, emphasis, lists, code, tables, and internal links. Reject external `javascript:` and data URLs.

- [ ] **Step 4: Implement the in-memory search index**

Tokenize casefolded Unicode words, index heading tokens with weight 4 and body tokens with weight 1, intersect query terms, rank by total score then chapter/section order, and produce a 180-character escaped snippet around the first match. A query shorter than 2 non-space characters returns no results.

- [ ] **Step 5: Load the repository during Django app startup**

`WikiConfig.ready()` calls `wiki.content.initialize_repository()`. File failures are caught per file and logged without body content. `get_repository()` returns the initialized immutable instance; tests replace it through a dedicated `set_repository_for_tests()` helper.

- [ ] **Step 6: Implement authenticated chapter and search views**

Routes:

```text
GET /wiki/                         ordered chapter list
GET /wiki/<chapter_slug>/          rendered chapter with section navigation
GET /search/?q=<query>             global wiki search results
```

Every route uses `LoginRequiredMixin`. Empty chapters display "Dieses Kapitel ist noch nicht ausgearbeitet.".

- [ ] **Step 7: Run tests and commit**

```powershell
.\.venv\Scripts\python -m pytest wiki/tests -v
git add wiki config
git commit -m "feat: add safe Markdown wiki and full-text search"
```

---

### Task 4: Extract Original Sheet Artwork and Build the Coordinate Schema Workflow

**Files:**
- Create: `tools/extract_sheet_assets.py`, `tools/sheet_mapper.html`
- Create: `sheets/schema.py`
- Create: `sheets/data/character-page-1.json`, `character-page-2.json`, `ship-page.json`
- Create: `sheets/static/sheets/images/character-page-1.webp`, `character-page-2.webp`, `ship-page.webp`
- Create: `sheets/tests/test_schema.py`, `test_assets.py`

**Interfaces:**
- Produces: `FieldSpec(id: str, kind: Literal["text","checkbox"], x: Decimal, y: Decimal, width: Decimal, height: Decimal, max_length: int, label: str)`.
- Produces: `SheetSchema(page_id, image_width, image_height, fields)` and `load_schema(page_id) -> SheetSchema`.
- Produces: immutable background assets derived only from source PDF pages 401-403.

- [ ] **Step 1: Write failing schema validation tests**

```python
def test_schema_rejects_duplicate_ids():
    payload = {
        "page_id": "character-page-1",
        "image": {"width": 1230, "height": 1620},
        "fields": [
            {"id": "character_name", "kind": "text", "x": 7, "y": 5, "width": 40, "height": 2, "max_length": 80, "label": "Character name"},
            {"id": "character_name", "kind": "text", "x": 50, "y": 5, "width": 40, "height": 2, "max_length": 80, "label": "Player name"},
        ],
    }
    with pytest.raises(SchemaError, match="duplicate field id"):
        SheetSchema.from_dict(payload)

def test_all_field_bounds_stay_inside_page(character_page_1_schema):
    for field in character_page_1_schema.fields:
        assert 0 <= field.x < 100
        assert 0 <= field.y < 100
        assert field.x + field.width <= 100
        assert field.y + field.height <= 100
```

Also test known page IDs, unique IDs across both character pages, positive dimensions, labels, text length bounds, and checkbox value typing.

- [ ] **Step 2: Implement asset extraction with deterministic output**

`tools/extract_sheet_assets.py` accepts `--pdf`, `--pdftoppm`, and `--output`. It renders exactly pages 401-403 at the scan's useful native resolution, converts them to lossless WebP, rotates page 403 until the Rogue Trader header is horizontal and output width exceeds height, strips metadata, and prints SHA-256 hashes. Refuse PDFs whose page count is below 403.

Run:

```powershell
.\.venv\Scripts\python tools\extract_sheet_assets.py `
  --pdf '..\737639872-Rogue-Trader-Core-Rulebook.pdf' `
  --pdftoppm 'C:\Users\NikolasReif\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin\pdftoppm.exe' `
  --output 'sheets\static\sheets\images'
```

- [ ] **Step 3: Implement the local mapper utility**

`tools/sheet_mapper.html` loads one extracted image, allows drawing/resizing rectangles, assigns a required stable ID, label, `text`/`checkbox` type, and max length, supports arrow-key nudging at 0.05% increments, and exports the exact schema JSON shape consumed by `SheetSchema.from_dict`. It is a local authoring tool only and is not served by Django.

- [ ] **Step 4: Calibrate all three schemas in printed reading order**

Map every printed blank line and rectangular value box as `text`. Map every printed small square and advance circle as `checkbox`. Use stable prefixes `c1_`, `c2_`, and `ship_`; use semantic suffixes such as `c1_character_name`, `c1_ws_value`, `c1_acrobatics_basic`, `c2_weapon_1_name`, `c2_wounds_current`, `ship_name`, `ship_weapon_1_damage`, and `ship_location_port_1`. Do not map labels, headings, artwork, borders, or table separators.

Perform four passes per page in the mapper: top-to-bottom text fields, top-to-bottom checkboxes, keyboard order, and overlay alignment at the supported desktop widths. Export JSON only after every printed control has exactly one overlay and no overlay extends beyond its printed region.

- [ ] **Step 5: Implement `sheets/schema.py` and validate exported data**

Parse JSON into frozen dataclasses, quantize coordinates to four decimal places, cache schemas by page ID, and expose `validate_value(field_id, value)`. Text accepts strings up to `max_length`; checkbox accepts only JSON booleans.

- [ ] **Step 6: Verify assets and schemas**

Run:

```powershell
.\.venv\Scripts\python -m pytest sheets/tests/test_schema.py sheets/tests/test_assets.py -v
```

Expected: all images have nonzero dimensions, character pages are portrait, ship page is landscape, schemas load, IDs are unique, and every field stays within bounds.

- [ ] **Step 7: Commit source artwork derivatives and schemas**

```powershell
git add tools sheets/schema.py sheets/data sheets/static/sheets/images sheets/tests/test_schema.py sheets/tests/test_assets.py
git commit -m "feat: add original sheet artwork and field schemas"
```

---

### Task 5: Sheet Models and Field-Level Optimistic Concurrency

**Files:**
- Create: `sheets/models.py`, `sheets/services.py`, `sheets/permissions.py`
- Create: `sheets/tests/test_models.py`, `test_services.py`, `test_permissions.py`
- Modify: `config/settings.py`

**Interfaces:**
- Produces: `CharacterSheet`, `ShipSheet`, and `SheetChange` models.
- Produces: `patch_character_field(*, sheet_id, actor, field_id, value, base_version) -> PatchResult`.
- Produces: `patch_ship_field(*, sheet_id, actor, field_id, value, base_version) -> PatchResult`.
- Raises: `SheetNotFound`, `FieldValidationError`, or `FieldConflict(current_value, current_version)`.

Use these exact result and conflict shapes:

```python
@dataclass(frozen=True)
class PatchResult:
    field_id: str
    value: str | bool
    version: int
    saved_at: datetime

class FieldConflict(Exception):
    def __init__(self, *, field_id: str, submitted_value: str | bool, current_value: str | bool, current_version: int): ...
```

- [ ] **Step 1: Write failing ownership, merge, conflict, and audit tests**

```python
@pytest.mark.django_db(transaction=True)
def test_different_fields_merge_from_same_base(character_sheet, owner):
    first = patch_character_field(sheet_id=character_sheet.id, actor=owner, field_id="c1_character_name", value="Lucian", base_version=0)
    second = patch_character_field(sheet_id=character_sheet.id, actor=owner, field_id="c1_player_name", value="Nikolas", base_version=0)
    assert first.version == 1
    assert second.version == 2

@pytest.mark.django_db(transaction=True)
def test_same_field_conflict_never_overwrites(character_sheet, owner):
    patch_character_field(sheet_id=character_sheet.id, actor=owner, field_id="c1_character_name", value="Lucian", base_version=0)
    with pytest.raises(FieldConflict) as error:
        patch_character_field(sheet_id=character_sheet.id, actor=owner, field_id="c1_character_name", value="Voss", base_version=0)
    assert error.value.current_value == "Lucian"
```

Add tests proving a normal user gets `SheetNotFound` for another user's character, an admin can read but cannot patch/delete that character, every user can patch the ship, unknown field IDs fail, and ship changes create an audit record with actor/old/new values.

- [ ] **Step 2: Implement models and database constraints**

```python
class CharacterSheet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="characters")
    display_name = models.CharField(max_length=120)
    values = models.JSONField(default=dict)
    field_versions = models.JSONField(default=dict)
    version = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class ShipSheet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    display_name = models.CharField(max_length=120, default="Gemeinsames Schiff")
    values = models.JSONField(default=dict)
    field_versions = models.JSONField(default=dict)
    version = models.PositiveBigIntegerField(default=0)
    is_active = models.BooleanField(default=True)
```

`SheetChange` has exactly one nullable foreign key (`character` or `ship`) enforced by a `CheckConstraint`, plus actor, field ID, old/new JSON values, resulting version, and timestamp.

- [ ] **Step 3: Implement transactional patch services**

Inside `transaction.atomic()`, fetch the sheet with `select_for_update()`, perform permission check before revealing existence, validate through the correct page schemas, compare `field_versions.get(field_id, 0)` with `base_version`, increment the sheet version, update only the requested field, record the field's new version, and write `SheetChange`. Updating `c1_character_name` also synchronizes `display_name` after validation.

- [ ] **Step 4: Seed one shared ship with a data migration**

Create a reversible migration that inserts `ShipSheet(display_name="Gemeinsames Schiff", is_active=True)` only when no ship exists. The reverse deletes only that migration's known UUID.

- [ ] **Step 5: Run migrations and service tests**

```powershell
.\.venv\Scripts\python manage.py makemigrations sheets
.\.venv\Scripts\python manage.py migrate
.\.venv\Scripts\python -m pytest sheets/tests/test_models.py sheets/tests/test_services.py sheets/tests/test_permissions.py -v
```

- [ ] **Step 6: Commit persistence and concurrency**

```powershell
git add sheets config
git commit -m "feat: persist sheets with field-level conflict protection"
```

---

### Task 6: Character CRUD and Read-Only Admin Visibility

**Files:**
- Create: `sheets/forms.py`, `sheets/views.py`, `sheets/urls.py`
- Create: `sheets/templates/sheets/character_list.html`, `character_create.html`, `character_confirm_delete.html`
- Create: `sheets/templates/sheets/admin_character_list.html`
- Create: `sheets/templates/sheets/_sheet_viewer.html`
- Create: `sheets/tests/test_character_views.py`, `test_admin_character_views.py`
- Modify: `config/urls.py`

**Interfaces:**
- Produces routes `GET/POST /characters/`, `GET /characters/<uuid>/`, `POST /characters/<uuid>/delete/`.
- Produces `GET /portal-admin/characters/` and read-only `GET /portal-admin/characters/<uuid>/`.
- Produces the initial read-only `sheets/_sheet_viewer.html`, rendering both background pages and disabled schema-driven overlays. Task 7 extends this same include with editing and document-scroll behavior.

- [ ] **Step 1: Write failing character isolation tests**

```python
@pytest.mark.django_db
def test_user_character_list_contains_only_owned_sheets(client, user_factory, character_factory):
    owner = user_factory()
    other = user_factory()
    own = character_factory(owner=owner, display_name="Own")
    character_factory(owner=other, display_name="Hidden")
    client.force_login(owner)
    response = client.get("/characters/")
    assert_contains(response, "Own")
    assert_not_contains(response, "Hidden")

@pytest.mark.django_db
def test_admin_foreign_character_is_read_only(client, admin_user, character_factory):
    sheet = character_factory(display_name="Visible")
    client.force_login(admin_user)
    response = client.get(f"/portal-admin/characters/{sheet.id}/")
    assert response.status_code == 200
    assert response.context["read_only"] is True
    assert client.post(f"/characters/{sheet.id}/delete/").status_code == 404
```

- [ ] **Step 2: Run tests to verify missing views**

Run: `.\.venv\Scripts\python -m pytest sheets/tests/test_character_views.py sheets/tests/test_admin_character_views.py -v`

Expected: route failures.

- [ ] **Step 3: Implement owner-scoped CRUD**

Every user-facing lookup starts with `CharacterSheet.objects.filter(owner=request.user)`. Create sets owner server-side and initializes an empty values dictionary. Delete accepts POST plus CSRF only. `display_name` is required at creation and later follows `c1_character_name`.

- [ ] **Step 4: Implement the separate admin read-only route**

Require `is_portal_admin`; list owner username, display name, and updated timestamp. The detail renders the same viewer with `read_only=True`, omits every save URL and destructive action, and marks inputs disabled. Never reuse owner mutation routes for admin viewing.

- [ ] **Step 5: Run tests and commit**

```powershell
.\.venv\Scripts\python -m pytest sheets/tests/test_character_views.py sheets/tests/test_admin_character_views.py -v
git add sheets config
git commit -m "feat: add isolated character management and admin viewing"
```

---

### Task 7: Pixel-Aligned Desktop Sheet Viewer, Autosave, and Conflict UI

**Files:**
- Modify: `sheets/templates/sheets/_sheet_viewer.html`
- Create: `sheets/templates/sheets/character_detail.html`
- Create: `sheets/static/sheets/sheet-viewer.css`, `sheet-viewer.js`
- Create: `sheets/tests/test_field_api.py`, `tests/e2e/test_character_sheet.py`
- Modify: `sheets/views.py`, `sheets/urls.py`

**Interfaces:**
- Produces: `POST /characters/<uuid>/fields/<field_id>/` with JSON `{value, base_version}`.
- Success: `200 {field_id, value, version, saved_at}`.
- Conflict: `409 {field_id, submitted_value, current_value, current_version}`.
- Validation: `422 {field_id, error}`; unauthorized or foreign sheet: `404`.

- [ ] **Step 1: Write failing API contract tests**

```python
@pytest.mark.django_db
def test_field_patch_returns_new_version(client, owner, character_sheet):
    client.force_login(owner)
    response = client.post(
        f"/characters/{character_sheet.id}/fields/c1_character_name/",
        data=json.dumps({"value": "Lucian Voss", "base_version": 0}),
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json()["version"] == 1

@pytest.mark.django_db
def test_same_field_conflict_returns_both_values(client, owner, character_sheet):
    client.force_login(owner)
    patch_character_field(sheet_id=character_sheet.id, actor=owner, field_id="c1_character_name", value="Server", base_version=0)
    response = client.post(
        f"/characters/{character_sheet.id}/fields/c1_character_name/",
        data=json.dumps({"value": "Browser", "base_version": 0}),
        content_type="application/json",
    )
    assert response.status_code == 409
    assert response.json()["current_value"] == "Server"
```

- [ ] **Step 2: Implement the strict JSON field endpoint**

Accept only POST, CSRF, `application/json`, exactly `value` and integer `base_version`, and a URL field ID known to the character schemas. Translate service exceptions to the response contract without revealing sheet existence.

- [ ] **Step 3: Render overlays from schema, never from database keys**

The template iterates schema fields in declared order and renders native `<input type="text">` or `<input type="checkbox">`. Set `left`, `top`, `width`, and `height` as percentages. Field values come from `sheet.values.get(field.id)`; unknown stored keys are never rendered. Use the schema label for `aria-label`.

- [ ] **Step 4: Implement the viewer geometry and controls**

The page image and overlay share one positioned `.sheet-canvas` with the image's intrinsic aspect ratio. CSS inputs are transparent at rest, dark-text only when they contain text, and gain a thin gold focus ring. The canvas uses the available desktop content width and the document scrolls vertically. Store the active page under a `localStorage` key scoped by user ID and sheet ID.

- [ ] **Step 5: Implement autosave and conflict resolution**

Text inputs save 600 ms after the last input and on blur; checkboxes save immediately. Track each field's last confirmed version and a pending request token so stale responses cannot replace newer local input. On 409, show an anchored conflict panel with "Aktuellen Wert übernehmen" and "Meinen Wert erneut speichern"; retry uses `current_version` only after explicit choice. Display `Speichert…`, `Gespeichert`, or `Fehler` in the toolbar without logging values.

- [ ] **Step 6: Add Playwright interaction tests**

Test keyboard tab order follows schema order, a text field survives reload, checkbox state survives reload, proportional alignment remains stable at supported desktop widths, foreign users receive 404, disabled admin view emits no field requests, and simulated same-field conflict displays both choices.

- [ ] **Step 7: Run focused tests and commit**

```powershell
.\.venv\Scripts\python -m pytest sheets/tests/test_field_api.py tests/e2e/test_character_sheet.py -v
git add sheets tests/e2e
git commit -m "feat: add interactive original character sheets"
```

---

### Task 8: Shared Ship Sheet and Audit History

**Files:**
- Create: `sheets/templates/sheets/ship_detail.html`, `ship_history.html`
- Create: `sheets/tests/test_ship_views.py`, `test_ship_field_api.py`
- Create: `tests/e2e/test_ship_sheet.py`
- Modify: `sheets/views.py`, `sheets/urls.py`, `sheets/static/sheets/sheet-viewer.js`

**Interfaces:**
- Produces: `GET /ship/` redirecting to the one active ship.
- Produces: `GET /ships/<uuid>/` and `POST /ships/<uuid>/fields/<field_id>/`.
- Produces: `GET /ships/<uuid>/history/`, available to all authenticated users and containing metadata only.
- Produces: `GET /ships/<uuid>/history/<int:change_id>/`, returning the escaped old/new value fragment for one change.

- [ ] **Step 1: Write failing shared-access and audit tests**

```python
@pytest.mark.django_db
def test_two_users_can_edit_the_shared_ship(client, user_factory, ship_sheet):
    first, second = user_factory(), user_factory()
    client.force_login(first)
    r1 = post_field(client, ship_sheet, "ship_name", "Rosinante", 0)
    client.force_login(second)
    r2 = post_field(client, ship_sheet, "ship_speed", "7", r1.json()["version"])
    assert r1.status_code == 200
    assert r2.status_code == 200

@pytest.mark.django_db
def test_ship_history_records_actor_without_rendering_values_in_list(client, user_factory, ship_sheet):
    user = user_factory()
    patch_ship_field(sheet_id=ship_sheet.id, actor=user, field_id="ship_name", value="Rosinante", base_version=0)
    client.force_login(user)
    response = client.get(f"/ships/{ship_sheet.id}/history/")
    assert_contains(response, user.username)
    assert_not_contains(response, "Rosinante")
```

- [ ] **Step 2: Implement shared ship routes using the same patch contract**

The list route always selects the single active ship in v1. Do not expose create/delete controls. All authenticated users receive the editable ship viewer; the service still validates only `ship-page` fields.

- [ ] **Step 3: Implement privacy-conscious audit history**

The history list shows timestamp, actor, and human field label. Expanding one row makes an authenticated request for old/new values. Escape text values; display booleans as "markiert"/"nicht markiert". Paginate at 50 changes.

- [ ] **Step 4: Add shared concurrency browser tests**

Use two browser contexts to load the same ship. Verify different-field edits merge and same-field edits show the conflict panel to the second saver. Verify reload shows the accepted value and history attributes the update to the correct actor.

- [ ] **Step 5: Run tests and commit**

```powershell
.\.venv\Scripts\python -m pytest sheets/tests/test_ship_views.py sheets/tests/test_ship_field_api.py tests/e2e/test_ship_sheet.py -v
git add sheets tests/e2e
git commit -m "feat: add collaborative ship sheet and audit history"
```

---

### Task 9: Brücken-Hybrid Shell and Double Command Dashboard

**Files:**
- Create: `templates/base.html`, `static/css/portal.css`
- Create: `core/templates/core/dashboard.html`, `core/tests/test_dashboard.py`
- Modify: `core/views.py`, `core/urls.py`, all app templates

**Interfaces:**
- Produces: authenticated `GET /dashboard/` with global search, own character summary, wiki entry, and shared ship entry.
- Produces consistent navigation to dashboard, wiki, characters, ship, account, and conditional portal-admin routes.

- [ ] **Step 1: Write failing dashboard content and role tests**

Test that normal users see only their own character names, all users see the shared ship, admins see the admin navigation, normal users do not, and empty states link to character creation without inventing statistics.

- [ ] **Step 2: Implement the dashboard query contract**

Fetch at most the five most recently updated owned characters, the active ship, and ordered wiki chapters. Search submits to `/search/`. Never query all users' characters for a normal dashboard.

- [ ] **Step 3: Implement the approved visual system**

Define a dark blue-green desktop shell, brass/gold active states, readable parchment-neutral content surfaces for long wiki pages, restrained borders, and system font fallbacks. Desktop uses fixed left navigation and a compact top bar. Do not change sheet canvas geometry.

- [ ] **Step 4: Add accessibility and desktop layout checks**

Provide a skip link, visible focus, semantic landmarks, reduced-motion behavior, and contrast-compliant text. Use Playwright at 1024x768 and 1440x900 to assert no page-level horizontal overflow.

- [ ] **Step 5: Run tests and commit**

```powershell
.\.venv\Scripts\python -m pytest core/tests/test_dashboard.py tests/e2e -v
git add templates static core accounts wiki sheets
git commit -m "feat: add Rogue Trader command interface"
```

---

### Task 10: Production Security, Backup, and Proxmox Operations

**Files:**
- Create: `docs/operations.md`, `scripts/backup.ps1`, `scripts/restore.ps1`
- Create: `core/tests/test_security_settings.py`
- Modify: `config/settings.py`, `compose.yaml`, `.env.example`, `Dockerfile`

**Interfaces:**
- Produces documented commands for first boot, admin bootstrap, deploy, health, backup, restore, and Markdown refresh.
- Produces backups containing one consistent SQLite snapshot plus a manifest with timestamp and SHA-256.

- [ ] **Step 1: Write failing production-setting tests**

```python
def test_production_rejects_default_secret(settings_from_env):
    with pytest.raises(ImproperlyConfigured):
        settings_from_env(DEBUG="0", SECRET_KEY="change-me")

def test_https_security_is_enabled_in_production(production_settings):
    assert production_settings.SESSION_COOKIE_SECURE is True
    assert production_settings.CSRF_COOKIE_SECURE is True
    assert production_settings.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")
```

Add tests for explicit `ALLOWED_HOSTS`, trusted CSRF origins derived from `PUBLIC_BASE_URL`, HSTS, MIME sniffing protection, frame denial, and sanitized error responses.

- [ ] **Step 2: Implement production settings**

Fail startup when production secrets or hosts are absent. Enable secure cookies, `SECURE_SSL_REDIRECT`, one-year HSTS only when `ENABLE_HSTS=1`, proxy SSL header, `X_FRAME_OPTIONS="DENY"`, and `SECURE_CONTENT_TYPE_NOSNIFF`. Keep development defaults usable only when `DEBUG=1`.

- [ ] **Step 3: Implement consistent backup and guarded restore scripts**

Backup runs SQLite's `.backup` command against the live volume, writes a dated database file and SHA-256 manifest to an explicitly supplied destination, then verifies `PRAGMA integrity_check`. Restore requires the container stopped, validates the manifest and integrity, copies the current database to a recovery filename, and only then replaces it. Never infer or recursively delete destinations.

- [ ] **Step 4: Write Proxmox/reverse-proxy operations documentation**

Document same-host binding (`127.0.0.1`) and separate-guest binding to an explicit private address, required `Host` and `X-Forwarded-Proto` headers, TLS at the proxy, firewall restriction to proxy source, `.env` creation, `docker compose up -d --build`, migration behavior, `bootstrap_admin`, account recovery, backup schedule, restore rehearsal, logs, and restart after Markdown edits.

- [ ] **Step 5: Run security and container checks**

```powershell
.\.venv\Scripts\python -m pytest core/tests/test_security_settings.py -v
docker compose config
docker compose build
docker compose up -d
docker compose ps
Invoke-RestMethod http://127.0.0.1:8000/healthz/
docker compose down
```

- [ ] **Step 6: Commit operations work**

```powershell
git add config compose.yaml Dockerfile .env.example docs/operations.md scripts core/tests/test_security_settings.py
git commit -m "ops: harden and document Proxmox deployment"
```

---

### Task 11: Full Verification and Release Baseline

**Files:**
- Create: `tests/e2e/test_complete_journey.py`, `tests/e2e/test_visual_regression.py`
- Create: `tests/visual/character-page-1.png`, `character-page-2.png`, `ship-page.png`
- Modify: `README.md`

**Interfaces:**
- Verifies every public route, permission boundary, persistence path, coordinate overlay, and deployment contract from the design spec.

- [ ] **Step 1: Write the end-to-end acceptance journey**

Automate: bootstrap admin; create two users with temporary passwords; force both password changes; create multiple private characters; verify mutual invisibility; verify admin read-only visibility; edit the shared ship from both accounts; provoke and resolve a same-field conflict; search and open a Wiki section; restart the app; verify all accepted values persist.

- [ ] **Step 2: Add deterministic visual checks**

For each sheet page, load blank data and capture only `.sheet-canvas`. Compare with its extracted background at a small antialiasing tolerance so idle transparent controls add no visible chrome. Enable a test-only overlay debug class and assert every schema rectangle remains inside the canvas at 1024x768 and 1440x900. Inspect the latest screenshots manually for clipped inputs, shifted fields, unreadable entered text, or incorrect ship rotation.

- [ ] **Step 3: Run the complete local suite**

```powershell
.\.venv\Scripts\python -m pytest -v
.\.venv\Scripts\python manage.py check --deploy
```

Expected: all unit, integration, E2E, security, and visual tests pass; deploy check reports no unaddressed warnings under production test settings.

- [ ] **Step 4: Run the clean-container acceptance test**

```powershell
docker compose build --no-cache
docker compose up -d
docker compose exec web python manage.py migrate --check
docker compose exec web python manage.py check --deploy
Invoke-RestMethod http://127.0.0.1:8000/healthz/
docker compose logs --no-color web
```

Expected: healthy container, no pending migration, no secret values or sheet content in logs, and no tracebacks.

- [ ] **Step 5: Complete manual visual and recovery acceptance**

Use the checklist from the design spec on supported desktop browsers. Confirm every printed line/value box and checkbox/circle has exactly one aligned control, every non-input element is inert, page 403 reads upright in landscape, normal document scrolling works, and the shared conflict dialog behaves correctly. Execute one backup and restore rehearsal against disposable test data.

- [ ] **Step 6: Document the release and commit**

`README.md` must link the design, plan, and operations guide; summarize local setup; state that the three background assets derive from the user's source PDF; and list the exact acceptance commands.

```powershell
git add tests README.md
git commit -m "test: verify complete Rogue Trader portal"
git status --short
```

Expected: clean working tree after the final commit.

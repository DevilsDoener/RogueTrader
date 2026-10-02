"""Django settings for the Rogue Trader portal.

Everything deployment-specific comes from environment variables (see
``.env.example`` and ``docs/operations.md``). With ``DJANGO_DEBUG`` unset or
``true`` the defaults suit local development; anything else is production and
requires a strong ``DJANGO_SECRET_KEY`` and explicit ``DJANGO_ALLOWED_HOSTS``.
"""

import os
import secrets
from ipaddress import ip_network
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

# Plain dataclasses, no Django imports -- safe to import while settings are
# still being assembled. Single source of truth for the wiki chapter list.
from wiki import manifest as wiki_manifest

BASE_DIR = Path(__file__).resolve().parent.parent

# Only the exact value "true" (any case) enables debug mode; "1" or "yes" do
# not, so a typo fails closed into production mode.
DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() == "true"

# Placeholder/example secrets that must never reach a production deployment.
# ".env.example" ships one of these on purpose so an operator who forgets to
# change it gets a hard failure instead of a silently insecure site.
_WEAK_SECRET_KEYS = {
    "change-me",
    "changeme",
    "secret",
    "insecure",
    "replace-with-a-long-random-secret",
}
# Django's own ``check --deploy`` bar (security.W009): 50 characters, at least
# 5 of them distinct. Enforced at boot instead of merely warned about.
_MINIMUM_PRODUCTION_SECRET_LENGTH = 50
_MINIMUM_PRODUCTION_SECRET_UNIQUE_CHARS = 5
# The Dockerfile runs ``collectstatic`` at build time with a random 74-character
# key starting with this prefix. It has to pass the checks then, but the string
# must never run a real deployment, so it is refused unless the build step says
# (DOCKER_BUILD_STEP=1, set inline on that one RUN command only).
_BUILD_PLACEHOLDER_PREFIX = "docker-build-placeholder"

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = secrets.token_urlsafe(50)
    else:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is false"
        )
elif not DEBUG:
    _normalized_secret = SECRET_KEY.strip().lower()
    if (
        _normalized_secret in _WEAK_SECRET_KEYS
        or _normalized_secret.startswith("django-insecure-")
        or len(SECRET_KEY) < _MINIMUM_PRODUCTION_SECRET_LENGTH
        or len(set(SECRET_KEY)) < _MINIMUM_PRODUCTION_SECRET_UNIQUE_CHARS
        or (
            _normalized_secret.startswith(_BUILD_PLACEHOLDER_PREFIX)
            and os.environ.get("DOCKER_BUILD_STEP") != "1"
        )
    ):
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY must be a strong, non-default secret when "
            f"DJANGO_DEBUG is false: at least {_MINIMUM_PRODUCTION_SECRET_LENGTH} "
            f"characters (yours has {len(SECRET_KEY)}), at least "
            f"{_MINIMUM_PRODUCTION_SECRET_UNIQUE_CHARS} different ones, not a "
            "placeholder from .env.example or the Dockerfile. Generate one with: "
            "python -c \"import secrets; print(secrets.token_urlsafe(50))\""
        )

# ALLOWED_HOSTS must be provided explicitly in production. The
# 127.0.0.1/localhost fallback below is only safe for local development.
_allowed_hosts_env = os.environ.get("DJANGO_ALLOWED_HOSTS")
if not DEBUG and not _allowed_hosts_env:
    raise ImproperlyConfigured(
        "DJANGO_ALLOWED_HOSTS must be set explicitly when DJANGO_DEBUG is false"
    )
ALLOWED_HOSTS = (_allowed_hosts_env or "127.0.0.1,localhost").split(",")

# Loopback addresses are always accepted, in addition to whatever the
# operator configures above -- the container's own HEALTHCHECK (and the
# documented manual smoke test in docs/operations.md) hit
# http://127.0.0.1:8000/healthz/ directly, with a "Host: 127.0.0.1:8000"
# header that would otherwise trip DisallowedHost once DJANGO_ALLOWED_HOSTS
# is set to the real public hostname. This grants nothing an external
# attacker can reach: these are loopback-only addresses that are only
# reachable from inside the container/host itself.
for _loopback_host in ("127.0.0.1", "localhost"):
    if _loopback_host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(_loopback_host)

PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://127.0.0.1:8000")

# The portal always sits behind a reverse proxy that terminates TLS and
# forwards the original scheme via X-Forwarded-Proto, so Django needs to
# trust that header to know a request was actually secure.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Which peers may tell us the real client address (login throttle, audit log).
# Empty by default: the client address is then the direct peer, REMOTE_ADDR, and
# any X-Real-IP / X-Forwarded-For header is ignored. Behind the reverse proxy
# list the proxy as seen from the container (comma-separated IPs or CIDRs, see
# docs/operations.md section 2); only then is TRUSTED_PROXY_HEADER believed.
# "x-real-ip" (a header the proxy overwrites) or "x-forwarded-for" (the
# rightmost entry that is not itself a trusted proxy).
TRUSTED_PROXY_IPS = [
    entry.strip()
    for entry in os.environ.get("TRUSTED_PROXY_IPS", "").split(",")
    if entry.strip()
]
for _proxy_entry in TRUSTED_PROXY_IPS:
    try:
        ip_network(_proxy_entry, strict=False)
    except ValueError:
        raise ImproperlyConfigured(
            f"TRUSTED_PROXY_IPS entry {_proxy_entry!r} is not an IP address or CIDR network"
        ) from None
TRUSTED_PROXY_HEADER = (os.environ.get("TRUSTED_PROXY_HEADER") or "x-real-ip").strip().lower()
if TRUSTED_PROXY_HEADER not in ("x-real-ip", "x-forwarded-for"):
    raise ImproperlyConfigured(
        "TRUSTED_PROXY_HEADER must be 'x-real-ip' or 'x-forwarded-for'"
    )

# CSRF_TRUSTED_ORIGINS must include the scheme (e.g. "https://example.com"),
# which PUBLIC_BASE_URL already carries. Trailing slashes are stripped --
# Django requires an origin with no path component, and both
# .env.example/docs/operations.md show PUBLIC_BASE_URL without one, but an
# operator who adds one anyway (e.g. "https://example.com/") would
# otherwise silently produce a CSRF_TRUSTED_ORIGINS entry Django never
# matches against the request's Origin header, making every POST 403.
CSRF_TRUSTED_ORIGINS = [PUBLIC_BASE_URL.rstrip("/")]

# Clickjacking / MIME-sniffing protections apply regardless of DEBUG -- they
# do not interfere with local development.
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True

# Cookie/transport security is only forced on in production so that plain
# HTTP development (DJANGO_DEBUG=true, no TLS-terminating proxy) keeps working.
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG

# The health-check endpoint is polled in plain HTTP over loopback -- by the
# Dockerfile's own HEALTHCHECK and by the manual smoke test in
# docs/operations.md -- so it must never be bounced to HTTPS the way every
# other view is. This is safe to exempt unconditionally: /healthz/ requires
# no login and returns no sheet content, only a liveness/DB status flag.
SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]

# HTTP Strict Transport Security is opt-in via ENABLE_HSTS=1 so it can only
# be turned on once the reverse proxy is confirmed to serve HTTPS correctly
# -- an incorrect HSTS header cannot be easily undone by clients.
ENABLE_HSTS = os.environ.get("ENABLE_HSTS", "0") == "1"
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365 if ENABLE_HSTS else 0
# includeSubDomains and preload widen that to every subdomain of the registrable
# domain and invite submission to browsers' preload list; each is its own
# opt-in (default off) and only has an effect together with ENABLE_HSTS=1.
SECURE_HSTS_INCLUDE_SUBDOMAINS = (
    ENABLE_HSTS and os.environ.get("HSTS_INCLUDE_SUBDOMAINS", "0") == "1"
)
SECURE_HSTS_PRELOAD = ENABLE_HSTS and os.environ.get("HSTS_PRELOAD", "0") == "1"

# The audit trail (``accounts.audit``) goes to the console like everything else
# and, in production, also to a file that survives container re-creation:
# AUDIT_LOG_FILE, default ``logs/audit.log`` next to the database (the /data
# volume). In development it is off unless AUDIT_LOG_FILE is set. The
# directory is only created when the first record is written. The handler only
# appends (several gunicorn workers share the file); the size limit and backup
# count below are applied once per container start by
# ``manage.py rotate_audit_log``, before the workers fork.
_database_file = Path(os.environ.get("DATABASE_PATH") or BASE_DIR / "data" / "db.sqlite3")
_default_audit_log = None if DEBUG else _database_file.parent / "logs" / "audit.log"
AUDIT_LOG_FILE = os.environ.get("AUDIT_LOG_FILE") or _default_audit_log
AUDIT_LOG_MAX_BYTES = 5 * 1024 * 1024
AUDIT_LOG_BACKUP_COUNT = 5

# Technical errors are logged; nothing here logs request bodies, so
# passwords, session values, and sheet content are never captured.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        },
        **(
            {
                "audit_file": {
                    "class": "accounts.auditlog.AuditFileHandler",
                    "filename": str(AUDIT_LOG_FILE),
                    "formatter": "default",
                },
            }
            if AUDIT_LOG_FILE
            else {}
        ),
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "accounts.audit": {
            # Console output comes from the root logger via propagation.
            "handlers": ["audit_file"] if AUDIT_LOG_FILE else [],
            "level": "INFO",
            "propagate": True,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.security": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts',
    'core',
    'sheets',
    'wiki',
]

MIDDLEWARE = [
    # First, so static files served by WhiteNoise and redirects carry the CSP.
    'config.security_headers.SecurityHeadersMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'accounts.middleware.ForcePasswordChangeMiddleware',
    'accounts.middleware.AdminAccessAuditMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'wiki.context_processors.wiki_navigation',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.environ.get("DATABASE_PATH", BASE_DIR / "data" / "db.sqlite3"),
        'OPTIONS': {
            # Take SQLite's write lock when a transaction *begins* and wait up
            # to 20 s for it. With the default deferred BEGIN, two writers that
            # both read first fail the second one at once with "database is
            # locked" (HTTP 500) instead of queueing -- and then seeing the
            # first one's version and answering 409.
            'transaction_mode': 'IMMEDIATE',
            'timeout': 20,
        },
    }
}

# Daily SQLite backups (``manage.py backup_db``, see docs/operations.md). The
# default sits next to the database; compose.yaml points it at a host bind
# mount so backups survive the loss of the data volume.
BACKUP_DIR = Path(
    os.environ.get("BACKUP_DIR") or Path(str(DATABASES["default"]["NAME"])).parent / "backups"
)
BACKUP_KEEP_DAYS = int(os.environ.get("BACKUP_KEEP_DAYS") or 14)

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
]

# Sessions last 14 days from the *last request* (sliding), so an active player
# is never signed out mid-campaign while an abandoned cookie expires. Expired
# rows are only removed by ``manage.py clearsessions`` (docs/operations.md).
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14
SESSION_SAVE_EVERY_REQUEST = True

LANGUAGE_CODE = 'de-de'
TIME_ZONE = 'Europe/Berlin'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Nothing else in front of this app serves static files (no nginx/CDN --
# see docs/operations.md, the reverse proxy only forwards to the portal),
# so WhiteNoise serves portal.css, the scripts under static/js/ and
# sheets/static/sheets/ (sheet-viewer.css/js, ...) and the three sheet
# background .webp images directly from the app process in
# production, with cache-busting hashed filenames and gzip/brotli
# compression via the manifest storage backend below. The manifest
# (staticfiles.json) only exists once `collectstatic` has run (the
# Dockerfile does this at image build time), so local development/tests
# -- which never run `collectstatic` -- keep using Django's plain
# staticfiles storage instead of erroring on a missing manifest entry.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        ),
    },
}

# Defense in depth for the scenario the comment above is guarding against:
# if the staticfiles.json manifest is ever missing at runtime anyway (a
# build step that forgot to run collectstatic under production-shaped
# settings, a wiped/never-populated STATIC_ROOT volume, a future regression
# in the Dockerfile, ...), WhiteNoise's manifest lookup must degrade to a
# missing/404-able static asset rather than hard-crash every single page
# render with `ValueError: Missing staticfiles manifest entry for '...'`
# raised out of the `{% static %}` template tag. With manifest_strict=True
# (the default), a fully absent manifest file is *not* itself an error --
# ManifestFilesMixin.read_manifest() treats FileNotFoundError as "empty
# manifest" -- but every subsequent stored_name() lookup then finds no
# entry and raises. Setting this False makes it fall back to hashing the
# requested file's on-disk contents instead of raising; this is a no-op
# whenever the manifest is present and complete (the normal case).
WHITENOISE_MANIFEST_STRICT = False

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = "accounts.User"

LOGIN_URL = "/account/login/"

# Default to this checkout's own ``content/`` directory so a plain
# ``manage.py runserver`` serves the bundled chapters. The Compose deployment
# mounts the same directory at /content/wiki and sets this explicitly (see
# compose.yaml), so production is unaffected. The previous default was that
# container-only absolute path, which does not exist on a developer machine --
# every local run then logged one "file not found" warning per chapter and
# served an empty wiki.
WIKI_CONTENT_ROOT = Path(os.environ.get("WIKI_CONTENT_ROOT", BASE_DIR / "content"))

# Ordered, explicit filenames (not extensions) allowed to be loaded as wiki
# chapters. Anything not listed here -- e.g. the project's own progress log
# -- is excluded even if it lives under WIKI_CONTENT_ROOT. Declared once in
# wiki/manifest.py, which also carries each chapter's slug and grouping; the
# environment variable below still overrides it.
WIKI_DEFAULT_CONTENT_ALLOWLIST = wiki_manifest.ALLOWLIST
# An empty or whitespace-only value falls back to the manifest rather than
# serving nothing: compose.yaml passes ${WIKI_CONTENT_ALLOWLIST:-} through, so
# "set but empty" is the normal case when no override is configured.
_wiki_allowlist_override = tuple(
    filename.strip()
    for filename in os.environ.get("WIKI_CONTENT_ALLOWLIST", "").split(",")
    if filename.strip()
)
WIKI_CONTENT_ALLOWLIST = _wiki_allowlist_override or WIKI_DEFAULT_CONTENT_ALLOWLIST
# Top-level sections whose heading matches one of these (casefolded) patterns
# are transcription bookkeeping, not rules: per-chapter PDF page audits left in
# the Markdown so the cross-check trail stays with the text. They are hidden
# from readers and from search at parse time, which keeps the source files
# untouched. Matched at depth 1 only, so a legitimately-named deeper heading is
# never swallowed. Note the two spellings of the cross-check heading.
WIKI_EDITORIAL_SECTION_PATTERNS = (
    r"^status$",
    r"^page (inventory|coverage) and cross-?check$",
    # The front-matter chapter also carries four transcription sections: a PDF
    # page inventory, the book's bibliographic data, the PDF bookmark tree and
    # a description of the endpaper map. They are German and they are about the
    # scan, not the rules, so they are hidden rather than translated -- the
    # Markdown keeps them as part of the transcription trail.
    r"^seiteninventar\b",
    r"^bibliografische kerndaten$",
    r"^vollständige pdf-lesezeichenstruktur$",
    r"^kartenübersicht\b",
)

# A section whose children are all leaves and number at least this many is a
# glossary (147 talents, 48 skills, 32 traits ...). Its table-of-contents entry
# renders as a compact index of links instead of a very long nested list.
WIKI_TOC_GLOSSARY_THRESHOLD = 16

# How many heading levels the in-page table of contents shows. The corpus
# nests at most three deep.
WIKI_TOC_MAX_DEPTH = 3

# When true, a failure to parse the content tree at startup aborts the boot
# instead of leaving the wiki silently empty. Enabled in the container (see
# compose.yaml), where an empty wiki means the mount is wrong.
WIKI_STRICT_CONTENT = os.environ.get("WIKI_STRICT_CONTENT", "false").lower() in (
    "1",
    "true",
    "yes",
)

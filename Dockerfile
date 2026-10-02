# Pinned by digest: python:3.13-slim is a moving tag. Refresh deliberately
# (docker pull python:3.13-slim, then copy the new digest from
# `docker inspect --format '{{index .RepoDigests 0}}' python:3.13-slim`) and
# rebuild.
FROM python:3.13-slim@sha256:bb2988715db2cf7ace7b53f38f3cffbef7c7046a656bee66245eb0ed386e2e81

# DJANGO_DEBUG defaults to "false" in the image: an orchestration that forgets
# to set it must boot as production (strict secret/host checks, secure cookies,
# manifest static storage), never as the debug server. compose.yaml and local
# development override it explicitly (DJANGO_DEBUG=true for runserver).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_DEBUG=false \
    DATABASE_PATH=/data/db.sqlite3

WORKDIR /app

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin app

COPY requirements.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements.txt

# The application code is owned by root and not writable by the runtime user:
# a code-execution bug cannot persist itself by editing .py files or templates
# in the container filesystem. Only /data (the volume) is writable by "app".
COPY . .

# collectstatic runs as root under the same production-shaped settings the
# container runs under at request time (DJANGO_DEBUG=false from the ENV above):
# config/settings.py only selects whitenoise's CompressedManifestStaticFilesStorage
# (and collectstatic only writes the staticfiles.json manifest it needs) when
# DJANGO_DEBUG=false. Without this, the build would silently run collectstatic
# in dev-shaped mode, never produce the manifest, and the runtime would then
# select the manifest backend against a manifest that doesn't exist.
#
# The secret key and host are set inline on this RUN command only (not via ENV),
# so they never persist into the image environment and cannot shadow the real
# DJANGO_SECRET_KEY/DJANGO_ALLOWED_HOSTS that compose.yaml and .env supply at
# runtime. The key is a build-only placeholder: labelled as such, longer than
# the 50-character production floor, and different on every build (random
# suffix), so there is no fixed string anyone could reuse for a real deployment.
# DOCKER_BUILD_STEP=1 (also inline, also build-only) is the one thing that lets
# config/settings.py accept a key with this "docker-build-placeholder" prefix;
# at runtime such a key is refused.
RUN DOCKER_BUILD_STEP=1 \
    DJANGO_SECRET_KEY="docker-build-placeholder-not-a-real-secret-$(python -c 'import secrets; print(secrets.token_urlsafe(32))')" \
    DJANGO_ALLOWED_HOSTS=localhost \
    python manage.py collectstatic --noinput \
    && chmod -R go-w /app \
    && mkdir -p /data \
    && chown app:app /data

USER app

EXPOSE 8000
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz/', timeout=3).status == 200 else 1)"]

# Start: remove expired login sessions once (the backup service mounts the
# data volume read-only and cannot), rotate the audit log once (the workers
# only append to it; in-process rotation is not safe across processes), then
# become gunicorn (exec: it is PID 1 and receives docker's SIGTERM). A failing
# clearsessions -- e.g. before the first migrate -- or rotate_audit_log must
# not keep the portal down.
#
# Three sync workers: one slow request no longer starves the portal, the health
# check and the sheet autosave. The wiki repository is loaded in every worker
# (no --preload), roughly 60 MB each; --timeout 30 kills a stuck one.
CMD ["sh", "-c", "python manage.py clearsessions || echo 'clearsessions failed - starting anyway' >&2; python manage.py rotate_audit_log || echo 'rotate_audit_log failed - starting anyway' >&2; exec gunicorn --bind 0.0.0.0:8000 --workers 3 --timeout 30 --access-logfile - config.wsgi:application"]

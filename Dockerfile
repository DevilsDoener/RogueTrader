FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_PATH=/data/db.sqlite3

WORKDIR /app

RUN useradd --create-home --uid 10001 app

COPY requirements.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements.txt

COPY --chown=app:app . .

RUN mkdir -p /app/staticfiles /data && chown app:app /app/staticfiles /data

USER app

# collectstatic must run under the same production-shaped settings the
# container runs under at request time: config/settings.py only selects
# whitenoise's CompressedManifestStaticFilesStorage (and collectstatic only
# writes the staticfiles.json manifest it needs) when DJANGO_DEBUG=false,
# but DJANGO_DEBUG defaults to "true" when unset. Without this, the build
# silently ran collectstatic in dev-shaped mode, never produced the
# manifest, and the runtime (where compose.yaml sets DJANGO_DEBUG=false)
# would then select the manifest backend against a manifest that doesn't
# exist.
#
# These are set inline on this RUN command only (not via ENV), so they
# never persist into the final image's environment: they cannot shadow the
# real DJANGO_SECRET_KEY/DJANGO_ALLOWED_HOSTS/DJANGO_DEBUG that compose.yaml
# and .env supply to the container at runtime.
RUN DJANGO_DEBUG=false \
    DJANGO_SECRET_KEY=docker-build-collectstatic-placeholder-not-for-runtime-use \
    DJANGO_ALLOWED_HOSTS=localhost \
    python manage.py collectstatic --noinput

EXPOSE 8000
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz/', timeout=3).status == 200 else 1)"]

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "config.wsgi:application"]

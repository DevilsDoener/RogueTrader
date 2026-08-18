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
RUN python manage.py collectstatic --noinput

EXPOSE 8000
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz/', timeout=3).status == 200 else 1)"]

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "config.wsgi:application"]

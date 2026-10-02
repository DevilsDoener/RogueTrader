"""Run by ``test_sqlite_concurrency.py`` in a child process against a real
SQLite *file* (the test database is in-memory, where SQLite's locking is
different). Prints one JSON object.

Part 1: 8 users post the same ship field with the same ``base_version``.
Part 2: 16 parallel failed logins hit one throttle counter.
"""
import json
import os
import sys
import threading
from datetime import UTC, datetime

sys.path.insert(0, os.environ["PROJECT_ROOT"])
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
from django.conf import settings

if os.environ.get("PROBE_DEFERRED_BEGIN"):
    # Reproduce the pre-fix behaviour (SQLite's default deferred BEGIN).
    settings.DATABASES["default"].pop("OPTIONS", None)

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.core.management import call_command  # noqa: E402
from django.db import connections  # noqa: E402
from django.test import Client  # noqa: E402
from django.urls import reverse  # noqa: E402

from accounts import throttle  # noqa: E402
from accounts.models import LoginThrottle  # noqa: E402
from sheets.models import SheetChange, ShipSheet  # noqa: E402

call_command("migrate", verbosity=0)
users = get_user_model()
players = [
    users.objects.create_user(username=f"u{i}", password="x" * 12, must_change_password=False)
    for i in range(8)
]
ship = ShipSheet.objects.filter(is_active=True).first()
url = reverse("sheets:ship_field_update", args=[ship.pk, "ship_space_used"])


def run_parallel(worker, items):
    barrier = threading.Barrier(len(items))
    results = []

    def target(item):
        barrier.wait()
        try:
            results.append(worker(item))
        finally:
            connections.close_all()

    threads = [threading.Thread(target=target, args=(item,)) for item in items]
    [t.start() for t in threads]
    [t.join() for t in threads]
    return results


def post_field(player):
    client = Client(raise_request_exception=False, HTTP_HOST="127.0.0.1")
    client.force_login(player)
    response = client.post(
        url,
        data=json.dumps({"value": player.username[1:], "base_version": 0}),
        content_type="application/json",
    )
    return response.status_code


statuses = run_parallel(post_field, players)
ship.refresh_from_db()

counter = throttle.login_counters("crew", "192.0.2.1").pair
now = datetime.now(UTC)
run_parallel(lambda _: throttle.record_failure([counter], now), range(16))
row = LoginThrottle.objects.get(key_hash=counter.key_hash)

print(
    json.dumps(
        {
            "statuses": sorted(statuses),
            "audit_rows": SheetChange.objects.filter(ship=ship).count(),
            "ship_version": ship.version,
            "failure_count": row.failure_count,
            "blocked": row.blocked_until is not None,
        }
    )
)

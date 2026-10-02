"""Parallel writers on a real SQLite file (AUTH-8, sheets F2).

With SQLite's default deferred BEGIN a second writer that has already read
fails at once with "database is locked" (HTTP 500). The settings ask for
``BEGIN IMMEDIATE`` plus a 20 s wait, so writers queue instead; the field
write then sees the winner's version and answers 409, and the throttle
counter loses no increments.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def probe(tmp_path_factory):
    env = {
        **os.environ,
        "PROJECT_ROOT": str(PROJECT_ROOT),
        "DATABASE_PATH": str(tmp_path_factory.mktemp("race") / "race.sqlite3"),
        "DJANGO_DEBUG": "true",
    }
    result = subprocess.run(  # noqa: S603 - fixed argv: this interpreter and a sibling script
        [sys.executable, str(Path(__file__).with_name("concurrency_probe.py"))],
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_parallel_field_writes_give_one_200_and_409s_never_500(probe):
    statuses = probe["statuses"]

    assert 500 not in statuses, statuses
    assert statuses.count(200) == 1, statuses
    assert statuses.count(409) == len(statuses) - 1, statuses
    assert probe["audit_rows"] == 1
    assert probe["ship_version"] == 1


def test_parallel_failures_are_all_counted(probe):
    assert probe["failure_count"] == 16
    assert probe["blocked"] is True

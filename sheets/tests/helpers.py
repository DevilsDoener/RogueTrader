"""Plain helper functions shared by the ``sheets`` test modules (no fixtures)."""
from __future__ import annotations

import importlib
from types import ModuleType, SimpleNamespace

from django.apps import apps
from django.db import connection


def assert_contains(response, text):
    assert text in response.content.decode()


def assert_not_contains(response, text):
    assert text not in response.content.decode()


def load_migration(name: str) -> ModuleType:
    """Import ``sheets/migrations/<name>.py`` (its name starts with a digit)."""
    return importlib.import_module(f"sheets.migrations.{name}")


def run_migration_step(step) -> None:
    """Call a ``RunPython`` function the way ``migrate`` would, against the
    live app registry and test database connection."""
    step(apps, SimpleNamespace(connection=connection))

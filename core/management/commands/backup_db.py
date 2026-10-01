"""Consistent copy of the live SQLite database, with retention.

Uses SQLite's online backup API (``sqlite3.Connection.backup``), so the copy
is consistent even while the portal is writing. The live database is only ever
opened read-only. The copy is verified with ``PRAGMA integrity_check``; a copy
that is not ``ok`` is removed and the command fails.
"""

import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

BACKUP_PREFIX = "db-"
BACKUP_SUFFIX = ".sqlite3"


def _integrity_check(path: Path) -> list[str]:
    connection = sqlite3.connect(path)
    try:
        return [row[0] for row in connection.execute("PRAGMA integrity_check")]
    finally:
        connection.close()


class Command(BaseCommand):
    help = (
        "Copy the SQLite database into BACKUP_DIR (db-YYYYMMDD-HHMMSS.sqlite3), "
        "verify the copy and delete backups older than BACKUP_KEEP_DAYS."
    )

    def add_arguments(self, parser):
        parser.add_argument("--backup-dir", help="Override settings.BACKUP_DIR.")
        parser.add_argument(
            "--keep-days",
            type=int,
            help="Override settings.BACKUP_KEEP_DAYS.",
        )

    def handle(self, *args, **options):
        source = Path(str(settings.DATABASES["default"]["NAME"]))
        if not source.is_file():
            raise CommandError(f"Database file not found: {source}")
        backup_dir = Path(options["backup_dir"] or settings.BACKUP_DIR)
        keep_days = (
            options["keep_days"]
            if options["keep_days"] is not None
            else settings.BACKUP_KEEP_DAYS
        )
        backup_dir.mkdir(parents=True, exist_ok=True)

        target = backup_dir / (
            f"{BACKUP_PREFIX}{datetime.now():%Y%m%d-%H%M%S}{BACKUP_SUFFIX}"
        )
        if target.exists():
            raise CommandError(f"Backup target already exists: {target}")

        self._copy(source, target)
        result = _integrity_check(target)
        if result != ["ok"]:
            target.unlink(missing_ok=True)
            raise CommandError(
                f"Integrity check failed for the backup copy: {'; '.join(result)}"
            )
        self.stdout.write(f"Backup written: {target} (integrity_check: ok)")

        removed = self._prune(backup_dir, keep_days, keep=target)
        for old in removed:
            self.stdout.write(f"Pruned old backup: {old.name}")

    @staticmethod
    def _copy(source: Path, target: Path) -> None:
        # mode=ro: reading only, the live database is never modified.
        live = sqlite3.connect(f"{source.resolve().as_uri()}?mode=ro", uri=True)
        try:
            copy = sqlite3.connect(target)
            try:
                live.backup(copy)
            finally:
                copy.close()
        finally:
            live.close()

    @staticmethod
    def _prune(backup_dir: Path, keep_days: int, keep: Path) -> list[Path]:
        cutoff = time.time() - keep_days * 86400
        removed = []
        for path in sorted(backup_dir.glob(f"{BACKUP_PREFIX}*{BACKUP_SUFFIX}")):
            if path == keep or not path.is_file():
                continue
            if path.stat().st_mtime < cutoff:
                os.remove(path)
                removed.append(path)
        return removed

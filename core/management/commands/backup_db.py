"""Consistent copy of the live SQLite database, with retention.

Uses SQLite's online backup API (``sqlite3.Connection.backup``), so the copy
is consistent even while the portal is writing. The live database is only ever
opened read-only (the backup service mounts it read-only), so nothing here may
write to it.

The copy is built under a temporary name next to its final location, stripped
of login sessions (a stolen backup must not yield a usable login; a restored
portal simply asks everybody to sign in again), verified with
``PRAGMA integrity_check`` and only then renamed to ``db-<timestamp>.sqlite3``.
A failed or killed run therefore never leaves a file that looks like a
finished backup -- the healthcheck and the retention only look at the final
names. Backups contain every password hash, so the directory and the files are
created readable by their owner only.
"""

import contextlib
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

BACKUP_PREFIX = "db-"
BACKUP_SUFFIX = ".sqlite3"
TEMP_SUFFIX = ".tmp"

#: A leftover ``*.tmp`` from a killed run is removed once it is this old.
STALE_TEMP_SECONDS = 3600

#: Session rows are removed from every copy (see the module docstring).
SESSION_TABLE = "django_session"


def _integrity_check(path: Path) -> list[str]:
    connection = sqlite3.connect(path)
    try:
        return [row[0] for row in connection.execute("PRAGMA integrity_check")]
    finally:
        connection.close()


def _strip_sessions(path: Path) -> None:
    """Delete all login sessions from the *copy* and shrink it again."""
    connection = sqlite3.connect(path)
    try:
        has_table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (SESSION_TABLE,)
        ).fetchone()
        if has_table:
            connection.execute(f'DELETE FROM "{SESSION_TABLE}"')
            connection.commit()
        # One self-contained file: no -wal/-shm left behind next to the copy.
        connection.execute("PRAGMA journal_mode = DELETE")
        connection.execute("VACUUM")
    finally:
        connection.close()


def _remove_with_sidecars(path: Path) -> None:
    for candidate in (path, *(path.with_name(path.name + s) for s in ("-wal", "-shm", "-journal"))):
        with contextlib.suppress(OSError):
            candidate.unlink()


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

        # Owner-only for everything created below (directory 0700, files 0600).
        previous_umask = os.umask(0o077)
        try:
            backup_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
            target = self._write_backup(source, backup_dir)
        finally:
            os.umask(previous_umask)
        self.stdout.write(f"Backup written: {target} (integrity_check: ok)")

        removed = self._prune(backup_dir, keep_days, keep=target)
        for old in removed:
            self.stdout.write(f"Pruned old backup: {old.name}")

    def _write_backup(self, source: Path, backup_dir: Path) -> Path:
        target = backup_dir / (
            f"{BACKUP_PREFIX}{datetime.now():%Y%m%d-%H%M%S}{BACKUP_SUFFIX}"
        )
        if target.exists():
            raise CommandError(f"Backup target already exists: {target}")
        temp = target.with_name(target.name + TEMP_SUFFIX)
        _remove_with_sidecars(temp)

        try:
            self._copy(source, temp)
            os.chmod(temp, 0o600)
            _strip_sessions(temp)
            result = _integrity_check(temp)
            if result != ["ok"]:
                raise CommandError(
                    f"Integrity check failed for the backup copy: {'; '.join(result)}"
                )
            os.replace(temp, target)
        except BaseException:
            # Includes KeyboardInterrupt/SystemExit: never leave a partial file.
            _remove_with_sidecars(temp)
            raise
        return target

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
        now = time.time()
        cutoff = now - keep_days * 86400
        removed = []
        for path in sorted(backup_dir.glob(f"{BACKUP_PREFIX}*{BACKUP_SUFFIX}")):
            if path == keep or not path.is_file():
                continue
            if path.stat().st_mtime < cutoff:
                os.remove(path)
                removed.append(path)
        # Debris of a run that was killed before it could clean up.
        for path in backup_dir.glob(f"{BACKUP_PREFIX}*{BACKUP_SUFFIX}{TEMP_SUFFIX}"):
            if path.is_file() and path.stat().st_mtime < now - STALE_TEMP_SECONDS:
                _remove_with_sidecars(path)
        return removed

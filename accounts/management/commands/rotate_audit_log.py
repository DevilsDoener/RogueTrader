"""Rotate the audit log file once, before the portal's workers start.

The portal runs several gunicorn worker processes that all append to
``AUDIT_LOG_FILE``. A rotating file handler inside each of them would race
(records land in an already-rotated file, the oldest file is pushed out early),
so the handler only appends (``accounts.auditlog.AuditFileHandler``) and the
rotation is done here, from the container's start command, while no worker is
running yet.

``audit.log`` becomes ``audit.log.1``, ``.1`` becomes ``.2`` and so on; the
file beyond ``AUDIT_LOG_BACKUP_COUNT`` is deleted. Everything is kept
owner-only (0600). This command never fails the boot: any problem is reported
as a warning on stderr and the exit status stays 0.
"""

import contextlib
import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


def _rotated(path: Path, number: int) -> Path:
    return path.with_name(f"{path.name}.{number}")


def rotate(path: Path, max_bytes: int, backup_count: int) -> bool:
    """Rotate ``path`` if it is larger than ``max_bytes``; True if it did."""
    try:
        size = path.stat().st_size
    except FileNotFoundError:
        return False
    if size <= max_bytes:
        return False

    if backup_count < 1:
        path.unlink()
    else:
        _rotated(path, backup_count).unlink(missing_ok=True)
        for number in range(backup_count - 1, 0, -1):
            source = _rotated(path, number)
            if source.exists():
                source.replace(_rotated(path, number + 1))
        path.replace(_rotated(path, 1))

    # A fresh, empty, owner-only file for the workers to append to.
    os.close(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600))
    for number in range(1, backup_count + 1):
        with contextlib.suppress(OSError):
            _rotated(path, number).chmod(0o600)
    with contextlib.suppress(OSError):
        path.chmod(0o600)
    return True


class Command(BaseCommand):
    help = "Rotate AUDIT_LOG_FILE (audit.log.1 ... .N) when it exceeds the size limit."

    def add_arguments(self, parser):
        parser.add_argument("--max-bytes", type=int, default=None)
        parser.add_argument("--backup-count", type=int, default=None)

    def handle(self, *args, **options):
        try:
            self._run(options)
        except Exception as error:  # noqa: BLE001 -- the boot must go on whatever happens here
            self.stderr.write(f"rotate_audit_log: warning: {error!r}; audit log not rotated")

    def _run(self, options):
        if not settings.AUDIT_LOG_FILE:
            self.stdout.write("rotate_audit_log: no AUDIT_LOG_FILE configured; nothing to do.")
            return
        max_bytes = options["max_bytes"]
        if max_bytes is None:
            max_bytes = settings.AUDIT_LOG_MAX_BYTES
        backup_count = options["backup_count"]
        if backup_count is None:
            backup_count = settings.AUDIT_LOG_BACKUP_COUNT
        path = Path(settings.AUDIT_LOG_FILE)
        if rotate(path, max_bytes, backup_count):
            self.stdout.write(f"rotate_audit_log: rotated {path}.")

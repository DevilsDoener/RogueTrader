"""Durable storage for the ``accounts.audit`` records."""
import contextlib
import os
from logging.handlers import WatchedFileHandler
from pathlib import Path


class AuditFileHandler(WatchedFileHandler):
    """An append-only log file that is only touched when a record arrives.

    ``config/settings.py`` builds the logging config in every process that
    loads the settings -- including the backup container, which mounts the
    data volume read-only and never writes an audit record. Creating the
    directory and opening the file lazily (and tolerating a failure, which
    ``logging`` reports on stderr without raising) keeps those processes, and
    the test suite, from needing a writable log directory.

    The handler never rotates. gunicorn runs several worker processes that all
    append to this file, and in-process rotation is not safe across processes.
    Rotation happens once per container start, before gunicorn forks, in
    ``manage.py rotate_audit_log``. Being a ``WatchedFileHandler``, a worker
    reopens the file by itself if it was moved away or replaced meanwhile
    (for example by an operator running that command by hand).
    """

    def __init__(self, filename, **kwargs):
        super().__init__(filename, delay=True, encoding="utf-8", **kwargs)

    def _open(self):
        path = Path(self.baseFilename)
        path.parent.mkdir(parents=True, exist_ok=True)
        # The log names accounts and addresses: owner-only, not the umask default.
        # Created (also after a rotation) with 0600 before the stream opens it;
        # a file left over from an older version is tightened too.
        os.close(os.open(self.baseFilename, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600))
        # Not ours to change (read-only volume, foreign owner): tolerated.
        with contextlib.suppress(OSError):
            path.chmod(0o600)
        return super()._open()

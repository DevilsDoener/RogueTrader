"""Durable storage for the ``accounts.audit`` records."""
import os
from logging.handlers import RotatingFileHandler


class AuditFileHandler(RotatingFileHandler):
    """A size-rotating log file that is only touched when a record arrives.

    ``config/settings.py`` builds the logging config in every process that
    loads the settings -- including the backup container, which mounts the
    data volume read-only and never writes an audit record. Creating the
    directory and opening the file lazily (and tolerating a failure, which
    ``logging`` reports on stderr without raising) keeps those processes, and
    the test suite, from needing a writable log directory.
    """

    def __init__(self, filename, **kwargs):
        super().__init__(filename, delay=True, encoding="utf-8", **kwargs)

    def _open(self):
        os.makedirs(os.path.dirname(self.baseFilename), exist_ok=True)
        # The log names accounts and addresses: owner-only, not the umask default.
        # Created (also after a rotation) with 0600 before the stream opens it;
        # a file left over from an older version is tightened too.
        os.close(os.open(self.baseFilename, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600))
        try:
            os.chmod(self.baseFilename, 0o600)
        except OSError:  # not ours to change (read-only volume, foreign owner)
            pass
        return super()._open()

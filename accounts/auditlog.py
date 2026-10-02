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
        return super()._open()

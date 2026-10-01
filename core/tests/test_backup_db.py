import os
import sqlite3
import time
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings


@pytest.fixture
def live_db(tmp_path, monkeypatch):
    path = tmp_path / "live.sqlite3"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE note (id INTEGER PRIMARY KEY, body TEXT)")
    connection.execute("INSERT INTO note (body) VALUES ('Hallo Welt')")
    connection.commit()
    connection.close()
    monkeypatch.setitem(settings.DATABASES["default"], "NAME", str(path))
    return path


def _backups(directory: Path):
    return sorted(directory.glob("db-*.sqlite3"))


def test_backup_creates_a_valid_copy_containing_the_data(live_db, tmp_path, capsys):
    target_dir = tmp_path / "backups"
    call_command("backup_db", backup_dir=str(target_dir))

    (backup,) = _backups(target_dir)
    assert backup.name.startswith("db-") and backup.suffix == ".sqlite3"
    connection = sqlite3.connect(backup)
    try:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute("SELECT body FROM note").fetchall() == [("Hallo Welt",)]
    finally:
        connection.close()
    assert "integrity_check: ok" in capsys.readouterr().out


def test_backup_uses_backup_dir_setting_and_leaves_live_db_untouched(live_db, tmp_path):
    target_dir = tmp_path / "from-settings" / "nested"
    before = (live_db.read_bytes(), live_db.stat().st_mtime_ns)
    with override_settings(BACKUP_DIR=target_dir):
        call_command("backup_db")
    assert len(_backups(target_dir)) == 1
    assert (live_db.read_bytes(), live_db.stat().st_mtime_ns) == before


def test_backup_prunes_old_files_by_mtime_and_keeps_recent_ones(live_db, tmp_path):
    target_dir = tmp_path / "backups"
    target_dir.mkdir()
    old = target_dir / "db-20200101-000000.sqlite3"
    recent = target_dir / "db-20990101-000000.sqlite3"
    unrelated = target_dir / "notes.txt"
    for path in (old, recent, unrelated):
        path.write_bytes(b"x")
    long_ago = time.time() - 30 * 86400
    os.utime(old, (long_ago, long_ago))
    os.utime(unrelated, (long_ago, long_ago))

    with override_settings(BACKUP_KEEP_DAYS=14):
        call_command("backup_db", backup_dir=str(target_dir))

    assert not old.exists()
    assert recent.exists()
    assert unrelated.exists()
    assert len(_backups(target_dir)) == 2  # the recent one plus the new copy


def test_backup_keep_days_option_overrides_setting(live_db, tmp_path):
    target_dir = tmp_path / "backups"
    target_dir.mkdir()
    middling = target_dir / "db-20200101-000000.sqlite3"
    middling.write_bytes(b"x")
    five_days_ago = time.time() - 5 * 86400
    os.utime(middling, (five_days_ago, five_days_ago))

    call_command("backup_db", backup_dir=str(target_dir), keep_days=3)

    assert not middling.exists()


def test_backup_with_a_corrupt_copy_fails_and_removes_the_copy(live_db, tmp_path, monkeypatch):
    from core.management.commands import backup_db

    monkeypatch.setattr(
        backup_db, "_integrity_check", lambda path: ["row 1 missing from index x"]
    )
    target_dir = tmp_path / "backups"
    with pytest.raises(CommandError, match="Integrity check failed"):
        call_command("backup_db", backup_dir=str(target_dir))
    assert _backups(target_dir) == []


def test_backup_fails_when_the_database_file_is_missing(tmp_path, monkeypatch):
    missing = tmp_path / "nope.sqlite3"
    monkeypatch.setitem(settings.DATABASES["default"], "NAME", str(missing))
    with pytest.raises(CommandError, match="not found"):
        call_command("backup_db", backup_dir=str(tmp_path / "b"))
    assert not missing.exists()

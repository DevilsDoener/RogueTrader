import os
import sqlite3
import stat
import sys
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


# ---- Private, atomic, session-free backups --------------------------------


@pytest.fixture
def live_db_with_sessions(live_db):
    connection = sqlite3.connect(live_db)
    connection.execute(
        "CREATE TABLE django_session (session_key TEXT PRIMARY KEY, session_data TEXT, expire_date TEXT)"
    )
    connection.executemany(
        "INSERT INTO django_session VALUES (?, ?, '2099-01-01')",
        [("k1", "secret-a"), ("k2", "secret-b")],
    )
    connection.commit()
    connection.close()
    return live_db


def _scalar(path, sql):
    connection = sqlite3.connect(path)
    try:
        return connection.execute(sql).fetchone()[0]
    finally:
        connection.close()


def test_backup_copy_has_no_login_sessions_but_keeps_the_data(live_db_with_sessions, tmp_path):
    target_dir = tmp_path / "backups"
    call_command("backup_db", backup_dir=str(target_dir))

    (backup,) = _backups(target_dir)
    assert _scalar(backup, "SELECT COUNT(*) FROM django_session") == 0
    assert _scalar(backup, "SELECT body FROM note") == "Hallo Welt"
    assert b"secret-a" not in backup.read_bytes()  # vacuumed, not just deleted
    # The live database keeps its sessions: the backup never writes to it.
    assert _scalar(live_db_with_sessions, "SELECT COUNT(*) FROM django_session") == 2


def test_a_failed_copy_leaves_no_backup_file_behind(live_db, tmp_path, monkeypatch):
    from core.management.commands import backup_db

    def disk_full(source, target):
        Path(target).write_bytes(b"half a database")
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(backup_db.Command, "_copy", staticmethod(disk_full))
    target_dir = tmp_path / "backups"
    with pytest.raises(OSError):
        call_command("backup_db", backup_dir=str(target_dir))
    assert list(target_dir.iterdir()) == []


def test_an_interrupted_run_leaves_no_backup_file_behind(live_db, tmp_path, monkeypatch):
    from core.management.commands import backup_db

    def killed(source, target):
        Path(target).write_bytes(b"half a database")
        raise KeyboardInterrupt

    monkeypatch.setattr(backup_db.Command, "_copy", staticmethod(killed))
    target_dir = tmp_path / "backups"
    with pytest.raises(KeyboardInterrupt):
        call_command("backup_db", backup_dir=str(target_dir))
    assert list(target_dir.iterdir()) == []


def test_the_final_name_only_exists_after_the_integrity_check(live_db, tmp_path, monkeypatch):
    from core.management.commands import backup_db

    seen = {}
    real_check = backup_db._integrity_check

    def spying_check(path):
        seen["checked"] = path.name
        seen["final_exists_during_check"] = any(path.parent.glob("db-*.sqlite3"))
        return real_check(path)

    monkeypatch.setattr(backup_db, "_integrity_check", spying_check)
    target_dir = tmp_path / "backups"
    call_command("backup_db", backup_dir=str(target_dir))

    assert seen["checked"].endswith(".sqlite3.tmp")
    assert seen["final_exists_during_check"] is False
    assert len(_backups(target_dir)) == 1
    assert list(target_dir.glob("*.tmp")) == []


def test_stale_temp_files_of_a_killed_run_are_cleaned_up(live_db, tmp_path):
    target_dir = tmp_path / "backups"
    target_dir.mkdir()
    stale = target_dir / "db-20200101-000000.sqlite3.tmp"
    fresh = target_dir / "db-20990101-000000.sqlite3.tmp"
    stale.write_bytes(b"x")
    fresh.write_bytes(b"x")
    long_ago = time.time() - 7200
    os.utime(stale, (long_ago, long_ago))

    call_command("backup_db", backup_dir=str(target_dir))

    assert not stale.exists()
    assert fresh.exists()  # could belong to a run that is still going
    assert len(_backups(target_dir)) == 1


def test_the_copy_is_chmodded_owner_only_and_the_umask_is_restored(live_db, tmp_path, monkeypatch):
    modes = []
    real_chmod = os.chmod
    monkeypatch.setattr(os, "chmod", lambda path, mode, *a, **kw: (modes.append(mode), real_chmod(path, mode, *a, **kw))[1])
    before = os.umask(0o022)
    try:
        call_command("backup_db", backup_dir=str(tmp_path / "backups"))
        restored = os.umask(0o022)
        if sys.platform != "win32":  # Windows only honours the owner write bit
            assert restored == 0o022
    finally:
        os.umask(before)
    assert 0o600 in modes


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes")
def test_backup_files_and_new_directory_are_owner_only(live_db, tmp_path):
    target_dir = tmp_path / "private" / "backups"
    call_command("backup_db", backup_dir=str(target_dir))

    (backup,) = _backups(target_dir)
    assert stat.S_IMODE(backup.stat().st_mode) == 0o600
    assert stat.S_IMODE(target_dir.stat().st_mode) == 0o700

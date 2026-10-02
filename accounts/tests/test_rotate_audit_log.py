"""``manage.py rotate_audit_log``: rotation once per container start."""
import os
from pathlib import Path

import pytest
from django.core.management import call_command

from accounts.management.commands import rotate_audit_log

POSIX = os.name != "nt"


def _mode(path: Path) -> int:
    return path.stat().st_mode & 0o777


def _run(tmp_path, settings, capsys, *args, **kwargs):
    settings.AUDIT_LOG_FILE = str(tmp_path / "audit.log")
    call_command("rotate_audit_log", *args, **kwargs)
    return capsys.readouterr()


def test_a_small_log_is_left_alone(tmp_path, settings, capsys):
    log = tmp_path / "audit.log"
    log.write_text("x" * 100, encoding="utf-8")

    _run(tmp_path, settings, capsys, max_bytes=100, backup_count=3)

    assert log.read_text(encoding="utf-8") == "x" * 100
    assert sorted(path.name for path in tmp_path.iterdir()) == ["audit.log"]


def test_a_log_over_the_limit_moves_to_dot_one_and_a_new_file_starts(tmp_path, settings, capsys):
    log = tmp_path / "audit.log"
    log.write_text("old" * 50, encoding="utf-8")

    out = _run(tmp_path, settings, capsys, max_bytes=100, backup_count=3)

    assert (tmp_path / "audit.log.1").read_text(encoding="utf-8") == "old" * 50
    assert log.exists() and log.stat().st_size == 0
    assert "rotated" in out.out


def test_the_backups_shift_and_the_oldest_falls_off(tmp_path, settings, capsys):
    (tmp_path / "audit.log.1").write_text("one", encoding="utf-8")
    (tmp_path / "audit.log.2").write_text("two", encoding="utf-8")
    (tmp_path / "audit.log.3").write_text("three", encoding="utf-8")
    (tmp_path / "audit.log").write_text("current" * 30, encoding="utf-8")

    _run(tmp_path, settings, capsys, max_bytes=100, backup_count=3)

    names = sorted(path.name for path in tmp_path.iterdir())
    assert names == ["audit.log", "audit.log.1", "audit.log.2", "audit.log.3"]
    assert (tmp_path / "audit.log.1").read_text(encoding="utf-8") == "current" * 30
    assert (tmp_path / "audit.log.2").read_text(encoding="utf-8") == "one"
    assert (tmp_path / "audit.log.3").read_text(encoding="utf-8") == "two"


def test_with_a_gap_in_the_backups_the_rest_still_shifts(tmp_path, settings, capsys):
    (tmp_path / "audit.log.2").write_text("two", encoding="utf-8")
    (tmp_path / "audit.log").write_text("current" * 30, encoding="utf-8")

    _run(tmp_path, settings, capsys, max_bytes=100, backup_count=5)

    assert (tmp_path / "audit.log.3").read_text(encoding="utf-8") == "two"
    assert (tmp_path / "audit.log.1").read_text(encoding="utf-8") == "current" * 30


def test_a_backup_count_of_zero_just_starts_over(tmp_path, settings, capsys):
    (tmp_path / "audit.log").write_text("x" * 500, encoding="utf-8")

    _run(tmp_path, settings, capsys, max_bytes=100, backup_count=0)

    assert sorted(path.name for path in tmp_path.iterdir()) == ["audit.log"]
    assert (tmp_path / "audit.log").stat().st_size == 0


def test_the_configured_limits_are_the_defaults(tmp_path, settings, capsys):
    settings.AUDIT_LOG_MAX_BYTES = 10
    settings.AUDIT_LOG_BACKUP_COUNT = 1
    (tmp_path / "audit.log").write_text("x" * 11, encoding="utf-8")

    _run(tmp_path, settings, capsys)

    assert (tmp_path / "audit.log.1").exists()
    assert not (tmp_path / "audit.log.2").exists()


def test_a_missing_log_or_directory_is_not_an_error(tmp_path, settings, capsys):
    settings.AUDIT_LOG_FILE = str(tmp_path / "nowhere" / "audit.log")

    call_command("rotate_audit_log")

    assert capsys.readouterr().err == ""
    assert not (tmp_path / "nowhere").exists()


def test_without_an_audit_log_file_it_does_nothing(settings, capsys):
    settings.AUDIT_LOG_FILE = None

    call_command("rotate_audit_log")

    assert "nothing to do" in capsys.readouterr().out


def test_an_error_is_a_warning_and_never_raises(tmp_path, settings, capsys, monkeypatch):
    (tmp_path / "audit.log").write_text("x" * 500, encoding="utf-8")

    def broken(*args, **kwargs):
        raise PermissionError("read-only volume")

    monkeypatch.setattr(rotate_audit_log, "rotate", broken)

    out = _run(tmp_path, settings, capsys, max_bytes=100, backup_count=2)

    assert "warning" in out.err and "read-only volume" in out.err


@pytest.mark.skipif(not POSIX, reason="POSIX file modes")
def test_all_files_are_owner_only_after_a_rotation(tmp_path, settings, capsys):
    old = tmp_path / "audit.log"
    old.write_text("x" * 500, encoding="utf-8")
    old.chmod(0o644)  # a file from an older version
    (tmp_path / "audit.log.1").write_text("older", encoding="utf-8")
    (tmp_path / "audit.log.1").chmod(0o644)

    _run(tmp_path, settings, capsys, max_bytes=100, backup_count=3)

    for name in ("audit.log", "audit.log.1", "audit.log.2"):
        assert _mode(tmp_path / name) == 0o600, name


def test_the_new_file_is_created_with_the_owner_only_mode(tmp_path, settings, capsys, monkeypatch):
    modes = []
    real_open = os.open

    def recording_open(path, flags, mode=0o777, *args, **kwargs):
        modes.append(mode)
        return real_open(path, flags, mode, *args, **kwargs)

    monkeypatch.setattr(rotate_audit_log.os, "open", recording_open)
    (tmp_path / "audit.log").write_text("x" * 500, encoding="utf-8")

    _run(tmp_path, settings, capsys, max_bytes=100, backup_count=1)

    assert modes == [0o600]

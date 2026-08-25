import sqlite3
from datetime import UTC, datetime

import pytest

from affiliate_mate.ops_backup import (
    backup_database,
    inspect_sqlite,
    restore_database,
    sha256_file,
    sqlite_readonly_uri,
)


def now() -> datetime:
    return datetime(2026, 1, 1, tzinfo=UTC)


def make_database(path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(
            """
            CREATE TABLE parent(id INTEGER PRIMARY KEY);
            CREATE TABLE child(
                id INTEGER PRIMARY KEY,
                parent_id INTEGER NOT NULL REFERENCES parent(id)
            );
            INSERT INTO parent(id) VALUES (1);
            INSERT INTO child(id, parent_id) VALUES (1, 1);
            """
        )
        connection.commit()
    finally:
        connection.close()


def test_backup_and_restore_validate_sqlite_and_hash(tmp_path) -> None:
    source = tmp_path / "source database.sqlite3"
    backup = tmp_path / "backups" / "snapshot.sqlite3"
    restored = tmp_path / "restore" / "restored.sqlite3"
    make_database(source)

    manifest = backup_database(source, backup, created_at=now())
    assert manifest.health.ok
    assert manifest.sha256 == sha256_file(backup)
    assert manifest.byte_length == backup.stat().st_size
    assert "parent" in manifest.health.tables

    health = restore_database(
        backup,
        restored,
        expected_sha256=manifest.sha256,
    )
    assert health.ok
    assert sha256_file(restored) == manifest.sha256


def test_backup_refuses_to_overwrite_without_explicit_flag(tmp_path) -> None:
    source = tmp_path / "source.sqlite3"
    destination = tmp_path / "backup.sqlite3"
    make_database(source)
    destination.write_bytes(b"occupied")
    with pytest.raises(FileExistsError):
        backup_database(source, destination, created_at=now())


def test_restore_refuses_wrong_hash_before_replacing_destination(tmp_path) -> None:
    source = tmp_path / "source.sqlite3"
    backup = tmp_path / "backup.sqlite3"
    destination = tmp_path / "destination.sqlite3"
    make_database(source)
    manifest = backup_database(source, backup, created_at=now())
    destination.write_bytes(b"keep-me")

    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        restore_database(
            backup,
            destination,
            expected_sha256="0" * 64,
            overwrite=True,
        )
    assert destination.read_bytes() == b"keep-me"
    assert manifest.sha256 != "0" * 64


def test_readonly_uri_handles_spaces_and_database_inspection(tmp_path) -> None:
    path = tmp_path / "folder with space" / "db.sqlite3"
    path.parent.mkdir()
    make_database(path)
    uri = sqlite_readonly_uri(path)
    assert "%20" in uri
    health = inspect_sqlite(path)
    assert health.ok

"""Validated SQLite backup/restore primitives with content-addressed manifests."""

from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

BACKUP_SCHEMA_VERSION = "affiliate-mate.sqlite-backup.v1"


@dataclass(frozen=True, slots=True)
class DatabaseHealth:
    path: str
    integrity_ok: bool
    integrity_message: str
    foreign_key_violations: int
    tables: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return self.integrity_ok and self.foreign_key_violations == 0

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "integrity_ok": self.integrity_ok,
            "integrity_message": self.integrity_message,
            "foreign_key_violations": self.foreign_key_violations,
            "tables": list(self.tables),
            "ok": self.ok,
        }


@dataclass(frozen=True, slots=True)
class BackupManifest:
    file_name: str
    sha256: str
    byte_length: int
    created_at: datetime
    health: DatabaseHealth

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": BACKUP_SCHEMA_VERSION,
            "file_name": self.file_name,
            "sha256": self.sha256,
            "byte_length": self.byte_length,
            "created_at": self.created_at.astimezone(UTC).isoformat(),
            "health": self.health.to_dict(),
        }


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_sqlite(path: str | Path) -> DatabaseHealth:
    target = Path(path).expanduser()
    if not target.is_file():
        raise FileNotFoundError(f"SQLite database does not exist: {target}")
    uri = f"file:{target.resolve().as_posix()}?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as exc:
        raise RuntimeError(f"cannot open SQLite database: {target}") from exc
    try:
        integrity_rows = connection.execute("PRAGMA integrity_check").fetchall()
        messages = tuple(str(row[0]) for row in integrity_rows)
        integrity_ok = messages == ("ok",)
        integrity_message = "; ".join(messages)
        foreign_rows = connection.execute("PRAGMA foreign_key_check").fetchall()
        table_rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        ).fetchall()
        tables = tuple(str(row[0]) for row in table_rows)
    finally:
        connection.close()
    return DatabaseHealth(
        path=str(target),
        integrity_ok=integrity_ok,
        integrity_message=integrity_message,
        foreign_key_violations=len(foreign_rows),
        tables=tables,
    )


def backup_database(
    source: str | Path,
    destination: str | Path,
    *,
    created_at: datetime,
    overwrite: bool = False,
) -> BackupManifest:
    """Create a consistent SQLite online backup and validate the produced bytes."""

    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("created_at must be timezone-aware")
    source_path = Path(source).expanduser()
    destination_path = Path(destination).expanduser()
    if not source_path.is_file():
        raise FileNotFoundError(f"source database does not exist: {source_path}")
    if source_path.resolve() == destination_path.resolve():
        raise ValueError("backup destination must differ from source database")
    if destination_path.exists() and not overwrite:
        raise FileExistsError(f"backup destination already exists: {destination_path}")
    destination_path.parent.mkdir(parents=True, exist_ok=True)

    fd, temp_name = tempfile.mkstemp(
        prefix=f".{destination_path.name}.",
        suffix=".tmp",
        dir=destination_path.parent,
    )
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        source_connection = sqlite3.connect(source_path)
        destination_connection = sqlite3.connect(temp_path)
        try:
            source_connection.backup(destination_connection)
            destination_connection.commit()
        finally:
            destination_connection.close()
            source_connection.close()
        health = inspect_sqlite(temp_path)
        if not health.ok:
            raise RuntimeError(
                "backup validation failed: "
                f"integrity={health.integrity_message!r}, "
                f"foreign_key_violations={health.foreign_key_violations}"
            )
        os.replace(temp_path, destination_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()

    final_health = inspect_sqlite(destination_path)
    return BackupManifest(
        file_name=destination_path.name,
        sha256=sha256_file(destination_path),
        byte_length=destination_path.stat().st_size,
        created_at=created_at,
        health=final_health,
    )


def restore_database(
    backup: str | Path,
    destination: str | Path,
    *,
    expected_sha256: str,
    overwrite: bool = False,
) -> DatabaseHealth:
    """Verify, stage, validate, and atomically replace a SQLite destination."""

    backup_path = Path(backup).expanduser()
    destination_path = Path(destination).expanduser()
    if not backup_path.is_file():
        raise FileNotFoundError(f"backup database does not exist: {backup_path}")
    if len(expected_sha256) != 64 or any(
        char not in "0123456789abcdef" for char in expected_sha256
    ):
        raise ValueError("expected_sha256 must be a lowercase SHA-256 digest")
    actual = sha256_file(backup_path)
    if actual != expected_sha256:
        raise ValueError(f"backup SHA-256 mismatch: expected {expected_sha256}, got {actual}")
    backup_health = inspect_sqlite(backup_path)
    if not backup_health.ok:
        raise RuntimeError("refusing to restore an unhealthy SQLite backup")
    if destination_path.exists() and not overwrite:
        raise FileExistsError(f"restore destination already exists: {destination_path}")
    if backup_path.resolve() == destination_path.resolve():
        raise ValueError("restore destination must differ from backup path")
    destination_path.parent.mkdir(parents=True, exist_ok=True)

    fd, temp_name = tempfile.mkstemp(
        prefix=f".{destination_path.name}.",
        suffix=".restore",
        dir=destination_path.parent,
    )
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        shutil.copyfile(backup_path, temp_path)
        staged_health = inspect_sqlite(temp_path)
        if not staged_health.ok:
            raise RuntimeError("staged restore failed SQLite validation")
        os.replace(temp_path, destination_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()
    return inspect_sqlite(destination_path)

"""Deterministic, content-addressed release manifests for v1 artifacts."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

RELEASE_MANIFEST_SCHEMA_VERSION = "affiliate-mate.release-manifest.v1"


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative(value: str) -> str:
    path = PurePosixPath(value)
    if (
        not value.strip()
        or path.is_absolute()
        or ".." in path.parts
        or "." == value
        or "\\" in value
    ):
        raise ValueError("release artifact path must be a safe relative POSIX path")
    return path.as_posix()


def _require_commit_sha(value: str) -> str:
    sha = value.strip().lower()
    if len(sha) != 40 or any(char not in "0123456789abcdef" for char in sha):
        raise ValueError("commit_sha must be a 40-character lowercase Git SHA")
    return sha


def _require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("created_at must be timezone-aware")
    return value.astimezone(UTC)


def build_release_manifest(
    paths: list[str | Path] | tuple[str | Path, ...],
    *,
    root: str | Path,
    version: str,
    commit_sha: str,
    created_at: datetime,
) -> dict[str, object]:
    """Build a stable manifest over exact bytes below ``root``."""

    base = Path(root).expanduser().resolve()
    artifacts: list[dict[str, object]] = []
    seen: set[str] = set()
    for raw in paths:
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = base / candidate
        resolved = candidate.resolve()
        try:
            relative = resolved.relative_to(base).as_posix()
        except ValueError as exc:
            raise ValueError(f"release artifact escapes root: {raw}") from exc
        relative = _safe_relative(relative)
        if relative in seen:
            raise ValueError(f"duplicate release artifact: {relative}")
        if not resolved.is_file():
            raise FileNotFoundError(resolved)
        seen.add(relative)
        artifacts.append(
            {
                "path": relative,
                "size_bytes": resolved.stat().st_size,
                "sha256": sha256_file(resolved),
            }
        )
    if not artifacts:
        raise ValueError("release manifest requires at least one artifact")
    return {
        "schema_version": RELEASE_MANIFEST_SCHEMA_VERSION,
        "version": version.strip(),
        "commit_sha": _require_commit_sha(commit_sha),
        "created_at": _require_aware(created_at).isoformat(),
        "artifacts": sorted(artifacts, key=lambda item: str(item["path"])),
    }


def validate_release_manifest(payload: dict[str, Any]) -> dict[str, object]:
    expected = {"schema_version", "version", "commit_sha", "created_at", "artifacts"}
    unknown = sorted(set(payload) - expected)
    missing = sorted(expected - set(payload))
    if unknown or missing:
        raise ValueError(f"release manifest keys mismatch; missing={missing}, unknown={unknown}")
    if payload["schema_version"] != RELEASE_MANIFEST_SCHEMA_VERSION:
        raise ValueError(f"unsupported release manifest schema: {payload['schema_version']}")
    version = str(payload["version"]).strip()
    if not version:
        raise ValueError("release manifest version must not be empty")
    commit_sha = _require_commit_sha(str(payload["commit_sha"]))
    created_at = datetime.fromisoformat(str(payload["created_at"]))
    _require_aware(created_at)
    raw_artifacts = payload["artifacts"]
    if not isinstance(raw_artifacts, list) or not raw_artifacts:
        raise ValueError("release manifest artifacts must be a non-empty array")
    normalized: list[dict[str, object]] = []
    seen: set[str] = set()
    for index, item in enumerate(raw_artifacts):
        if not isinstance(item, dict):
            raise ValueError(f"release artifact {index} must be an object")
        if set(item) != {"path", "size_bytes", "sha256"}:
            raise ValueError(f"release artifact {index} keys are invalid")
        path = _safe_relative(str(item["path"]))
        if path in seen:
            raise ValueError(f"duplicate release artifact: {path}")
        seen.add(path)
        size = item["size_bytes"]
        if not isinstance(size, int) or size < 0:
            raise ValueError(f"release artifact {path} has invalid size_bytes")
        digest = str(item["sha256"])
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError(f"release artifact {path} has invalid sha256")
        normalized.append({"path": path, "size_bytes": size, "sha256": digest})
    return {
        "schema_version": RELEASE_MANIFEST_SCHEMA_VERSION,
        "version": version,
        "commit_sha": commit_sha,
        "created_at": _require_aware(created_at).isoformat(),
        "artifacts": sorted(normalized, key=lambda item: str(item["path"])),
    }


def verify_release_manifest(payload: dict[str, Any], *, root: str | Path) -> dict[str, object]:
    manifest = validate_release_manifest(payload)
    base = Path(root).expanduser().resolve()
    checks: list[dict[str, object]] = []
    for item in manifest["artifacts"]:
        artifact = dict(item)
        path = base / str(artifact["path"])
        exists = path.is_file()
        size_ok = exists and path.stat().st_size == int(artifact["size_bytes"])
        digest_ok = exists and sha256_file(path) == artifact["sha256"]
        checks.append(
            {
                "path": artifact["path"],
                "exists": exists,
                "size_matches": size_ok,
                "sha256_matches": digest_ok,
                "passed": exists and size_ok and digest_ok,
            }
        )
    passed = all(bool(check["passed"]) for check in checks)
    return {
        "schema_version": "affiliate-mate.release-verification.v1",
        "passed": passed,
        "version": manifest["version"],
        "commit_sha": manifest["commit_sha"],
        "checks": checks,
    }

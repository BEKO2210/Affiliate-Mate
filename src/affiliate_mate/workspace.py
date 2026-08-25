"""Portable workspace/profile model for the Affiliate-Mate product experience."""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self

from . import __version__

WORKSPACE_SCHEMA_VERSION = "affiliate-mate.workspace.v1"
WORKSPACE_DIR = ".affiliate-mate"
WORKSPACE_FILE = "workspace.json"
_PROFILE_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


class WorkspaceError(ValueError):
    """Raised when workspace state is unsafe, ambiguous, or unsupported."""


def _strict_keys(payload: dict[str, object], allowed: set[str], context: str) -> None:
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise WorkspaceError(f"unknown {context} keys: {', '.join(unknown)}")


def _require_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise WorkspaceError(f"{field_name} must be a non-empty string")
    return value.strip()


def _safe_profile_name(value: object) -> str:
    name = _require_text(value, "profile name").lower()
    if not _PROFILE_RE.fullmatch(name):
        raise WorkspaceError(
            "profile name must be 1-64 lowercase letters, digits, '.', '_' or '-', "
            "starting with a letter or digit"
        )
    return name


def _safe_relative_path(value: object, field_name: str) -> str:
    raw = _require_text(value, field_name)
    path = Path(raw)
    if path.is_absolute() or raw.startswith("~"):
        raise WorkspaceError(f"{field_name} must be workspace-relative")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise WorkspaceError(f"{field_name} must not contain '.', '..', or empty path segments")
    return path.as_posix()


def _atomic_write_text(path: Path, text: str, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp = Path(raw_tmp)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        os.chmod(path, mode)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        tmp.unlink(missing_ok=True)
        raise


@dataclass(frozen=True, slots=True)
class WorkspaceProfile:
    name: str = "default"
    marketplace: str = "DE"
    config_path: str = f"{WORKSPACE_DIR}/config.json"
    database_path: str = f"{WORKSPACE_DIR}/state.sqlite3"
    data_dir: str = "data"
    artifacts_dir: str = "artifacts"

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _safe_profile_name(self.name))
        marketplace = _require_text(self.marketplace, "marketplace").upper()
        if len(marketplace) != 2 or not marketplace.isalpha():
            raise WorkspaceError("marketplace must be a two-letter code such as DE or US")
        object.__setattr__(self, "marketplace", marketplace)
        for field_name in ("config_path", "database_path", "data_dir", "artifacts_dir"):
            object.__setattr__(
                self,
                field_name,
                _safe_relative_path(getattr(self, field_name), field_name),
            )

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "marketplace": self.marketplace,
            "config_path": self.config_path,
            "database_path": self.database_path,
            "data_dir": self.data_dir,
            "artifacts_dir": self.artifacts_dir,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, object]) -> Self:
        _strict_keys(
            raw,
            {"name", "marketplace", "config_path", "database_path", "data_dir", "artifacts_dir"},
            "workspace profile",
        )
        required = {"name", "marketplace", "config_path", "database_path", "data_dir", "artifacts_dir"}
        missing = sorted(required - set(raw))
        if missing:
            raise WorkspaceError(f"missing workspace profile keys: {', '.join(missing)}")
        return cls(
            name=_require_text(raw["name"], "name"),
            marketplace=_require_text(raw["marketplace"], "marketplace"),
            config_path=_require_text(raw["config_path"], "config_path"),
            database_path=_require_text(raw["database_path"], "database_path"),
            data_dir=_require_text(raw["data_dir"], "data_dir"),
            artifacts_dir=_require_text(raw["artifacts_dir"], "artifacts_dir"),
        )


@dataclass(frozen=True, slots=True)
class WorkspaceManifest:
    active_profile: str
    profiles: tuple[WorkspaceProfile, ...]
    schema_version: str = WORKSPACE_SCHEMA_VERSION
    created_with: str = __version__

    def __post_init__(self) -> None:
        if self.schema_version != WORKSPACE_SCHEMA_VERSION:
            raise WorkspaceError(f"unsupported workspace schema: {self.schema_version}")
        active = _safe_profile_name(self.active_profile)
        object.__setattr__(self, "active_profile", active)
        names = [profile.name for profile in self.profiles]
        if not names:
            raise WorkspaceError("workspace must contain at least one profile")
        if len(names) != len(set(names)):
            raise WorkspaceError("workspace profile names must be unique")
        if active not in names:
            raise WorkspaceError(f"active profile does not exist: {active}")
        if not self.created_with.strip():
            raise WorkspaceError("created_with must not be empty")

    @property
    def profile(self) -> WorkspaceProfile:
        return self.get_profile(self.active_profile)

    def get_profile(self, name: str) -> WorkspaceProfile:
        normalized = _safe_profile_name(name)
        for profile in self.profiles:
            if profile.name == normalized:
                return profile
        raise WorkspaceError(f"workspace profile not found: {normalized}")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "created_with": self.created_with,
            "active_profile": self.active_profile,
            "profiles": [profile.to_dict() for profile in sorted(self.profiles, key=lambda item: item.name)],
        }

    @classmethod
    def from_dict(cls, raw: dict[str, object]) -> Self:
        _strict_keys(raw, {"schema_version", "created_with", "active_profile", "profiles"}, "workspace")
        required = {"schema_version", "created_with", "active_profile", "profiles"}
        missing = sorted(required - set(raw))
        if missing:
            raise WorkspaceError(f"missing workspace keys: {', '.join(missing)}")
        profiles_raw = raw["profiles"]
        if not isinstance(profiles_raw, list) or not all(isinstance(item, dict) for item in profiles_raw):
            raise WorkspaceError("profiles must be an array of objects")
        return cls(
            schema_version=_require_text(raw["schema_version"], "schema_version"),
            created_with=_require_text(raw["created_with"], "created_with"),
            active_profile=_require_text(raw["active_profile"], "active_profile"),
            profiles=tuple(WorkspaceProfile.from_dict(item) for item in profiles_raw),
        )


@dataclass(frozen=True, slots=True)
class Workspace:
    root: Path
    manifest: WorkspaceManifest

    @property
    def profile(self) -> WorkspaceProfile:
        return self.manifest.profile

    def resolve(self, relative: str) -> Path:
        safe = _safe_relative_path(relative, "workspace path")
        root = self.root.resolve()
        candidate = (root / safe).resolve(strict=False)
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise WorkspaceError(f"workspace path escapes root: {relative}") from exc
        return candidate

    @property
    def config_path(self) -> Path:
        return self.resolve(self.profile.config_path)

    @property
    def database_path(self) -> Path:
        return self.resolve(self.profile.database_path)

    @property
    def data_dir(self) -> Path:
        return self.resolve(self.profile.data_dir)

    @property
    def artifacts_dir(self) -> Path:
        return self.resolve(self.profile.artifacts_dir)

    def to_dict(self) -> dict[str, object]:
        return {
            "root": str(self.root.resolve()),
            "manifest": self.manifest.to_dict(),
            "resolved": {
                "config_path": str(self.config_path),
                "database_path": str(self.database_path),
                "data_dir": str(self.data_dir),
                "artifacts_dir": str(self.artifacts_dir),
            },
        }


def workspace_manifest_path(root: str | Path) -> Path:
    return Path(root).expanduser() / WORKSPACE_DIR / WORKSPACE_FILE


def load_workspace(root: str | Path, *, profile: str | None = None) -> Workspace:
    base = Path(root).expanduser()
    path = workspace_manifest_path(base)
    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise WorkspaceError(f"workspace manifest does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise WorkspaceError(f"workspace manifest is not valid JSON: {path}") from exc
    if not isinstance(raw, dict):
        raise WorkspaceError("workspace manifest root must be a JSON object")
    manifest = WorkspaceManifest.from_dict(raw)
    if profile is not None:
        selected = manifest.get_profile(profile)
        manifest = WorkspaceManifest(
            active_profile=selected.name,
            profiles=manifest.profiles,
            created_with=manifest.created_with,
        )
    return Workspace(root=base.resolve(), manifest=manifest)


def find_workspace(start: str | Path | None = None, *, profile: str | None = None) -> Workspace:
    current = Path.cwd() if start is None else Path(start).expanduser()
    current = current.resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if workspace_manifest_path(candidate).is_file():
            return load_workspace(candidate, profile=profile)
    raise WorkspaceError(f"no {WORKSPACE_DIR}/{WORKSPACE_FILE} found from {current} upward")


def _default_config(profile: WorkspaceProfile) -> dict[str, object]:
    return {
        "schema_version": "affiliate-mate.config.v1",
        "database": {"path": profile.database_path},
        "features": {"live_publishing": False},
        "observability": {"jsonl_path": f"{WORKSPACE_DIR}/events.jsonl"},
    }


def create_workspace(
    root: str | Path,
    *,
    profile_name: str = "default",
    marketplace: str = "DE",
    force: bool = False,
) -> Workspace:
    base = Path(root).expanduser().resolve()
    manifest_path = workspace_manifest_path(base)
    if manifest_path.exists() and not force:
        raise WorkspaceError(f"workspace already exists: {manifest_path}")
    profile = WorkspaceProfile(name=profile_name, marketplace=marketplace)
    manifest = WorkspaceManifest(active_profile=profile.name, profiles=(profile,))
    base.mkdir(parents=True, exist_ok=True)
    workspace_dir = base / WORKSPACE_DIR
    workspace_dir.mkdir(parents=True, exist_ok=True)
    (base / profile.data_dir).mkdir(parents=True, exist_ok=True)
    (base / profile.artifacts_dir).mkdir(parents=True, exist_ok=True)
    manifest_text = json.dumps(manifest.to_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    config_text = json.dumps(_default_config(profile), indent=2, sort_keys=True) + "\n"
    _atomic_write_text(base / profile.config_path, config_text)
    _atomic_write_text(manifest_path, manifest_text)
    return Workspace(root=base, manifest=manifest)


_DEMO_CSV = """product_id,title,marketplace,currency,price,commission_rate,monthly_searches,youtube_competition,buyer_intent,content_gap,evidence_quality,estimated_ctr,estimated_conversion_rate
DEMO-001,USB-C Desk Charger,DE,EUR,79.90,0.03,5400,42,76,68,82,0.045,0.035
DEMO-002,Compact Travel Tripod,DE,EUR,59.00,0.04,3600,35,71,74,78,0.042,0.031
DEMO-003,Premium Cable Organizer,DE,EUR,24.90,0.05,2100,61,63,57,75,0.038,0.028
"""


def create_demo_workspace(root: str | Path, *, force: bool = False) -> Workspace:
    """Create a deterministic credential-free workspace that can be analyzed immediately."""

    workspace = create_workspace(root, profile_name="demo", marketplace="DE", force=force)
    candidate_path = workspace.data_dir / "products.csv"
    readme_path = workspace.root / "DEMO.md"
    if candidate_path.exists() and not force:
        raise WorkspaceError(f"demo candidate file already exists: {candidate_path}")
    _atomic_write_text(candidate_path, _DEMO_CSV, mode=0o644)
    _atomic_write_text(
        readme_path,
        "# Affiliate-Mate demo workspace\n\n"
        "This workspace contains synthetic product candidates only. No credentials, live APIs, "
        "publishing, or income claims are involved. Run:\n\n"
        "    affiliate-mate analyze data/products.csv --include-rejected\n",
        mode=0o644,
    )
    return workspace

"""Deterministic SPDX 2.3 JSON SBOM generation for the active Python environment."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from importlib import metadata
from typing import Any

SPDX_VERSION = "SPDX-2.3"
SBOM_SCHEMA_VERSION = "affiliate-mate.sbom.v1"


def _spdx_id(name: str, version: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9.-]+", "-", f"{name}-{version}").strip("-")
    return f"SPDXRef-Package-{normalized or 'unknown'}"


def _environment_packages() -> list[dict[str, str]]:
    seen: dict[str, str] = {}
    for distribution in metadata.distributions():
        name = distribution.metadata.get("Name")
        if not name:
            continue
        normalized = name.lower().replace("_", "-")
        seen[normalized] = distribution.version
    return [
        {"name": name, "version": version}
        for name, version in sorted(seen.items())
    ]


def build_spdx_sbom(*, created_at: datetime) -> dict[str, Any]:
    """Build a deterministic package inventory when `created_at` is fixed."""

    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("created_at must be timezone-aware")
    packages = _environment_packages()
    fingerprint = hashlib.sha256(
        json.dumps(packages, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    spdx_packages: list[dict[str, object]] = []
    for package in packages:
        name = package["name"]
        version = package["version"]
        spdx_packages.append(
            {
                "SPDXID": _spdx_id(name, version),
                "name": name,
                "versionInfo": version,
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "licenseConcluded": "NOASSERTION",
                "licenseDeclared": "NOASSERTION",
                "copyrightText": "NOASSERTION",
                "externalRefs": [
                    {
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceType": "purl",
                        "referenceLocator": f"pkg:pypi/{name}@{version}",
                    }
                ],
            }
        )
    return {
        "affiliateMateSchema": SBOM_SCHEMA_VERSION,
        "spdxVersion": SPDX_VERSION,
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": "affiliate-mate-python-environment",
        "documentNamespace": f"https://affiliate-mate.invalid/sbom/{fingerprint}",
        "creationInfo": {
            "created": created_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "creators": ["Tool: Affiliate-Mate"],
        },
        "packages": spdx_packages,
    }


def sbom_json(*, created_at: datetime) -> str:
    return json.dumps(
        build_spdx_sbom(created_at=created_at),
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
    ) + "\n"

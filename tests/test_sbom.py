import json
from datetime import UTC, datetime

from affiliate_mate.sbom import build_spdx_sbom, sbom_json


def created_at() -> datetime:
    return datetime(2026, 1, 1, tzinfo=UTC)


def test_sbom_is_spdx_23_and_contains_affiliate_mate() -> None:
    payload = build_spdx_sbom(created_at=created_at())
    assert payload["spdxVersion"] == "SPDX-2.3"
    assert payload["affiliateMateSchema"] == "affiliate-mate.sbom.v1"
    packages = payload["packages"]
    assert isinstance(packages, list)
    assert any(package["name"] == "affiliate-mate" for package in packages)


def test_sbom_is_deterministic_for_fixed_environment_and_timestamp() -> None:
    first = sbom_json(created_at=created_at())
    second = sbom_json(created_at=created_at())
    assert first == second
    parsed = json.loads(first)
    assert parsed["creationInfo"]["created"] == "2026-01-01T00:00:00Z"

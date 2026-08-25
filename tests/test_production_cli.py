from __future__ import annotations

import json

from affiliate_mate.production_cli import main

from .production_helpers import PRODUCT_ID, build_approved_store


def test_production_cli_builds_script_package_and_dry_run(tmp_path) -> None:
    database = tmp_path / "research.sqlite3"
    store, _authorization = build_approved_store(database)
    store.close()

    script_path = tmp_path / "script.json"
    assert (
        main(
            [
                "script-template",
                str(database),
                PRODUCT_ID,
                "--title",
                "Example Product",
                "--language",
                "en",
                "--locale",
                "en-US",
                "--output",
                str(script_path),
            ]
        )
        == 0
    )

    package_path = tmp_path / "package.json"
    assert (
        main(
            [
                "package",
                str(database),
                PRODUCT_ID,
                str(script_path),
                "--title",
                "Example Product",
                "--affiliate-url",
                "https://example.invalid/affiliate",
                "--locale",
                "en-US",
                "--output",
                str(package_path),
            ]
        )
        == 0
    )

    package = json.loads(package_path.read_text(encoding="utf-8"))
    assert package["schema_version"] == "affiliate-mate.production-package.v1"
    assert package["research_digest"]

    signoff_path = tmp_path / "signoff.json"
    assert (
        main(
            [
                "signoff",
                str(package_path),
                "--actor",
                "editor",
                "--reason",
                "Package reviewed.",
                "--output",
                str(signoff_path),
            ]
        )
        == 0
    )

    output = tmp_path / "publish-plan.json"
    assert (
        main(
            [
                "publish-dry-run",
                str(database),
                PRODUCT_ID,
                str(package_path),
                "--signoff",
                str(signoff_path),
                "--allow-missing-artifacts",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["ready_for_live_adapter"] is True
    assert report["plan"]["side_effecting"] is False

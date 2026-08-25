from __future__ import annotations

import pytest

from affiliate_mate.disclosures import disclosure_template
from affiliate_mate.production_manifest import (
    build_production_package,
    sign_production_package,
    verify_signoff,
)
from affiliate_mate.production_planner import (
    build_dry_run_adapter_plans,
    build_thumbnail_brief,
    build_video_metadata,
)
from affiliate_mate.production_serialization import (
    package_from_dict,
    script_from_dict,
    signoff_from_dict,
)
from affiliate_mate.script_compiler import (
    StrictTemplateScriptGenerator,
    build_script_request,
    generate_and_validate_script,
)

from .production_helpers import build_approved_store


def test_production_contracts_round_trip(tmp_path) -> None:
    store, authorization = build_approved_store(tmp_path / "research.sqlite3")
    disclosure = disclosure_template(locale="en-US")
    request = build_script_request(
        store,
        authorization,
        working_title="Example",
        language="en",
        disclosure=disclosure,
    )
    script = generate_and_validate_script(
        store,
        authorization,
        request,
        StrictTemplateScriptGenerator(),
    )
    thumbnail = build_thumbnail_brief(product_title="Example")
    package = build_production_package(
        store,
        authorization,
        script=script,
        metadata=build_video_metadata(
            product_title="Example",
            affiliate_url="https://example.invalid/a",
            disclosure=disclosure,
        ),
        thumbnail=thumbnail,
        adapter_plans=build_dry_run_adapter_plans(script, thumbnail),
    )
    signoff = sign_production_package(package, actor="editor", reason="Checked.")

    restored_script = script_from_dict(script.to_dict())
    restored_package = package_from_dict(package.to_dict())
    restored_signoff = signoff_from_dict(signoff.to_dict())

    assert restored_script == script
    assert restored_package == package
    assert restored_signoff == signoff
    store.close()


def test_schema_mismatch_is_rejected(tmp_path) -> None:
    store, authorization = build_approved_store(tmp_path / "research.sqlite3")
    disclosure = disclosure_template(locale="en-US")
    request = build_script_request(
        store,
        authorization,
        working_title="Example",
        language="en",
        disclosure=disclosure,
    )
    script = StrictTemplateScriptGenerator().generate(request)
    payload = script.to_dict()
    payload["schema_version"] = "other"
    with pytest.raises(ValueError, match="unsupported schema_version"):
        script_from_dict(payload)
    store.close()


def test_package_mutation_invalidates_signoff(tmp_path) -> None:
    store, authorization = build_approved_store(tmp_path / "research.sqlite3")
    disclosure = disclosure_template(locale="en-US")
    request = build_script_request(
        store,
        authorization,
        working_title="Example",
        language="en",
        disclosure=disclosure,
    )
    script = StrictTemplateScriptGenerator().generate(request)
    thumbnail = build_thumbnail_brief(product_title="Example")
    package = build_production_package(
        store,
        authorization,
        script=script,
        metadata=build_video_metadata(
            product_title="Example",
            affiliate_url="https://example.invalid/a",
            disclosure=disclosure,
        ),
        thumbnail=thumbnail,
        adapter_plans=build_dry_run_adapter_plans(script, thumbnail),
    )
    signoff = sign_production_package(package, actor="editor", reason="Checked.")
    mutated = package.to_dict()
    mutated["metadata"]["title"] = "Changed title"
    restored = package_from_dict(mutated)
    assert restored.digest != package.digest
    assert verify_signoff(restored, signoff) is False
    store.close()

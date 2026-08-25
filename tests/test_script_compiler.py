from __future__ import annotations

import pytest

from affiliate_mate.disclosures import disclosure_template
from affiliate_mate.production_models import ScriptSegmentKind
from affiliate_mate.script_compiler import (
    StrictTemplateScriptGenerator,
    build_script_request,
    generate_and_validate_script,
)

from .production_helpers import PRODUCT_ID, build_approved_store


def test_script_request_exports_only_grounded_claims(tmp_path) -> None:
    store, authorization = build_approved_store(tmp_path / "research.sqlite3")
    disclosure = disclosure_template(locale="en-US")
    request = build_script_request(
        store,
        authorization,
        working_title="Example Product",
        language="en",
        disclosure=disclosure,
    )
    assert request.product_id == PRODUCT_ID
    assert [claim.claim_id for claim in request.claims] == ["claim-1"]
    assert request.claims[0].source_ids == ("source-1",)
    assert request.claims[0].source_locators == ("Specifications > Cable",)
    store.close()


def test_strict_template_generator_reuses_approved_claim_text(tmp_path) -> None:
    store, authorization = build_approved_store(tmp_path / "research.sqlite3")
    disclosure = disclosure_template(locale="en-US")
    request = build_script_request(
        store,
        authorization,
        working_title="Example Product",
        language="en",
        disclosure=disclosure,
    )
    script = generate_and_validate_script(
        store,
        authorization,
        request,
        StrictTemplateScriptGenerator(),
    )
    factual = [segment for segment in script.segments if segment.kind is ScriptSegmentKind.FACT]
    assert len(factual) == 1
    assert factual[0].text == "The cable is detachable."
    assert factual[0].claim_ids == ("claim-1",)
    assert disclosure.spoken in script.narration_text
    store.close()


def test_disclosure_templates_are_explicit() -> None:
    german = disclosure_template(locale="de-DE", network="amazon")
    english = disclosure_template(locale="en-US", network="amazon")
    assert "Affiliate" in german.spoken
    assert "affiliate" in english.spoken.lower()


def test_unknown_disclosure_locale_fails() -> None:
    with pytest.raises(ValueError, match="no built-in disclosure"):
        disclosure_template(locale="xx-XX")

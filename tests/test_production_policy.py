from __future__ import annotations

from datetime import UTC, datetime

import pytest

from affiliate_mate.production_models import ScriptDocument, ScriptSegment, ScriptSegmentKind
from affiliate_mate.production_policy import (
    ProductionAuthorizationError,
    ScriptGroundingError,
    assert_authorization_current,
    evaluate_production_authorization,
    validate_script_grounding,
)
from affiliate_mate.research_models import ResearchSource, SourceKind

from .production_helpers import PRODUCT_ID, build_approved_store


def test_production_authorization_binds_current_approval(tmp_path) -> None:
    store, authorization = build_approved_store(tmp_path / "research.sqlite3")
    check = evaluate_production_authorization(store, PRODUCT_ID)
    assert check.passed is True
    assert check.authorization is not None
    assert check.authorization.approval_event_id == authorization.approval_event_id
    assert check.authorization.research_digest == authorization.research_digest
    store.close()


def test_authorization_fails_closed_after_research_mutation(tmp_path) -> None:
    store, authorization = build_approved_store(tmp_path / "research.sqlite3")
    store.add_source(
        ResearchSource(
            source_id="source-new",
            product_id=PRODUCT_ID,
            kind=SourceKind.EDITORIAL,
            title="New evidence",
            locator="https://example.invalid/new",
            publisher="Another Publisher",
            retrieved_at=datetime(2026, 8, 25, 2, 0, tzinfo=UTC),
        )
    )
    with pytest.raises(ProductionAuthorizationError, match="research"):
        assert_authorization_current(store, authorization)
    store.close()


def test_script_grounding_rejects_unknown_claim(tmp_path) -> None:
    store, authorization = build_approved_store(tmp_path / "research.sqlite3")
    script = ScriptDocument(
        product_id=PRODUCT_ID,
        research_digest=authorization.research_digest,
        language="en",
        title="Example",
        segments=(
            ScriptSegment(
                segment_id="fact",
                kind=ScriptSegmentKind.FACT,
                text="Invented statement.",
                claim_ids=("unknown-claim",),
            ),
        ),
        generator="test",
        request_digest="0" * 64,
        created_at=datetime(2026, 8, 25, 2, 0, tzinfo=UTC),
    )
    with pytest.raises(ScriptGroundingError, match="unknown-claim"):
        validate_script_grounding(store, authorization, script)
    store.close()


def test_fact_segment_requires_claim_reference() -> None:
    with pytest.raises(ValueError, match="fact segments"):
        ScriptSegment(
            segment_id="fact",
            kind=ScriptSegmentKind.FACT,
            text="A factual statement.",
        )

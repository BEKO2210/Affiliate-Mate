from affiliate_mate.analysis import (
    ANALYSIS_SCHEMA_VERSION,
    analyze_inputs,
    build_automation_payload,
)
from affiliate_mate.io import CandidateInput
from affiliate_mate.models import ProductCandidate

REQUIRED = frozenset(
    {
        "monthly_searches",
        "youtube_competition",
        "buyer_intent",
        "content_gap",
        "evidence_quality",
    }
)


def candidate(product_id, **overrides):
    data = {
        "product_id": product_id,
        "title": product_id,
        "marketplace": "DE",
        "currency": "EUR",
        "price": 300.0,
        "commission_rate": 0.05,
        "monthly_searches": 3000,
        "youtube_competition": 30,
        "buyer_intent": 85,
        "content_gap": 75,
        "evidence_quality": 85,
        "estimated_ctr": 0.05,
        "estimated_conversion_rate": 0.03,
    }
    data.update(overrides)
    return ProductCandidate(**data)


def test_analysis_ranks_shortlisted_before_rejected():
    strong = CandidateInput(candidate("strong"), REQUIRED)
    weak = CandidateInput(candidate("weak", monthly_searches=5), REQUIRED)
    results = analyze_inputs([weak, strong])
    assert results[0].candidate.product_id == "strong"
    assert results[0].decision.accepted
    assert not results[1].decision.accepted


def test_automation_payload_has_versioned_schema_and_summary():
    results = analyze_inputs(
        [
            CandidateInput(candidate("strong"), REQUIRED),
            CandidateInput(candidate("weak", monthly_searches=5), REQUIRED),
        ]
    )
    payload = build_automation_payload(results)
    assert payload["schema_version"] == ANALYSIS_SCHEMA_VERSION
    assert payload["summary"] == {"total": 2, "shortlisted": 1, "rejected": 1}
    assert len(payload["results"]) == 2
    assert "sensitivity" in payload["results"][0]
    assert "gates" in payload["results"][0]["decision"]


def test_persisted_evidence_can_fill_missing_required_input_field(tmp_path):
    from datetime import UTC, datetime

    from affiliate_mate.evidence import EvidenceObservation, SQLiteEvidenceStore

    fields_missing_quality = REQUIRED - {"evidence_quality"}
    item = CandidateInput(candidate("strong", evidence_quality=50), fields_missing_quality)
    now = datetime(2026, 8, 25, 10, 0, tzinfo=UTC)
    with SQLiteEvidenceStore(tmp_path / "evidence.sqlite3") as store:
        store.add(
            EvidenceObservation(
                product_id="strong",
                signal="evidence_quality",
                value=90,
                source="manual-audit",
                observed_at=now,
            )
        )
        result = analyze_inputs([item], evidence_store=store, as_of=now)[0]
    assert result.decision.accepted
    assert "evidence_quality" in result.provided_fields
    assert result.evidence_resolution is not None
    assert result.evidence_resolution.applied_signals == {"evidence_quality"}

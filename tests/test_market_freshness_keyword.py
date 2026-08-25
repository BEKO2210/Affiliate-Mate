from datetime import UTC, datetime, timedelta

import pytest

from affiliate_mate.evidence import EvidenceObservation
from affiliate_mate.freshness import SignalFreshnessPolicy
from affiliate_mate.keyword_intelligence import CSVKeywordEvidenceProvider, load_keyword_demand_csv
from affiliate_mate.models import ProductCandidate


def _candidate() -> ProductCandidate:
    return ProductCandidate(
        product_id="p1",
        title="Example Camera",
        marketplace="DE",
        currency="EUR",
        price=199.0,
        commission_rate=0.03,
        monthly_searches=100,
        youtube_competition=50,
        buyer_intent=50,
        content_gap=50,
        evidence_quality=80,
    )


def test_freshness_policy_attaches_signal_specific_expiry() -> None:
    observed = datetime(2026, 8, 25, tzinfo=UTC)
    raw = EvidenceObservation(
        product_id="p1",
        signal="youtube_competition",
        value=42,
        source="test",
        observed_at=observed,
    )
    applied = SignalFreshnessPolicy().apply(raw)
    assert applied.expires_at == observed + timedelta(days=7)


def test_freshness_policy_preserves_explicit_expiry() -> None:
    observed = datetime(2026, 8, 25, tzinfo=UTC)
    explicit = observed + timedelta(hours=2)
    raw = EvidenceObservation(
        product_id="p1",
        signal="monthly_searches",
        value=100,
        source="test",
        observed_at=observed,
        expires_at=explicit,
    )
    assert SignalFreshnessPolicy().apply(raw).expires_at == explicit


def test_keyword_provider_uses_latest_snapshot_and_emits_two_signals(tmp_path) -> None:
    path = tmp_path / "keywords.csv"
    path.write_text(
        "product_id,marketplace,monthly_searches,buyer_intent,observed_at,source,confidence\n"
        "p1,DE,900,70,2026-08-01T00:00:00Z,export-a,0.7\n"
        "p1,DE,1500,82,2026-08-20T00:00:00Z,export-b,0.9\n",
        encoding="utf-8",
    )
    provider = CSVKeywordEvidenceProvider.from_csv(path)
    observations = provider.collect(_candidate())
    assert [item.signal for item in observations] == ["monthly_searches", "buyer_intent"]
    assert observations[0].value == 1500
    assert observations[1].value == 82
    assert observations[0].source == "export-b"
    assert observations[0].confidence == 0.9
    assert observations[0].expires_at is not None


def test_keyword_csv_rejects_missing_required_column(tmp_path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text(
        "product_id,marketplace,monthly_searches,observed_at\n"
        "p1,DE,100,2026-08-20T00:00:00Z\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="buyer_intent"):
        load_keyword_demand_csv(path)

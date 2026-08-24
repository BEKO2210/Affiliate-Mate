from datetime import UTC, datetime, timedelta

import pytest

from affiliate_mate.evidence import EvidenceObservation, SQLiteEvidenceStore
from affiliate_mate.models import ProductCandidate
from affiliate_mate.resolution import resolve_candidate_from_store

NOW = datetime(2026, 8, 25, 10, 0, tzinfo=UTC)


def candidate(**overrides):
    data = {
        "product_id": "p1",
        "title": "Widget",
        "marketplace": "DE",
        "currency": "EUR",
        "price": 100.0,
        "commission_rate": 0.03,
        "monthly_searches": 100,
        "youtube_competition": 60,
        "buyer_intent": 50,
        "content_gap": 50,
        "evidence_quality": 50,
        "estimated_ctr": 0.04,
        "estimated_conversion_rate": 0.03,
    }
    data.update(overrides)
    return ProductCandidate(**data)


def obs(signal, value, **overrides):
    data = {
        "product_id": "p1",
        "signal": signal,
        "value": value,
        "source": "provider",
        "marketplace": "DE",
        "observed_at": NOW,
        "confidence": 0.9,
    }
    data.update(overrides)
    return EvidenceObservation(**data)


def test_resolver_applies_latest_supported_signals(tmp_path):
    with SQLiteEvidenceStore(tmp_path / "evidence.sqlite3") as store:
        store.add(obs("price", 250, unit="EUR"))
        store.add(obs("monthly_searches", 5000))
        store.add(obs("buyer_intent", 88))
        result = resolve_candidate_from_store(candidate(), store, as_of=NOW)
    assert result.candidate.price == 250
    assert result.candidate.monthly_searches == 5000
    assert result.candidate.buyer_intent == 88
    assert result.applied_signals == {"price", "monthly_searches", "buyer_intent"}


def test_resolver_skips_low_confidence_observation(tmp_path):
    with SQLiteEvidenceStore(tmp_path / "evidence.sqlite3") as store:
        store.add(obs("monthly_searches", 5000, confidence=0.2))
        result = resolve_candidate_from_store(
            candidate(),
            store,
            as_of=NOW,
            min_confidence=0.5,
        )
    assert result.candidate.monthly_searches == 100
    assert result.applied == ()
    assert result.skipped_low_confidence[0].signal == "monthly_searches"


def test_resolver_uses_older_still_valid_observation_when_newest_is_expired(tmp_path):
    with SQLiteEvidenceStore(tmp_path / "evidence.sqlite3") as store:
        store.add(obs("monthly_searches", 1000, observed_at=NOW - timedelta(days=2)))
        store.add(
            obs(
                "monthly_searches",
                9999,
                observed_at=NOW - timedelta(days=1),
                expires_at=NOW - timedelta(hours=1),
            )
        )
        result = resolve_candidate_from_store(candidate(), store, as_of=NOW)
    assert result.candidate.monthly_searches == 1000


def test_resolver_rejects_fractional_integer_signal(tmp_path):
    with SQLiteEvidenceStore(tmp_path / "evidence.sqlite3") as store:
        store.add(obs("buyer_intent", 77.5))
        with pytest.raises(ValueError, match="integer-valued"):
            resolve_candidate_from_store(candidate(), store, as_of=NOW)


def test_resolver_fails_closed_on_price_currency_mismatch(tmp_path):
    with SQLiteEvidenceStore(tmp_path / "evidence.sqlite3") as store:
        store.add(obs("price", 200, unit="USD"))
        with pytest.raises(ValueError, match="currency mismatch"):
            resolve_candidate_from_store(candidate(), store, as_of=NOW)


def test_resolver_validates_confidence_threshold(tmp_path):
    with (
        SQLiteEvidenceStore(tmp_path / "evidence.sqlite3") as store,
        pytest.raises(ValueError, match="between 0 and 1"),
    ):
        resolve_candidate_from_store(candidate(), store, min_confidence=1.1)

from datetime import UTC, datetime, timedelta

import pytest

from affiliate_mate.evidence import EvidenceObservation, SQLiteEvidenceStore


NOW = datetime(2026, 8, 25, 10, 0, tzinfo=UTC)


def observation(**overrides):
    data = {
        "product_id": "p1",
        "signal": "monthly_searches",
        "value": 1200.0,
        "source": "test-provider",
        "marketplace": "DE",
        "observed_at": NOW,
        "confidence": 0.9,
        "unit": "searches/month",
        "metadata": {"query": "widget review"},
    }
    data.update(overrides)
    return EvidenceObservation(**data)


def test_observation_requires_timezone_aware_timestamp():
    with pytest.raises(ValueError, match="timezone-aware"):
        observation(observed_at=datetime(2026, 8, 25, 10, 0))


def test_observation_rejects_invalid_confidence():
    with pytest.raises(ValueError, match="confidence"):
        observation(confidence=1.1)


def test_observation_rejects_non_finite_value():
    with pytest.raises(ValueError, match="finite"):
        observation(value=float("inf"))


def test_observation_rejects_non_standard_json_metadata():
    with pytest.raises(ValueError, match="strict JSON"):
        observation(metadata={"bad": float("nan")})


def test_observation_rejects_expiry_before_observation():
    with pytest.raises(ValueError, match="after observed_at"):
        observation(expires_at=NOW - timedelta(seconds=1))


def test_is_expired_uses_expiry_boundary():
    item = observation(expires_at=NOW + timedelta(hours=1))
    assert not item.is_expired(NOW + timedelta(minutes=59))
    assert item.is_expired(NOW + timedelta(hours=1))


def test_store_round_trips_observation_and_metadata(tmp_path):
    db = tmp_path / "evidence.sqlite3"
    item = observation()
    with SQLiteEvidenceStore(db) as store:
        assert store.add(item)
        loaded = store.latest("p1", "monthly_searches", as_of=NOW)
    assert loaded is not None
    assert loaded.value == 1200.0
    assert loaded.source == "test-provider"
    assert loaded.metadata == {"query": "widget review"}
    assert loaded.observed_at == NOW


def test_store_deduplicates_same_source_signal_and_timestamp(tmp_path):
    with SQLiteEvidenceStore(tmp_path / "evidence.sqlite3") as store:
        assert store.add(observation())
        assert not store.add(observation())
        assert store.count() == 1


def test_add_many_is_single_batch_and_counts_only_new_rows(tmp_path):
    first = observation()
    second = observation(signal="buyer_intent", value=80)
    with SQLiteEvidenceStore(tmp_path / "evidence.sqlite3") as store:
        assert store.add_many([first, second, first]) == 2
        assert store.count() == 2


def test_latest_returns_newest_observation_available_as_of_time(tmp_path):
    older = observation(value=100.0, observed_at=NOW)
    newer = observation(value=200.0, observed_at=NOW + timedelta(hours=2))
    with SQLiteEvidenceStore(tmp_path / "evidence.sqlite3") as store:
        assert store.add_many([older, newer]) == 2
        at_one_hour = store.latest(
            "p1", "monthly_searches", as_of=NOW + timedelta(hours=1)
        )
        at_three_hours = store.latest(
            "p1", "monthly_searches", as_of=NOW + timedelta(hours=3)
        )
    assert at_one_hour is not None and at_one_hour.value == 100.0
    assert at_three_hours is not None and at_three_hours.value == 200.0


def test_latest_excludes_expired_by_default_but_can_include_it(tmp_path):
    expired = observation(expires_at=NOW + timedelta(hours=1))
    as_of = NOW + timedelta(hours=2)
    with SQLiteEvidenceStore(tmp_path / "evidence.sqlite3") as store:
        store.add(expired)
        assert store.latest("p1", "monthly_searches", as_of=as_of) is None
        included = store.latest(
            "p1",
            "monthly_searches",
            as_of=as_of,
            include_expired=True,
        )
    assert included is not None and included.value == 1200.0


def test_history_is_newest_first_and_keeps_expired_rows(tmp_path):
    with SQLiteEvidenceStore(tmp_path / "evidence.sqlite3") as store:
        store.add(observation(value=1, observed_at=NOW))
        store.add(observation(value=2, observed_at=NOW + timedelta(minutes=1)))
        history = store.history("p1", "monthly_searches")
    assert [item.value for item in history] == [2.0, 1.0]


def test_delete_expired_is_explicit_housekeeping(tmp_path):
    with SQLiteEvidenceStore(tmp_path / "evidence.sqlite3") as store:
        store.add(observation(expires_at=NOW + timedelta(hours=1)))
        store.add(
            observation(
                signal="buyer_intent",
                value=80,
                expires_at=NOW + timedelta(hours=3),
            )
        )
        deleted = store.delete_expired(NOW + timedelta(hours=2))
        assert deleted == 1
        assert store.count() == 1


def test_store_persists_across_instances(tmp_path):
    db = tmp_path / "nested" / "evidence.sqlite3"
    with SQLiteEvidenceStore(db) as store:
        store.add(observation())
    with SQLiteEvidenceStore(db) as reopened:
        assert reopened.count() == 1

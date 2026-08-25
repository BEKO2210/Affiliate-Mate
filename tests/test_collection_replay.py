import json
from datetime import UTC, datetime

from affiliate_mate.collection import ProviderRunStatus, collect_evidence
from affiliate_mate.evidence import EvidenceObservation, SQLiteEvidenceStore
from affiliate_mate.models import ProductCandidate
from affiliate_mate.replay import ReplayEvidenceProvider


def _candidate() -> ProductCandidate:
    return ProductCandidate(
        product_id="p1",
        title="Example Product",
        marketplace="DE",
        currency="EUR",
        price=100.0,
        commission_rate=0.05,
        monthly_searches=500,
        youtube_competition=50,
        buyer_intent=60,
        content_gap=50,
        evidence_quality=80,
    )


class GoodProvider:
    @property
    def name(self):
        return "good"

    def collect(self, candidate):
        return [
            EvidenceObservation(
                product_id=candidate.product_id,
                signal="buyer_intent",
                value=75,
                source="good",
                marketplace=candidate.marketplace,
                observed_at=datetime(2026, 8, 25, tzinfo=UTC),
            )
        ]


class BadProvider:
    @property
    def name(self):
        return "bad"

    def collect(self, candidate):
        raise RuntimeError("provider unavailable")


def test_collection_reports_failure_without_losing_successful_evidence(tmp_path) -> None:
    db = tmp_path / "evidence.sqlite3"
    with SQLiteEvidenceStore(db) as store:
        report = collect_evidence(
            _candidate(),
            [GoodProvider(), BadProvider()],
            store=store,
        )
        latest = store.latest("p1", "buyer_intent", marketplace="DE")
    assert report.observations_collected == 1
    assert report.observations_stored == 1
    assert report.failed_providers == ("bad",)
    assert report.provider_results[0].status == ProviderRunStatus.SUCCESS
    assert report.provider_results[1].status == ProviderRunStatus.FAILED
    assert latest is not None and latest.value == 75


def test_collection_rejects_cross_product_evidence_as_provider_failure() -> None:
    class WrongProduct:
        @property
        def name(self):
            return "wrong"

        def collect(self, candidate):
            return [
                EvidenceObservation(
                    product_id="someone-else",
                    signal="content_gap",
                    value=90,
                    source="wrong",
                    marketplace="DE",
                    observed_at=datetime(2026, 8, 25, tzinfo=UTC),
                )
            ]

    report = collect_evidence(_candidate(), [WrongProduct()])
    assert report.observations_collected == 0
    assert report.provider_results[0].status == ProviderRunStatus.FAILED
    assert report.provider_results[0].error_type == "ValueError"


def test_replay_provider_reads_fixture_and_filters_candidate(tmp_path) -> None:
    fixture = tmp_path / "replay.json"
    fixture.write_text(
        json.dumps(
            {
                "observations": [
                    {
                        "product_id": "p1",
                        "signal": "youtube_competition",
                        "value": 44,
                        "source": "captured-youtube",
                        "marketplace": "DE",
                        "observed_at": "2026-08-20T10:00:00Z",
                        "confidence": 0.9,
                    },
                    {
                        "product_id": "p2",
                        "signal": "youtube_competition",
                        "value": 90,
                        "marketplace": "DE",
                        "observed_at": "2026-08-20T10:00:00Z",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    provider = ReplayEvidenceProvider.from_json(fixture)
    observations = provider.collect(_candidate())
    assert len(observations) == 1
    assert observations[0].value == 44
    assert observations[0].source == "captured-youtube"

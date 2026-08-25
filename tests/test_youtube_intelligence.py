import json
from datetime import UTC, datetime

import pytest

from affiliate_mate.http_client import HttpResponse, JsonHttpClient, RetryPolicy
from affiliate_mate.models import ProductCandidate
from affiliate_mate.youtube_intelligence import (
    YouTubeCompetitionProvider,
    YouTubeDataAPIClient,
    YouTubeVideo,
    analyze_youtube_landscape,
)


class FakeTransport:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def send(self, method, url, *, headers, body, timeout):
        self.urls.append(url)
        if "/search?" in url:
            payload = {
                "items": [
                    {
                        "id": {"videoId": "v1"},
                        "snippet": {
                            "title": "Example Camera Review &amp; Test",
                            "channelId": "c1",
                            "publishedAt": "2026-08-01T00:00:00Z",
                        },
                    },
                    {
                        "id": {"videoId": "v2"},
                        "snippet": {
                            "title": "Example Camera vs Competitor",
                            "channelId": "c2",
                            "publishedAt": "2025-02-01T00:00:00Z",
                        },
                    },
                ]
            }
        else:
            payload = {
                "items": [
                    {"id": "v1", "statistics": {"viewCount": "200000"}},
                    {"id": "v2", "statistics": {"viewCount": "50000"}},
                ]
            }
        return HttpResponse(200, {}, json.dumps(payload).encode())


def _video(video_id: str, title: str, views: int, year: int) -> YouTubeVideo:
    return YouTubeVideo(
        video_id=video_id,
        title=title,
        channel_id=video_id,
        published_at=datetime(year, 8, 1, tzinfo=UTC),
        view_count=views,
    )


def _candidate() -> ProductCandidate:
    return ProductCandidate(
        product_id="p1",
        title="Example Camera",
        marketplace="DE",
        currency="EUR",
        price=199.0,
        commission_rate=0.03,
        monthly_searches=1000,
        youtube_competition=50,
        buyer_intent=70,
        content_gap=50,
        evidence_quality=80,
    )


def test_landscape_score_is_transparent_and_bounded() -> None:
    observed = datetime(2026, 8, 25, tzinfo=UTC)
    crowded = [
        _video("a", "Example Camera Review", 1_000_000, 2026),
        _video("b", "Example Camera Test", 800_000, 2026),
    ]
    weak = [
        _video("c", "Old camera thoughts", 500, 2020),
        _video("d", "Random photography", 300, 2021),
    ]
    crowded_metrics = analyze_youtube_landscape(
        "Example Camera", crowded, observed_at=observed
    )
    weak_metrics = analyze_youtube_landscape("Example Camera", weak, observed_at=observed)
    assert 0 <= crowded_metrics.competition <= 100
    assert 0 <= weak_metrics.content_gap <= 100
    assert crowded_metrics.competition > weak_metrics.competition
    assert weak_metrics.content_gap > crowded_metrics.content_gap


def test_empty_landscape_is_low_competition_high_gap() -> None:
    metrics = analyze_youtube_landscape(
        "Example Camera",
        [],
        observed_at=datetime(2026, 8, 25, tzinfo=UTC),
    )
    assert metrics.competition == 0
    assert metrics.content_gap == 100


def test_youtube_client_uses_search_then_video_statistics() -> None:
    transport = FakeTransport()
    client = YouTubeDataAPIClient(
        "secret-key",
        http=JsonHttpClient(
            transport,
            retry_policy=RetryPolicy(max_attempts=1),
        ),
    )
    videos = client.search_videos(
        "Example Camera",
        region_code="DE",
        relevance_language="de",
        max_results=2,
    )
    assert [video.video_id for video in videos] == ["v1", "v2"]
    assert videos[0].title == "Example Camera Review & Test"
    assert videos[0].view_count == 200000
    assert len(transport.urls) == 2
    assert "regionCode=DE" in transport.urls[0]
    assert "relevanceLanguage=de" in transport.urls[0]


def test_youtube_client_rejects_invalid_result_limit() -> None:
    client = YouTubeDataAPIClient("key")
    with pytest.raises(ValueError, match="between 1 and 50"):
        client.search_videos("camera", max_results=51)


def test_provider_emits_competition_and_gap_with_expiry() -> None:
    class FakeClient:
        def search_videos(self, query, **kwargs):
            return [_video("a", "Example Camera Review", 10000, 2026)]

    provider = YouTubeCompetitionProvider(
        FakeClient(),
        now=lambda: datetime(2026, 8, 25, tzinfo=UTC),
    )
    observations = provider.collect(_candidate())
    assert {item.signal for item in observations} == {
        "youtube_competition",
        "content_gap",
    }
    assert all(item.source == "youtube-data-api-v3" for item in observations)
    assert all(item.expires_at is not None for item in observations)

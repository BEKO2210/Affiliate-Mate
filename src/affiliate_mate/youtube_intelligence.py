"""YouTube Data API market-landscape evidence with transparent scoring."""

import html
import json
import math
import os
import re
import statistics
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

from affiliate_mate.budgets import SourceCallBudget
from affiliate_mate.evidence import EvidenceObservation
from affiliate_mate.freshness import SignalFreshnessPolicy
from affiliate_mate.http_client import HttpRequestError, JsonHttpClient, JsonProtocolError
from affiliate_mate.models import ProductCandidate


YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
_INTENT_TERMS = {
    "review",
    "test",
    "tested",
    "comparison",
    "compare",
    "vergleich",
    "erfahrung",
    "erfahrungen",
    "unboxing",
    "guide",
    "buying",
    "kaufberatung",
    "vs",
}
_TOKEN_RE = re.compile(r"\w+", flags=re.UNICODE)


@dataclass(frozen=True, slots=True)
class YouTubeVideo:
    video_id: str
    title: str
    channel_id: str
    published_at: datetime
    view_count: int

    def __post_init__(self) -> None:
        if not self.video_id.strip():
            raise ValueError("video_id must not be empty")
        if not self.title.strip():
            raise ValueError("title must not be empty")
        if self.published_at.tzinfo is None or self.published_at.utcoffset() is None:
            raise ValueError("published_at must be timezone-aware")
        if self.view_count < 0:
            raise ValueError("view_count must be >= 0")


@dataclass(frozen=True, slots=True)
class YouTubeLandscapeMetrics:
    competition: float
    content_gap: float
    median_views: float
    query_token_coverage: float
    fresh_result_share: float
    intent_format_share: float
    dominant_channel_share: float
    result_count: int


class YouTubeAPIError(RuntimeError):
    def __init__(self, status: int, message: str) -> None:
        self.status = status
        super().__init__(f"YouTube Data API error ({status}): {message}")


def _tokens(value: str) -> set[str]:
    return {
        token.casefold()
        for token in _TOKEN_RE.findall(html.unescape(value))
        if len(token) >= 2
    }


def _parse_datetime(value: object) -> datetime:
    if not isinstance(value, str):
        raise TypeError("YouTube publishedAt must be a string")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("YouTube publishedAt must include a timezone")
    return parsed.astimezone(UTC)


def analyze_youtube_landscape(
    query: str,
    videos: list[YouTubeVideo],
    *,
    observed_at: datetime,
) -> YouTubeLandscapeMetrics:
    """Turn a top-results landscape into inspectable 0-100 evidence scores."""

    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")
    if not videos:
        return YouTubeLandscapeMetrics(
            competition=0.0,
            content_gap=100.0,
            median_views=0.0,
            query_token_coverage=0.0,
            fresh_result_share=0.0,
            intent_format_share=0.0,
            dominant_channel_share=0.0,
            result_count=0,
        )

    query_tokens = _tokens(query)
    coverage_values: list[float] = []
    intent_hits = 0
    fresh_hits = 0
    channel_counts: Counter[str] = Counter()
    view_counts: list[int] = []
    freshness_cutoff = observed_at - timedelta(days=365)

    for video in videos:
        title_tokens = _tokens(video.title)
        coverage = 0.0
        if query_tokens:
            coverage = len(query_tokens & title_tokens) / len(query_tokens)
        coverage_values.append(coverage)
        if title_tokens & _INTENT_TERMS:
            intent_hits += 1
        if video.published_at >= freshness_cutoff:
            fresh_hits += 1
        if video.channel_id:
            channel_counts[video.channel_id] += 1
        view_counts.append(video.view_count)

    count = len(videos)
    median_views = float(statistics.median(view_counts))
    coverage = statistics.fmean(coverage_values)
    fresh_share = fresh_hits / count
    intent_share = intent_hits / count
    dominant_share = max(channel_counts.values(), default=0) / count

    view_strength = min(100.0, math.log10(max(1.0, median_views)) / 6.0 * 100.0)
    competition = (
        0.40 * view_strength
        + 0.25 * coverage * 100.0
        + 0.20 * fresh_share * 100.0
        + 0.15 * dominant_share * 100.0
    )
    stale_share = 1.0 - fresh_share
    content_gap = (
        0.45 * (1.0 - coverage) * 100.0
        + 0.30 * (1.0 - intent_share) * 100.0
        + 0.25 * stale_share * 100.0
    )

    return YouTubeLandscapeMetrics(
        competition=round(min(100.0, max(0.0, competition)), 2),
        content_gap=round(min(100.0, max(0.0, content_gap)), 2),
        median_views=round(median_views, 2),
        query_token_coverage=round(coverage, 4),
        fresh_result_share=round(fresh_share, 4),
        intent_format_share=round(intent_share, 4),
        dominant_channel_share=round(dominant_share, 4),
        result_count=count,
    )


class YouTubeDataAPIClient:
    """Small YouTube Data API v3 client using bounded HTTP and source budgets."""

    def __init__(
        self,
        api_key: str,
        *,
        http: JsonHttpClient | None = None,
        budget: SourceCallBudget | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("YouTube API key must not be empty")
        self._api_key = api_key
        self._http = http or JsonHttpClient()
        self._budget = budget

    @classmethod
    def from_env(
        cls,
        env: dict[str, str] | None = None,
        *,
        http: JsonHttpClient | None = None,
        budget: SourceCallBudget | None = None,
    ) -> "YouTubeDataAPIClient":
        values = os.environ if env is None else env
        api_key = values.get("YOUTUBE_API_KEY", "")
        if not api_key.strip():
            raise ValueError("missing required environment variable: YOUTUBE_API_KEY")
        return cls(api_key, http=http, budget=budget)

    def search_videos(
        self,
        query: str,
        *,
        region_code: str | None = None,
        relevance_language: str | None = None,
        max_results: int = 25,
    ) -> list[YouTubeVideo]:
        if not query.strip():
            raise ValueError("query must not be empty")
        if not 1 <= max_results <= 50:
            raise ValueError("max_results must be between 1 and 50")
        if self._budget is not None:
            self._budget.reserve(
                {
                    "youtube.search.list": 1,
                    "youtube.videos.list": 1,
                }
            )
        params = {
            "part": "snippet",
            "type": "video",
            "order": "relevance",
            "maxResults": str(max_results),
            "q": query,
            "key": self._api_key,
        }
        if region_code:
            params["regionCode"] = region_code.upper()
        if relevance_language:
            params["relevanceLanguage"] = relevance_language
        search = self._get("search", params)
        raw_items = search.get("items")
        if not isinstance(raw_items, list):
            raise JsonProtocolError("YouTube search response missing items array")

        search_rows: dict[str, tuple[str, str, datetime]] = {}
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            identifier = raw.get("id")
            snippet = raw.get("snippet")
            if not isinstance(identifier, dict) or not isinstance(snippet, dict):
                continue
            video_id = identifier.get("videoId")
            title = snippet.get("title")
            channel_id = snippet.get("channelId")
            published_at = snippet.get("publishedAt")
            if not isinstance(video_id, str) or not isinstance(title, str):
                continue
            try:
                parsed_time = _parse_datetime(published_at)
            except (TypeError, ValueError):
                continue
            search_rows[video_id] = (
                html.unescape(title),
                channel_id if isinstance(channel_id, str) else "",
                parsed_time,
            )

        if not search_rows:
            return []
        stats = self._get(
            "videos",
            {
                "part": "statistics",
                "id": ",".join(search_rows),
                "key": self._api_key,
            },
        )
        raw_stats = stats.get("items")
        if not isinstance(raw_stats, list):
            raise JsonProtocolError("YouTube videos response missing items array")
        views_by_id: dict[str, int] = {}
        for raw in raw_stats:
            if not isinstance(raw, dict):
                continue
            video_id = raw.get("id")
            statistics_data = raw.get("statistics")
            if not isinstance(video_id, str) or not isinstance(statistics_data, dict):
                continue
            raw_views = statistics_data.get("viewCount", "0")
            try:
                views_by_id[video_id] = max(0, int(raw_views))
            except (TypeError, ValueError):
                views_by_id[video_id] = 0

        return [
            YouTubeVideo(
                video_id=video_id,
                title=row[0],
                channel_id=row[1],
                published_at=row[2],
                view_count=views_by_id.get(video_id, 0),
            )
            for video_id, row in search_rows.items()
        ]

    def _get(self, resource: str, params: dict[str, str]) -> dict[str, object]:
        url = f"{YOUTUBE_API_BASE}/{resource}?{urlencode(params)}"
        try:
            return self._http.request_json("GET", url)
        except HttpRequestError as exc:
            message = _youtube_error_message(exc.body)
            raise YouTubeAPIError(exc.status, message) from exc


def _youtube_error_message(body: bytes) -> str:
    try:
        decoded = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return "request failed"
    if not isinstance(decoded, dict):
        return "request failed"
    error = decoded.get("error")
    if not isinstance(error, dict):
        return "request failed"
    message = error.get("message")
    return message if isinstance(message, str) and message else "request failed"


class YouTubeCompetitionProvider:
    """Collect competition and content-gap evidence for a normalized candidate."""

    def __init__(
        self,
        client: YouTubeDataAPIClient,
        *,
        max_results: int = 25,
        relevance_language: str | None = None,
        confidence: float = 0.85,
        freshness: SignalFreshnessPolicy | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if not 1 <= max_results <= 50:
            raise ValueError("max_results must be between 1 and 50")
        if not 0 <= confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        self._client = client
        self._max_results = max_results
        self._relevance_language = relevance_language
        self._confidence = confidence
        self._freshness = freshness or SignalFreshnessPolicy()
        self._now = now

    @property
    def name(self) -> str:
        return "youtube-data-api-v3"

    def collect(self, candidate: ProductCandidate) -> list[EvidenceObservation]:
        observed_at = self._now().astimezone(UTC)
        videos = self._client.search_videos(
            candidate.title,
            region_code=candidate.marketplace,
            relevance_language=self._relevance_language,
            max_results=self._max_results,
        )
        metrics = analyze_youtube_landscape(
            candidate.title,
            videos,
            observed_at=observed_at,
        )
        metadata = {
            "query": candidate.title,
            "result_count": metrics.result_count,
            "median_views": metrics.median_views,
            "query_token_coverage": metrics.query_token_coverage,
            "fresh_result_share": metrics.fresh_result_share,
            "intent_format_share": metrics.intent_format_share,
            "dominant_channel_share": metrics.dominant_channel_share,
            "method": "top-result-landscape-v1",
        }
        observations = [
            EvidenceObservation(
                product_id=candidate.product_id,
                signal="youtube_competition",
                value=metrics.competition,
                source=self.name,
                marketplace=candidate.marketplace,
                observed_at=observed_at,
                confidence=self._confidence,
                unit="score_0_100",
                metadata=metadata,
            ),
            EvidenceObservation(
                product_id=candidate.product_id,
                signal="content_gap",
                value=metrics.content_gap,
                source=self.name,
                marketplace=candidate.marketplace,
                observed_at=observed_at,
                confidence=self._confidence,
                unit="score_0_100",
                metadata=metadata,
            ),
        ]
        return [self._freshness.apply(observation) for observation in observations]

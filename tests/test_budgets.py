import json

import pytest

from affiliate_mate.budgets import BudgetExceededError, SourceCallBudget
from affiliate_mate.http_client import HttpResponse, JsonHttpClient, RetryPolicy
from affiliate_mate.youtube_intelligence import YouTubeDataAPIClient


class EmptyYouTubeTransport:
    def __init__(self) -> None:
        self.calls = 0

    def send(self, method, url, *, headers, body, timeout):
        self.calls += 1
        return HttpResponse(200, {}, json.dumps({"items": []}).encode())


def test_group_reservation_is_atomic() -> None:
    budget = SourceCallBudget({"search": 1, "stats": 0})
    with pytest.raises(BudgetExceededError):
        budget.reserve({"search": 1, "stats": 1})
    assert budget.used("search") == 0
    assert budget.used("stats") == 0


def test_youtube_budget_blocks_second_collection_before_network() -> None:
    transport = EmptyYouTubeTransport()
    budget = SourceCallBudget(
        {
            "youtube.search.list": 1,
            "youtube.videos.list": 1,
        }
    )
    client = YouTubeDataAPIClient(
        "key",
        http=JsonHttpClient(
            transport,
            retry_policy=RetryPolicy(max_attempts=1),
        ),
        budget=budget,
    )
    assert client.search_videos("camera") == []
    with pytest.raises(BudgetExceededError):
        client.search_videos("camera")
    assert transport.calls == 1
    assert budget.used("youtube.search.list") == 1
    assert budget.used("youtube.videos.list") == 1
